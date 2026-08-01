from django.test import SimpleTestCase

from apps.assistant.config import (
    AskDeliskyProviderMode,
    load_ask_delisky_provider_config,
)


class AskDeliskyProviderConfigTests(SimpleTestCase):
    def test_provider_is_disabled_by_default(self):
        config = load_ask_delisky_provider_config(
            environ={}
        )

        self.assertEqual(
            config.mode,
            AskDeliskyProviderMode.DISABLED,
        )
        self.assertEqual(
            config.model_name,
            "",
        )
        self.assertEqual(
            config.base_url,
            "",
        )

    def test_local_configuration_is_loaded(self):
        config = load_ask_delisky_provider_config(
            environ={
                "ASK_DELISKY_PROVIDER": "local",
                "ASK_DELISKY_LOCAL_MODEL": "test-model",
                "ASK_DELISKY_LOCAL_BASE_URL": (
                    "http://127.0.0.1:11434/"
                ),
                "ASK_DELISKY_TIMEOUT_SECONDS": "45",
            }
        )

        self.assertEqual(
            config.mode,
            AskDeliskyProviderMode.LOCAL,
        )
        self.assertEqual(
            config.model_name,
            "test-model",
        )
        self.assertEqual(
            config.base_url,
            "http://127.0.0.1:11434",
        )
        self.assertEqual(
            config.timeout_seconds,
            45,
        )

    def test_local_configuration_requires_model(self):
        with self.assertRaisesRegex(
            ValueError,
            "model name cannot be empty",
        ):
            load_ask_delisky_provider_config(
                environ={
                    "ASK_DELISKY_PROVIDER": "local",
                }
            )

    def test_invalid_provider_mode_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must be 'disabled' or 'local'",
        ):
            load_ask_delisky_provider_config(
                environ={
                    "ASK_DELISKY_PROVIDER": "unknown",
                }
            )

    def test_non_loopback_local_endpoint_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must use a loopback host",
        ):
            load_ask_delisky_provider_config(
                environ={
                    "ASK_DELISKY_PROVIDER": "local",
                    "ASK_DELISKY_LOCAL_MODEL": "test-model",
                    "ASK_DELISKY_LOCAL_BASE_URL": (
                        "https://example.com"
                    ),
                }
            )

    def test_invalid_timeout_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must be an integer",
        ):
            load_ask_delisky_provider_config(
                environ={
                    "ASK_DELISKY_TIMEOUT_SECONDS": "abc",
                }
            )

    def test_credentials_in_local_url_are_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Credentials are not allowed",
        ):
            load_ask_delisky_provider_config(
                environ={
                    "ASK_DELISKY_PROVIDER": "local",
                    "ASK_DELISKY_LOCAL_MODEL": "test-model",
                    "ASK_DELISKY_LOCAL_BASE_URL": (
                        "http://user:secret@localhost:11434"
                    ),
                }
            )


    def test_local_endpoint_path_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot contain a path",
        ):
            load_ask_delisky_provider_config(
                environ={
                    "ASK_DELISKY_PROVIDER": "local",
                    "ASK_DELISKY_LOCAL_MODEL": "test-model",
                    "ASK_DELISKY_LOCAL_BASE_URL": (
                        "http://127.0.0.1:11434/api/generate"
                    ),
                }
            )

    def test_local_endpoint_query_or_fragment_is_rejected(
        self,
    ):
        invalid_urls = (
            "http://127.0.0.1:11434?token=test",
            "http://127.0.0.1:11434#fragment",
        )

        for invalid_url in invalid_urls:
            with self.subTest(
                invalid_url=invalid_url
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "cannot contain a query or fragment",
                ):
                    load_ask_delisky_provider_config(
                        environ={
                            "ASK_DELISKY_PROVIDER": "local",
                            "ASK_DELISKY_LOCAL_MODEL": (
                                "test-model"
                            ),
                            "ASK_DELISKY_LOCAL_BASE_URL": (
                                invalid_url
                            ),
                        }
                    )
