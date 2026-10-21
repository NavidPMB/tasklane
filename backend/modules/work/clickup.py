"""ClickUp-Auswahlimport mit geprüfter vollständiger Zeithistorie."""
from datetime import datetime, timedelta, timezone as dt_timezone
import hashlib
import json
import math
import re
from uuid import uuid4

import requests
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from integrations.models import IntegrationCredential
from .access import project_members
from .errors import WorkError
from .models import (ClickUpConnection, ClickUpImportBatch, ClickUpPerson, ClickUpProject,
                     ClickUpTask, ClickUpTimeSource, Project, Status, Tag, Ticket, TimeEntry, Workspace)
from .workspaces import workspace_for

REMOTE_ID = {'type': 'string', 'pattern': r'^[0-9]{1,100}$'}
TASK_ID = {'type': 'string', 'pattern': r'^[A-Za-z0-9]{1,100}$'}
BATCH_SIZE = 20


def remote_id(value, task=False):
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9]{1,100}' if task else r'[0-9]{1,100}', value):
        raise WorkError('ClickUp hat eine ungültige Quell-ID geliefert.', 502)
    return value


@sensitive_variables('token')
def clickup_request(token, path, params=None):
    allowed = r'(?:user|team|team/[0-9]+/(?:space|time_entries)|space/[0-9]+/(?:folder|list)|folder/[0-9]+/list|list/[0-9]+(?:/task)?|task/[A-Za-z0-9]+(?:/time)?)'
    if not re.fullmatch(allowed, path):
        raise WorkError('Ungültiger ClickUp-Endpunkt.')
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get('https://api.clickup.com/api/v2/' + path, params=params,
                                   headers={'Authorization': token, 'Accept': 'application/json'},
                                   timeout=(5, 25), allow_redirects=False, stream=True)
            if response.status_code in (401, 403):
                raise WorkError('ClickUp verweigert den Zugriff. Bitte Token und Berechtigungen prüfen. Für fremde Teamzeiten ist ein ClickUp-Workspace-Owner oder -Admin erforderlich.')
            if response.status_code == 429:
                raise WorkError('ClickUp begrenzt gerade die Anfragen. Bitte kurz warten und die Prüfung erneut starten.', 429)
            if response.status_code >= 400 or response.is_redirect:
                raise WorkError('ClickUp-Anfrage fehlgeschlagen. Bitte Quellbereich und Zugriff prüfen.', 502)
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 8_000_000:
                    raise WorkError('ClickUp-Antwort zu groß. Bitte weniger Aufgaben auswählen.', 502)
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError()
            return data
    except (requests.RequestException, ValueError):
        raise WorkError('ClickUp ist nicht erreichbar oder hat keine gültige Antwort geliefert.', 502) from None


def fetch(connection, path, params=None):
    return clickup_request(connection.credential.get_secret(), path, params)


def connection_for(user, workspace_id):
    workspace_for(user, workspace_id, manage=True)
    connection = ClickUpConnection.objects.select_related('credential').filter(workspace_id=workspace_id).first()
    if not connection or not connection.credential.enabled or not connection.credential.is_configured:
        raise WorkError('Bitte zuerst ClickUp verbinden.')
    return connection


def unchanged(user, connection):
    current = connection_for(user, connection.workspace_id)
    if current.updated_at != connection.updated_at:
        raise WorkError('Die ClickUp-Verbindung wurde inzwischen geändert. Bitte erneut prüfen.', 409)


def connection_data(connection):
    return {'account_name': connection.account_name, 'configured': connection.credential.enabled and connection.credential.is_configured}


def get_clickup_connection(user, workspace_id):
    workspace_for(user, workspace_id, manage=True)
    connection = ClickUpConnection.objects.select_related('credential').filter(workspace_id=workspace_id).first()
    return {'connection': connection_data(connection) if connection else None}


