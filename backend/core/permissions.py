from functools import wraps

from django.http import JsonResponse


def require_user(*, staff=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Anmeldung erforderlich."}, status=401)
            if staff and not request.user.is_staff:
                return JsonResponse({"error": "Keine Berechtigung für diesen Bereich."}, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate
