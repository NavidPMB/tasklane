"""Gemeinsame Fachlogik für Browser-API und MCP. Keine Berechtigungslogik im Client."""
from datetime import date
import csv
from io import StringIO
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, OuterRef, Subquery, Value, IntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone
from jsonschema import Draft202012Validator

from .models import Project, Status, Tag, Ticket, TimeEntry, Workspace, ClickUpPerson, Comment, Attachment, ChecklistItem

from .time_values import minute_sum, external_person_data
from .errors import WorkError
from .access import accessible_projects, project_members, person

CATEGORIES = [{'id': key, 'name': label} for key, label in Status.Category.choices]
CATEGORY_ORDER = {item['id']: index for index, item in enumerate(CATEGORIES)}


def project_for(user, project_id):
    project = accessible_projects(user).filter(pk=project_id).first()
    if not project:
        raise WorkError('Projekt nicht gefunden.', 404)
    return project


def owner_only(user, project):
    if project.owner_id != user.pk and project.workspace.owner_id != user.pk:
        raise WorkError('Nur die Projekt- oder Workspace-Leitung kann Mitglieder oder Projekteinstellungen ändern.', 403)


def project_data(project, user):
    ticket_count = getattr(project, 'ticket_count', None)
    return {
        'id': project.pk, 'name': project.name, 'key': project.key,
        'description': project.description, 'owner_id': project.owner_id,
        'workspace_id': project.workspace_id, 'workspace_name': project.workspace.name,
        'can_manage': user.pk in (project.owner_id, project.workspace.owner_id),
        'ticket_count': ticket_count if ticket_count is not None else project.tickets.count(),
    }


def status_data(status):
    return {'id': status.pk, 'name': status.name, 'category': status.category,
            'position': status.position, 'is_base': status.is_base}


def statuses_for(project):
    return sorted(project.statuses.all(), key=lambda s: (CATEGORY_ORDER[s.category], s.position, s.pk))


def ticket_query(project):
    def counter(model, path, **filters):
        rows = model.objects.filter(**{path: OuterRef('pk'), **filters}).order_by().values(path).annotate(n=Count('pk')).values('n')
        return Coalesce(Subquery(rows, output_field=IntegerField()), Value(0))
    return project.tickets.select_related('project', 'jira_source__connection', 'clickup_source').prefetch_related('tags', 'assignees', 'field_values__field').annotate(
        logged_minutes=minute_sum('time_entries__'),
        comments_total=counter(Comment, 'ticket_id', deleted_at__isnull=True),
        attachments_total=counter(Attachment, 'ticket_id', state='ready'),
        checklist_items_total=counter(ChecklistItem, 'checklist__ticket_id'),
        checklist_items_done=counter(ChecklistItem, 'checklist__ticket_id', done=True),
    )


def ticket_data(ticket):
    logged_minutes = getattr(ticket, 'logged_minutes', None)
    return {
        'id': ticket.pk, 'key': f'{ticket.project.key}-{ticket.number}',
        'project_id': ticket.project_id, 'title': ticket.title,
        'web_url': f'{settings.PUBLIC_URL}/dashboard?workspace={ticket.project.workspace_id}&project={ticket.project_id}&ticket={ticket.pk}',
        'description': ticket.description, 'kind': ticket.kind, 'parent_id': ticket.parent_id,
        'status_id': ticket.status_id, 'assignee_ids': [u.pk for u in ticket.assignees.all()],
        'tag_ids': [t.pk for t in ticket.tags.all()], 'priority': ticket.priority,
        'due_date': ticket.due_date.isoformat() if ticket.due_date else None,
        'created_at': ticket.created_at.isoformat(), 'updated_at': ticket.updated_at.isoformat(),
        'jira': jira_ticket_source(ticket),
        'clickup': clickup_ticket_source(ticket),
        'custom_fields': {v.field.key: v.value for v in ticket.field_values.all()},
        'comment_count': getattr(ticket, 'comments_total', None) if getattr(ticket, 'comments_total', None) is not None else ticket.comments.filter(deleted_at__isnull=True).count(),
        'attachment_count': getattr(ticket, 'attachments_total', None) if getattr(ticket, 'attachments_total', None) is not None else ticket.attachments.filter(state='ready').count(),
        'checklist_total': getattr(ticket, 'checklist_items_total', None) if getattr(ticket, 'checklist_items_total', None) is not None else ChecklistItem.objects.filter(checklist__ticket=ticket).count(),
        'checklist_done': getattr(ticket, 'checklist_items_done', None) if getattr(ticket, 'checklist_items_done', None) is not None else ChecklistItem.objects.filter(checklist__ticket=ticket, done=True).count(),
        'logged_minutes': logged_minutes if logged_minutes is not None else ticket.time_entries.aggregate(total=minute_sum())['total'],
    }


