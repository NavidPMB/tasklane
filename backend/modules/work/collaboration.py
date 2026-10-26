"""Kommentare, Checklisten, Projektfelder und Aktivitäten für UI, API und MCP."""
from datetime import date
import math
import re
from urllib.parse import urlsplit

from django.db.models import Count
from django.utils import timezone

from .access import person, project_members
from .errors import WorkError
from .models import Activity, Checklist, ChecklistItem, Comment, CustomField, TicketFieldValue


def ticket_for(user, project_id, ticket_id):
    from .services import project_for, related
    project = project_for(user, project_id)
    return related(project, 'tickets', ticket_id, 'Ticket')


def conflict(obj, expected):
    if expected is not None and expected != obj.updated_at.isoformat():
        raise WorkError('Dieser Inhalt wurde inzwischen geändert. Bitte neu laden.', 409)


def event(user, project, ticket, kind, summary, **data):
    return Activity.objects.create(project=project, ticket=ticket, actor=user, kind=kind, summary=summary[:500], data=data)


def comment_data(comment, user):
    return {'id': comment.pk, 'body': '' if comment.deleted_at else comment.body,
            'author': person(comment.author) if comment.author_id else {'id': None, 'name': comment.original_author, 'email': ''},
            'deleted': bool(comment.deleted_at), 'can_edit': comment.author_id == user.pk and not comment.deleted_at,
            'created_at': comment.created_at.isoformat(), 'updated_at': comment.updated_at.isoformat()}


def list_comments(user, project_id, ticket_id, offset=0, limit=50):
    comments = ticket_for(user, project_id, ticket_id).comments.select_related('author')
    return {'comments': [comment_data(c, user) for c in comments[offset:offset+limit]], 'total': comments.count()}


def create_comment(user, project_id, ticket_id, body):
    from .services import nonblank
    ticket = ticket_for(user, project_id, ticket_id)
    comment = Comment.objects.create(ticket=ticket, author=user, body=nonblank(body))
    event(user, ticket.project, ticket, 'comment_created', 'Kommentar hinzugefügt', comment_id=comment.pk)
    return comment_data(comment, user)


def own_comment(user, project_id, ticket_id, comment_id, expected_updated_at=None):
    ticket = ticket_for(user, project_id, ticket_id)
    comment = ticket.comments.filter(pk=comment_id, deleted_at__isnull=True).first()
    if not comment:
        raise WorkError('Kommentar nicht gefunden.', 404)
    if comment.author_id != user.pk:
        raise WorkError('Nur eigene Kommentare können geändert oder gelöscht werden.', 403)
    conflict(comment, expected_updated_at)
    return comment


def update_comment(user, project_id, ticket_id, comment_id, body, expected_updated_at=None):
    from .services import nonblank
    comment = own_comment(user, project_id, ticket_id, comment_id, expected_updated_at)
    comment.body = nonblank(body)
    comment.save(update_fields=['body', 'updated_at'])
    event(user, comment.ticket.project, comment.ticket, 'comment_updated', 'Kommentar bearbeitet', comment_id=comment.pk)
    return comment_data(comment, user)


def delete_comment(user, project_id, ticket_id, comment_id, expected_updated_at=None):
    comment = own_comment(user, project_id, ticket_id, comment_id, expected_updated_at)
    comment.body = ''
    comment.deleted_at = timezone.now()
    comment.save(update_fields=['body', 'deleted_at', 'updated_at'])
    event(user, comment.ticket.project, comment.ticket, 'comment_deleted', 'Kommentar entfernt', comment_id=comment.pk)
    return {'deleted': True}


def item_data(item):
    return {'id': item.pk, 'title': item.title, 'done': item.done, 'position': item.position, 'assignee_id': item.assignee_id,
            'created_at': item.created_at.isoformat(), 'updated_at': item.updated_at.isoformat()}


def checklist_data(checklist):
    return {'id': checklist.pk, 'name': checklist.name, 'position': checklist.position,
            'updated_at': checklist.updated_at.isoformat(), 'items': [item_data(i) for i in checklist.items.all()]}


def list_checklists(user, project_id, ticket_id):
    return {'checklists': [checklist_data(c) for c in ticket_for(user, project_id, ticket_id).checklists.prefetch_related('items')]}


def create_checklist(user, project_id, ticket_id, name='Checkliste'):
    from .services import nonblank
    ticket = ticket_for(user, project_id, ticket_id)
    checklist = Checklist.objects.create(ticket=ticket, name=nonblank(name), position=ticket.checklists.count()*10)
    event(user, ticket.project, ticket, 'checklist_created', 'Checkliste hinzugefügt', checklist_id=checklist.pk)
    return checklist_data(checklist)


