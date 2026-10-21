"""Jira Cloud: verschlüsselte Verbindung, Vorschau und atomarer Auswahlimport."""
import re
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import requests
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from integrations.models import IntegrationCredential
from .models import JiraConnection, JiraIssue, JiraProject, Project, Workspace, Status, Tag, Ticket
from .errors import WorkError
from .access import project_members
from .workspaces import workspace_for

FIELDS = ['summary', 'description', 'project', 'issuetype', 'status', 'labels', 'priority', 'duedate', 'assignee', 'parent']
KEY = r'[A-Z][A-Z0-9_]*-[1-9][0-9]*'


def cloud_url(value):
    try:
        url = urlsplit(value.strip())
        port = url.port
    except ValueError:
        raise WorkError('Bitte eine gültige Jira-Cloud-Adresse angeben.') from None
    if url.scheme != 'https' or not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.atlassian\.net', url.hostname or '') or port not in (None, 443) or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment:
        raise WorkError('Bitte eine Jira-Cloud-Adresse wie https://team.atlassian.net angeben.')
    return 'https://' + url.hostname


class JiraAuthenticationError(WorkError):
    pass


def validated_cloud_id(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise WorkError('Die Jira Cloud-ID konnte nicht ermittelt werden.', 502) from None


@sensitive_variables('token')
def fetch_jira_json(url, email=None, token=None, payload=None):
    # Called only with validated Atlassian URLs; redirects never receive credentials.
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.request('POST' if payload is not None else 'GET', url,
                                       auth=(email, token) if email else None, json=payload, timeout=(5, 25), allow_redirects=False,
                                       headers={'Accept': 'application/json'}, stream=True)
            if response.status_code in (401, 403):
                raise JiraAuthenticationError('Jira lehnt den Zugriff ab. Bitte E-Mail, API-Token und Jira-Projektberechtigungen prüfen.', 400)
            if response.status_code == 429:
                raise WorkError('Jira begrenzt gerade die Anfragen. Bitte später erneut versuchen.', 429)
            if response.status_code >= 400 or response.is_redirect:
                raise WorkError('Jira-Anfrage fehlgeschlagen. Bitte JQL, Ticketzugriff und Cloud-Adresse prüfen.', 502)
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 8_000_000:
                    raise WorkError('Jira-Antwort zu groß. Bitte die Auswahl weiter eingrenzen.', 502)
            import json
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError()
            return result
    except (requests.RequestException, ValueError):
        # Never relay upstream bodies, URLs, request objects or credentials to logs/UI.
        raise WorkError('Jira ist nicht erreichbar oder hat keine gültige Antwort geliefert.', 502) from None


@sensitive_variables('token')
def jira_request(base_url, email, token, path, payload=None, *, cloud_id=''):
    base_url = cloud_url(base_url)
    origin = 'https://api.atlassian.com/ex/jira/' + validated_cloud_id(cloud_id) if cloud_id else base_url
    return fetch_jira_json(origin + '/rest/api/3/' + path, email, token, payload)


def connection_for(user, workspace_id):
    workspace_for(user, workspace_id, manage=True)
    connection = JiraConnection.objects.select_related('credential').filter(workspace_id=workspace_id).first()
    if not connection or not connection.credential.enabled or not connection.credential.is_configured:
        raise WorkError('Bitte zuerst eine Jira-Verbindung einrichten.')
    return connection


def connection_data(connection):
    return {'base_url': connection.base_url, 'email': connection.email, 'configured': connection.credential.enabled and connection.credential.is_configured}


def get_jira_connection(user, workspace_id):
    workspace_for(user, workspace_id, manage=True)
    connection = JiraConnection.objects.select_related('credential').filter(workspace_id=workspace_id).first()
    return {'connection': connection_data(connection) if connection else None}


@sensitive_variables('api_token')
def configure_jira(user, workspace_id, base_url, email, api_token):
    workspace_for(user, workspace_id, manage=True)
    base_url = cloud_url(base_url)
    email = email.strip()
    if not re.fullmatch(r'[^\s@:]+@[^\s@]+\.[^\s@]+', email) or not api_token.strip():
        raise WorkError('Bitte Jira-E-Mail und API-Token angeben.')
    cloud_id = ''
    try:
        jira_request(base_url, email, api_token, 'myself')
    except JiraAuthenticationError:
        # Scoped tokens require Atlassian's API gateway. Discover its public tenant ID without credentials.
        tenant = fetch_jira_json(base_url + '/_edge/tenant_info')
        cloud_id = validated_cloud_id(tenant.get('cloudId'))
        jira_request(base_url, email, api_token, 'myself', cloud_id=cloud_id)
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=workspace_id)
        workspace_for(user, workspace_id, manage=True)
        connection = JiraConnection.objects.select_related('credential').filter(workspace_id=workspace_id).first()
        if connection and connection.base_url != base_url and connection.issue_links.exists():
            raise WorkError('Diese Verbindung hat bereits Importe. Für eine andere Jira-Site bitte einen neuen Workspace verwenden.')
        credential = connection.credential if connection else IntegrationCredential(key='jira-' + uuid4().hex, name='Jira Workspace ' + str(workspace_id), kind=IntegrationCredential.Kind.API_KEY)
        credential.enabled = True
        credential.set_secret(api_token)
        credential.save()
        connection, _ = JiraConnection.objects.update_or_create(workspace_id=workspace_id, defaults={'base_url': base_url, 'email': email, 'credential': credential, 'cloud_id': cloud_id})
        return {'connection': connection_data(connection), 'verified': True}


