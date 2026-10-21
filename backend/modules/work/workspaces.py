"""Workspace-Freigaben gelten für bestehende und zukünftige Projekte."""
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Workspace, Ticket
from .errors import WorkError
from .access import accessible_projects, person


def accessible_workspaces(user):
    return Workspace.objects.filter(Q(owner=user) | Q(members=user) | Q(projects__in=accessible_projects(user))).distinct()


def workspace_for(user, workspace_id, *, manage=False, member=False):
    if not get_user_model().objects.filter(pk=user.pk, is_active=True).exists():
        raise WorkError('Aktive Anmeldung erforderlich.', 401)
    workspace = accessible_workspaces(user).filter(pk=workspace_id).first()
    if not workspace:
        raise WorkError('Workspace nicht gefunden.', 404)
    if manage and workspace.owner_id != user.pk:
        raise WorkError('Nur die Workspace-Leitung kann Freigaben und Jira verwalten.', 403)
    if member and workspace.owner_id != user.pk and not workspace.members.filter(pk=user.pk).exists():
        raise WorkError('Dafür ist eine Workspace-Mitgliedschaft erforderlich.', 403)
    return workspace


def workspace_data(workspace, user):
    return {'id': workspace.pk, 'name': workspace.name, 'owner_id': workspace.owner_id,
            'can_manage': workspace.owner_id == user.pk,
            'can_create_project': workspace.owner_id == user.pk or workspace.members.filter(pk=user.pk).exists(),
            'project_count': accessible_projects(user).filter(workspace=workspace).count()}


def list_workspaces(user):
    return {'workspaces': [workspace_data(w, user) for w in accessible_workspaces(user)]}


def create_workspace(user, name):
    from .services import nonblank
    workspace = Workspace.objects.create(name=nonblank(name), owner=user)
    return workspace_data(workspace, user)


def get_workspace(user, workspace_id):
    workspace = workspace_for(user, workspace_id)
    # Project-only guests see the workspace name, not the workspace team or integrations.
    is_member = workspace.owner_id == user.pk or workspace.members.filter(pk=user.pk).exists()
    people = get_user_model().objects.filter(Q(pk=workspace.owner_id) | Q(workspaces=workspace), is_active=True).distinct().order_by('email') if is_member else []
    return {'workspace': workspace_data(workspace, user), 'members': [person(u) for u in people]}


def update_workspace(user, workspace_id, name):
    from .services import nonblank
    workspace = workspace_for(user, workspace_id, manage=True)
    workspace.name = nonblank(name)
    workspace.save(update_fields=['name'])
    return workspace_data(workspace, user)


def add_workspace_member(user, workspace_id, email):
    workspace = workspace_for(user, workspace_id, manage=True)
    member = get_user_model().objects.filter(email__iexact=email.strip(), is_active=True).first()
    if not member:
        raise WorkError('Kein aktives Konto mit dieser E-Mail gefunden. Bitte das Konto zuerst unter Benutzer anlegen oder anmelden lassen.')
    workspace.members.add(member)
    return person(member)


def remove_workspace_member(user, workspace_id, user_id):
    workspace = workspace_for(user, workspace_id, manage=True)
    if workspace.owner_id == user_id:
        raise WorkError('Die Workspace-Leitung kann nicht entfernt werden.')
    if not workspace.members.filter(pk=user_id).exists():
        raise WorkError('Workspace-Mitglied nicht gefunden.', 404)
    workspace.members.remove(user_id)
    # Direct project sharing and project ownership still grant access deliberately.
    retained = accessible_projects(get_user_model().objects.get(pk=user_id)).values('id')
    Ticket.assignees.through.objects.filter(ticket__project__workspace=workspace, user_id=user_id).exclude(ticket__project__in=retained).delete()
    return {'removed': True}


def register_operations(register, ID, NAME, TEXT):
    register(list_workspaces, 'Zugängliche Workspaces auflisten. Projektgäste sehen nur ihre zugänglichen Projekte.', project=False)
    register(create_workspace, 'Workspace für gemeinsame Projekte erstellen.', {'name': NAME(120)}, ['name'], write=True, project=False)
    for fn, description, props, required, write in [
        (get_workspace, 'Workspace und Team lesen.', {}, [], False),
        (update_workspace, 'Workspace umbenennen (nur Leitung).', {'name': NAME(120)}, ['name'], True),
        (add_workspace_member, 'Aktives Konto per E-Mail für alle bestehenden und zukünftigen Projekte freigeben (nur Leitung).', {'email': NAME(254)}, ['email'], True),
        (remove_workspace_member, 'Workspace-Freigabe entziehen. Separate Projektfreigaben bleiben erhalten (nur Leitung).', {'user_id': ID}, ['user_id'], True),
    ]:
        register(fn, description, {'workspace_id': ID, **props}, ['workspace_id', *required], write=write, project=False)
