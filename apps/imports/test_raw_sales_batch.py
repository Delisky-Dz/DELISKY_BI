from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.fleet.models import Truck
from .models import ImportBatch, SourceTruckExclusion, SourceTruckMapping
from .services.approval_dispatch import approve_reviewed_batch
from .test_raw_sales_derived_review import SalesReviewFixtures


class SalesBatchWorkflowTests(SalesReviewFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.client.force_login(self.user)
        self.url = reverse("imports:raw_sales_upload")

    def upload(self, truck, key, date="18/08/2026"):
        name = truck + ".xlsx"
        rows = [[key, date + " 10:00:00", "Client A", 100, 100, "MILA", 100]]
        return self.make_upload(name, self.make_payload(filename=name, rows=rows))

    def validate(self, source, files):
        response = self.client.post(self.url, {
            "action": "validate", "source_system": source.pk, "period_start": "2026-08-01",
            "period_end": "2026-08-18", "files": files,
        })
        return response.context["sales_batch"]

    def execute(self, batch):
        return self.client.post(self.url, {"action": "import", "token": batch["token"]}).context["sales_batch"]

    def second_truck(self, source, first):
        truck = Truck.objects.create(
            internal_code=first.internal_code[:-2] + "09", distribution_brand=first.distribution_brand,
            registration_number="TEST-BATCH-09", brand="TEST", model="TEST",
        )
        SourceTruckMapping.objects.create(source_system=source, source_code="FUTURE", truck=truck)

    def test_bifa_ready_files_are_reviewed_then_approved_together(self):
        self.second_truck(self.bifa_source, self.bifa_truck)
        batch = self.validate(self.bifa_source, [self.upload("DCV-03", "VDD-1"), self.upload("FUTURE", "VDD-2")])
        self.assertEqual(batch["ready"], 2)
        self.assertFalse(ImportBatch.objects.filter(status="APPROVED").exists())
        self.assertEqual(self.execute(batch)["imported"], 2)
        self.assertEqual(self.execute(batch)["imported"], 0)
        duplicate = self.validate(self.bifa_source, [self.upload("DCV-03", "VDD-1")])
        self.assertEqual(duplicate["duplicate"], 1)

    def test_aio_partial_failure_rolls_back_one_file(self):
        self.second_truck(self.aio_source, self.delisky_truck)
        batch = self.validate(self.aio_source, [self.upload("VAN2-DELISKY", "VDD-3"), self.upload("FUTURE", "VDD-4")])
        self.assertEqual(batch["ready"], 2)
        fail_id = batch["rows"][1]["batch_id"]

        def fail_after_write(pk, **kwargs):
            result = approve_reviewed_batch(pk, **kwargs)
            if pk == fail_id:
                raise RuntimeError("injected failure")
            return result

        with patch("apps.imports.services.bulk_approval.approve_reviewed_batch", side_effect=fail_after_write):
            result = self.execute(batch)
        self.assertEqual([r["state"] for r in result["rows"]], ["IMPORTED", "FAILED"])
        self.assertEqual(ImportBatch.objects.get(pk=fail_id).status, "REVIEWED")

    def test_mixed_source_unknown_excluded_invalid_dates_and_duplicate(self):
        SourceTruckExclusion.objects.create(source_system=self.bifa_source, source_code="STORE")
        one = self.upload("DCV-03", "VDD-1")
        same = self.make_upload(one.name, one.read())
        one.seek(0)
        batch = self.validate(self.bifa_source, [
            self.upload("VAN2-DELISKY", "VDD-3"), self.upload("UNKNOWN", "VDD-4"),
            self.upload("STORE", "VDD-5"), self.make_upload("DCV-03.xlsx", b"invalid"),
            self.upload("DCV-03", "VDD-1", "19/08/2026"), one, same,
        ])
        self.assertEqual([r["state"] for r in batch["rows"]],
                         ["BLOCKED", "BLOCKED", "BLOCKED", "INVALID", "BLOCKED", "READY", "DUPLICATE"])
        self.assertIn("OUT_OF_SCOPE", batch["rows"][2]["note"])
        self.assertIn("2026-08-19", batch["rows"][4]["note"])
        result = self.execute(batch)
        self.assertEqual(len(result["rows"]), 7)
        self.assertEqual(result["imported"], 1)
