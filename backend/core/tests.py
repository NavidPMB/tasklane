from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from allauth.core.exceptions import ImmediateHttpResponse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, transaction
from django.test import Client, TestCase

from accounts.adapters import VerifiedGoogleAdapter
from integrations.models import IntegrationCredential

User = get_user_model()


class AccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user("member@example.com", first_name="Mia")
        cls.staff = User.objects.create_user("staff@example.com", is_staff=True)

    def test_landing_api_is_public(self):
        self.assertEqual(self.client.get("/api/cms/").status_code, 200)

    def test_protected_apis_reject_anonymous_requests(self):
        for url in ("/api/dashboard/", "/api/admin/", "/api/admin/users/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)

    def test_member_can_access_dashboard_but_not_admin(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 200)
        for url in ("/api/admin/", "/api/admin/users/"):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_staff_can_access_admin_and_user_list(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/api/admin/").json()["users"], 2)
        response = self.client.get("/api/admin/users/").json()
        self.assertEqual(response["count"], 2)
        self.assertNotIn("password", response["results"][0])

    def test_deactivated_user_cannot_use_existing_session(self):
        self.client.force_login(self.member)
        self.member.is_active = False
        self.member.save()
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 401)

    def test_session_is_private_and_not_cached(self):
        self.client.force_login(self.member)
        response = self.client.get("/api/auth/session/")
        self.assertTrue(response.json()["authenticated"])
        self.assertEqual(response.json()["user"]["email"], self.member.email)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(response.cookies[settings.CSRF_COOKIE_NAME]["httponly"])

    def test_csrf_is_required_for_logout(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.member)
        self.assertEqual(client.post("/api/auth/logout/").status_code, 403)
        self.assertEqual(client.get("/api/auth/logout/").status_code, 405)
        token = client.get("/api/auth/session/").json()["csrfToken"]
        self.assertEqual(client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertFalse(client.get("/api/auth/session/").json()["authenticated"])

    def test_database_rejects_case_insensitive_duplicate_email(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email="MEMBER@example.com")

    def test_health_checks_real_database(self):
        self.assertEqual(self.client.get("/api/health/").json()["status"], "ok")
        with patch("core.views.connection.cursor", side_effect=DatabaseError):
            self.assertEqual(self.client.get("/api/health/").status_code, 503)

    def test_user_list_validates_page(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/api/admin/users/?page=invalid").status_code, 400)


class GoogleLoginTests(TestCase):
    def test_google_login_requires_post_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get("/accounts/google/login/").status_code, 405)
        self.assertEqual(client.post("/accounts/google/login/").status_code, 403)

    def test_missing_google_credentials_have_controlled_redirect(self):
        response = self.client.post("/accounts/google/login/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("google-not-configured", response["Location"])

    def test_google_redirect_contains_state_pkce_and_frontend_callback(self):
        credential = IntegrationCredential.objects.get(key="google")
        credential.client_id = "test-client"
        credential.set_secret("test-secret")
        credential.enabled = True
        credential.save()
        response = self.client.post("/accounts/google/login/", HTTP_X_FORWARDED_HOST="localhost:3002")
        self.assertEqual(response.status_code, 302)
        location = urlsplit(response["Location"])
        params = parse_qs(location.query)
        self.assertEqual(location.hostname, "accounts.google.com")
        self.assertEqual(params["redirect_uri"], ["http://localhost:3002/accounts/google/login/callback/"])
        self.assertTrue(params["state"][0])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertTrue(params["code_challenge"][0])

    def test_unverified_google_email_is_rejected(self):
        adapter = VerifiedGoogleAdapter()
        login = SimpleNamespace(email_addresses=[SimpleNamespace(verified=False)])
        with self.assertRaises(ImmediateHttpResponse):
            adapter.pre_social_login(None, login)

    def test_verified_google_email_is_accepted(self):
        adapter = VerifiedGoogleAdapter()
        login = SimpleNamespace(email_addresses=[SimpleNamespace(verified=True)])
        self.assertIsNone(adapter.pre_social_login(None, login))