@sensitive_variables('api_token')
def configure_clickup(user, workspace_id, api_token):
    workspace_for(user, workspace_id, manage=True)
    api_token = api_token.strip()
    if not api_token.startswith('pk_') or any(char.isspace() for char in api_token):
        raise WorkError('Bitte einen persönlichen ClickUp-API-Token eingeben.')
    account = clickup_request(api_token, 'user').get('user') or {}
    account_id = remote_id(account.get('id'))
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=workspace_id)
        workspace_for(user, workspace_id, manage=True)
        connection = ClickUpConnection.objects.select_related('credential').filter(workspace_id=workspace_id).first()
        credential = connection.credential if connection else IntegrationCredential(key='clickup-' + uuid4().hex, name='ClickUp Workspace ' + str(workspace_id), kind=IntegrationCredential.Kind.API_KEY)
        credential.set_secret(api_token)
        credential.enabled = True
        credential.save()
        connection, _ = ClickUpConnection.objects.update_or_create(workspace_id=workspace_id, defaults={
            'credential': credential, 'remote_user_id': account_id,
            'account_name': str(account.get('username') or account.get('email') or account_id)[:200],
        })
        return {'connection': connection_data(connection), 'verified': True}


def array(data, key):
    result = data.get(key)
    if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
        raise WorkError('ClickUp hat unvollständige Daten geliefert.', 502)
    return result


def team_for(connection, team_id):
    teams = array(fetch(connection, 'team'), 'teams')
    team = next((item for item in teams if str(item.get('id')) == team_id), None)
    if not team:
        raise WorkError('Der ClickUp-Workspace ist mit diesem Token nicht zugänglich.')
    return team


def location(item):
    return {'id': remote_id(item['id']), 'name': str(item.get('name') or item['id'])[:200]}


def list_clickup_locations(user, workspace_id, team_id=None, space_id=None, folder_id=None, archived=False):
    connection = connection_for(user, workspace_id)
    params = {'archived': str(archived).lower()}
    result = {'teams': [], 'spaces': [], 'folders': [], 'lists': []}
    if (space_id and not team_id) or (folder_id and not space_id):
        raise WorkError('Bitte zuerst ClickUp-Workspace und Space wählen.')
    if not team_id:
        result['teams'] = [location(t) for t in array(fetch(connection, 'team'), 'teams')]
    else:
        team_for(connection, team_id)
        if not space_id:
            result['spaces'] = [location(s) for s in array(fetch(connection, f'team/{team_id}/space', params), 'spaces')]
        elif not folder_id:
            result['folders'] = [location(f) for f in array(fetch(connection, f'space/{space_id}/folder', params), 'folders')]
            result['lists'] = [location(l) for l in array(fetch(connection, f'space/{space_id}/list', params), 'lists')]
        else:
            result['lists'] = [location(l) for l in array(fetch(connection, f'folder/{folder_id}/list', params), 'lists')]
    unchanged(user, connection)
    return result


def preview_clickup(user, workspace_id, team_id, list_id, page=0, archived=False, only_completed=False):
    connection = connection_for(user, workspace_id)
    team_for(connection, team_id)
    result = fetch(connection, f'list/{list_id}/task', {'page': page, 'subtasks': 'true', 'include_closed': 'true', 'archived': str(archived).lower(), 'order_by': 'id'})
    tasks = array(result, 'tasks')
    existing = set(connection.task_links.filter(remote_id__in=[str(t['id']) for t in tasks]).values_list('remote_id', flat=True))
    rows = []
    for task in tasks:
        if str(task.get('team_id')) != team_id:
            raise WorkError('Die gewählte Liste gehört nicht zum ClickUp-Workspace.')
        status = task.get('status') or {}
        if only_completed and status.get('type') not in ('done', 'closed'):
            continue
        rows.append({'id': remote_id(task['id'], task=True), 'title': str(task.get('name') or ''),
                     'status': str(status.get('status') or ''), 'completed': status.get('type') in ('done', 'closed'),
                     'parent_id': task.get('parent'), 'minutes': integer(task.get('time_spent') or 0) / 60000,
                     'list_name': str((task.get('list') or {}).get('name') or list_id),
                     'imported': str(task['id']) in existing})
    unchanged(user, connection)
    return {'tasks': rows, 'page': page, 'next_page': page + 1 if len(tasks) == 100 and not result.get('last_page') else None}


