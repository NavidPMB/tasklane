import json

from allauth.account.adapter import get_adapter
from allauth.socialaccount.providers.google.views import oauth2_login
from django.conf import settings
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_POST

from integrations.services import google_login_enabled


@never_cache
@require_POST
@sensitive_post_parameters("password")
@sensitive_variables("password", "payload")
def password_login(request):
    if request.content_type != "application/json":
        return JsonResponse({"error": "JSON-Anfrage erforderlich."}, status=415)
    if len(request.body) > 8192:
        return JsonResponse({"error": "Anfrage zu groß."}, status=413)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Ungültiges JSON."}, status=400)
    if not isinstance(payload, dict) or set(payload) != {"email", "password"}:
        return JsonResponse({"error": "E-Mail-Adresse und Passwort sind erforderlich."}, status=400)
    email, password = payload["email"], payload["password"]
    if not isinstance(email, str) or not isinstance(password, str):
        return JsonResponse({"error": "E-Mail-Adresse und Passwort sind erforderlich."}, status=400)
    email = email.strip().lower()
    if len(email) > 254 or not password or len(password) > 4096:
        return JsonResponse({"error": "Bitte eine gültige E-Mail-Adresse und ein Passwort eingeben."}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "Bitte eine gültige E-Mail-Adresse eingeben."}, status=400)
    try:
        # Bestehende Auth-Backends und den allauth-Schutz gegen wiederholte Fehlversuche verwenden.
        user = get_adapter(request).authenticate(request, email=email, password=password)
    except ValidationError:
        response = JsonResponse({"error": "Zu viele Anmeldeversuche. Bitte in einigen Minuten erneut versuchen."}, status=429)
        return response
    if user is None or not user.is_active:
        return JsonResponse({"error": "E-Mail-Adresse oder Passwort ist falsch."}, status=401)
    login(request, user)
    return JsonResponse({"ok": True})


@require_POST
def google_login(request):
    if not google_login_enabled():
        return redirect(f"{settings.LOGIN_URL}?error=google-not-configured")
    return oauth2_login(request)
