import json
from threading import Event
from time import monotonic
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.test import Client, SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.assistant import streaming
from apps.assistant.contracts import AskDeliskyResponse
from apps.assistant.models import AskDeliskyAuditEvent, AskDeliskyAuditOutcome
from apps.assistant.ollama_transport import OllamaTransportError
from apps.assistant.provider_factory import (
    AskDeliskyProviderConfigurationError, AskDeliskyProviderDisabledError,
)
from apps.assistant.rate_limit import AskDeliskyRateLimitResult


class StreamTransportTests(SimpleTestCase):
    def test_ack_heartbeats_bounded_capacity_and_disconnect(self):
        finish = Event()
        entered = Event()

        def execute():
            entered.set()
            finish.wait(5)
            return JsonResponse({"ok": True, "answer": "not retained"})

        with patch.object(streaming, 'HEARTBEAT_SECONDS', 0.01):
            response = streaming.stream_ask_response(execute, on_failure=lambda: None)
            try:
                iterator = iter(response.streaming_content)
                start = monotonic()
                self.assertIn(b'event: accepted', next(iterator))
                self.assertLess(monotonic() - start, 0.2)
                self.assertTrue(entered.wait(1))
                self.assertIn(b'event: progress', next(iterator))
                self.assertIsNone(streaming.stream_ask_response(execute, on_failure=lambda: None))
                response.close()
                # Refresh cannot release a running computation's capacity.
                self.assertIsNone(streaming.stream_ask_response(execute, on_failure=lambda: None))
            finally:
                finish.set()
                response._iterator._thread.join(5)
                response.close()
            self.assertTrue(response._iterator._results.empty())

    def test_unconsumed_response_close_discards_result(self):
        response = streaming.stream_ask_response(
            lambda: JsonResponse({'ok': True, 'answer': 'secret'}), on_failure=lambda: None,
        )
        response._iterator._thread.join(5)
        response.close()
        self.assertTrue(response._iterator._results.empty())

    def test_stream_deadline_reports_error_and_retains_computation_slot(self):
        finish = Event()
        response = streaming.stream_ask_response(
            lambda: (finish.wait(5), JsonResponse({'ok': True}))[1], on_failure=lambda: None,
        )
        try:
            with patch.object(streaming, 'STREAM_LIMIT_SECONDS', -1):
                iterator = iter(response.streaming_content)
                next(iterator)
                self.assertIn(b'STREAM_TIMEOUT', next(iterator))
                self.assertIsNone(streaming.stream_ask_response(lambda: None, on_failure=lambda: None))
        finally:
            finish.set()
            response._iterator._thread.join(5)
            response.close()


@override_settings(ASK_DELISKY_STREAMING_ENABLED=True)
class AskStreamingApiTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='stream_manager')
        self.user.groups.add(Group.objects.get_or_create(name='Manager')[0])
        self.client.force_login(self.user)
        self.url = reverse('dashboard:ask_delisky')
        self.data = {'question': 'Analyze', 'period_start': '2026-04-04', 'period_end': '2026-08-26'}

    def consume(self, response):
        try:
            body = b''.join(response.streaming_content).decode()
            frames = [json.loads(f.split('data: ', 1)[1]) for f in body.strip().split('\n\n')]
            return frames[-1]
        finally:
            response.close()

    @patch('apps.dashboard.views.ask_manager_delisky')
    def test_success_and_second_question_invoke_provider_again_and_audit(self, runtime):
        runtime.return_value = AskDeliskyResponse(answer='الدليل والقيود', provider_name='local', model_name='qwen3:4b-instruct', context_schema_version='v2')
        for question in ['Analyze', 'Another question']:
            response = self.client.post(self.url, dict(self.data, question=question))
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/event-stream', response['Content-Type'])
            self.assertIn('no-store', response['Cache-Control'])
            payload = self.consume(response)
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['answer'], 'الدليل والقيود')
        self.assertEqual(runtime.call_count, 2)
        self.assertEqual(AskDeliskyAuditEvent.objects.filter(outcome=AskDeliskyAuditOutcome.SUCCESS).count(), 2)
        self.assertNotIn('answer', {field.name for field in AskDeliskyAuditEvent._meta.fields})

    @patch('apps.dashboard.views.ask_manager_delisky')
    def test_provider_errors_are_terminal_events_with_failure_audit(self, runtime):
        for error, outcome in [
            (OllamaTransportError('private detail'), AskDeliskyAuditOutcome.PROVIDER_UNAVAILABLE),
            (AskDeliskyProviderDisabledError('private detail'), AskDeliskyAuditOutcome.PROVIDER_DISABLED),
            (AskDeliskyProviderConfigurationError('private detail'), AskDeliskyAuditOutcome.PROVIDER_CONFIGURATION_ERROR),
        ]:
            with self.subTest(outcome=outcome):
                runtime.side_effect = error
                payload = self.consume(self.client.post(self.url, self.data))
                self.assertFalse(payload['ok'])
                self.assertEqual(payload['status'], 503)
                self.assertNotIn('private detail', json.dumps(payload))
                audit = AskDeliskyAuditEvent.objects.latest('pk')
                self.assertEqual(audit.outcome, outcome)
                self.assertEqual(audit.http_status, 503)

    @patch('apps.dashboard.views.ask_manager_delisky', side_effect=RuntimeError('private detail'))
    def test_unexpected_failure_is_safe_and_audited(self, runtime):
        payload = self.consume(self.client.post(self.url, self.data))
        self.assertFalse(payload['ok'])
        self.assertNotIn('private detail', json.dumps(payload))
        self.assertEqual(AskDeliskyAuditEvent.objects.get().outcome, AskDeliskyAuditOutcome.PROVIDER_UNAVAILABLE)

    @patch('apps.dashboard.views.ask_manager_delisky')
    def test_invalid_form_and_rate_limit_remain_short_json_responses(self, runtime):
        response = self.client.post(self.url, dict(self.data, question=''))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.streaming)
        with patch('apps.dashboard.views.check_ask_delisky_rate_limit', return_value=AskDeliskyRateLimitResult(allowed=False, retry_after_seconds=30)):
            response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '30')
        runtime.assert_not_called()
        self.assertEqual(AskDeliskyAuditEvent.objects.count(), 2)

    @patch('apps.dashboard.views.ask_manager_delisky')
    def test_busy_returns_short_response_and_is_audited(self, runtime):
        with patch('apps.dashboard.views.stream_ask_response', return_value=None):
            response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response['Retry-After'], '10')
        runtime.assert_not_called()
        self.assertEqual(AskDeliskyAuditEvent.objects.get().http_status, 503)

    @patch('apps.dashboard.views.ask_manager_delisky')
    def test_authentication_and_role_blocks(self, runtime):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        for group, superuser in [('Accountant', False), ('Super Admin', False), ('Manager', True)]:
            with self.subTest(group=group, superuser=superuser):
                self.user.groups.clear()
                self.user.groups.add(Group.objects.get_or_create(name=group)[0])
                self.user.is_superuser = superuser
                self.user.save()
                self.client.force_login(self.user)
                self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.user.is_superuser = False
        self.user.save()
        self.user.groups.add(Group.objects.get(name='Accountant'))
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        runtime.assert_not_called()

    @patch('apps.dashboard.views.ask_manager_delisky')
    def test_csrf_is_required(self, runtime):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, self.data).status_code, 403)
        runtime.assert_not_called()