def integer(value):
    if isinstance(value, bool) or not re.fullmatch(r'-?[0-9]+', str(value)):
        raise WorkError('ClickUp hat eine ungültige Zeitangabe geliefert.', 502)
    return int(value)


def normalized_time(raw, task_id, now_ms):
    if str((raw.get('task') or {}).get('id')) != task_id:
        raise WorkError('ClickUp hat Zeiten eines anderen Tickets geliefert.', 502)
    duration = integer(raw.get('duration'))
    if duration < 0:
        raise WorkError('Auf einem gewählten ClickUp-Ticket läuft noch ein Timer. Bitte zuerst stoppen und die Prüfung erneut starten.')
    start = integer(raw.get('start'))
    end = integer(raw.get('end'))
    if not 0 <= start <= end <= now_ms or duration > 3155760000000:
        raise WorkError('Eine ClickUp-Zeitbuchung enthält ungültige Start-/Endzeiten oder eine unrealistische Dauer.')
    author = raw.get('user') or {}
    entry = {'id': remote_id(raw.get('id')), 'task_id': task_id, 'start': start, 'end': end, 'duration': duration,
             'description': str(raw.get('description') or ''),
             'person': {'id': remote_id(author.get('id')), 'name': str(author.get('username') or author.get('email') or author.get('id'))[:200], 'email': str(author.get('email') or '').strip().lower()[:254]}}
    entry['fingerprint'] = hashlib.sha256(json.dumps({k: v for k, v in entry.items() if k != 'person'} | {'person_id': entry['person']['id']}, sort_keys=True).encode()).hexdigest()
    return entry


def task_times(connection, team, task, now_ms):
    task_id = remote_id(task['id'], task=True)
    users = {remote_id(connection.remote_user_id)}
    users |= {remote_id(m['user']['id']) for m in team.get('members', []) if (m.get('user') or {}).get('id') is not None}
    users |= {remote_id(u['id']) for u in task.get('assignees', []) if u.get('id') is not None}
    entries = {}
    def load(user_ids):
        ordered = sorted(user_ids)
        for offset in range(0, len(ordered), 50):
            data = fetch(connection, f'team/{team["id"]}/time_entries', {'task_id': task_id, 'start_date': 0, 'end_date': now_ms,
                         'assignee': ','.join(ordered[offset:offset+50])})
            for raw in array(data, 'data'):
                entry = normalized_time(raw, task_id, now_ms)
                if entry['id'] in entries and entries[entry['id']] != entry:
                    raise WorkError('ClickUp-Zeiten haben sich während der Prüfung geändert. Bitte erneut prüfen.', 409)
                entries[entry['id']] = entry
    load(users)
    expected = integer(task.get('time_spent') or 0)
    if sum(e['duration'] for e in entries.values()) < expected:
        # Legacy endpoint only discovers former contributors; actual imported entries always use the current API.
        legacy = fetch(connection, f'task/{task_id}/time')
        former = {remote_id(row['user']['id']) for row in array(legacy, 'data') if (row.get('user') or {}).get('id') is not None} - users
        if former:
            load(former)
    if sum(e['duration'] for e in entries.values()) != expected:
        raise WorkError(f'Die Einzelbuchungen von ClickUp-Ticket {task_id} stimmen nicht mit dessen Zeitsumme überein. Es wird nichts importiert. Bitte Teamzeit-Berechtigungen prüfen oder nach Änderungen erneut versuchen.')
    return list(entries.values())


