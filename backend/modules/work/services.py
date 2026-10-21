"""Gemeinsame Fachlogik für Browser-API und MCP. Keine Berechtigungslogik im Client."""
from datetime import date
import re

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from jsonschema import Draft202012Validator

from .models import Project, Status, Tag, Ticket


class WorkError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


CATEGORIES = [{'id': key, 'name': label} for key, label in Status.Category.choices]
CATEGORY_ORDER = {item['id']: index for index, item in enumerate(CATEGORIES)}


def person(user):
    return {'id': user.pk, 'name': user.get_full_name() or user.email, 'email': user.email}


def project_for(user, project_id):
    project = Project.objects.filter(Q(owner=user) | Q(members=user), pk=project_id).distinct().first()
    if not project:
        raise WorkError('Projekt nicht gefunden.', 404)
    return project


def owner_only(user, project):
    if project.owner_id != user.pk:
        raise WorkError('Nur die Projektleitung kann Mitglieder oder Projekteinstellungen ändern.', 403)


def project_data(project, user):
    ticket_count = getattr(project, 'ticket_count', None)
    return {
        'id': project.pk, 'name': project.name, 'key': project.key,
        'description': project.description, 'owner_id': project.owner_id,
        'can_manage': project.owner_id == user.pk,
        'ticket_count': ticket_count if ticket_count is not None else project.tickets.count(),
    }


def status_data(status):
    return {'id': status.pk, 'name': status.name, 'category': status.category,
            'position': status.position, 'is_base': status.is_base}


def statuses_for(project):
    return sorted(project.statuses.all(), key=lambda s: (CATEGORY_ORDER[s.category], s.position, s.pk))


def ticket_query(project):
    return project.tickets.select_related('project').prefetch_related('tags', 'assignees')


def ticket_data(ticket):
    return {
        'id': ticket.pk, 'key': f'{ticket.project.key}-{ticket.number}',
        'project_id': ticket.project_id, 'title': ticket.title,
        'description': ticket.description, 'kind': ticket.kind, 'parent_id': ticket.parent_id,
        'status_id': ticket.status_id, 'assignee_ids': [u.pk for u in ticket.assignees.all()],
        'tag_ids': [t.pk for t in ticket.tags.all()], 'priority': ticket.priority,
        'due_date': ticket.due_date.isoformat() if ticket.due_date else None,
        'created_at': ticket.created_at.isoformat(), 'updated_at': ticket.updated_at.isoformat(),
    }


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


def list_projects(user):
    projects = Project.objects.filter(Q(owner=user) | Q(members=user)).distinct().annotate(ticket_count=Count('tickets', distinct=True))
    return {'projects': [project_data(p, user) for p in projects]}


def create_project(user, name, key, description=''):
    key = key.strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9]{1,11}', key):
        raise WorkError('Projektkürzel: 2–12 Zeichen, beginnend mit einem Buchstaben, danach Buchstaben oder Ziffern.')
    project = Project.objects.create(name=nonblank(name), key=key, description=description, owner=user)
    project.members.add(user)
    Status.objects.bulk_create([Status(project=project, name=item['name'], category=item['id'], is_base=True) for item in CATEGORIES])
    return project_data(project, user)


