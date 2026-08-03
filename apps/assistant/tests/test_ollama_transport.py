import json
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.assistant.ollama_transport import (
    OllamaTransport,
    OllamaTransportError,
    _RejectRedirectHandler,
)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False


class FakeOpener:
    def __init__(
        self,
        *,
        response=None,
        error=None,
    ):
        self.response = response
        self.error = error
        self.request = None
        self.timeout = None

    def open(
        self,
        request,
        *,
        timeout,
    ):
        self.request = request
        self.timeout = timeout

        if self.error is not None:
            raise self.error

        return self.response


class OllamaTransportTests(SimpleTestCase):
    def make_transport(self):
        return OllamaTransport()

    def test_generate_uses_generate_endpoint(self):
        opener = FakeOpener(
            response=FakeResponse(
                b'{"response":"result","done":true}'
            )
        )

        with patch(
            "apps.assistant.ollama_transport.build_opener",
            return_value=opener,
        ):
            answer = self.make_transport().generate(
                base_url="http://127.0.0.1:11434",
                model_name="test-model",
                timeout_seconds=30,
                system_prompt="System rules",
                user_prompt="Analyze results",
            )

        self.assertEqual(
            answer,
            "result",
        )

        self.assertEqual(
            opener.request.full_url,
            "http://127.0.0.1:11434/api/generate",
        )

        self.assertEqual(
            opener.timeout,
            30,
        )

        payload = json.loads(
            opener.request.data.decode("utf-8")
        )

        self.assertEqual(
            payload,
            {
                "model": "test-model",
                "system": "System rules",
                "prompt": "Analyze results",
                "stream": False,
                "keep_alive": "5m",
                "options": {
                    "temperature": 0.2,
                    "num_predict": 96,
                },
            },
        )

    def test_custom_num_predict_is_used(self):
        opener = FakeOpener(
            response=FakeResponse(
                b'{"response":"result","done":true}'
            )
        )

        transport = OllamaTransport(
            num_predict=192
        )

        with patch(
            "apps.assistant.ollama_transport.build_opener",
            return_value=opener,
        ):
            answer = transport.generate(
                base_url="http://127.0.0.1:11434",
                model_name="test-model",
                timeout_seconds=30,
                system_prompt="System rules",
                user_prompt="Give commercial advice",
            )

        self.assertEqual(
            answer,
            "result",
        )

        payload = json.loads(
            opener.request.data.decode("utf-8")
        )

        self.assertEqual(
            payload["options"]["num_predict"],
            192,
        )

    def test_invalid_num_predict_is_rejected(self):
        invalid_values = (
            0,
            -1,
            513,
            True,
            "192",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    OllamaTransport(
                        num_predict=value
                    )

    def test_proxy_is_disabled_and_redirects_are_blocked(
        self,
    ):
        opener = FakeOpener(
            response=FakeResponse(
                b'{"response":"answer"}'
            )
        )

        with patch(
            "apps.assistant.ollama_transport.build_opener",
            return_value=opener,
        ) as builder:
            self.make_transport().generate(
                base_url="http://localhost:11434",
                model_name="test-model",
                timeout_seconds=30,
                system_prompt="system",
                user_prompt="question",
            )

        self.assertEqual(
            builder.call_args.args[0].proxies,
            {},
        )

        self.assertIsInstance(
            builder.call_args.args[1],
            _RejectRedirectHandler,
        )

    def test_redirect_handler_rejects_redirects(self):
        handler = _RejectRedirectHandler()

        with self.assertRaisesRegex(
            OllamaTransportError,
            "redirects are not allowed",
        ):
            handler.redirect_request(
                None,
                None,
                302,
                "Found",
                {},
                "https://example.com",
            )

    def test_non_loopback_endpoint_is_rejected_before_network(
        self,
    ):
        with patch(
            "apps.assistant.ollama_transport.build_opener",
        ) as builder:
            with self.assertRaisesRegex(
                ValueError,
                "must use a loopback host",
            ):
                self.make_transport().generate(
                    base_url="https://example.com",
                    model_name="test-model",
                    timeout_seconds=30,
                    system_prompt="system",
                    user_prompt="question",
                )

        builder.assert_not_called()

    def test_unsafe_local_url_parts_are_rejected(self):
        invalid_urls = (
            "http://user:secret@localhost:11434",
            "http://127.0.0.1:11434/api",
            "http://127.0.0.1:11434?x=1",
            "http://127.0.0.1:11434#fragment",
        )

        for invalid_url in invalid_urls:
            with self.subTest(
                invalid_url=invalid_url
            ):
                with self.assertRaises(ValueError):
                    self.make_transport().generate(
                        base_url=invalid_url,
                        model_name="test-model",
                        timeout_seconds=30,
                        system_prompt="system",
                        user_prompt="question",
                    )

    def test_http_error_is_normalized(self):
        error = HTTPError(
            url=(
                "http://127.0.0.1:11434/"
                "api/generate"
            ),
            code=500,
            msg="error",
            hdrs=None,
            fp=None,
        )

        opener = FakeOpener(
            error=error
        )

        with patch(
            "apps.assistant.ollama_transport.build_opener",
            return_value=opener,
        ):
            with self.assertRaisesRegex(
                OllamaTransportError,
                "HTTP status 500",
            ):
                self.make_transport().generate(
                    base_url="http://127.0.0.1:11434",
                    model_name="test-model",
                    timeout_seconds=30,
                    system_prompt="system",
                    user_prompt="question",
                )

    def test_connection_error_is_normalized(self):
        opener = FakeOpener(
            error=URLError(
                "connection refused"
            )
        )

        with patch(
            "apps.assistant.ollama_transport.build_opener",
            return_value=opener,
        ):
            with self.assertRaisesRegex(
                OllamaTransportError,
                "Could not connect",
            ):
                self.make_transport().generate(
                    base_url="http://127.0.0.1:11434",
                    model_name="test-model",
                    timeout_seconds=30,
                    system_prompt="system",
                    user_prompt="question",
                )

    def test_invalid_json_is_rejected(self):
        opener = FakeOpener(
            response=FakeResponse(
                b"not-json"
            )
        )

        with patch(
            "apps.assistant.ollama_transport.build_opener",
            return_value=opener,
        ):
            with self.assertRaisesRegex(
                OllamaTransportError,
                "invalid JSON",
            ):
                self.make_transport().generate(
                    base_url="http://127.0.0.1:11434",
                    model_name="test-model",
                    timeout_seconds=30,
                    system_prompt="system",
                    user_prompt="question",
                )

    def test_error_payload_is_rejected(self):
        opener = FakeOpener(
            response=FakeResponse(
                b'{"error":"model not found"}'
            )
        )

        with patch(
            "apps.assistant.ollama_transport.build_opener",
            return_value=opener,
        ):
            with self.assertRaisesRegex(
                OllamaTransportError,
                "error response",
            ):
                self.make_transport().generate(
                    base_url="http://127.0.0.1:11434",
                    model_name="test-model",
                    timeout_seconds=30,
                    system_prompt="system",
                    user_prompt="question",
                )

    def test_missing_response_text_is_rejected(self):
        invalid_payloads = (
            b'{"done":true}',
            b'{"response":null}',
            b'{"response":"   "}',
        )

        for body in invalid_payloads:
            with self.subTest(body=body):
                opener = FakeOpener(
                    response=FakeResponse(body)
                )

                with patch(
                    "apps.assistant.ollama_transport.build_opener",
                    return_value=opener,
                ):
                    with self.assertRaises(
                        OllamaTransportError
                    ):
                        self.make_transport().generate(
                            base_url=(
                                "http://127.0.0.1:11434"
                            ),
                            model_name="test-model",
                            timeout_seconds=30,
                            system_prompt="system",
                            user_prompt="question",
                        )

    def test_invalid_generation_inputs_are_rejected(self):
        invalid_cases = (
            {
                "model_name": " ",
                "timeout_seconds": 30,
                "system_prompt": "system",
                "user_prompt": "question",
            },
            {
                "model_name": "model",
                "timeout_seconds": 0,
                "system_prompt": "system",
                "user_prompt": "question",
            },
            {
                "model_name": "model",
                "timeout_seconds": 30,
                "system_prompt": " ",
                "user_prompt": "question",
            },
            {
                "model_name": "model",
                "timeout_seconds": 30,
                "system_prompt": "system",
                "user_prompt": " ",
            },
        )

        for case in invalid_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    self.make_transport().generate(
                        base_url=(
                            "http://127.0.0.1:11434"
                        ),
                        **case,
                    )