def jira_ticket_source(ticket):
    from .models import JiraIssue
    try:
        source = ticket.jira_source
    except JiraIssue.DoesNotExist:
        return None
    return {'key': source.remote_key, 'url': source.connection.base_url + '/browse/' + source.remote_key} if source else None


def clickup_ticket_source(ticket):
    from .models import ClickUpTask
    try:
        source = ticket.clickup_source
    except ClickUpTask.DoesNotExist:
        return None
    return {'key': source.remote_id, 'url': 'https://app.clickup.com/t/' + source.remote_id}


def nonblank(value):
    value = value.strip()
    if not value:
        raise WorkError('Bitte einen Namen oder Titel eingeben.')
    return value


def related(project, relation, pk, label):
    obj = getattr(project, relation).filter(pk=pk).first()
    if obj is None:
        raise WorkError(f'{label} gehört nicht zu diesem Projekt.', 400)
    return obj


def list_projects(user, workspace_id=None):
    projects = accessible_projects(user)
    if workspace_id is not None:
        from .workspaces import workspace_for
        workspace_for(user, workspace_id)
        projects = projects.filter(workspace_id=workspace_id)
    projects = projects.annotate(ticket_count=Count('tickets', distinct=True))
    return {'projects': [project_data(p, user) for p in projects]}


def create_project(user, name, key, description='', workspace_id=None):
    from .workspaces import workspace_for
    if workspace_id is None:
        workspace, _ = Workspace.objects.get_or_create(owner=user, is_personal=True, defaults={'name': 'Meine Projekte'})
    else:
        workspace = workspace_for(user, workspace_id, member=True)
    key = key.strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9]{1,11}', key):
        raise WorkError('Projektkürzel: 2–12 Zeichen, beginnend mit einem Buchstaben, danach Buchstaben oder Ziffern.')
    project = Project.objects.create(name=nonblank(name), key=key, description=description, owner=user, workspace=workspace)
    project.members.add(user)
    Status.objects.bulk_create([Status(project=project, name=item['name'], category=item['id'], is_base=True) for item in CATEGORIES])
    return project_data(project, user)


def get_project(user, project_id):
    from .collaboration import field_data
    project = project_for(user, project_id)
    inherited = set(project.workspace.members.values_list('id', flat=True)) | {project.workspace.owner_id}
    return {
        'project': project_data(project, user), 'categories': CATEGORIES,
        'custom_fields': [field_data(f) for f in project.custom_fields.all()],
        'statuses': [status_data(s) for s in statuses_for(project)],
        'members': [{**person(u), 'inherited': u.pk in inherited} for u in project_members(project)],
        'tags': list(project.tags.values('id', 'name')),
        'tickets': [ticket_data(t) for t in ticket_query(project)],
    }


def update_project(user, project_id, name=None, description=None):
    project = project_for(user, project_id)
    owner_only(user, project)
    if name is not None:
        project.name = nonblank(name)
    if description is not None:
        project.description = description
    project.save(update_fields=['name', 'description'])
    return project_data(project, user)


def add_project_member(user, project_id, email):
    project = project_for(user, project_id)
    owner_only(user, project)
    member = get_user_model().objects.filter(email__iexact=email.strip(), is_active=True).first()
    if not member:
        raise WorkError('Kein aktives Konto mit dieser E-Mail gefunden. Das Teammitglied muss sich zuerst anmelden.')
    project.members.add(member)
    return person(member)


def remove_project_member(user, project_id, user_id):
    project = project_for(user, project_id)
    owner_only(user, project)
    if project.owner_id == user_id:
        raise WorkError('Die Projektleitung kann nicht entfernt werden.')
    if project.workspace.owner_id == user_id or project.workspace.members.filter(pk=user_id).exists():
        raise WorkError('Dieses Mitglied gehört zum gesamten Workspace. Bitte dort verwalten.')
    member = related(project, 'members', user_id, 'Mitglied')
    Ticket.assignees.through.objects.filter(ticket__project=project, user_id=member.pk).delete()
    project.members.remove(member)
    return {'removed': True}


def list_statuses(user, project_id):
    project = project_for(user, project_id)
    return {'categories': CATEGORIES, 'statuses': [status_data(s) for s in statuses_for(project)]}


def create_status(user, project_id, name, category, position=None):
    project = project_for(user, project_id)
    if position is None:
        position = max((s.position for s in project.statuses.filter(category=category)), default=0) + 10
    status = Status.objects.create(project=project, name=nonblank(name), category=category, position=position)
    reposition_status(status, position)
    return status_data(status)


