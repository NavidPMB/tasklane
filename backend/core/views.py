from django.contrib.auth import logout
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from integrations.services import google_login_enabled


@never_cache
@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    from .version import VERSION
    return JsonResponse({"status": "ok", "database": "postgresql", "version": VERSION, "api_version": "1"})


@never_cache
@require_GET
def session(request):
    user = request.user
    return JsonResponse({
        "authenticated": user.is_authenticated,
        "csrfToken": get_token(request),
        "googleLoginEnabled": google_login_enabled(),
        "user": {
            "id": user.pk,
            "email": user.email,
            "name": user.get_full_name() or user.email,
            "firstName": user.first_name, "lastName": user.last_name, "hasPassword": user.has_usable_password(),
            "isStaff": user.is_staff,
            "isSuperuser": user.is_superuser,
        } if user.is_authenticated else None,
    })


@never_cache
@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"ok": True})
