from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.views.decorators.debug import sensitive_variables


class IntegrationCredential(models.Model):
    class Kind(models.TextChoices):
        OAUTH2 = "oauth2", "OAuth 2 / Client-Secret"
        API_KEY = "api_key", "API-Schlüssel"
        MCP = "mcp", "MCP-Zugangsschlüssel"

    key = models.SlugField("Interner Schlüssel", unique=True, help_text="Zum Beispiel google, openai oder mein-mcp-server.")
    name = models.CharField("Name", max_length=150)
    kind = models.CharField("Typ", max_length=20, choices=Kind.choices, default=Kind.API_KEY)
    enabled = models.BooleanField("Aktiv", default=False)
    client_id = models.CharField("Client-ID", max_length=500, blank=True)
    encrypted_secret = models.TextField(blank=True, editable=False)
    notes = models.TextField("Notizen", blank=True, help_text="Keine Zugangsdaten in dieses Feld schreiben.")
    updated_at = models.DateTimeField("Zuletzt geändert", auto_now=True)

    class Meta:
        verbose_name = "Integration / Zugangsdaten"
        verbose_name_plural = "Integrationen & Zugangsdaten"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_configured(self):
        return bool(self.encrypted_secret and (self.kind != self.Kind.OAUTH2 or self.client_id))

    @sensitive_variables("value")
    def set_secret(self, value):
        self.encrypted_secret = Fernet(settings.CREDENTIAL_ENCRYPTION_KEY).encrypt(value.encode()).decode() if value else ""

    @sensitive_variables()
    def get_secret(self):
        if not self.encrypted_secret:
            return ""
        try:
            return Fernet(settings.CREDENTIAL_ENCRYPTION_KEY).decrypt(self.encrypted_secret.encode()).decode()
        except (InvalidToken, ValueError) as error:
            raise ImproperlyConfigured("Zugangsdaten können mit dem konfigurierten Verschlüsselungsschlüssel nicht gelesen werden.") from error
