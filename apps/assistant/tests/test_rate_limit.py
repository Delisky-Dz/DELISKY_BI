from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.assistant.models import (
    AskDeliskyRateLimit,
)
from apps.assistant.rate_limit import (
    AskDeliskyRateLimitConfigurationError,
    check_ask_delisky_rate_limit,
    load_ask_delisky_rate_limit_config,
)


class AskDeliskyRateLimitConfigTests(
    SimpleTestCase
):
    def test_defaults_are_safe(self):
        config = (
            load_ask_delisky_rate_limit_config(
                environ={}
            )
        )

        self.assertEqual(
            config.requests,
            5,
        )
        self.assertEqual(
            config.window_seconds,
            60,
        )

    def test_environment_overrides_defaults(self):
        config = (
            load_ask_delisky_rate_limit_config(
                environ={
                    "ASK_DELISKY_RATE_LIMIT_REQUESTS":
                        "3",
                    "ASK_DELISKY_RATE_LIMIT_WINDOW_SECONDS":
                        "90",
                }
            )
        )

        self.assertEqual(
            config.requests,
            3,
        )
        self.assertEqual(
            config.window_seconds,
            90,
        )

    def test_invalid_configuration_is_rejected(
        self
    ):
        with self.assertRaises(
            AskDeliskyRateLimitConfigurationError
        ):
            load_ask_delisky_rate_limit_config(
                environ={
                    "ASK_DELISKY_RATE_LIMIT_REQUESTS":
                        "0",
                }
            )


class AskDeliskyRateLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.user = User.objects.create_user(
            username="rate_limit_manager",
            password="Temporary-Test-Password-2026",
        )

        cls.other_user = User.objects.create_user(
            username="rate_limit_other",
            password="Temporary-Test-Password-2026",
        )

    def test_requests_are_allowed_until_limit(
        self
    ):
        now = timezone.now()

        for _ in range(5):
            result = check_ask_delisky_rate_limit(
                user=self.user,
                now=now,
                environ={
                    "ASK_DELISKY_RATE_LIMIT_REQUESTS":
                        "5",
                    "ASK_DELISKY_RATE_LIMIT_WINDOW_SECONDS":
                        "60",
                },
            )

            self.assertTrue(
                result.allowed
            )

        bucket = AskDeliskyRateLimit.objects.get(
            user=self.user,
            scope="manager_ask",
        )

        self.assertEqual(
            bucket.request_count,
            5,
        )

    def test_request_above_limit_is_rejected(
        self
    ):
        now = timezone.now()

        environ = {
            "ASK_DELISKY_RATE_LIMIT_REQUESTS":
                "2",
            "ASK_DELISKY_RATE_LIMIT_WINDOW_SECONDS":
                "60",
        }

        check_ask_delisky_rate_limit(
            user=self.user,
            now=now,
            environ=environ,
        )
        check_ask_delisky_rate_limit(
            user=self.user,
            now=now,
            environ=environ,
        )

        result = check_ask_delisky_rate_limit(
            user=self.user,
            now=now,
            environ=environ,
        )

        self.assertFalse(
            result.allowed
        )
        self.assertEqual(
            result.retry_after_seconds,
            60,
        )

    def test_window_resets_after_expiration(
        self
    ):
        started_at = timezone.now()

        environ = {
            "ASK_DELISKY_RATE_LIMIT_REQUESTS":
                "1",
            "ASK_DELISKY_RATE_LIMIT_WINDOW_SECONDS":
                "60",
        }

        first = check_ask_delisky_rate_limit(
            user=self.user,
            now=started_at,
            environ=environ,
        )

        blocked = check_ask_delisky_rate_limit(
            user=self.user,
            now=started_at,
            environ=environ,
        )

        after_window = (
            started_at
            + timedelta(
                seconds=61
            )
        )

        reset = check_ask_delisky_rate_limit(
            user=self.user,
            now=after_window,
            environ=environ,
        )

        self.assertTrue(
            first.allowed
        )
        self.assertFalse(
            blocked.allowed
        )
        self.assertTrue(
            reset.allowed
        )

    def test_users_have_independent_buckets(
        self
    ):
        now = timezone.now()

        environ = {
            "ASK_DELISKY_RATE_LIMIT_REQUESTS":
                "1",
            "ASK_DELISKY_RATE_LIMIT_WINDOW_SECONDS":
                "60",
        }

        first_user = (
            check_ask_delisky_rate_limit(
                user=self.user,
                now=now,
                environ=environ,
            )
        )

        second_user = (
            check_ask_delisky_rate_limit(
                user=self.other_user,
                now=now,
                environ=environ,
            )
        )

        self.assertTrue(
            first_user.allowed
        )
        self.assertTrue(
            second_user.allowed
        )

        self.assertEqual(
            AskDeliskyRateLimit.objects.count(),
            2,
        )