def reposition_status(status, position):
    others = list(status.project.statuses.filter(category=status.category, is_base=False).exclude(pk=status.pk).order_by('position', 'id'))
    index = next((i for i, other in enumerate(others) if other.position >= position), len(others))
    others.insert(index, status)
    for index, item in enumerate(others, start=1):
        item.position = index * 10
    Status.objects.bulk_update(others, ['position'])


def update_status(user, project_id, status_id, name=None, category=None, position=None):
    project = project_for(user, project_id)
    status = related(project, 'statuses', status_id, 'Status')
    if status.is_base and ((category is not None and category != status.category) or (position is not None and position != 0)):
        raise WorkError('Die vier Grundstatus behalten ihre Kategorie und Anfangsposition.')
    if name is not None:
        status.name = nonblank(name)
    if category is not None:
        if category != status.category and position is None:
            position = max((s.position for s in project.statuses.filter(category=category)), default=0) + 10
        status.category = category
    if position is not None:
        status.position = position
    status.save()
    if not status.is_base and position is not None:
        reposition_status(status, position)
    return status_data(status)


def delete_status(user, project_id, status_id, replacement_status_id=None):
    project = project_for(user, project_id)
    status = related(project, 'statuses', status_id, 'Status')
    if status.is_base:
        raise WorkError('Die vier Grundstatus können nicht gelöscht werden.')
    if replacement_status_id == status_id:
        raise WorkError('Der Ersatzstatus muss ein anderer Status sein.')
    replacement = related(project, 'statuses', replacement_status_id, 'Ersatzstatus') if replacement_status_id else None
    if status.tickets.exists() and replacement is None:
        raise WorkError('Für einen belegten Status bitte einen Ersatzstatus angeben.')
    if replacement:
        from django.utils import timezone
        status.tickets.update(status=replacement, updated_at=timezone.now())
    status.delete()
    return {'deleted': True}


def create_tag(user, project_id, name):
    project = project_for(user, project_id)
    tag = Tag.objects.create(project=project, name=nonblank(name))
    return {'id': tag.pk, 'name': tag.name}


def update_tag(user, project_id, tag_id, name):
    tag = related(project_for(user, project_id), 'tags', tag_id, 'Tag')
    tag.name = nonblank(name)
    tag.save()
    return {'id': tag.pk, 'name': tag.name}


def delete_tag(user, project_id, tag_id):
    related(project_for(user, project_id), 'tags', tag_id, 'Tag').delete()
    return {'deleted': True}


def list_tickets(user, project_id, query='', status_id=None, assignee_id=None, tag_id=None, parent_id=None, kind=None, offset=0, limit=100):
    project = project_for(user, project_id)
    tickets = ticket_query(project)
    if query:
        tickets = tickets.filter(Q(title__icontains=query) | Q(description__icontains=query))
    for field, value in [('status_id', status_id), ('assignees__id', assignee_id), ('tags__id', tag_id), ('parent_id', parent_id), ('kind', kind)]:
        if value is not None:
            tickets = tickets.filter(**{field: value})
    return {'tickets': [ticket_data(t) for t in tickets[offset:offset + limit]], 'total': tickets.count(), 'offset': offset, 'limit': limit}


def get_ticket(user, project_id, ticket_id):
    ticket = ticket_query(project_for(user, project_id)).filter(pk=ticket_id).first()
    if not ticket: raise WorkError('Ticket nicht gefunden.', 404)
    return ticket_data(ticket)


def set_ticket_fields(project, ticket, fields):
    from .collaboration import set_ticket_values
    creating = ticket.pk is None
    custom_values = fields.pop('custom_fields', {})
    for field in ['title', 'description', 'kind', 'priority']:
        if field in fields:
            setattr(ticket, field, nonblank(fields[field]) if field == 'title' else fields[field])
    if 'status_id' in fields:
        ticket.status = related(project, 'statuses', fields['status_id'], 'Status')
    if 'parent_id' in fields:
        ticket.parent = related(project, 'tickets', fields['parent_id'], 'Übergeordnetes Ticket') if fields['parent_id'] else None
    if ticket.kind == Ticket.Kind.EPIC and ticket.parent_id:
        raise WorkError('Ein Epic steht auf der obersten Ebene.')
    ancestor = ticket.parent if ticket.parent_id else None
    visited = {ticket.pk} if ticket.pk else set()
    while ancestor:
        if ancestor.pk in visited:
            raise WorkError('Die Tickethierarchie darf keinen Kreis enthalten.')
        visited.add(ancestor.pk)
        ancestor = ancestor.parent
    if 'due_date' in fields:
        try:
            ticket.due_date = date.fromisoformat(fields['due_date']) if fields['due_date'] else None
        except ValueError:
            raise WorkError('Das Fälligkeitsdatum muss ein gültiges Datum im Format JJJJ-MM-TT sein.')
    members, tags = None, None
    if 'assignee_ids' in fields:
        members = list(project_members(project).filter(pk__in=fields['assignee_ids'], is_active=True))
        if len(members) != len(fields['assignee_ids']):
            raise WorkError('Zuweisungen sind nur an aktive Projektmitglieder möglich.')
    if 'tag_ids' in fields:
        tags = list(project.tags.filter(pk__in=fields['tag_ids']))
        if len(tags) != len(fields['tag_ids']):
            raise WorkError('Alle Tags müssen zum Projekt gehören.')
    ticket.save()
    set_ticket_values(ticket, custom_values, creating=creating)
    if members is not None:
        ticket.assignees.set(members)
    if tags is not None:
        ticket.tags.set(tags)
    return ticket_data(ticket)


