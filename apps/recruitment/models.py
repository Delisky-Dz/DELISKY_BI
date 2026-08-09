from django.conf import settings
from django.db import models


class ApplicationStatus(models.TextChoices):
    NEW = "NEW", "\u062c\u062f\u064a\u062f"
    REVIEWING = (
        "REVIEWING",
        "\u0642\u064a\u062f \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
    )
    CONTACTED = (
        "CONTACTED",
        "\u062a\u0645 \u0627\u0644\u062a\u0648\u0627\u0635\u0644",
    )
    ACCEPTED = "ACCEPTED", "\u0645\u0642\u0628\u0648\u0644"
    REJECTED = "REJECTED", "\u0645\u0631\u0641\u0648\u0636"


class MaritalStatus(models.TextChoices):
    SINGLE = "SINGLE", "\u0623\u0639\u0632\u0628"
    MARRIED = "MARRIED", "\u0645\u062a\u0632\u0648\u062c"
    DIVORCED = "DIVORCED", "\u0645\u0637\u0644\u0642"
    WIDOWED = "WIDOWED", "\u0623\u0631\u0645\u0644"


class RequestedPosition(models.TextChoices):
    SELLER = "SELLER", "\u0628\u0627\u0626\u0639"
    DRIVER = "DRIVER", "\u0633\u0627\u0626\u0642"
    DRIVER_SELLER = (
        "DRIVER_SELLER",
        "\u0633\u0627\u0626\u0642 \u0648\u0628\u0627\u0626\u0639",
    )
    WAREHOUSE_KEEPER = (
        "WAREHOUSE_KEEPER",
        "\u0623\u0645\u064a\u0646 \u0645\u062e\u0632\u0646",
    )
    ACCOUNTING_MANAGER = (
        "ACCOUNTING_MANAGER",
        "\u0645\u062f\u064a\u0631 \u062d\u0633\u0627\u0628\u0627\u062a",
    )
    SALES_MANAGER = (
        "SALES_MANAGER",
        "\u0645\u0633\u064a\u0631 \u0645\u0628\u064a\u0639\u0627\u062a",
    )
    SALES_SUPERVISOR = (
        "SALES_SUPERVISOR",
        "\u0645\u0634\u0631\u0641 \u0645\u0628\u064a\u0639\u0627\u062a",
    )


class JobApplication(models.Model):
    first_name = models.CharField(
        max_length=100,
    )
    last_name = models.CharField(
        max_length=100,
    )

    birth_date = models.DateField()

    marital_status = models.CharField(
        max_length=20,
        choices=MaritalStatus.choices,
    )
    children_count = models.PositiveSmallIntegerField(
        default=0,
    )

    phone = models.CharField(
        max_length=32,
    )
    email = models.EmailField(
        blank=True,
    )

    wilaya = models.CharField(
        max_length=120,
    )
    residence = models.CharField(
        max_length=180,
    )

    requested_position = models.CharField(
        max_length=32,
        choices=RequestedPosition.choices,
    )

    experience_years = models.PositiveSmallIntegerField(
        default=0,
    )

    previous_companies = models.TextField(
        blank=True,
    )

    has_driving_license = models.BooleanField(
        default=False,
    )
    driving_license_category = models.CharField(
        max_length=50,
        blank=True,
    )
    driving_experience_years = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    cv = models.FileField(
        upload_to="recruitment/cv/%Y/%m/",
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.NEW,
    )

    status_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recruitment_status_updates",
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "-submitted_at",
            "-id",
        )
        indexes = [
            models.Index(
                fields=[
                    "status",
                    "-submitted_at",
                ],
                name="recruit_status_sub_idx",
            ),
            models.Index(
                fields=[
                    "requested_position",
                    "-submitted_at",
                ],
                name="recruit_position_sub_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.first_name} {self.last_name}"
            f" - {self.get_requested_position_display()}"
        )

    @property
    def full_name(self):
        return (
            f"{self.first_name} {self.last_name}"
        ).strip()
