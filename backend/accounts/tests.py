import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings


class PasswordLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user('login@example.test', password='Test-only-password-83!')
        cls.inactive = User.objects.create_user('inactive@example.test', password='Test-only-password-83!', is_active=False)
        cls.social = User.objects.create_user('social@example.test')

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.browser = Client(enforce_csrf_checks=True)
        self.token = self.browser.get('/api/auth/session/').json()['csrfToken']

    def login(self, email='login@example.test', password='Test-only-password-83!', **extra):
        return self.browser.post('/api/auth/login/', json.dumps({'email': email, 'password': password}), content_type='application/json', HTTP_X_CSRFTOKEN=self.token, **extra)

    def test_login_normalizes_email_and_sets_httponly_session(self):
        response = self.login(email='  LOGIN@EXAMPLE.TEST  ')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertTrue(response.cookies[settings.SESSION_COOKIE_NAME]['httponly'])
        session = self.browser.get('/api/auth/session/').json()
        self.assertTrue(session['authenticated'])
        self.assertEqual(session['user']['email'], self.user.email)
        self.assertEqual(self.browser.get('/api/dashboard/').status_code, 200)
        self.assertEqual(self.browser.get('/api/admin/').status_code, 403)

    def test_login_requires_post_csrf_and_rejects_foreign_origin(self):
        self.assertEqual(self.browser.get('/api/auth/login/').status_code, 405)
        self.assertEqual(self.browser.post('/api/auth/login/', '{}', content_type='application/json').status_code, 403)
        self.assertEqual(self.login(HTTP_ORIGIN='https://untrusted.example').status_code, 403)

    def test_invalid_unknown_inactive_and_social_credentials_have_same_error(self):
        responses = [
            self.login(password='Incorrect'),
            self.login(email='unknown@example.test'),
            self.login(email=self.inactive.email),
            self.login(email=self.social.email),
        ]
        self.assertEqual({r.status_code for r in responses}, {401})
        self.assertEqual({r.json()['error'] for r in responses}, {'E-Mail-Adresse oder Passwort ist falsch.'})
        self.assertFalse(self.browser.get('/api/auth/session/').json()['authenticated'])

    @override_settings(ACCOUNT_LOGIN_ATTEMPTS_LIMIT=2, ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT=300)
    def test_repeated_failures_are_throttled(self):
        self.assertEqual(self.login(password='Incorrect').status_code, 401)
        self.assertEqual(self.login(password='Incorrect').status_code, 401)
        self.assertEqual(self.login(password='Incorrect').status_code, 429)
        self.assertEqual(self.login().status_code, 429)

    def test_login_rotates_existing_session_and_csrf(self):
        session = self.browser.session
        session['before_login'] = True
        session.save()
        self.browser.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
        before = session.session_key
        self.assertEqual(self.login().status_code, 200)
        self.assertNotEqual(self.browser.cookies[settings.SESSION_COOKIE_NAME].value, before)
        self.assertNotEqual(self.browser.get('/api/auth/session/').json()['csrfToken'], self.token)
        self.assertEqual(self.browser.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=self.token).status_code, 403)
        token = self.browser.get('/api/auth/session/').json()['csrfToken']
        self.assertEqual(self.browser.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(self.browser.get('/api/dashboard/').status_code, 401)

    def test_malformed_or_oversized_payloads_do_not_authenticate(self):
        for body in ['[]', '{', '{}', json.dumps({'email': ['login@example.test'], 'password': 'x'}), json.dumps({'email': 'bad', 'password': 'x'}), json.dumps({'email': 'login@example.test', 'password': ''}), json.dumps({'email': 'login@example.test', 'password': 'x' * 9000})]:
            response = self.browser.post('/api/auth/login/', body, content_type='application/json', HTTP_X_CSRFTOKEN=self.token)
            self.assertIn(response.status_code, [400, 413])
        self.assertEqual(self.browser.post('/api/auth/login/', 'email=x', content_type='text/plain', HTTP_X_CSRFTOKEN=self.token).status_code, 415)
        self.assertFalse(self.browser.get('/api/auth/session/').json()['authenticated'])


class AccountSettingsTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user=get_user_model().objects.create_user('profile@example.test',password='Old-fixture-password-4622')
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token=self.client.get('/api/auth/session/').json()['csrfToken']

    def post(self,args):
        import json
        return self.client.post('/api/auth/account/',json.dumps(args),content_type='application/json',HTTP_X_CSRFTOKEN=self.token)

    def test_profile_csrf_identity_and_password_session(self):
        import json
        self.assertEqual(self.client.post('/api/auth/account/',json.dumps({'first_name':'A','last_name':'B'}),content_type='application/json').status_code,403)
        self.assertEqual(self.post({'first_name':'Alex','last_name':'Team'}).status_code,200)
        self.user.refresh_from_db();self.assertEqual(self.user.get_full_name(),'Alex Team')
        self.assertEqual(self.post({'is_staff':True}).status_code,400)
        self.assertEqual(self.post({'current_password':'Wrong','new_password':'New-fixture-password-6842','confirm_password':'New-fixture-password-6842'}).status_code,400)
        self.assertEqual(self.post({'current_password':'Old-fixture-password-4622','new_password':'New-fixture-password-6842','confirm_password':'New-fixture-password-6842'}).status_code,200)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('New-fixture-password-6842'))
        self.assertTrue(self.client.get('/api/auth/session/').json()['authenticated'])