def create_ticket(user, project_id, title, **fields):
    project = project_for(user, project_id)
    status = project.statuses.get(category=Status.Category.OPEN, is_base=True)
    ticket = Ticket(project=project, number=project.next_number, created_by=user, status=status)
    result = set_ticket_fields(project, ticket, {'title': title, **fields})
    project.next_number += 1
    project.save(update_fields=['next_number'])
    from .collaboration import event
    event(user, project, ticket, 'ticket_created', 'Ticket erstellt: ' + ticket.title)
    return result


def update_ticket(user, project_id, ticket_id, **fields):
    project = project_for(user, project_id)
    ticket = related(project, 'tickets', ticket_id, 'Ticket')
    expected = fields.pop('expected_updated_at', None)
    if expected is not None and expected != ticket.updated_at.isoformat():
        raise WorkError('Dieses Ticket wurde inzwischen geändert. Bitte schließen und erneut öffnen.', 409)
    changed_fields = list(fields)
    result = set_ticket_fields(project, ticket, fields)
    from .collaboration import event
    event(user, project, ticket, 'ticket_updated', 'Ticket geändert', fields=changed_fields)
    return result


def delete_ticket(user, project_id, ticket_id):
    ticket = related(project_for(user, project_id), 'tickets', ticket_id, 'Ticket')
    if ticket.children.exists():
        raise WorkError('Zuerst untergeordnete Tickets umhängen oder löschen.')
    if ticket.time_entries.exists():
        raise WorkError('Tickets mit Zeitbuchungen bleiben für die Berichte erhalten. Bitte stattdessen schließen.')
    from .collaboration import event
    from .attachments import delete_file_after_commit
    for attachment in ticket.attachments.all(): delete_file_after_commit(attachment)
    event(user, ticket.project, None, 'ticket_deleted', 'Ticket entfernt: ' + ticket.title, ticket_id=ticket.pk)
    ticket.delete()
    return {'deleted': True}


def parse_work_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise WorkError('Bitte ein gültiges Datum im Format JJJJ-MM-TT angeben.')


def time_entry_data(entry, user):
    return {
        'id': entry.pk, 'project_id': entry.ticket.project_id,
        'project_name': entry.ticket.project.name,
        'ticket_id': entry.ticket_id, 'ticket_key': f'{entry.ticket.project.key}-{entry.ticket.number}',
        'ticket_title': entry.ticket.title, 'user': person(entry.user) if entry.user_id else external_person_data(entry.external_person),
        'work_date': entry.work_date.isoformat(), 'minutes': entry.duration_ms / 60000 if entry.duration_ms is not None else entry.minutes,
        'duration_ms': entry.duration_ms if entry.duration_ms is not None else entry.minutes * 60000,
        'note': entry.clickup_source.description if entry.clickup_source_id else entry.note,
        'source': {'provider': 'clickup', 'id': entry.clickup_source.remote_id, 'person': entry.clickup_source.person.name} if entry.clickup_source_id else None,
        'can_edit': entry.user_id == user.pk and not entry.clickup_source_id, 'updated_at': entry.updated_at.isoformat(),
    }


def validate_time_fields(work_date):
    parsed = parse_work_date(work_date)
    if parsed > timezone.localdate():
        raise WorkError('Arbeitszeit kann nicht für ein zukünftiges Datum gebucht werden.')
    return parsed


def create_time_entry(user, project_id, ticket_id, work_date, minutes, note=''):
    from .collaboration import event
    ticket = related(project_for(user, project_id), 'tickets', ticket_id, 'Ticket')
    entry = TimeEntry.objects.create(ticket=ticket, user=user, work_date=validate_time_fields(work_date), minutes=minutes, note=note.strip())
    event(user, ticket.project, ticket, 'time_created', 'Arbeitszeit erfasst', entry_id=entry.pk, minutes=minutes, work_date=entry.work_date.isoformat())
    return time_entry_data(entry, user)


