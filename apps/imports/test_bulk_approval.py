from io import BytesIO
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from openpyxl import Workbook

from apps.imports.models import DistributionBrand, ImportBatchStatus
from apps.imports.services.approval_dispatch import approve_reviewed_batch
from apps.imports.services.batch_review import create_or_update_import_review


class BulkAccountantApprovalTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_user(username="bulk-accountant", password="test")
        self.user.groups.add(Group.objects.create(name="Accountant"))
        self.other = get_user_model().objects.create_user(username="bulk-other", password="test")
        self.brand = DistributionBrand.objects.create(code="BIFA", name="BIFA")
        self.client.force_login(self.user)
        self.list_url = reverse("imports:batch_list")
        self.url = reverse("imports:approve_ready_batches")

    def batch(self, number, *, status=ImportBatchStatus.REVIEWED, errors=0):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["VAN", "Date&Heure", "Nom du client", "Total", "Region"])
        sheet.append(["BIFA LIV01", "27/08/2026 09:00:00", f"CLIENT {number}", number * 100, "MILA"])
        payload = BytesIO()
        workbook.save(payload)
        workbook.close()
        batch = create_or_update_import_review(
            SimpleUploadedFile("Sales_BIFA_2026-08-27_2026-10-22.xlsx", payload.getvalue()),
            uploaded_by=self.user,
        ).batch
        if status != batch.status or errors:
            batch.status, batch.error_count = status, errors
            batch.save()
        return batch

    def snapshot(self):
        return self.client.get(self.list_url).context["ready_snapshot"]

    def submit(self, token, **kwargs):
        return self.client.post(self.url, {"ready_snapshot": token, "confirm": "yes"}, **kwargs)

    def test_accountant_approves_visible_ready_set_and_refreshes_counts(self):
        first, second = self.batch(1), self.batch(2)
        page = self.client.get(self.list_url)
        self.assertContains(page, "اعتماد 2 دفعة جاهزة")
        self.assertEqual(page.context["ready_count"], 2)
        self.assertEqual(page.context["status_counts"]["APPROVED"], 0)
        result = self.submit(page.context["ready_snapshot"], follow=True)
        self.assertContains(result, "2 نجحت / 0 فشلت")
        self.assertEqual(result.context["ready_count"], 0)
        self.assertEqual(result.context["status_counts"]["APPROVED"], 2)
        for batch in (first, second):
            batch.refresh_from_db()
            self.assertEqual(batch.status, "APPROVED")
            self.assertEqual(batch.approved_by_id, self.user.pk)

    def test_confirmation_lists_exact_scope_without_approving(self):
        batch = self.batch(1)
        response = self.client.post(self.url, {"ready_snapshot": self.snapshot()})
        self.assertContains(response, "سيتم اعتماد 1 دفعة جاهزة. هل تريد المتابعة؟")
        for text in ("BIFA", "2026-08-27", "2026-10-22"):
            self.assertContains(response, text)
        self.assertContains(response, 'name="confirm" value="yes"')
        batch.refresh_from_db()
        self.assertEqual(batch.status, "REVIEWED")

    def test_unauthorized_and_anonymous_cannot_approve(self):
        self.batch(1)
        token = self.snapshot()
        self.client.force_login(self.other)
        self.assertEqual(self.submit(token).status_code, 403)
        self.client.logout()
        self.assertEqual(self.submit(token).status_code, 302)

    def test_get_is_not_an_approval_action(self):
        self.batch(1)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_non_ready_statuses_and_blockers_are_not_submitted(self):
        ready = self.batch(1)
        excluded = [self.batch(i, status=status) for i, status in enumerate(
            ["APPROVED", "BLOCKED", "REJECTED", "SUPERSEDED", "PENDING", "FAILED"], 2,
        )]
        excluded.append(self.batch(8, errors=1))
        response = self.submit(self.snapshot(), follow=True)
        self.assertEqual(response.context["bulk_approval_result"]["succeeded_ids"], [ready.pk])
        for batch in excluded:
            old_status = batch.status
            batch.refresh_from_db()
            self.assertEqual(batch.status, old_status)

    def test_new_ready_batch_after_page_load_is_not_included(self):
        first = self.batch(1)
        token = self.snapshot()
        later = self.batch(2)
        self.submit(token)
        first.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(first.status, "APPROVED")
        self.assertEqual(later.status, "REVIEWED")

    def test_changed_status_or_review_version_is_never_forced(self):
        first, second = self.batch(1), self.batch(2)
        token = self.snapshot()
        first.status = "BLOCKED"
        first.save()
        second.review_summary["review_note"] = "review changed"
        second.save()
        response = self.submit(token, follow=True)
        self.assertContains(response, "0 نجحت / 2 فشلت")
        self.assertContains(response, f"دفعة #{first.pk}")
        self.assertContains(response, "تغيرت الدفعة")
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.status, second.status), ("BLOCKED", "REVIEWED"))

    def test_existing_domain_row_validation_is_not_bypassed(self):
        broken, valid = self.batch(1), self.batch(2)
        token = self.snapshot()
        broken.rows.all().delete()
        response = self.submit(token, follow=True)
        self.assertContains(response, "1 نجحت / 1 فشلت")
        broken.refresh_from_db()
        valid.refresh_from_db()
        self.assertEqual((broken.status, valid.status), ("REVIEWED", "APPROVED"))

    def test_same_status_new_review_revision_is_rejected_at_full_precision(self):
        batch = self.batch(1)
        batch.updated_at = batch.updated_at.replace(microsecond=100000)
        type(batch).objects.filter(pk=batch.pk).update(updated_at=batch.updated_at)
        token = self.snapshot()
        type(batch).objects.filter(pk=batch.pk).update(updated_at=batch.updated_at + timedelta(microseconds=1))
        response = self.submit(token, follow=True)
        self.assertContains(response, "0 نجحت / 1 فشلت")
        batch.refresh_from_db()
        self.assertEqual(batch.status, "REVIEWED")

    def test_per_batch_failure_rolls_back_and_other_batches_continue(self):
        broken, valid = self.batch(1), self.batch(2)
        token = self.snapshot()
        def approve(batch_id, *, approved_by):
            if batch_id == broken.pk:
                broken.status = "APPROVED"
                broken.save()
                raise RuntimeError("simulated failure after write")
            return approve_reviewed_batch(batch_id, approved_by=approved_by)
        with patch("apps.imports.services.bulk_approval.approve_reviewed_batch", side_effect=approve):
            with self.assertLogs("apps.imports.services.bulk_approval", level="ERROR"):
                response = self.submit(token, follow=True)
        self.assertContains(response, "1 نجحت / 1 فشلت")
        broken.refresh_from_db()
        valid.refresh_from_db()
        self.assertEqual((broken.status, valid.status), ("REVIEWED", "APPROVED"))

    def test_replayed_post_does_not_approve_or_generate_again(self):
        first, second = self.batch(1), self.batch(2)
        token = self.snapshot()
        with patch("apps.imports.services.bulk_approval.approve_reviewed_batch", wraps=approve_reviewed_batch) as service:
            self.submit(token)
            response = self.submit(token, follow=True)
        self.assertEqual(service.call_count, 2)
        self.assertContains(response, "0 نجحت / 2 فشلت")
        self.assertEqual(first.rows.count() + second.rows.count(), 2)

    def test_zero_ready_batches_is_safe(self):
        response = self.submit(self.snapshot(), follow=True)
        self.assertContains(response, "0 نجحت / 0 فشلت")
        self.assertNotContains(response, "تأكيد اعتماد")
        self.assertContains(response, "اعتماد 0 دفعة جاهزة")
        self.assertContains(response, 'type="submit" disabled', html=False)

    def test_snapshot_cannot_be_tampered_expired_or_used_by_another_accountant(self):
        self.batch(1)
        token = self.snapshot()
        self.assertEqual(self.submit(token + "tamper").status_code, 400)
        with patch("apps.imports.services.bulk_approval.SNAPSHOT_MAX_AGE", -1):
            self.assertEqual(self.submit(token).status_code, 400)
        self.other.groups.add(Group.objects.get(name="Accountant"))
        self.client.force_login(self.other)
        self.assertEqual(self.submit(token).status_code, 400)

    def test_csrf_required_for_both_confirmation_and_execution(self):
        self.batch(1)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        page = client.get(self.list_url)
        token = page.context["ready_snapshot"]
        for data in ({"ready_snapshot": token}, {"ready_snapshot": token, "confirm": "yes"}):
            self.assertEqual(client.post(self.url, data).status_code, 403)
        csrf = client.cookies["csrftoken"].value
        response = client.post(self.url, {"ready_snapshot": token, "confirm": "yes", "csrfmiddlewaretoken": csrf}, follow=True)
        self.assertContains(response, "1 نجحت / 0 فشلت")

    def test_pagination_does_not_hide_any_of_the_confirmed_ready_set(self):
        ready = self.batch(1)
        for number in range(2, 22):
            self.batch(number, status="APPROVED")
        response = self.client.get(self.list_url, {"page": 1})
        self.assertNotIn(ready.pk, [batch.pk for batch in response.context["recent_batches"]])
        self.assertEqual([batch.pk for batch in response.context["ready_batches"]], [ready.pk])
        self.assertContains(response, "عبر جميع صفحات السجل")
        result = self.submit(response.context["ready_snapshot"], follow=True)
        self.assertEqual(result.context["bulk_approval_result"]["succeeded_ids"], [ready.pk])
