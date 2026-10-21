from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.shortcuts import redirect


class VerifiedGoogleAdapter(DefaultSocialAccountAdapter):
    def list_apps(self, request, provider=None, client_id=None):
        from allauth.socialaccount.models import SocialApp
        from integrations.models import IntegrationCredential

        # Google verwendet ausschließlich die zentrale, verschlüsselte Konfiguration.
        apps = [] if provider == "google" else [
            app for app in super().list_apps(request, provider, client_id) if app.provider != "google"
        ]
        if provider in (None, "google"):
            credential = IntegrationCredential.objects.filter(key="google", enabled=True).first()
            if credential and credential.is_configured and (not client_id or client_id == credential.client_id):
                apps.append(SocialApp(provider="google", name=credential.name,
                                      client_id=credential.client_id, secret=credential.get_secret()))
        return apps

    def pre_social_login(self, request, sociallogin):
        if not any(address.verified for address in sociallogin.email_addresses):
            raise ImmediateHttpResponse(redirect(f"{settings.LOGIN_URL}?error=unverified-email"))