def own_time_entry(user, project_id, entry_id, expected_updated_at=None):
    project = project_for(user, project_id)
    entry = TimeEntry.objects.select_related('ticket__project', 'user', 'external_person', 'clickup_source__person').filter(ticket__project=project, pk=entry_id).first()
    if not entry:
        raise WorkError('Zeitbuchung nicht gefunden.', 404)
    if entry.clickup_source_id:
        raise WorkError('Importierte ClickUp-Zeiten bleiben als Quellhistorie unverändert.', 403)
    if entry.user_id != user.pk:
        raise WorkError('Zeitbuchungen können nur von der Person geändert werden, die sie erfasst hat.', 403)
    if expected_updated_at is not None and entry.updated_at.isoformat() != expected_updated_at:
        raise WorkError('Diese Zeitbuchung wurde inzwischen geändert. Bitte neu laden.', 409)
    return entry


def update_time_entry(user, project_id, entry_id, work_date=None, minutes=None, note=None, expected_updated_at=None):
    from .collaboration import event
    entry = own_time_entry(user, project_id, entry_id, expected_updated_at)
    if work_date is not None:
        entry.work_date = validate_time_fields(work_date)
    if minutes is not None:
        entry.minutes = minutes
    if note is not None:
        entry.note = note.strip()
    entry.save()
    event(user, entry.ticket.project, entry.ticket, 'time_updated', 'Arbeitszeit korrigiert', entry_id=entry.pk, minutes=entry.minutes, work_date=entry.work_date.isoformat())
    return time_entry_data(entry, user)


def delete_time_entry(user, project_id, entry_id, expected_updated_at=None):
    from .collaboration import event
    entry = own_time_entry(user, project_id, entry_id, expected_updated_at)
    event(user, entry.ticket.project, entry.ticket, 'time_deleted', 'Arbeitszeit entfernt', entry_id=entry.pk, minutes=entry.minutes, work_date=entry.work_date.isoformat())
    entry.delete()
    return {'deleted': True}


def time_scope(user, project_id=None, ticket_id=None, user_id=None, date_from=None, date_to=None, workspace_id=None):
    projects = accessible_projects(user)
    if project_id is not None:
        project_for(user, project_id)
        projects = projects.filter(pk=project_id)
    if workspace_id is not None:
        from .workspaces import workspace_for
        workspace_for(user, workspace_id)
        projects = projects.filter(workspace_id=workspace_id)
    entries = TimeEntry.objects.filter(ticket__project__in=projects).select_related('ticket__project', 'user', 'external_person', 'clickup_source__person')
    if ticket_id is not None:
        if not Ticket.objects.filter(project__in=projects, pk=ticket_id).exists():
            raise WorkError('Ticket nicht gefunden.', 404)
        entries = entries.filter(ticket_id=ticket_id)
    if user_id is not None:
        entries = entries.filter(user_id=user_id) if user_id > 0 else entries.filter(external_person_id=-user_id)
    start = parse_work_date(date_from) if date_from else None
    end = parse_work_date(date_to) if date_to else None
    if start and end and start > end:
        raise WorkError('Der Beginn des Zeitraums muss vor oder am Ende liegen.')
    if start:
        entries = entries.filter(work_date__gte=start)
    if end:
        entries = entries.filter(work_date__lte=end)
    return projects, entries


def list_time_entries(user, project_id=None, ticket_id=None, user_id=None, date_from=None, date_to=None, offset=0, limit=100, workspace_id=None):
    _, entries = time_scope(user, project_id, ticket_id, user_id, date_from, date_to, workspace_id)
    totals = entries.aggregate(total_minutes=minute_sum(), total=Count('id'))
    return {**totals, 'entries': [time_entry_data(entry, user) for entry in entries[offset:offset + limit]], 'offset': offset, 'limit': limit}


def report_period(date_from, date_to):
    today = timezone.localdate()
    return date_from or today.replace(day=1).isoformat(), date_to or today.isoformat()


