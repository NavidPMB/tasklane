from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.permissions import require_user


@never_cache
@require_GET
@require_user()
def overview(request):
    return JsonResponse({"area": "dashboard", "userId": request.user.pk})