def checklist_for(user, project_id, ticket_id, checklist_id):
    checklist = ticket_for(user, project_id, ticket_id).checklists.filter(pk=checklist_id).first()
    if not checklist:
        raise WorkError('Checkliste nicht gefunden.', 404)
    return checklist


def update_checklist(user, project_id, ticket_id, checklist_id, name=None, position=None, expected_updated_at=None):
    from .services import nonblank
    checklist = checklist_for(user, project_id, ticket_id, checklist_id)
    conflict(checklist, expected_updated_at)
    if name is not None: checklist.name = nonblank(name)
    if position is not None: checklist.position = position
    checklist.save()
    event(user, checklist.ticket.project, checklist.ticket, 'checklist_updated', 'Checkliste geändert', checklist_id=checklist.pk)
    return checklist_data(checklist)


def delete_checklist(user, project_id, ticket_id, checklist_id, expected_updated_at=None):
    checklist = checklist_for(user, project_id, ticket_id, checklist_id)
    conflict(checklist, expected_updated_at)
    event(user, checklist.ticket.project, checklist.ticket, 'checklist_deleted', 'Checkliste mit ihren Punkten entfernt', checklist_id=checklist.pk)
    checklist.delete()
    return {'deleted': True}


def assignee_for(project, assignee_id):
    if assignee_id is not None and not project_members(project).filter(pk=assignee_id).exists():
        raise WorkError('Checklistenpunkte können nur aktiven Projektmitgliedern zugeordnet werden.')
    return assignee_id


def create_checklist_item(user, project_id, ticket_id, checklist_id, title, done=False, assignee_id=None, position=None):
    from .services import nonblank
    checklist = checklist_for(user, project_id, ticket_id, checklist_id)
    item = ChecklistItem.objects.create(checklist=checklist, title=nonblank(title), done=done,
              assignee_id=assignee_for(checklist.ticket.project, assignee_id), position=position if position is not None else checklist.items.count()*10)
    checklist.save(update_fields=['updated_at'])
    event(user, checklist.ticket.project, checklist.ticket, 'checklist_item_created', 'Checklistenpunkt hinzugefügt', item_id=item.pk)
    return item_data(item)


def update_checklist_item(user, project_id, ticket_id, checklist_id, item_id, expected_updated_at=None, **fields):
    from .services import nonblank
    checklist = checklist_for(user, project_id, ticket_id, checklist_id)
    item = checklist.items.filter(pk=item_id).first()
    if not item: raise WorkError('Checklistenpunkt nicht gefunden.', 404)
    conflict(item, expected_updated_at)
    for key, value in fields.items():
        if key == 'title': value = nonblank(value)
        if key == 'assignee_id': value = assignee_for(checklist.ticket.project, value)
        setattr(item, key, value)
    item.save()
    if 'position' in fields:
        others = list(checklist.items.exclude(pk=item.pk).order_by('position', 'id'))
        index = next((i for i, other in enumerate(others) if other.position >= fields['position']), len(others))
        others.insert(index, item)
        for i, other in enumerate(others, start=1): other.position = i*10
        ChecklistItem.objects.bulk_update(others, ['position'])
        item.refresh_from_db()
    checklist.save(update_fields=['updated_at'])
    event(user, checklist.ticket.project, checklist.ticket, 'checklist_item_updated', 'Checklistenpunkt geändert', item_id=item.pk, done=item.done)
    return item_data(item)


def delete_checklist_item(user, project_id, ticket_id, checklist_id, item_id, expected_updated_at=None):
    checklist = checklist_for(user, project_id, ticket_id, checklist_id)
    item = checklist.items.filter(pk=item_id).first()
    if not item: raise WorkError('Checklistenpunkt nicht gefunden.', 404)
    conflict(item, expected_updated_at)
    item.delete()
    checklist.save(update_fields=['updated_at'])
    event(user, checklist.ticket.project, checklist.ticket, 'checklist_item_deleted', 'Checklistenpunkt entfernt', item_id=item_id)
    return {'deleted': True}


def field_data(field):
    return {'id': field.pk, 'key': field.key, 'name': field.name, 'kind': field.kind, 'scope': field.scope,
            'options': field.options, 'required': field.required, 'position': field.position, 'archived': field.archived,
            'project_value': field.project_value, 'updated_at': field.updated_at.isoformat()}