def get_time_report(user, project_id=None, user_id=None, date_from=None, date_to=None, workspace_id=None):
    date_from, date_to = report_period(date_from, date_to)
    projects, entries = time_scope(user, project_id=project_id, user_id=user_id, date_from=date_from, date_to=date_to, workspace_id=workspace_id)
    people = get_user_model().objects.filter(
        Q(work_projects__in=projects) | Q(owned_projects__in=projects) | Q(workspaces__projects__in=projects) | Q(owned_workspaces__projects__in=projects) | Q(time_entries__ticket__project__in=projects)
    ).distinct().order_by('email')
    people_data = [{**person(p), 'is_active': p.is_active} for p in people]
    external = ClickUpPerson.objects.filter(time_entries__ticket__project__in=projects).distinct().order_by('name', 'id')
    people_data += [external_person_data(p) for p in external]
    grouped = {(row['user_id'] or -row['external_person_id']): row for row in entries.order_by().values('user_id', 'external_person_id').annotate(minutes=minute_sum(), entry_count=Count('id'), ticket_count=Count('ticket_id', distinct=True), day_count=Count('work_date', distinct=True))}
    users = [{**p, **{k: v for k, v in grouped.get(p['id'], {'minutes': 0, 'entry_count': 0, 'ticket_count': 0, 'day_count': 0}).items() if k not in ('user_id', 'external_person_id')}} for p in people_data if user_id is None or p['id'] == user_id]
    totals = entries.aggregate(total_minutes=minute_sum(), entry_count=Count('id'), ticket_count=Count('ticket_id', distinct=True), people_count=Count('user_id', distinct=True) + Count('external_person_id', distinct=True))
    by_project = [{'id': row['ticket__project_id'], 'name': row['ticket__project__name'], 'key': row['ticket__project__key'], 'minutes': row['minutes']} for row in entries.order_by('ticket__project__name').values('ticket__project_id', 'ticket__project__name', 'ticket__project__key').annotate(minutes=minute_sum())]
    by_ticket = [{'id': row['ticket_id'], 'key': f"{row['ticket__project__key']}-{row['ticket__number']}", 'title': row['ticket__title'], 'project_id': row['ticket__project_id'], 'minutes': row['minutes']} for row in entries.order_by('ticket__project__key', 'ticket__number').values('ticket_id', 'ticket__project__key', 'ticket__number', 'ticket__title', 'ticket__project_id').annotate(minutes=minute_sum())]
    return {**totals, 'date_from': date_from, 'date_to': date_to, 'people': people_data, 'users': users,
            'projects': by_project, 'tickets': by_ticket,
            'days': [{'date': row['work_date'].isoformat(), 'minutes': row['minutes']} for row in entries.order_by('work_date').values('work_date').annotate(minutes=minute_sum())]}