def prepare_clickup_import(user, workspace_id, team_id, task_ids):
    connection = connection_for(user, workspace_id)
    team = team_for(connection, team_id)
    now = timezone.now()
    now_ms = int(now.timestamp() * 1000)
    tasks, lists, warnings = [], {}, []
    for task_id in task_ids:
        task = fetch(connection, f'task/{task_id}', {'include_markdown_description': 'true'})
        if str(task.get('id')) != task_id or str(task.get('team_id')) != team_id:
            raise WorkError('Ein gewähltes Ticket gehört nicht zum ClickUp-Workspace.')
        list_id = remote_id((task.get('list') or {}).get('id'))
        if list_id not in lists:
            source_list = fetch(connection, f'list/{list_id}')
            lists[list_id] = {'id': list_id, 'name': str(source_list.get('name') or list_id)[:120],
                              'description': 'Importiert aus ClickUp: ' + ' / '.join(str((source_list.get(k) or {}).get('name') or '') for k in ('space', 'folder'))}
        times = task_times(connection, team, task, now_ms)
        if any(e['duration'] == 0 for e in times):
            warnings.append(task_id + ': Buchungen mit Dauer 0 erzeugen keine Arbeitszeit.')
        tasks.append({'id': task_id, 'name': str(task.get('name') or '')[:200], 'description': str(task.get('markdown_description') or task.get('description') or '')[:20000],
                      'list_id': list_id, 'status': task.get('status') or {}, 'parent': task.get('parent'),
                      'priority': (task.get('priority') or {}).get('id'), 'due_date': task.get('due_date'),
                      'assignees': [{'email': str(u.get('email') or '').strip().lower()} for u in task.get('assignees', [])],
                      'tags': [str(t.get('name') or '')[:40] for t in task.get('tags', [])], 'times': times})
    payload = {'connection_revision': connection.updated_at.isoformat(), 'team_id': team_id, 'tasks': tasks,
               'lists': lists, 'timezone': timezone.get_current_timezone_name(), 'warnings': warnings}
    if len(json.dumps(payload).encode()) > 20_000_000:
        raise WorkError('Die gewählte Historie ist zu groß. Bitte weniger Tickets auswählen.')
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=workspace_id)
        unchanged(user, connection)
        ClickUpImportBatch.objects.filter(connection=connection, expires_at__lt=now).delete()
        batch = ClickUpImportBatch.objects.create(connection=connection, created_by=user, payload=payload, expires_at=now + timedelta(minutes=30))
        people = {}
        dates = []
        for task in tasks:
            for entry in task['times']:
                dates.append(timezone.localdate(datetime.fromtimestamp(entry['start'] / 1000, tz=dt_timezone.utc)).isoformat())
                author = entry['person']
                key = author['id']
                item = people.setdefault(key, {**author, 'minutes': 0, 'entry_count': 0})
                item['minutes'] += entry['duration'] / 60000
                item['entry_count'] += 1
        return {'batch_id': str(batch.pk), 'expires_at': batch.expires_at.isoformat(), 'prepared_at': now.isoformat(),
                'task_count': len(tasks), 'entry_count': sum(len(t['times']) for t in tasks),
                'total_minutes': sum(e['duration'] for t in tasks for e in t['times']) / 60000,
                'people': list(people.values()), 'timezone': payload['timezone'], 'warnings': warnings,
                'date_from': min(dates) if dates else None, 'date_to': max(dates) if dates else None}


