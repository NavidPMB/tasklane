from django import forms
from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html
from allauth.socialaccount.models import SocialApp, SocialToken

from .models import IntegrationCredential

# Ein einziger Verwaltungsort für Secrets; keine parallele Klartext-Konfiguration.
for model in (SocialApp, SocialToken):
    if admin.site.is_registered(model):
        admin.site.unregister(model)


class CredentialForm(forms.ModelForm):
    secret_value = forms.CharField(
        label="Secret / API-Schlüssel", required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Neuen Wert eingeben, um ihn verschlüsselt zu speichern. Leer lassen, um den vorhandenen Wert beizubehalten.",
    )

    class Meta:
        model = IntegrationCredential
        fields = ("key", "name", "kind", "enabled", "client_id", "notes")

    def clean(self):
        data = super().clean()
        if data.get("key", self.instance.key) == "google" and data.get("kind") != IntegrationCredential.Kind.OAUTH2:
            self.add_error("kind", "Google-Login benötigt den Typ OAuth 2 / Client-Secret.")
        if data.get("enabled"):
            if not data.get("secret_value") and not self.instance.encrypted_secret:
                self.add_error("secret_value", "Zum Aktivieren ist ein Secret erforderlich.")
            if data.get("kind") == IntegrationCredential.Kind.OAUTH2 and not data.get("client_id"):
                self.add_error("client_id", "Zum Aktivieren ist die Client-ID erforderlich.")
        return data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("secret_value"):
            instance.set_secret(self.cleaned_data["secret_value"])
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(IntegrationCredential)
class CredentialAdmin(admin.ModelAdmin):
    form = CredentialForm
    list_display = ("name", "key", "kind", "enabled", "configured", "updated_at")
    list_filter = ("kind", "enabled")
    search_fields = ("key", "name")
    readonly_fields = ("setup_instructions", "configured", "updated_at")
    fieldsets = (
        ("Einrichtung", {"fields": ("setup_instructions",)}),
        ("Integration", {"fields": ("key", "name", "kind", "enabled")}),
        ("Zugangsdaten", {"fields": ("client_id", "secret_value", "configured")}),
        ("Weitere Angaben", {"fields": ("notes", "updated_at")}),
    )

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission
    has_delete_permission = has_view_permission

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "key") if obj and obj.key == "google" else fields

    @admin.display(description="Secret gespeichert", boolean=True)
    def configured(self, obj):
        return obj.is_configured if obj else False

    @admin.display(description="Google-Login einrichten")
    def setup_instructions(self, obj):
        if obj and obj.key != "google":
            return "Zugangsschlüssel beim Anbieter erstellen, unten als Secret speichern und die Integration aktivieren."
        origin = settings.PUBLIC_URL
        return format_html(
            '<p>1. In der <a href="https://console.cloud.google.com/auth/clients" target="_blank" rel="noopener noreferrer">Google Cloud Console</a> ein Projekt wählen und den OAuth-Zustimmungsbildschirm einrichten.</p>'
            '<p>2. OAuth-Client vom Typ <strong>Webanwendung</strong> erstellen.</p>'
            '<p>3. Unter <strong>Autorisierte JavaScript-Quellen</strong> eintragen: <code>{}</code></p>'
            '<p>4. Unter <strong>Autorisierte Weiterleitungs-URIs</strong> exakt eintragen: <code>{}/accounts/google/login/callback/</code></p>'
            '<p>5. Client-ID und Client-Secret unten speichern und <strong>Aktiv</strong> auswählen. Im Google-Testmodus die erlaubten Testnutzer hinzufügen.</p>'
            '<p>Die URLs werden aus der Server-Einstellung PUBLIC_URL abgeleitet. Änderungen der Zugangsdaten gelten sofort.</p>',
            origin, origin,
        )