def export_time_report(user, project_id=None, user_id=None, date_from=None, date_to=None, workspace_id=None):
    date_from, date_to = report_period(date_from, date_to)
    _, entries = time_scope(user, project_id=project_id, user_id=user_id, date_from=date_from, date_to=date_to, workspace_id=workspace_id)
    output = StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Datum', 'Projekt', 'Ticket', 'Titel', 'Person', 'E-Mail', 'Minuten', 'Notiz', 'Dauer (ms)', 'Quelle', 'Quell-ID', 'Originalperson'])
    def safe(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text
    for entry in entries.order_by('work_date', 'user__email', 'id').iterator(chunk_size=500):
        row = time_entry_data(entry, user)
        writer.writerow([row['work_date'], safe(row['project_name']), row['ticket_key'], safe(row['ticket_title']), safe(row['user']['name']), safe(row['user']['email']), row['minutes'], safe(row['note']), row['duration_ms'], row['source']['provider'] if row['source'] else '', row['source']['id'] if row['source'] else '', safe(row['source']['person']) if row['source'] else ''])
    return {'filename': f'tasklane-zeiten-{date_from}-{date_to}.csv', 'csv': output.getvalue()}


# Dieselben Eingabeschemata gelten in der HTTP-API und in der MCP-Toolliste.
ID = {'type': 'integer', 'minimum': 1}
TEXT = lambda maximum: {'type': 'string', 'maxLength': maximum}
NAME = lambda maximum: {'type': 'string', 'minLength': 1, 'maxLength': maximum}
IDS = {'type': 'array', 'items': ID, 'uniqueItems': True, 'maxItems': 100}
NULL_ID = {'anyOf': [ID, {'type': 'null'}]}
CATEGORY = {'type': 'string', 'enum': list(Status.Category.values)}
POSITION = {'type': 'integer', 'minimum': 1, 'maximum': 100000}
TICKET_FIELDS = {
    'custom_fields': {'type': 'object', 'maxProperties': 100, 'propertyNames': {'pattern': r'^[a-z][a-z0-9_]{0,59}$'}},
    'title': NAME(200), 'description': TEXT(20000), 'kind': {'type': 'string', 'enum': list(Ticket.Kind.values)},
    'parent_id': NULL_ID, 'status_id': ID, 'assignee_ids': IDS, 'tag_ids': IDS,
    'priority': {'type': 'string', 'enum': list(Ticket.Priority.values)},
    'due_date': {'anyOf': [{'type': 'string', 'pattern': r'^\d{4}-\d{2}-\d{2}$'}, {'type': 'null'}]},
}
OPERATIONS = {}


def register(fn, description, properties=None, required=(), *, write=False, project=True):
    props = {'project_id': ID} if project else {}
    props.update(properties or {})
    OPERATIONS[fn.__name__] = {
        'handler': fn, 'description': description, 'write': write,
        'inputSchema': {'type': 'object', 'properties': props, 'required': (['project_id'] if project else []) + list(required), 'additionalProperties': False},
    }


register(list_projects, 'Zugängliche Projekte mit Workspace, Kürzel und Ticketanzahl auflisten.', {'workspace_id': ID}, project=False)
register(create_project, 'Projekt im Workspace mit vier Grundstatus erstellen. Ohne workspace_id wird ein persönlicher Workspace verwendet. Ersteller wird Projektleitung.', {'name': NAME(120), 'key': NAME(12), 'description': TEXT(10000), 'workspace_id': ID}, ['name', 'key'], write=True, project=False)
register(get_project, 'Aktueller Projektstand: Mitglieder, dynamische Status in Board-Reihenfolge, Tags und Tickets. Vor Statusauswahl abrufen.')
register(update_project, 'Projektname oder Beschreibung ändern (nur Projekt- oder Workspace-Leitung).', {'name': NAME(120), 'description': TEXT(10000)}, write=True)
register(add_project_member, 'Bestehendes aktives Konto per E-Mail zum Projekt hinzufügen (nur Projekt- oder Workspace-Leitung).', {'email': NAME(254)}, ['email'], write=True)
register(remove_project_member, 'Mitglied entfernen und dessen Ticketzuweisungen in diesem Projekt lösen (nur Projekt- oder Workspace-Leitung).', {'user_id': ID}, ['user_id'], write=True)
register(list_statuses, 'Live-Status und vier Grundkategorien abrufen. Benutzerdefinierte Status haben eigene IDs; keine Statusnamen fest codieren.')
register(create_status, 'Zwischenstatus in einer Grundkategorie erstellen. Position ordnet innerhalb der Kategorie, nach dem Grundstatus. Sofort in Board und Dropdowns verfügbar.', {'name': NAME(60), 'category': CATEGORY, 'position': POSITION}, ['name', 'category'], write=True)
register(update_status, 'Status umbenennen, Zwischenstatus einer Kategorie zuordnen oder mit Position umsortieren. Grundstatus bleiben erhalten.', {'status_id': ID, 'name': NAME(60), 'category': CATEGORY, 'position': POSITION}, ['status_id'], write=True)
register(delete_status, 'Zwischenstatus löschen. Bei belegtem Status ist replacement_status_id aus demselben Projekt erforderlich; Tickets werden atomar umgehängt.', {'status_id': ID, 'replacement_status_id': ID}, ['status_id'], write=True)
register(create_tag, 'Projektbezogenen Tag erstellen.', {'name': NAME(40)}, ['name'], write=True)
register(update_tag, 'Tag umbenennen.', {'tag_id': ID, 'name': NAME(40)}, ['tag_id', 'name'], write=True)
register(delete_tag, 'Tag entfernen und von den Tickets lösen.', {'tag_id': ID}, ['tag_id'], write=True)
register(list_tickets, 'Tickets suchen und nach Live-Status-ID, Zuweisung, Tag, Eltern-Ticket oder Typ filtern. Paginierte Ergebnisse.', {'query': TEXT(200), 'status_id': ID, 'assignee_id': ID, 'tag_id': ID, 'parent_id': ID, 'kind': TICKET_FIELDS['kind'], 'offset': {'type': 'integer', 'minimum': 0}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200}})
register(get_ticket, 'Ein Ticket mit Beschreibung, Hierarchie und Zuweisungen lesen.', {'ticket_id': ID}, ['ticket_id'])
register(create_ticket, 'Epic, Ticket oder Unterticket erstellen. parent_id verbindet die Hierarchie. status_id aus list_statuses/get_project verwenden; Standard ist Offen.', TICKET_FIELDS, ['title'], write=True)
register(update_ticket, 'Ticketfelder gezielt ändern; ausgelassene Felder bleiben erhalten. null löst Eltern-Ticket oder Datum, leere ID-Listen lösen Tags/Zuweisungen. expected_updated_at schützt optional vor konkurrierenden Änderungen.', {'ticket_id': ID, 'expected_updated_at': TEXT(40), **TICKET_FIELDS}, ['ticket_id'], write=True)
register(delete_ticket, 'Ticket ohne Untertickets löschen. Tickets mit Kindern müssen zuerst umgehängt werden.', {'ticket_id': ID}, ['ticket_id'], write=True)