def validate_options(kind, options):
    if kind in ('select', 'multiselect'):
        if not options or any(not o.strip() for o in options) or len(set(options)) != len(options):
            raise WorkError('Auswahlfelder benötigen unterschiedliche, nicht leere Optionen.')
    elif options:
        raise WorkError('Optionen sind nur für Auswahlfelder zulässig.')


def validate_value(field, value):
    if value is None or value == '' or value == []:
        if field.required: raise WorkError(f'Das Feld „{field.name}“ ist erforderlich.')
        return None
    valid = False
    if field.kind in ('text', 'textarea'):
        valid = isinstance(value, str) and len(value) <= (10000 if field.kind == 'textarea' else 1000)
    elif field.kind == 'number': valid = type(value) in (int, float) and math.isfinite(value)
    elif field.kind == 'boolean': valid = type(value) is bool
    elif field.kind == 'date':
        try: valid = isinstance(value, str) and date.fromisoformat(value).isoformat() == value
        except (ValueError, TypeError): pass
    elif field.kind == 'url':
        try:
            url = urlsplit(value) if isinstance(value, str) else None
            valid = bool(url and url.scheme in ('https', 'http') and url.hostname and not url.username and not url.password and len(value) <= 2000)
        except ValueError: pass
    elif field.kind == 'select': valid = isinstance(value, str) and value in field.options
    elif field.kind == 'multiselect': valid = isinstance(value, list) and all(isinstance(v, str) and v in field.options for v in value) and len(value) == len(set(value))
    if not valid: raise WorkError(f'Ungültiger Wert für „{field.name}“ ({field.kind}).')
    return value


def set_ticket_values(ticket, values, creating=False):
    fields = {f.key: f for f in ticket.project.custom_fields.filter(scope='ticket', archived=False)}
    if set(values) - set(fields): raise WorkError('Unbekanntes oder archiviertes Ticketfeld.')
    current = dict(ticket.field_values.values_list('field__key', 'value')) if ticket.pk else {}
    combined = {**current, **values}
    for key, field in fields.items():
        if key in values or (creating and field.required): validate_value(field, combined.get(key))
    for key, value in values.items():
        TicketFieldValue.objects.update_or_create(ticket=ticket, field=fields[key], defaults={'value': validate_value(fields[key], value)})


def list_custom_fields(user, project_id):
    from .services import project_for
    return {'fields': [field_data(f) for f in project_for(user, project_id).custom_fields.all()]}


def create_custom_field(user, project_id, key, name, kind, scope='ticket', options=None, required=False, position=0, project_value=None):
    from .services import project_for, owner_only, nonblank
    project = project_for(user, project_id); owner_only(user, project)
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,59}', key): raise WorkError('Feldschlüssel: Kleinbuchstaben, Ziffern und Unterstrich; beginnend mit einem Buchstaben.')
    validate_options(kind, options or [])
    field = CustomField(project=project, key=key, name=nonblank(name), kind=kind, scope=scope, options=options or [], required=required, position=position)
    if scope == 'project': field.project_value = validate_value(field, project_value)
    elif project_value is not None: raise WorkError('Projektwert ist nur bei Projektfeldern zulässig.')
    field.save()
    event(user, project, None, 'field_created', 'Eigenes Feld hinzugefügt', key=key)
    return field_data(field)


def update_custom_field(user, project_id, field_id, expected_updated_at=None, **changes):
    from .services import project_for, owner_only, nonblank
    project = project_for(user, project_id); owner_only(user, project)
    field = project.custom_fields.filter(pk=field_id).first()
    if not field: raise WorkError('Feld nicht gefunden.', 404)
    conflict(field, expected_updated_at)
    for key, value in changes.items(): setattr(field, key, nonblank(value) if key == 'name' else value)
    validate_options(field.kind, field.options)
    if field.scope == 'project': field.project_value = validate_value(field, field.project_value)
    elif 'project_value' in changes: raise WorkError('Projektwert ist nur bei Projektfeldern zulässig.')
    for value in field.ticket_values.values_list('value', flat=True):
        if value is not None: validate_value(field, value)
    field.save()
    event(user, project, None, 'field_updated', 'Eigenes Feld geändert', key=field.key)
    return field_data(field)


def list_activity(user, project_id, ticket_id=None, offset=0, limit=50):
    from .services import project_for
    project = project_for(user, project_id)
    events = project.activities.select_related('actor')
    if ticket_id is not None:
        ticket_for(user, project_id, ticket_id)
        events = events.filter(ticket_id=ticket_id)
    return {'events': [{'id': e.pk, 'kind': e.kind, 'summary': e.summary, 'data': e.data, 'ticket_id': e.ticket_id,
                      'actor': person(e.actor) if e.actor_id else {'id': None, 'name': e.original_actor or 'System', 'email': ''},
                      'created_at': e.created_at.isoformat()} for e in events[offset:offset+limit]], 'total': events.count()}


