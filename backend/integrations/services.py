from .models import IntegrationCredential


def google_login_enabled():
    return IntegrationCredential.objects.filter(
        key="google", enabled=True, kind=IntegrationCredential.Kind.OAUTH2,
    ).exclude(client_id="").exclude(encrypted_secret="").exists()


def get_integration_secret(key):
    """Nur im Backend verwenden; Secrets niemals an das Frontend weiterreichen."""
    return IntegrationCredential.objects.get(key=key, enabled=True).get_secret()
