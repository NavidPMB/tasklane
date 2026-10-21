from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.permissions import require_user


@never_cache
@require_GET
@require_user(staff=True)
def overview(request):
    users = get_user_model().objects
    return JsonResponse({"area": "admin", "users": users.count(), "staff": users.filter(is_staff=True).count()})


@never_cache
@require_GET
@require_user(staff=True)
def users(request):
    # Begrenzte, seitenweise Liste ohne Schreibzugriff.
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except ValueError:
        return JsonResponse({"error": "Ungültige Seite."}, status=400)
    queryset = get_user_model().objects.order_by("id")
    offset = (page - 1) * 50
    return JsonResponse({
        "count": queryset.count(),
        "page": page,
        "results": list(queryset.values("id", "email", "first_name", "last_name", "is_staff", "is_active")[offset:offset + 50]),
    })
