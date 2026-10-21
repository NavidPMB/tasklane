from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.adapters import VerifiedGoogleAdapter
from .admin import CredentialForm
from .models import IntegrationCredential
from .services import google_login_enabled


class CredentialTests(TestCase):
    def setUp(self):
        self.credential = IntegrationCredential.objects.get(key="google")

    def configure_google(self):
        self.credential.client_id = "client-id"
        self.credential.set_secret("very-private-client-secret")
        self.credential.enabled = True
        self.credential.save()

    def test_secret_is_encrypted_at_rest(self):
        self.configure_google()
        self.credential.refresh_from_db()
        self.assertNotIn("very-private", self.credential.encrypted_secret)
        self.assertEqual(self.credential.get_secret(), "very-private-client-secret")

    def test_credentials_apply_immediately_and_can_be_disabled(self):
        self.assertFalse(google_login_enabled())
        self.configure_google()
        self.assertTrue(self.client.get("/api/auth/session/").json()["googleLoginEnabled"])
        adapter = VerifiedGoogleAdapter()
        self.assertEqual(adapter.list_apps(None, "google")[0].secret, "very-private-client-secret")
        self.credential.enabled = False
        self.credential.save()
        self.assertFalse(google_login_enabled())
        self.assertEqual(adapter.list_apps(None, "google"), [])

    def test_blank_secret_in_admin_preserves_existing_secret(self):
        self.configure_google()
        form = CredentialForm(data={"key": "google", "name": "Google Login", "kind": "oauth2", "enabled": True, "client_id": "new-id", "secret_value": "", "notes": ""}, instance=self.credential)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.get_secret(), "very-private-client-secret")

    def test_enabled_oauth_configuration_requires_both_credentials(self):
        form = CredentialForm(data={"key": "another-provider", "name": "OAuth", "kind": "oauth2", "enabled": True, "client_id": "", "secret_value": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("client_id", form.errors)
        self.assertIn("secret_value", form.errors)

    def test_admin_shows_callback_instructions_but_never_existing_secret(self):
        self.configure_google()
        user = get_user_model().objects.create_superuser("admin@example.com", "a-strong-test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("admin:integrations_integrationcredential_change", args=[self.credential.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{settings.PUBLIC_URL}/accounts/google/login/callback/")
        self.assertContains(response, "Autorisierte JavaScript-Quellen")
        self.assertNotContains(response, "very-private-client-secret")
        self.assertNotContains(response, self.credential.encrypted_secret)

    def test_regular_staff_cannot_read_or_change_credentials(self):
        user = get_user_model().objects.create_user("staff@example.com", is_staff=True)
        self.client.force_login(user)
        url = reverse("admin:integrations_integrationcredential_change", args=[self.credential.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"secret_value": "attacker-value"}).status_code, 403)

    def test_public_session_never_exposes_credentials(self):
        self.configure_google()
        response = self.client.get("/api/auth/session/")
        self.assertNotContains(response, "very-private-client-secret")
        self.assertNotContains(response, "client-id")
