"""Gemeinsame Projektgrenzen für API, MCP, Berichte und Importe."""
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Project


def person(user):
    return {'id': user.pk, 'name': user.get_full_name() or user.email, 'email': user.email}


def accessible_projects(user):
    return Project.objects.filter(Q(owner=user) | Q(members=user) | Q(workspace__owner=user) | Q(workspace__members=user)).select_related('workspace').distinct()


def project_members(project):
    return get_user_model().objects.filter(Q(work_projects=project) | Q(pk=project.owner_id) | Q(workspaces=project.workspace) | Q(pk=project.workspace.owner_id), is_active=True).distinct().order_by('email')