def get_project(user, project_id):
    project = project_for(user, project_id)
    return {
        'project': project_data(project, user), 'categories': CATEGORIES,
        'statuses': [status_data(s) for s in statuses_for(project)],
        'members': [person(u) for u in project.members.filter(is_active=True).order_by('email')],
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
    ticket = related(project_for(user, project_id), 'tickets', ticket_id, 'Ticket')
    return ticket_data(ticket)


def set_ticket_fields(project, ticket, fields):
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
        members = list(project.members.filter(pk__in=fields['assignee_ids'], is_active=True))
        if len(members) != len(fields['assignee_ids']):
            raise WorkError('Zuweisungen sind nur an aktive Projektmitglieder möglich.')
    if 'tag_ids' in fields:
        tags = list(project.tags.filter(pk__in=fields['tag_ids']))
        if len(tags) != len(fields['tag_ids']):
            raise WorkError('Alle Tags müssen zum Projekt gehören.')
    ticket.save()
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
    return result


def update_ticket(user, project_id, ticket_id, **fields):
    project = project_for(user, project_id)
    ticket = related(project, 'tickets', ticket_id, 'Ticket')
    expected = fields.pop('expected_updated_at', None)
    if expected is not None and expected != ticket.updated_at.isoformat():
        raise WorkError('Dieses Ticket wurde inzwischen geändert. Bitte schließen und erneut öffnen.', 409)
    return set_ticket_fields(project, ticket, fields)


def delete_ticket(user, project_id, ticket_id):
    ticket = related(project_for(user, project_id), 'tickets', ticket_id, 'Ticket')
    if ticket.children.exists():
        raise WorkError('Zuerst untergeordnete Tickets umhängen oder löschen.')
    ticket.delete()
    return {'deleted': True}


# Dieselben Eingabeschemata gelten in der HTTP-API und in der MCP-Toolliste.
ID = {'type': 'integer', 'minimum': 1}
TEXT = lambda maximum: {'type': 'string', 'maxLength': maximum}
NAME = lambda maximum: {'type': 'string', 'minLength': 1, 'maxLength': maximum}
IDS = {'type': 'array', 'items': ID, 'uniqueItems': True, 'maxItems': 100}
NULL_ID = {'anyOf': [ID, {'type': 'null'}]}
CATEGORY = {'type': 'string', 'enum': list(Status.Category.values)}
POSITION = {'type': 'integer', 'minimum': 1, 'maximum': 100000}
TICKET_FIELDS = {
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


register(list_projects, 'Eigene Projekte mit Kürzel und Ticketanzahl auflisten.', project=False)
register(create_project, 'Projekt mit vier Grundstatus erstellen. Ersteller wird Projektleitung.', {'name': NAME(120), 'key': NAME(12), 'description': TEXT(10000)}, ['name', 'key'], write=True, project=False)
register(get_project, 'Aktueller Projektstand: Mitglieder, dynamische Status in Board-Reihenfolge, Tags und Tickets. Vor Statusauswahl abrufen.')
register(update_project, 'Projektname oder Beschreibung ändern (nur Projektleitung).', {'name': NAME(120), 'description': TEXT(10000)}, write=True)
register(add_project_member, 'Bestehendes aktives Konto per E-Mail zum Projekt hinzufügen (nur Projektleitung).', {'email': NAME(254)}, ['email'], write=True)
register(remove_project_member, 'Mitglied entfernen und dessen Ticketzuweisungen in diesem Projekt lösen (nur Projektleitung).', {'user_id': ID}, ['user_id'], write=True)
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


def execute(user, action, arguments):
    if not user or not user.is_authenticated or not user.is_active:
        raise WorkError('Aktive Anmeldung erforderlich.', 401)
    operation = OPERATIONS.get(action) if isinstance(action, str) else None
    if not operation:
        raise WorkError('Unbekannte Aktion.')
    errors = list(Draft202012Validator(operation['inputSchema']).iter_errors(arguments))
    if errors:
        error = errors[0]
        location = '.'.join(map(str, error.path)) or 'Parameter'
        raise WorkError(f'Ungültige Eingabe ({location}): {error.message}')
    try:
        with transaction.atomic():
            # Serialisiert Änderungen pro Projekt: Nummern, Hierarchie und Mitgliedschaft bleiben konsistent.
            if operation['write'] and 'project_id' in arguments:
                Project.objects.select_for_update().filter(pk=arguments['project_id']).first()
            return operation['handler'](user, **arguments)
    except IntegrityError:
        raise WorkError('Dieses Kürzel oder dieser Name ist bereits vergeben oder die Änderung verletzt eine Verknüpfung.')