def search_remote(connection, jql, next_page_token=None):
    payload = {'jql': jql.strip(), 'fields': FIELDS, 'maxResults': 50}
    if next_page_token:
        payload['nextPageToken'] = next_page_token
    result = jira_request(connection.base_url, connection.email, connection.credential.get_secret(), 'search/jql', payload, cloud_id=connection.cloud_id)
    if not isinstance(result.get('issues'), list):
        raise WorkError('Jira hat keine gültige Ticketliste geliefert.', 502)
    return result


def preview_jira(user, workspace_id, jql, next_page_token=None):
    connection = connection_for(user, workspace_id)
    result = search_remote(connection, jql, next_page_token)
    imported = set(connection.issue_links.filter(remote_id__in=[str(issue['id']) for issue in result['issues']]).values_list('remote_id', flat=True))
    issues = []
    for issue in result['issues']:
        fields = issue.get('fields') or {}
        issues.append({'id': str(issue['id']), 'key': issue['key'], 'title': fields.get('summary', ''),
                       'project': (fields.get('project') or {}).get('name', ''),
                       'status': (fields.get('status') or {}).get('name', ''),
                       'kind': (fields.get('issuetype') or {}).get('name', ''),
                       'parent_key': (fields.get('parent') or {}).get('key'),
                       'imported': str(issue['id']) in imported})
    # Membership may have changed during the remote request.
    current = connection_for(user, workspace_id)
    if current.updated_at != connection.updated_at:
        raise WorkError('Die Jira-Verbindung wurde inzwischen geändert. Bitte die Vorschau neu laden.', 409)
    return {'issues': issues, 'next_page_token': result.get('nextPageToken') if not result.get('isLast') else None}


def adf_text(node):
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ''
    if node.get('type') == 'text':
        return node.get('text', '')
    if node.get('type') == 'hardBreak':
        return '\n'
    if node.get('type') == 'mention':
        return node.get('attrs', {}).get('text', '')
    text = ''.join(adf_text(child) for child in node.get('content', []))
    return text + ('\n' if node.get('type') in ('paragraph', 'heading', 'listItem', 'codeBlock', 'blockquote') else '')


