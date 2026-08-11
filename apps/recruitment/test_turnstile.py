import json
from unittest.mock import (
    MagicMock,
    patch,
)

from django.test import (
    TestCase,
    override_settings,
)

from .models import JobApplication
from .turnstile import verify_turnstile


TURNSTILE_TEST_SETTINGS = {
    "TURNSTILE_ENABLED": True,
    "TURNSTILE_SITE_KEY": "test-site-key",
    "TURNSTILE_SECRET_KEY": "test-secret-key",
    "TURNSTILE_EXPECTED_HOSTNAME": (
        "www.delisky-dz.com"
    ),
}


@override_settings(
    **TURNSTILE_TEST_SETTINGS
)
class PublicTurnstileIntegrationTests(TestCase):
    def valid_payload(self):
        return {
            "first_name": "Ahmed",
            "last_name": "Test",
            "birth_date": "1995-01-10",
            "marital_status": "MARRIED",
            "children_count": "2",
            "phone": "0660775108",
            "email": "",
            "wilaya": "Constantine",
            "residence": "Ali Mendjeli",
            "requested_position": "SELLER",
            "experience_years": "5",
            "previous_companies": "Company A",
        }

    def test_widget_is_rendered_when_enabled(self):
        response = self.client.get(
            "/en/careers/apply/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            'class="cf-turnstile"',
        )

        self.assertContains(
            response,
            'data-sitekey="test-site-key"',
        )

        self.assertContains(
            response,
            "challenges.cloudflare.com/"
            "turnstile/v0/api.js",
        )

    @patch(
        "apps.recruitment.public_views."
        "verify_turnstile"
    )
    def test_missing_token_does_not_save(
        self,
        verify_mock,
    ):
        verify_mock.return_value = False

        response = self.client.post(
            "/en/careers/apply/",
            self.valid_payload(),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            JobApplication.objects.count(),
            0,
        )

        verify_mock.assert_called_once_with("")

    @patch(
        "apps.recruitment.public_views."
        "verify_turnstile"
    )
    def test_rejected_token_does_not_save(
        self,
        verify_mock,
    ):
        verify_mock.return_value = False

        payload = self.valid_payload()
        payload[
            "cf-turnstile-response"
        ] = "rejected-token"

        response = self.client.post(
            "/en/careers/apply/",
            payload,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            JobApplication.objects.count(),
            0,
        )

        verify_mock.assert_called_once_with(
            "rejected-token"
        )

    @patch(
        "apps.recruitment.public_views."
        "verify_turnstile"
    )
    def test_verified_token_saves_application(
        self,
        verify_mock,
    ):
        verify_mock.return_value = True

        payload = self.valid_payload()
        payload[
            "cf-turnstile-response"
        ] = "verified-token"

        response = self.client.post(
            "/en/careers/apply/",
            payload,
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            JobApplication.objects.count(),
            1,
        )

        verify_mock.assert_called_once_with(
            "verified-token"
        )


@override_settings(
    TURNSTILE_SECRET_KEY="test-secret",
    TURNSTILE_EXPECTED_HOSTNAME=(
        "www.delisky-dz.com"
    ),
)
class TurnstileVerificationServiceTests(TestCase):
    def response_mock(self, payload):
        response = MagicMock()

        response.read.return_value = (
            json.dumps(payload).encode("utf-8")
        )

        response.__enter__.return_value = (
            response
        )

        response.__exit__.return_value = False

        return response

    @patch(
        "apps.recruitment.turnstile.urlopen"
    )
    def test_valid_cloudflare_response_passes(
        self,
        urlopen_mock,
    ):
        urlopen_mock.return_value = (
            self.response_mock(
                {
                    "success": True,
                    "hostname": (
                        "www.delisky-dz.com"
                    ),
                }
            )
        )

        self.assertTrue(
            verify_turnstile(
                "valid-token"
            )
        )

    @patch(
        "apps.recruitment.turnstile.urlopen"
    )
    def test_wrong_hostname_is_rejected(
        self,
        urlopen_mock,
    ):
        urlopen_mock.return_value = (
            self.response_mock(
                {
                    "success": True,
                    "hostname": (
                        "evil.example.com"
                    ),
                }
            )
        )

        self.assertFalse(
            verify_turnstile(
                "valid-token"
            )
        )

    @patch(
        "apps.recruitment.turnstile.urlopen"
    )
    def test_cloudflare_rejection_is_rejected(
        self,
        urlopen_mock,
    ):
        urlopen_mock.return_value = (
            self.response_mock(
                {
                    "success": False,
                    "error-codes": [
                        "invalid-input-response"
                    ],
                }
            )
        )

        self.assertFalse(
            verify_turnstile(
                "invalid-token"
            )
        )

    def test_empty_token_fails_closed(self):
        self.assertFalse(
            verify_turnstile("")
        )

    @override_settings(
        TURNSTILE_SECRET_KEY=""
    )
    @patch(
        "apps.recruitment.turnstile.urlopen"
    )
    def test_missing_secret_fails_closed(
        self,
        urlopen_mock,
    ):
        self.assertFalse(
            verify_turnstile(
                "valid-token"
            )
        )

        urlopen_mock.assert_not_called()

    @patch(
        "apps.recruitment.turnstile.urlopen"
    )
    def test_network_error_fails_closed(
        self,
        urlopen_mock,
    ):
        urlopen_mock.side_effect = (
            TimeoutError(
                "Turnstile timeout"
            )
        )

        self.assertFalse(
            verify_turnstile(
                "valid-token"
            )
        )

