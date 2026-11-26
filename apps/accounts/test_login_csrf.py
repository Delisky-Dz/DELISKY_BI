import os
import re
import subprocess
import sys
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import strip_tags


class LoginCsrfTests(TestCase):
    password = "Login-recovery-test-only!"
    notice = "انتهت صلاحية صفحة الدخول"

    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", stdout=StringIO())
        for role in ("Manager", "Accountant"):
            user = get_user_model().objects.create_user(
                username=f"fixture_{role}", password=cls.password, is_staff=True
            )
            user.groups.add(Group.objects.get(name=role))
        cls.login_url = reverse("accounts:login")
        cls.route_url = reverse("accounts:route")

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def token_from(self, page):
        self.assertEqual(page.status_code, 200)
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())
        self.assertIsNotNone(match)
        return match.group(1)

    def post_login(self, client, token=None, username="fixture_Manager", password=None):
        fields = {"username": username, "password": password or self.password}
        if token is not None:
            fields["csrfmiddlewaretoken"] = token
        return client.post(self.login_url, fields, secure=True, HTTP_ORIGIN="https://testserver")

    def test_normal_form_is_uncached_and_wrong_password_keeps_existing_error(self):
        page = self.client.get(self.login_url, secure=True)
        self.assertNotContains(page, self.notice)
        directives = set(page["Cache-Control"].split(", "))
        self.assertTrue({"no-store", "no-cache", "private", "max-age=0"} <= directives)
        invalid = self.post_login(self.client, self.token_from(page), password="wrong-password")
        self.assertContains(invalid, "تعذر تسجيل الدخول")
        self.assertNotContains(invalid, self.notice)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_missing_token_rejected_before_authentication(self):
        self.client.get(self.login_url, secure=True)
        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            rejected = self.post_login(self.client)
        authenticate.assert_not_called()
        self.assertEqual(rejected.status_code, 303)
        self.assertEqual(rejected["Location"], self.login_url)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_old_tab_after_real_login_rotation_and_logout_can_retry(self):
        stale = self.token_from(self.client.get(self.login_url, secure=True))
        old_secret = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        other_tab = self.token_from(self.client.get(self.login_url, secure=True))
        logged_in = self.post_login(self.client, other_tab)
        self.assertRedirects(logged_in, self.route_url, fetch_redirect_response=False)
        current_secret = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertNotEqual(current_secret, old_secret)
        logged_out = self.client.post(
            reverse("accounts:logout"), {"csrfmiddlewaretoken": current_secret},
            secure=True, HTTP_ORIGIN="https://testserver",
        )
        self.assertRedirects(logged_out, self.login_url, fetch_redirect_response=False)

        with self.assertLogs("django.security.csrf", "INFO") as warnings:
            with patch("django.contrib.auth.forms.authenticate") as authenticate:
                rejected = self.post_login(self.client, stale)
        authenticate.assert_not_called()
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(rejected.status_code, 303)
        self.assertEqual(rejected["Location"], self.login_url)
        for value in ("fixture_Manager", self.password, stale):
            self.assertNotIn(value, "\n".join(warnings.output))

        fresh = self.client.get(rejected["Location"], secure=True)
        self.assertContains(fresh, self.notice, count=1)
        self.assertIn("no-store", fresh["Cache-Control"])
        visible = strip_tags(fresh.content.decode())
        for value in ("CSRF", "Forbidden", "403", "incorrect", "fixture_Manager", self.password):
            self.assertNotIn(value, visible)
        self.assertNotContains(self.client.get(self.login_url, secure=True), self.notice)
        success = self.post_login(self.client, self.token_from(fresh))
        self.assertRedirects(success, self.route_url, fetch_redirect_response=False)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_csrf_failure_on_logout_keeps_session_and_returns_403(self):
        self.client.force_login(get_user_model().objects.get(username="fixture_Manager"))
        denied = self.client.post(reverse("accounts:logout"), secure=True, HTTP_ORIGIN="https://testserver")
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn("Location", denied)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_stale_post_with_active_session_routes_existing_user(self):
        token = self.token_from(self.client.get(self.login_url, secure=True))
        self.post_login(self.client, token)
        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            denied = self.post_login(self.client, token, username="fixture_Accountant")
        authenticate.assert_not_called()
        self.assertEqual(denied.status_code, 303)
        page = self.client.get(denied["Location"], follow=True, secure=True)
        self.assertEqual(page.wsgi_request.user.get_username(), "fixture_Manager")
        self.assertEqual(page.wsgi_request.path, reverse("dashboard:manager_dashboard"))

    def test_both_devices_retain_authenticated_access_to_their_role_page(self):
        for role, destination in (
            ("Manager", "dashboard:manager_dashboard"),
            ("Accountant", "imports:accountant_home"),
        ):
            with self.subTest(role=role):
                username = f"fixture_{role}"
                devices = [Client(enforce_csrf_checks=True) for _ in range(2)]
                for device in devices:
                    token = self.token_from(device.get(self.login_url, secure=True))
                    login = self.post_login(device, token, username=username)
                    self.assertRedirects(login, self.route_url, fetch_redirect_response=False)
                self.assertNotEqual(devices[0].session.session_key, devices[1].session.session_key)
                for device in devices:
                    page = device.get(self.route_url, secure=True, follow=True)
                    self.assertEqual(page.redirect_chain, [(reverse(destination), 302)])
                    self.assertEqual(page.status_code, 200)
                    self.assertEqual(page.wsgi_request.user.get_username(), username)


class ProductionLoginSecurityTests(SimpleTestCase):
    def test_effective_production_settings_keep_login_protected(self):
        # Import production settings in isolation. This check never opens a database.
        probe = """
import django
django.setup()
from django.conf import settings
from django.urls import resolve
assert settings.CSRF_COOKIE_SECURE and settings.SESSION_COOKIE_SECURE
assert settings.SECURE_SSL_REDIRECT
assert "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE
assert not getattr(resolve("/login/").func, "csrf_exempt", False)
"""
        result = subprocess.run(
            [sys.executable, "-c", probe], cwd=settings.BASE_DIR,
            env={**os.environ, "DB_NAME": "delisky_bi", "DJANGO_SETTINGS_MODULE": "config.settings.production"},
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
