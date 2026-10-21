import json
from functools import wraps

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
    if len(request.body) > 100000:
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
