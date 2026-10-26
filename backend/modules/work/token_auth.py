"""Widerrufbare persönliche Integrationsschlüssel; Identität kommt nie aus API-Argumenten."""
from datetime import timedelta
import hashlib
import secrets
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from integrations.models import IntegrationCredential
from .errors import WorkError
from .models import ApiToken, Project
from .workspaces import workspace_for

MANAGEMENT = {'create_workspace', 'update_workspace', 'add_workspace_member', 'remove_workspace_member',
              'add_project_member', 'remove_project_member', 'configure_jira', 'configure_clickup'}


def token_data(token):
    return {'id': token.pk, 'name': token.name, 'scope': token.scope, 'workspace_id': token.workspace_id,
            'expires_at': token.expires_at.isoformat(), 'revoked': bool(token.revoked_at),
            'last_used_at': token.last_used_at.isoformat() if token.last_used_at else None,
            'created_at': token.created_at.isoformat()}


def list_tokens(user):
    return {'tokens': [token_data(t) for t in ApiToken.objects.filter(user=user).order_by('-created_at')]}


@sensitive_variables('raw')
@transaction.atomic
def create_token(user, name, scope='read', workspace_id=None, expires_in_days=90):
    if not isinstance(name, str) or not name.strip() or len(name) > 120 or scope not in ('read', 'write', 'manage'):
        raise WorkError('Bitte Namen und gültige Zugriffsart angeben.')
    if type(expires_in_days) is not int or not 1 <= expires_in_days <= 365:
        raise WorkError('Gültigkeit: 1 bis 365 Tage.')
    if workspace_id is not None:
        if type(workspace_id) is not int or workspace_id < 1: raise WorkError('Ungültiger Workspace.')
        workspace_for(user, workspace_id, member=True)
    raw = 'tl_' + secrets.token_urlsafe(40)
    credential = IntegrationCredential(key='tasklane-api-' + uuid4().hex, name='Tasklane API: ' + name.strip(), kind=IntegrationCredential.Kind.MCP, enabled=True)
    credential.set_secret(raw); credential.save()
    token = ApiToken.objects.create(user=user, name=name.strip(), scope=scope, workspace_id=workspace_id,
                credential=credential, digest=hashlib.sha256(raw.encode()).hexdigest(), audience=settings.PUBLIC_URL,
                expires_at=timezone.now()+timedelta(days=expires_in_days))
    return {**token_data(token), 'token': raw}


@transaction.atomic
def revoke_token(user, token_id):
    token = ApiToken.objects.select_for_update().select_related('credential').filter(user=user, pk=token_id).first()
    if not token: raise WorkError('Schlüssel nicht gefunden.', 404)
    token.revoked_at = timezone.now(); token.save(update_fields=['revoked_at'])
    token.credential.enabled = False
    token.credential.set_secret('')
    token.credential.save(update_fields=['enabled', 'encrypted_secret', 'updated_at'])
    return {'revoked': True}


@sensitive_variables('raw')
def authenticate_token(raw):
    if not isinstance(raw, str) or len(raw) > 256 or not raw.startswith('tl_'):
        raise WorkError('Gültiger Bearer-Schlüssel erforderlich.', 401)
    token = ApiToken.objects.select_related('user', 'credential', 'workspace').filter(digest=hashlib.sha256(raw.encode()).hexdigest(),
                    revoked_at__isnull=True, expires_at__gt=timezone.now(), user__is_active=True, credential__enabled=True,
                    audience=settings.PUBLIC_URL).first()
    if not token: raise WorkError('Schlüssel ungültig, abgelaufen oder widerrufen.', 401)
    if token.workspace_id: workspace_for(token.user, token.workspace_id, member=True)
    if token.last_used_at is None or token.last_used_at < timezone.now()-timedelta(minutes=1):
        ApiToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
    return token


def action_allowed(token, action):
    from .services import OPERATIONS
    operation = OPERATIONS.get(action)
    if not operation: return False
    if token.scope == 'read' and operation['write']: return False
    if action in MANAGEMENT and token.scope != 'manage': return False
    if token.workspace_id and action == 'create_workspace': return False
    return True


def scope_arguments(token, action, arguments):
    if not action_allowed(token, action): raise WorkError('Dieser Schlüssel erlaubt diese Aktion nicht.', 403)
    if not isinstance(arguments, dict): raise WorkError('Parameter müssen ein JSON-Objekt sein.')
    args = dict(arguments)
    if token.workspace_id:
        if 'workspace_id' in args and args['workspace_id'] != token.workspace_id:
            raise WorkError('Der Schlüssel ist auf einen anderen Workspace begrenzt.', 403)
        if 'project_id' in args:
            if type(args['project_id']) is not int or args['project_id'] < 1: raise WorkError('Ungültige Projekt-ID.')
            if not Project.objects.filter(pk=args['project_id'], workspace_id=token.workspace_id).exists():
                raise WorkError('Projekt für diesen Schlüssel nicht verfügbar.', 404)
        if action in ('list_projects', 'create_project', 'get_time_report', 'list_time_entries', 'export_time_report'):
            args['workspace_id'] = token.workspace_id
    return args


def execute_with_token(token, action, arguments):
    from .services import execute
    args = scope_arguments(token, action, arguments)
    result = execute(token.user, action, args)
    if token.workspace_id and action == 'list_workspaces':
        result['workspaces'] = [w for w in result['workspaces'] if w['id'] == token.workspace_id]
    return result