def import_jira(user, workspace_id, issue_keys):
    from .services import create_project, create_ticket, update_ticket
    connection = connection_for(user, workspace_id)
    keys = set(issue_keys)
    # Refetch server-side; browser-supplied ticket data is never trusted.
    result = search_remote(connection, 'key in (' + ','.join('"' + key + '"' for key in sorted(keys)) + ')')
    issues = result['issues']
    if {issue.get('key') for issue in issues} != keys or len(issues) != len(keys) or result.get('nextPageToken'):
        raise WorkError('Nicht alle gewählten Tickets sind in Jira zugänglich. Es wurde nichts importiert. Bitte die Vorschau neu laden.')
    warnings, created, skipped, projects_created = [], [], [], []
    with transaction.atomic():
        # Lock workspace then projects in the same order used by execute().
        Workspace.objects.select_for_update().get(pk=workspace_id)
        workspace_for(user, workspace_id, manage=True)
        current = connection_for(user, workspace_id)
        if current.updated_at != connection.updated_at:
            raise WorkError('Die Jira-Verbindung wurde inzwischen geändert. Bitte erneut importieren.', 409)
        local = {}
        for issue in issues:
            existing = connection.issue_links.select_related('ticket').filter(remote_id=str(issue['id'])).first()
            if existing:
                local[issue['key']] = existing.ticket
                skipped.append(issue['key'])
                continue
            f = issue.get('fields') or {}
            remote_project = f.get('project') or {}
            if not remote_project.get('id') or not remote_project.get('key') or not f.get('summary'):
                raise WorkError('Ein Jira-Ticket enthält unvollständige Projektdaten. Der Import wurde zurückgerollt.')
            link = connection.project_links.select_related('project').filter(remote_id=str(remote_project['id'])).first()
            if not link:
                stem = re.sub('[^A-Z0-9]', '', remote_project['key'].upper())[:10]
                if not stem or not stem[0].isalpha():
                    stem = 'JP' + stem[:8]
                if len(stem) < 2:
                    stem += 'P'
                key, suffix = stem, 1
                while Project.objects.filter(workspace_id=workspace_id, key=key).exists():
                    suffix += 1
                    key = stem[:12-len(str(suffix))] + str(suffix)
                p = create_project(user, name=remote_project.get('name', key)[:120], key=key, workspace_id=workspace_id)
                link = JiraProject.objects.create(connection=connection, remote_id=str(remote_project['id']), project_id=p['id'])
                projects_created.append(p)
            project = Project.objects.select_for_update().get(pk=link.project_id)
            remote_status = f.get('status') or {}
            status_name = (remote_status.get('name') or 'Offen')[:60]
            category = {'new': 'open', 'indeterminate': 'in_progress', 'done': 'done'}.get((remote_status.get('statusCategory') or {}).get('key'), 'open')
            if status_name.casefold() in ('closed', 'geschlossen'):
                category = 'closed'
            status = project.statuses.filter(name__iexact=status_name).first()
            if not status:
                status = Status.objects.create(project=project, name=status_name, category=category, position=10 + max(project.statuses.values_list('position', flat=True), default=0))
            tags = []
            for label in f.get('labels') or []:
                label = label.strip()[:40]
                if label:
                    tag = project.tags.filter(name__iexact=label).first() or Tag.objects.create(project=project, name=label)
                    tags.append(tag.pk)
            assignee = f.get('assignee') or {}
            members = project_members(project)
            match = members.filter(email__iexact=assignee['emailAddress']).first() if assignee.get('emailAddress') else None
            if assignee and not match:
                warnings.append(issue['key'] + ': Jira-Zuweisung konnte keinem aktiven Projektmitglied zugeordnet werden.')
            priority = (f.get('priority') or {}).get('name', '').casefold()
            priority = 'urgent' if priority in ('highest', 'blocker', 'critical', 'höchste') else 'high' if priority in ('high', 'hoch') else 'low' if priority in ('low', 'lowest', 'niedrig') else 'normal'
            issue_type = f.get('issuetype') or {}
            kind = 'epic' if issue_type.get('hierarchyLevel') == 1 or issue_type.get('name', '').casefold() == 'epic' else 'ticket'
            ticket = create_ticket(user, project.pk, title=f['summary'][:200], description=adf_text(f.get('description')).strip()[:20000], kind=kind, status_id=status.pk, tag_ids=list(dict.fromkeys(tags)), assignee_ids=[match.pk] if match else [], priority=priority, due_date=f.get('duedate'))
            obj = Ticket.objects.get(pk=ticket['id'])
            JiraIssue.objects.create(connection=connection, remote_id=str(issue['id']), remote_key=issue['key'], ticket=obj)
            local[issue['key']] = obj
            created.append(issue['key'])
        for issue in issues:
            if issue['key'] not in created:
                continue
            ticket = local[issue['key']]
            parent_key = (issue.get('fields', {}).get('parent') or {}).get('key')
            if not parent_key or ticket.kind == 'epic':
                continue
            parent = local.get(parent_key)
            if not parent:
                source = connection.issue_links.select_related('ticket').filter(remote_key=parent_key).first()
                parent = source.ticket if source else None
            if parent and parent.project_id == ticket.project_id:
                update_ticket(user, ticket.project_id, ticket.pk, parent_id=parent.pk)
            else:
                warnings.append(issue['key'] + ': Übergeordnetes Ticket ' + parent_key + ' wurde nicht verknüpft; bitte ebenfalls importieren oder manuell zuordnen.')
    return {'created': created, 'skipped': skipped, 'projects_created': projects_created, 'warnings': warnings}


def register_operations(register, ID, NAME, TEXT):
    register(get_jira_connection, 'Jira-Verbindungsstatus lesen (nur Workspace-Leitung). Gibt niemals den API-Token zurück.', {'workspace_id': ID}, ['workspace_id'], project=False)
    register(configure_jira, 'Jira Cloud mit E-Mail und API-Token prüfen und verschlüsselt speichern (nur Workspace-Leitung). Token wird nie zurückgegeben.', {'workspace_id': ID, 'base_url': NAME(250), 'email': NAME(254), 'api_token': NAME(2000)}, ['workspace_id', 'base_url', 'email', 'api_token'], write=True, project=False)
    register(preview_jira, 'Jira-Tickets per JQL suchen. Auswahlvorschau mit Pagination; verändert nichts. Nur Workspace-Leitung.', {'workspace_id': ID, 'jql': NAME(2000), 'next_page_token': TEXT(4000)}, ['workspace_id', 'jql'], project=False)
    register(import_jira, 'Bis zu 50 gewählte Jira-Tickets importieren. Erstellt Projekte im Workspace automatisch, erkennt Duplikate und übernimmt Status, Tags und ausgewählte Eltern. Bestehende Tickets bleiben unverändert. Nur Workspace-Leitung.', {'workspace_id': ID, 'issue_keys': {'type': 'array', 'items': {'type': 'string', 'pattern': '^' + KEY + '$', 'maxLength': 100}, 'minItems': 1, 'maxItems': 50, 'uniqueItems': True}}, ['workspace_id', 'issue_keys'], write=True, project=False)
    from .services import OPERATIONS
    for name in ('configure_jira', 'preview_jira', 'import_jira'):
        OPERATIONS[name]['external'] = True
