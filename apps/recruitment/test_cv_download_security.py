import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import JobApplication


class RecruitmentCvDownloadSuccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        accountant_group, _ = (
            Group.objects.get_or_create(
                name="Accountant"
            )
        )

        cls.accountant = (
            user_model.objects.create_user(
                username="cv-download-accountant",
                password="test-password-123",
            )
        )

        cls.accountant.groups.add(
            accountant_group
        )

        cls.application = (
            JobApplication.objects.create(
                first_name="CV",
                last_name="Download",
                birth_date="1995-01-10",
                marital_status="SINGLE",
                children_count=0,
                phone="+213660000098",
                wilaya="Constantine",
                residence="Constantine",
                requested_position="SELLER",
                experience_years=2,
            )
        )

    def test_accountant_can_download_existing_cv(
        self,
    ):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(
                MEDIA_ROOT=media_root
            ):
                application = (
                    JobApplication.objects.get(
                        pk=self.application.pk
                    )
                )

                application.cv.save(
                    "security-test.pdf",
                    SimpleUploadedFile(
                        "security-test.pdf",
                        (
                            b"%PDF-1.4\n"
                            b"DELISKY CV TEST\n"
                            b"%%EOF\n"
                        ),
                        content_type=(
                            "application/pdf"
                        ),
                    ),
                    save=True,
                )

                self.client.force_login(
                    self.accountant
                )

                response = self.client.get(
                    reverse(
                        "recruitment_accountant:"
                        "download_cv",
                        args=[application.pk],
                    )
                )

                self.assertEqual(
                    response.status_code,
                    200,
                )

                self.assertEqual(
                    response["Content-Type"],
                    "application/pdf",
                )

                self.assertIn(
                    "attachment",
                    response[
                        "Content-Disposition"
                    ],
                )

                self.assertIn(
                    "security-test.pdf",
                    response[
                        "Content-Disposition"
                    ],
                )

                content = b"".join(
                    response.streaming_content
                )

                self.assertTrue(
                    content.startswith(
                        b"%PDF-"
                    )
                )