def import_clickup(user, workspace_id, batch_id):
    from zoneinfo import ZoneInfo
    from .services import create_project, create_ticket, update_ticket
    connection = connection_for(user, workspace_id)
    batch = ClickUpImportBatch.objects.select_for_update().filter(pk=batch_id, connection=connection, created_by=user).first()
    if not batch or batch.expires_at <= timezone.now():
        raise WorkError('Die Importprüfung ist abgelaufen oder nicht verfügbar. Bitte erneut prüfen.', 404)
    if batch.imported_at:
        return {**batch.result, 'replayed': True}
    payload = batch.payload
    if payload['connection_revision'] != connection.updated_at.isoformat():
        raise WorkError('Die ClickUp-Verbindung wurde geändert. Bitte erneut prüfen.', 409)
    created, skipped, new_projects, warnings = [], [], [], list(payload['warnings'])
    local, new_times, skipped_times, imported_ms = {}, 0, 0, 0
    for task in payload['tasks']:
        link = connection.task_links.select_related('ticket__project').filter(remote_id=task['id']).first()
        if link:
            ticket = link.ticket
            skipped.append(task['id'])
        else:
            source_list = payload['lists'][task['list_id']]
            project_link = connection.project_links.select_related('project').filter(remote_list_id=task['list_id']).first()
            if not project_link:
                stem = re.sub('[^A-Z0-9]', '', source_list['name'].upper())[:8] or 'CU'
                if not stem[0].isalpha(): stem = 'CU' + stem[:6]
                if len(stem) < 2: stem += 'P'
                key, suffix = stem, 1
                while Project.objects.filter(workspace_id=workspace_id, key=key).exists():
                    suffix += 1; key = stem + str(suffix)
                data = create_project(user, source_list['name'], key, description=source_list['description'], workspace_id=workspace_id)
                project_link = ClickUpProject.objects.create(connection=connection, remote_list_id=task['list_id'], remote_team_id=payload['team_id'], project_id=data['id'])
                new_projects.append(data)
            project = Project.objects.select_for_update().get(pk=project_link.project_id)
            status_name = str(task['status'].get('status') or 'Offen')[:60]
            category = {'open': 'open', 'done': 'done', 'closed': 'closed'}.get(task['status'].get('type'), 'in_progress')
            status = project.statuses.filter(name__iexact=status_name).first() or Status.objects.create(project=project, name=status_name, category=category, position=max(project.statuses.values_list('position', flat=True), default=0)+10)
            tag_ids = []
            for label in task['tags']:
                if label.strip():
                    tag = project.tags.filter(name__iexact=label.strip()).first() or Tag.objects.create(project=project, name=label.strip())
                    tag_ids.append(tag.pk)
            members = project_members(project)
            assignees = list(members.filter(email__in=[a['email'] for a in task['assignees'] if a['email']]).values_list('id', flat=True))
            if len(assignees) < len(task['assignees']): warnings.append(task['id'] + ': Nicht alle ClickUp-Zuweisungen passen zu aktiven Projektmitgliedern.')
            due = datetime.fromtimestamp(integer(task['due_date']) / 1000, tz=dt_timezone.utc).astimezone(ZoneInfo(payload['timezone'])).date().isoformat() if task['due_date'] else None
            data = create_ticket(user, project.pk, title=task['name'], description=task['description'], status_id=status.pk,
                                 tag_ids=list(set(tag_ids)), assignee_ids=assignees, priority={'1': 'urgent', '2': 'high', '3': 'normal', '4': 'low'}.get(str(task['priority']), 'normal'), due_date=due)
            ticket = Ticket.objects.get(pk=data['id'])
            ClickUpTask.objects.create(connection=connection, remote_id=task['id'], ticket=ticket)
            created.append(task['id'])
        local[task['id']] = ticket
        for entry in task['times']:
            existing = connection.time_sources.filter(remote_id=entry['id']).first()
            if existing:
                if existing.fingerprint != entry['fingerprint'] or existing.ticket_id != ticket.pk:
                    raise WorkError('Eine bereits importierte ClickUp-Zeitbuchung wurde in der Quelle geändert. Vorhandene Historie wird nicht überschrieben; bitte den Unterschied prüfen.', 409)
                skipped_times += 1
                continue
            if entry['duration'] == 0: continue
            author = entry['person']
            external, _ = ClickUpPerson.objects.get_or_create(connection=connection, remote_id=author['id'], defaults={'name': author['name'], 'email': author['email']})
            matched = project_members(ticket.project).filter(email__iexact=author['email']).first() if author['email'] else None
            source = ClickUpTimeSource.objects.create(connection=connection, remote_id=entry['id'], ticket=ticket, person=external,
                        start_ms=entry['start'], end_ms=entry['end'], duration_ms=entry['duration'], description=entry['description'], fingerprint=entry['fingerprint'])
            work_date = datetime.fromtimestamp(entry['start'] / 1000, tz=dt_timezone.utc).astimezone(ZoneInfo(payload['timezone'])).date()
            remaining = entry['duration']
            while remaining:
                duration = min(remaining, 86400000)
                TimeEntry.objects.create(ticket=ticket, user=matched, external_person=None if matched else external, clickup_source=source,
                                         work_date=work_date, minutes=math.ceil(duration/60000), duration_ms=duration, note=entry['description'][:2000])
                remaining -= duration
            new_times += 1; imported_ms += entry['duration']
    for task in payload['tasks']:
        if task['id'] not in created or not task['parent']: continue
        ticket = local[task['id']]
        parent = local.get(str(task['parent']))
        if not parent:
            source = connection.task_links.select_related('ticket').filter(remote_id=str(task['parent'])).first()
            parent = source.ticket if source else None
        if parent and parent.project_id == ticket.project_id:
            update_ticket(user, ticket.project_id, ticket.pk, parent_id=parent.pk)
        else:
            warnings.append(task['id'] + ': Eltern-Aufgabe nicht im selben Projekt importiert; bitte manuell zuordnen.')
    dates = [timezone.localdate(datetime.fromtimestamp(e['start'] / 1000, tz=dt_timezone.utc), timezone=ZoneInfo(payload['timezone'])).isoformat() for t in payload['tasks'] for e in t['times']]
    result = {'date_from': min(dates) if dates else None, 'date_to': max(dates) if dates else None, 'created': created, 'skipped': skipped, 'projects_created': new_projects, 'time_entries_created': new_times,
              'time_entries_skipped': skipped_times, 'imported_minutes': imported_ms / 60000, 'warnings': warnings}
    batch.imported_at = timezone.now(); batch.result = result; batch.payload = {}
    batch.save(update_fields=['imported_at', 'result', 'payload'])
    return result


