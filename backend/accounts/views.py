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


@require_POST
@sensitive_post_parameters('current_password', 'new_password', 'confirm_password')
@sensitive_variables('payload', 'current_password', 'new_password')
def account_update(request):
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.password_validation import validate_password
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': 'Anmeldung erforderlich.'}, status=401)
    if request.content_type != 'application/json': return JsonResponse({'error': 'JSON-Anfrage erforderlich.'}, status=415)
    if len(request.body) > 16384: return JsonResponse({'error': 'Anfrage zu groß.'}, status=413)
    try: payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError): return JsonResponse({'error': 'Ungültiges JSON.'}, status=400)
    if not isinstance(payload, dict): return JsonResponse({'error': 'JSON-Objekt erforderlich.'}, status=400)
    if set(payload) == {'first_name', 'last_name'}:
        if any(not isinstance(value, str) or len(value) > 150 for value in payload.values()):
            return JsonResponse({'error': 'Namen dürfen höchstens 150 Zeichen enthalten.'}, status=400)
        request.user.first_name=payload['first_name'].strip();request.user.last_name=payload['last_name'].strip()
        request.user.save(update_fields=['first_name','last_name'])
        return JsonResponse({'ok': True})
    if set(payload) != {'current_password', 'new_password', 'confirm_password'} or any(not isinstance(value, str) or len(value)>4096 for value in payload.values()):
        return JsonResponse({'error': 'Ungültige Parameter.'}, status=400)
    current_password=payload['current_password'];new_password=payload['new_password']
    if not request.user.has_usable_password():
        return JsonResponse({'error': 'Dieses Konto nutzt die externe Anmeldung. Ein Passwort kann die Kontoverwaltung einrichten.'}, status=400)
    try:
        user=get_adapter(request).authenticate(request,email=request.user.email,password=current_password)
    except ValidationError:
        return JsonResponse({'error': 'Zu viele Versuche. Bitte später erneut versuchen.'},status=429)
    if user is None or user.pk != request.user.pk:
        return JsonResponse({'error': 'Das aktuelle Passwort ist nicht korrekt.'},status=400)
    if new_password != payload['confirm_password']:
        return JsonResponse({'error': 'Die neuen Passwörter stimmen nicht überein.'},status=400)
    try: validate_password(new_password,user=request.user)
    except ValidationError as error: return JsonResponse({'error': ' '.join(error.messages)},status=400)
    request.user.set_password(new_password);request.user.save(update_fields=['password'])
    update_session_auth_hash(request,request.user)
    return JsonResponse({'ok': True})
