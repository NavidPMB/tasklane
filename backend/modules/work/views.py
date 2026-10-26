import json
from functools import wraps

from django.conf import settings

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core.permissions import require_user
from .services import WorkError, execute


def errors(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except WorkError as error:
            return JsonResponse({'error': str(error)}, status=error.status)
    return wrapped


@never_cache
@require_GET
@require_user()
@errors
def projects(request):
    return JsonResponse(execute(request.user, 'list_projects', time_arguments(request, 'list_projects')))


@never_cache
@require_GET
@require_user()
@errors
def project(request, project_id):
    return JsonResponse(execute(request.user, 'get_project', {'project_id': project_id}))


@never_cache
@require_POST
@require_user()
@errors
def actions(request):
    if request.content_type != 'application/json':
        raise WorkError('JSON-Anfrage erforderlich.', 415)
    if len(request.body) > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
        raise WorkError('Anfrage zu groß.', 413)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise WorkError('Ungültiges JSON.')
    if not isinstance(data, dict) or set(data) - {'action', 'arguments'}:
        raise WorkError('Erwartet werden action und arguments.')
    return JsonResponse({'result': execute(request.user, data.get('action'), data.get('arguments', {}))})


def time_arguments(request, action):
    from .services import OPERATIONS
    allowed = OPERATIONS[action]['inputSchema']['properties']
    args = {}
    for key, value in request.GET.items():
        if key not in allowed:
            raise WorkError('Unbekannter Filter.')
        if allowed[key].get('type') == 'integer':
            try:
                value = int(value)
            except ValueError:
                raise WorkError('Projekt, Person, Ticket und Seitengröße müssen gültige Zahlen sein.')
        args[key] = value
    return args


@never_cache
@require_GET
@require_user()
@errors
def time_entries(request):
    return JsonResponse(execute(request.user, 'list_time_entries', time_arguments(request, 'list_time_entries')))


@never_cache
@require_GET
@require_user()
@errors
def time_report(request):
    return JsonResponse(execute(request.user, 'get_time_report', time_arguments(request, 'get_time_report')))


@never_cache
@require_GET
@require_user()
@errors
def time_export(request):
    result = execute(request.user, 'export_time_report', time_arguments(request, 'export_time_report'))
    response = HttpResponse(result['csv'], content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{result["filename"]}"'
    return response


@never_cache
@require_GET
@require_user()
@errors
def workspaces(request):
    return JsonResponse(execute(request.user, 'list_workspaces', {}))


@never_cache
@require_GET
@require_user()
@errors
def attachment_download(request, project_id, attachment_id):
    from django.http import FileResponse
    from .attachments import attachment_for, attachment_path
    a = attachment_for(request.user, project_id, attachment_id)
    try:
        stream = attachment_path(a).open('rb')
    except FileNotFoundError:
        raise WorkError('Die gespeicherte Datei ist nicht verfügbar.', 503)
    response = FileResponse(stream, as_attachment=True, filename=a.filename, content_type=a.content_type)
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
@require_POST
@require_user()
@errors
def attachment_upload(request, project_id, ticket_id):
    from django.conf import settings
    from django.db import transaction
    from .attachments import start_attachment_upload, write_chunk, complete_attachment_upload, cancel_attachment_upload, CHUNK_SIZE
    from .services import project_for
    # Check access before parsing multipart data.
    project_for(request.user, project_id)
    if request.content_type != 'multipart/form-data': raise WorkError('Multipart-Datei erforderlich.', 415)
    upload = request.FILES.get('file')
    if not upload or len(request.FILES) != 1: raise WorkError('Bitte genau eine Datei hochladen.')
    if upload.size > settings.ATTACHMENT_MAX_BYTES: raise WorkError('Datei zu groß.', 413)
    comment = request.POST.get('comment_id')
    if comment:
        try: comment = int(comment)
        except ValueError: raise WorkError('Ungültiger Kommentar.')
    from .models import Workspace, Project
    with transaction.atomic():
        workspace_id = Project.objects.get(pk=project_id).workspace_id
        Workspace.objects.select_for_update().get(pk=workspace_id)
        Project.objects.select_for_update().get(pk=project_id)
        info = start_attachment_upload(request.user, project_id, ticket_id, upload.name, upload.size, upload.content_type, comment_id=comment or None)
    try:
        offset = 0
        for chunk in upload.chunks(CHUNK_SIZE):
            for start in range(0, len(chunk), CHUNK_SIZE):
                part = chunk[start:start+CHUNK_SIZE]
                execute(request.user, 'put_attachment_chunk', {'project_id': project_id, 'attachment_id': info['id'], 'offset': offset, 'data_base64': __import__('base64').b64encode(part).decode()})
                offset += len(part)
        result = execute(request.user, 'complete_attachment_upload', {'project_id': project_id, 'attachment_id': info['id']})
    except Exception:
        # Keep the original error; expired/revoked access may prevent explicit cancellation.
        from .models import Attachment
        from .attachments import delete_file_after_commit
        with transaction.atomic():
            a = Attachment.objects.select_for_update().filter(pk=info['id'], state='uploading').first()
            if a:
                a.state = 'deleted'; a.save(update_fields=['state']); delete_file_after_commit(a)
        raise
    return JsonResponse({'result': result}, status=201)


@never_cache
@require_user()
@errors
def access_tokens(request):
    from .token_auth import list_tokens, create_token, revoke_token
    if request.method == 'GET': return JsonResponse(list_tokens(request.user))
    if request.method != 'POST': return JsonResponse({'error': 'Methode nicht erlaubt.'}, status=405)
    if request.content_type != 'application/json': raise WorkError('JSON-Anfrage erforderlich.', 415)
    if len(request.body) > 8192: raise WorkError('Anfrage zu groß.', 413)
    try: args = json.loads(request.body)
    except (ValueError, UnicodeDecodeError): raise WorkError('Ungültiges JSON.')
    if not isinstance(args, dict): raise WorkError('JSON-Objekt erforderlich.')
    if set(args) == {'revoke_id'}:
        if type(args['revoke_id']) is not int: raise WorkError('Ungültige Schlüssel-ID.')
        return JsonResponse(revoke_token(request.user, args['revoke_id']))
    if set(args) - {'name', 'scope', 'workspace_id', 'expires_in_days'} or 'name' not in args:
        raise WorkError('Ungültige Parameter.')
    return JsonResponse(create_token(request.user, **args), status=201)
