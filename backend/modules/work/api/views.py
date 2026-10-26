import json
from functools import wraps

from django.conf import settings
from django.http import JsonResponse, FileResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ..errors import WorkError
from ..services import OPERATIONS
from ..token_auth import action_allowed, authenticate_token, execute_with_token, scope_arguments


def api_auth(view):
    @csrf_exempt
    @never_cache
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            origin = request.headers.get('Origin')
            if origin and origin.rstrip('/') not in settings.INTEGRATION_ALLOWED_ORIGINS:
                raise WorkError('Origin nicht zugelassen.', 403)
            header = request.headers.get('Authorization', '')
            if not header.startswith('Bearer '): raise WorkError('Bearer-Schlüssel erforderlich.', 401)
            request.integration_token = authenticate_token(header[7:])
            return view(request, *args, **kwargs)
        except WorkError as error:
            response = JsonResponse({'error': str(error)}, status=error.status)
            if error.status == 401:
                response['WWW-Authenticate'] = 'Bearer realm="tasklane"'
            return response
    return wrapped


@api_auth
@require_POST
def action(request, action):
    if request.content_type != 'application/json': raise WorkError('JSON-Anfrage erforderlich.', 415)
    if len(request.body) > settings.DATA_UPLOAD_MAX_MEMORY_SIZE: raise WorkError('Anfrage zu groß.', 413)
    try: args = json.loads(request.body)
    except (ValueError, UnicodeDecodeError): raise WorkError('Ungültiges JSON.')
    if action not in OPERATIONS: raise WorkError('Aktion nicht gefunden.', 404)
    return JsonResponse({'result': execute_with_token(request.integration_token, action, args)})


@api_auth
@require_GET
def capabilities(request):
    token = request.integration_token
    return JsonResponse({'api_version': '1', 'actions': [{'name': name, 'description': op['description'], 'write': op['write'], 'input_schema': op['inputSchema']} for name, op in OPERATIONS.items() if action_allowed(token, name)]})


@api_auth
@require_GET
def projects(request):
    args = {}
    if request.GET.get('workspace_id'):
        try: args['workspace_id'] = int(request.GET['workspace_id'])
        except ValueError: raise WorkError('Ungültiger Workspace.')
    return JsonResponse(execute_with_token(request.integration_token, 'list_projects', args))


@api_auth
@require_GET
def workspaces(request):
    return JsonResponse(execute_with_token(request.integration_token, 'list_workspaces', {}))


@api_auth
@require_GET
def project(request, project_id):
    return JsonResponse(execute_with_token(request.integration_token, 'get_project', {'project_id': project_id}))


@api_auth
@require_GET
def ticket(request, project_id, ticket_id):
    return JsonResponse(execute_with_token(request.integration_token, 'get_ticket', {'project_id': project_id, 'ticket_id': ticket_id}))


@api_auth
@require_GET
def attachment_download(request, project_id, attachment_id):
    from ..attachments import attachment_for, attachment_path
    token = request.integration_token
    scope_arguments(token, 'read_attachment_chunk', {'project_id': project_id, 'attachment_id': str(attachment_id)})
    attachment = attachment_for(token.user, project_id, attachment_id)
    try: stream = attachment_path(attachment).open('rb')
    except FileNotFoundError: raise WorkError('Gespeicherte Datei nicht verfügbar.', 503)
    response = FileResponse(stream, as_attachment=True, filename=attachment.filename, content_type=attachment.content_type)
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@require_GET
def openapi(request):
    from core.version import VERSION
    security = [{'bearerAuth': []}]
    paths = {}
    for name, op in OPERATIONS.items():
        paths['/api/v1/actions/' + name] = {'post': {
            'operationId': name, 'summary': op['description'], 'security': security,
            'requestBody': {'required': True, 'content': {'application/json': {'schema': op['inputSchema']}}},
            'responses': {'200': {'description': 'Fachliches Ergebnis unter result'}, '400': {'description': 'Ungültige Eingabe'},
                          '401': {'description': 'Anmeldung erforderlich'}, '403': {'description': 'Aktion nicht erlaubt'},
                          '404': {'description': 'Ressource nicht zugänglich'}, '409': {'description': 'Konflikt'}}}}
    for path, operation in [('/api/v1/projects', 'list_projects'), ('/api/v1/workspaces', 'list_workspaces'), ('/api/v1/actions', 'capabilities')]:
        paths[path] = {'get': {'summary': operation, 'security': security, 'responses': {'200': {'description': 'Berechtigungsgeprüfte Daten'}}}}
    paths['/api/v1/projects']['get']['parameters'] = [
        {'name': 'workspace_id', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1}}]
    for path, operation, parameters in [
        ('/api/v1/projects/{project_id}', 'get_project', [('project_id', 'integer')]),
        ('/api/v1/projects/{project_id}/tickets/{ticket_id}', 'get_ticket', [('project_id', 'integer'), ('ticket_id', 'integer')]),
        ('/api/v1/projects/{project_id}/attachments/{attachment_id}/content', 'download_attachment', [('project_id', 'integer'), ('attachment_id', 'string')]),
    ]:
        paths[path] = {'get': {
            'operationId': operation + '_http', 'summary': operation, 'security': security,
            'parameters': [{'name': name, 'in': 'path', 'required': True, 'schema': {'type': kind}} for name, kind in parameters],
            'responses': {'200': {'description': 'Private Datei' if operation == 'download_attachment' else 'Berechtigungsgeprüfte Daten'},
                          '401': {'description': 'Anmeldung erforderlich'}, '404': {'description': 'Ressource nicht zugänglich'}},
        }}
    return JsonResponse({'openapi': '3.1.0', 'info': {'title': 'Tasklane API', 'version': VERSION},
                'servers': [{'url': settings.PUBLIC_URL}], 'paths': paths,
                'components': {'securitySchemes': {'bearerAuth': {'type': 'http', 'scheme': 'bearer'}}}})