def register_operations(register, ID, NAME, TEXT):
    common = {'workspace_id': ID}
    register(get_clickup_connection, 'ClickUp-Verbindungsstatus lesen; niemals den Token. Nur Workspace-Leitung.', common, ['workspace_id'], project=False)
    register(configure_clickup, 'Persönlichen ClickUp-API-Token prüfen und zentral verschlüsseln. Nur Workspace-Leitung.', {**common, 'api_token': NAME(2000)}, ['workspace_id', 'api_token'], write=True, project=False)
    register(list_clickup_locations, 'Zugängliche ClickUp-Workspaces, Spaces, Ordner und Listen schrittweise lesen. team_id, dann space_id, dann optional folder_id angeben.', {**common, 'team_id': REMOTE_ID, 'space_id': REMOTE_ID, 'folder_id': REMOTE_ID, 'archived': {'type': 'boolean'}}, ['workspace_id'], project=False)
    register(preview_clickup, 'ClickUp-Aufgaben einer Liste inklusive Unteraufgaben und abgeschlossener Tickets anzeigen. Paginierte Auswahlvorschau; nur Workspace-Leitung.', {**common, 'team_id': REMOTE_ID, 'list_id': REMOTE_ID, 'page': {'type': 'integer', 'minimum': 0}, 'archived': {'type': 'boolean'}, 'only_completed': {'type': 'boolean'}}, ['workspace_id', 'team_id', 'list_id'], project=False)
    register(prepare_clickup_import, 'Bis zu 20 ClickUp-Tickets und sämtliche historischen Zeitbuchungen prüfen. Vergleicht Einzelbuchungen mit Quellsummen und liefert einen 30 Minuten gültigen Importplan mit Personen und Zeiten. Noch keine lokalen Projekte/Tickets.', {**common, 'team_id': REMOTE_ID, 'task_ids': {'type': 'array', 'items': TASK_ID, 'minItems': 1, 'maxItems': BATCH_SIZE, 'uniqueItems': True}}, ['workspace_id', 'team_id', 'task_ids'], write=True, project=False)
    register(import_clickup, 'Geprüften ClickUp-Importplan atomar übernehmen: Listen werden Projekte, Tickets inklusive Status und Historie. Vorhandene Quellen überspringen; fremde Personen bleiben historische Mitwirkende ohne Konto. Nur Workspace-Leitung.', {**common, 'batch_id': {'type': 'string', 'format': 'uuid', 'pattern': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'}}, ['workspace_id', 'batch_id'], write=True, project=False)
    from .services import OPERATIONS
    for name in ('configure_clickup', 'list_clickup_locations', 'preview_clickup', 'prepare_clickup_import'):
        OPERATIONS[name]['external'] = True