def register_operations(register, ID, NAME, TEXT):
    paging = {'offset': {'type': 'integer', 'minimum': 0}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200}}
    expected = {'expected_updated_at': TEXT(40)}
    register(list_comments, 'Kommentare eines Tickets paginiert lesen.', {'ticket_id': ID, **paging}, ['ticket_id'])
    register(create_comment, 'Eigenen Markdown-Kommentar hinzufügen.', {'ticket_id': ID, 'body': NAME(20000)}, ['ticket_id', 'body'], write=True)
    register(update_comment, 'Eigenen Kommentar bearbeiten; optional mit Konfliktschutz.', {'ticket_id': ID, 'comment_id': ID, 'body': NAME(20000), **expected}, ['ticket_id', 'comment_id', 'body'], write=True)
    register(delete_comment, 'Eigenen Kommentar entfernen. Dateianhänge bleiben gesondert erhalten.', {'ticket_id': ID, 'comment_id': ID, **expected}, ['ticket_id', 'comment_id'], write=True)
    register(list_checklists, 'Checklisten und Punkte eines Tickets lesen.', {'ticket_id': ID}, ['ticket_id'])
    register(create_checklist, 'Benannte Checkliste zu einem Ticket hinzufügen.', {'ticket_id': ID, 'name': NAME(120)}, ['ticket_id'], write=True)
    for fn in (update_checklist, delete_checklist):
        props = {'ticket_id': ID, 'checklist_id': ID, **expected}
        if fn == update_checklist: props.update({'name': NAME(120), 'position': {'type': 'integer', 'minimum': 0, 'maximum': 1000000}})
        register(fn, 'Checkliste bearbeiten bzw. mit ihren Punkten entfernen.', props, ['ticket_id', 'checklist_id'], write=True)
    fields = {'title': NAME(500), 'done': {'type': 'boolean'}, 'assignee_id': {'anyOf': [ID, {'type': 'null'}]}, 'position': {'type': 'integer', 'minimum': 0, 'maximum': 1000000}}
    register(create_checklist_item, 'Checklistenpunkt mit optionaler Zuweisung hinzufügen.', {'ticket_id': ID, 'checklist_id': ID, **fields}, ['ticket_id', 'checklist_id', 'title'], write=True)
    register(update_checklist_item, 'Checklistenpunkt abhaken, bearbeiten, zuweisen oder umsortieren.', {'ticket_id': ID, 'checklist_id': ID, 'item_id': ID, **fields, **expected}, ['ticket_id', 'checklist_id', 'item_id'], write=True)
    register(delete_checklist_item, 'Checklistenpunkt entfernen.', {'ticket_id': ID, 'checklist_id': ID, 'item_id': ID, **expected}, ['ticket_id', 'checklist_id', 'item_id'], write=True)
    options = {'type': 'array', 'items': NAME(120), 'maxItems': 100, 'uniqueItems': True}
    kinds = {'type': 'string', 'enum': ['text', 'textarea', 'number', 'date', 'boolean', 'select', 'multiselect', 'url']}
    register(list_custom_fields, 'Live-Felddefinitionen und Projektwerte einschließlich archivierter Felder lesen.')
    register(create_custom_field, 'Eigenes Projekt- oder Ticketfeld anlegen (nur Leitung). Schlüssel und Typ bleiben stabil.', {'key': NAME(60), 'name': NAME(120), 'kind': kinds, 'scope': {'enum': ['ticket', 'project']}, 'options': options, 'required': {'type': 'boolean'}, 'position': {'type': 'integer', 'minimum': 0, 'maximum': 1000000}, 'project_value': {}}, ['key', 'name', 'kind'], write=True)
    register(update_custom_field, 'Feld umbenennen, Optionen ergänzen, Werte ändern oder archivieren. Vorhandene Werte bleiben geprüft erhalten (nur Leitung).', {'field_id': ID, 'name': NAME(120), 'options': options, 'required': {'type': 'boolean'}, 'archived': {'type': 'boolean'}, 'position': {'type': 'integer', 'minimum': 0, 'maximum': 1000000}, 'project_value': {}, **expected}, ['field_id'], write=True)
    register(list_activity, 'Vollständige Projekthistorie paginiert lesen, optional für ein Ticket.', {'ticket_id': ID, **paging})
