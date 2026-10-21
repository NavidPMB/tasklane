from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Article


class WikiAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Article.objects.all().delete()
        User = get_user_model()
        cls.member = User.objects.create_user("wiki-member@example.com")
        cls.staff = User.objects.create_user("wiki-staff@example.com", is_staff=True)
        cls.superuser = User.objects.create_superuser("wiki-root@example.com")
        for visibility in Article.Visibility.values:
            Article.objects.create(title=f"{visibility} article", slug=visibility,
                                   summary=f"Summary {visibility}", body=f"Private marker {visibility}",
                                   visibility=visibility, is_published=True)
            Article.objects.create(title=f"Draft {visibility}", slug=f"draft-{visibility}",
                                   body="Unpublished draft marker", visibility=visibility)

    def visible_slugs(self, query=""):
        response = self.client.get(f"/api/wiki/{query}")
        self.assertEqual(response.status_code, 200)
        return {article["slug"] for article in response.json()["articles"]}

    def test_anonymous_readers_only_see_public_articles(self):
        self.assertEqual(self.visible_slugs(), {"public"})
        self.assertEqual(self.client.get("/api/wiki/public/").status_code, 200)

    def test_members_and_staff_do_not_gain_internal_access(self):
        for user in (self.member, self.staff):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                self.assertEqual(self.visible_slugs(), {"public", "registered"})
                self.assertEqual(self.client.get("/api/wiki/registered/").status_code, 200)
                self.assertEqual(self.client.get("/api/wiki/internal/").status_code, 404)

    def test_superuser_sees_all_published_audiences_in_one_list(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.visible_slugs(), {"public", "registered", "internal"})
        self.assertEqual(self.client.get("/api/wiki/internal/").status_code, 200)

    def test_drafts_are_never_available_in_frontend_even_to_superuser(self):
        self.client.force_login(self.superuser)
        for visibility in Article.Visibility.values:
            self.assertEqual(self.client.get(f"/api/wiki/draft-{visibility}/").status_code, 404)

    def test_hidden_and_missing_articles_have_identical_responses(self):
        missing = self.client.get("/api/wiki/not-existing/")
        for slug in ("registered", "internal", "draft-public"):
            response = self.client.get(f"/api/wiki/{slug}/")
            self.assertEqual(response.status_code, missing.status_code)
            self.assertEqual(response.json(), missing.json())

    def test_search_filters_after_access_control(self):
        self.assertEqual(self.visible_slugs("?q=marker+internal"), set())
        self.assertEqual(self.visible_slugs("?visibility=internal"), set())
        self.client.force_login(self.superuser)
        self.assertEqual(self.visible_slugs("?q=marker+internal"), {"internal"})
        self.assertEqual(self.visible_slugs("?visibility=registered"), {"registered"})

    def test_invalid_filter_returns_bad_request(self):
        self.assertEqual(self.client.get("/api/wiki/?visibility=unknown").status_code, 400)

    def test_list_does_not_include_bodies_or_unavailable_metadata(self):
        response = self.client.get("/api/wiki/")
        self.assertNotContains(response, "Private marker")
        self.assertNotContains(response, "Summary internal")
        self.assertNotContains(response, "registered article")
        self.assertNotIn("body", response.json()["articles"][0])

    def test_authorized_responses_are_not_cacheable(self):
        self.client.force_login(self.superuser)
        for url in ("/api/wiki/", "/api/wiki/internal/"):
            response = self.client.get(url)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertIn("private", response["Cache-Control"])

    def test_changing_visibility_revokes_access_immediately(self):
        self.assertEqual(self.client.get("/api/wiki/public/").status_code, 200)
        Article.objects.filter(slug="public").update(visibility=Article.Visibility.INTERNAL)
        self.assertEqual(self.client.get("/api/wiki/public/").status_code, 404)
        self.assertEqual(self.visible_slugs(), set())

    def test_deactivated_account_cannot_read_member_articles(self):
        self.client.force_login(self.member)
        self.member.is_active = False
        self.member.save()
        self.assertEqual(self.visible_slugs(), {"public"})
        self.assertEqual(self.client.get("/api/wiki/registered/").status_code, 404)

    def test_admin_editor_is_reserved_for_superusers(self):
        article = Article.objects.get(slug="internal")
        url = reverse("admin:wiki_article_change", args=[article.pk])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"visibility": "public"}).status_code, 403)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_session_distinguishes_staff_and_superuser(self):
        self.client.force_login(self.staff)
        self.assertFalse(self.client.get("/api/auth/session/").json()["user"]["isSuperuser"])
        self.client.force_login(self.superuser)
        self.assertTrue(self.client.get("/api/auth/session/").json()["user"]["isSuperuser"])

    def test_new_articles_default_to_unpublished_and_internal(self):
        article = Article.objects.create(title="New article", slug="new", body="New")
        self.assertEqual(article.visibility, Article.Visibility.INTERNAL)
        self.assertFalse(article.is_published)
        self.assertNotIn(article, Article.objects.visible_to(AnonymousUser()))


class WikiSeedTests(TestCase):
    def test_google_live_guide_is_internal_and_not_public(self):
        article = Article.objects.get(slug="google-login-live")
        self.assertEqual(article.visibility, Article.Visibility.INTERNAL)
        self.assertTrue(article.is_published)
        self.assertEqual(self.client.get("/api/wiki/google-login-live/").status_code, 404)
        articles = self.client.get("/api/wiki/").json()["articles"]
        self.assertNotIn("google-login-live", [item["slug"] for item in articles])
        self.assertTrue(all(item["visibility"] == "public" for item in articles))

    def test_login_help_is_public(self):
        response = self.client.get("/api/wiki/tasklane-anmelden/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwort")

    @override_settings(PUBLIC_URL="https://live.example.com")
    def test_google_guide_uses_current_project_urls(self):
        user = get_user_model().objects.create_superuser("wiki-guide@example.com")
        self.client.force_login(user)
        response = self.client.get("/api/wiki/google-login-live/")
        self.assertContains(response, "https://live.example.com/accounts/google/login/callback/")
        self.assertNotContains(response, "{{PUBLIC_URL}}")
        self.assertNotContains(response, "{{GOOGLE_CALLBACK_URL}}")