DATE = {'type': 'string', 'pattern': r'^\d{4}-\d{2}-\d{2}$'}
TIME_FIELDS = {'work_date': DATE, 'minutes': {'type': 'integer', 'minimum': 1, 'maximum': 1440}, 'note': TEXT(2000)}
TIME_FILTERS = {'workspace_id': ID, 'project_id': ID, 'user_id': {'type': 'integer', 'not': {'const': 0}}, 'date_from': DATE, 'date_to': DATE}
register(create_time_entry, 'Eigene Arbeitszeit auf ein Ticket buchen: Datum (nicht in der Zukunft), ganze Minuten (1–1440) und optionale Notiz. Person ist immer das angemeldete Konto.', {'ticket_id': ID, **TIME_FIELDS}, ['ticket_id', 'work_date', 'minutes'], write=True)
register(update_time_entry, 'Eigene Zeitbuchung korrigieren. Fremde Buchungen können auch von der Projektleitung nicht verändert werden. expected_updated_at schützt vor Konflikten.', {'entry_id': ID, 'expected_updated_at': TEXT(40), **TIME_FIELDS}, ['entry_id'], write=True)
register(delete_time_entry, 'Eigene Zeitbuchung löschen; fremde Buchungen bleiben geschützt.', {'entry_id': ID, 'expected_updated_at': TEXT(40)}, ['entry_id'], write=True)
register(list_time_entries, 'Zeitbuchungen mit Projekt, Ticket, Person, Datum, Minuten und Notiz lesen. Filter optional, ohne Zeitraum alle Buchungen; paginiert. Nur zugängliche Projekte.', {**TIME_FILTERS, 'ticket_id': ID, 'offset': {'type': 'integer', 'minimum': 0}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200}}, project=False)
register(get_time_report, 'Arbeitszeit pro Person, Projekt, Ticket und Tag summieren. Ohne Projektfilter alle zugänglichen Projekte. Zeitraum inklusive beider Tage; Standard ist Monatsbeginn bis heute. Historische Buchungen entfernter Mitglieder bleiben enthalten. Historische ClickUp-Personen ohne Konto haben negative Personen-IDs; IDs aus diesem Bericht lesen.', TIME_FILTERS, project=False)
register(export_time_report, 'Zeitbericht als UTF-8-CSV mit Semikolon exportieren. Dieselben Projekt-, Personen- und Zeitraumfilter wie get_time_report. Enthält die einzelnen Buchungen; verändert keine Daten.', TIME_FILTERS, project=False)


def execute(user, action, arguments):
    if not user or not user.is_authenticated or not user.is_active:
        raise WorkError('Aktive Anmeldung erforderlich.', 401)
    operation = OPERATIONS.get(action) if isinstance(action, str) else None
    if not operation:
        raise WorkError('Unbekannte Aktion.')
    errors = list(Draft202012Validator(operation['inputSchema']).iter_errors(arguments))
    if errors:
        if action in ('configure_jira', 'configure_clickup'):
            raise WorkError('Ungültige Verbindungsdaten. Bitte die Felder und den API-Token prüfen.')
        error = errors[0]
        location = '.'.join(map(str, error.path)) or 'Parameter'
        raise WorkError(f'Ungültige Eingabe ({location}): {error.message}')
    try:
        if operation.get('external'):
            return operation['handler'](user, **arguments)
        with transaction.atomic():
            if operation['write']:
                workspace_id = arguments.get('workspace_id')
                if 'project_id' in arguments:
                    workspace_id = Project.objects.filter(pk=arguments['project_id']).values_list('workspace_id', flat=True).first()
                if workspace_id:
                    Workspace.objects.select_for_update().filter(pk=workspace_id).first()
            # Serialisiert Änderungen pro Projekt: Nummern, Hierarchie und Mitgliedschaft bleiben konsistent.
            if operation['write'] and 'project_id' in arguments:
                Project.objects.select_for_update().filter(pk=arguments['project_id']).first()
            return operation['handler'](user, **arguments)
    except IntegrityError:
        raise WorkError('Dieses Kürzel oder dieser Name ist bereits vergeben oder die Änderung verletzt eine Verknüpfung.')


from .workspaces import register_operations as register_workspaces
from .jira import register_operations as register_jira
register_workspaces(register, ID, NAME, TEXT)
register_jira(register, ID, NAME, TEXT)

from .clickup import register_operations as register_clickup
register_clickup(register, ID, NAME, TEXT)

from .collaboration import register_operations as register_collaboration
from .attachments import register_operations as register_attachments
register_collaboration(register, ID, NAME, TEXT)
register_attachments(register, ID, NAME, TEXT)
