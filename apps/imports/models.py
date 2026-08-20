from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower


brand_code_validator = RegexValidator(
    regex=r"^[A-Z0-9][A-Z0-9_-]*$",
    message=(
        "\u064a\u062c\u0628 \u0623\u0646 \u064a\u0628\u062f\u0623 "
        "\u0627\u0644\u0631\u0645\u0632 \u0628\u062d\u0631\u0641 "
        "\u0623\u0648 \u0631\u0642\u0645\u060c \u0648\u064a\u062d\u062a\u0648\u064a "
        "\u0641\u0642\u0637 \u0639\u0644\u0649 \u062d\u0631\u0648\u0641 "
        "\u0625\u0646\u062c\u0644\u064a\u0632\u064a\u0629 \u0643\u0628\u064a\u0631\u0629\u060c "
        "\u0623\u0631\u0642\u0627\u0645\u060c \u0634\u0631\u0637\u0629 "
        "\u0623\u0648 \u0634\u0631\u0637\u0629 \u0633\u0641\u0644\u064a\u0629."
    ),
)



sha256_validator = RegexValidator(
    regex=r"^[0-9a-fA-F]{64}$",
    message=(
        "\u064a\u062c\u0628 \u0623\u0646 \u062a\u062a\u0643\u0648\u0646 "
        "\u0628\u0635\u0645\u0629 SHA-256 \u0645\u0646 64 "
        "\u062d\u0631\u0641\u064b\u0627 \u0633\u062f\u0627\u0633\u064a\u064b\u0627."
    ),
)


class ImportReportType(models.TextChoices):
    OPENING_STOCK = (
        "OPENING_STOCK",
        "\u0627\u0644\u0645\u062e\u0632\u0648\u0646 \u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a",
    )
    CHARGEMENT = (
        "CHARGEMENT",
        "\u0627\u0644\u062a\u062d\u0645\u064a\u0644",
    )
    SALES = (
        "SALES",
        "\u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a",
    )
    ITEMS = (
        "ITEMS",
        "\u062a\u0641\u0627\u0635\u064a\u0644 \u0627\u0644\u0645\u0646\u062a\u062c\u0627\u062a",
    )
    POS = (
        "POS",
        "\u0646\u0642\u0627\u0637 \u0627\u0644\u0628\u064a\u0639 \u0648\u0627\u0644\u0632\u064a\u0627\u0631\u0627\u062a",
    )


class ImportBatchStatus(models.TextChoices):
    PENDING = (
        "PENDING",
        "\u0641\u064a \u0627\u0646\u062a\u0638\u0627\u0631 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
    )
    REVIEWED = (
        "REVIEWED",
        "\u062a\u0645\u062a \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
    )
    BLOCKED = (
        "BLOCKED",
        "\u0645\u0631\u0641\u0648\u0636 \u0628\u0633\u0628\u0628 \u0623\u062e\u0637\u0627\u0621",
    )
    APPROVED = (
        "APPROVED",
        "\u0645\u0639\u062a\u0645\u062f",
    )
    SUPERSEDED = (
        "SUPERSEDED",
        "\u0645\u0633\u062a\u0628\u062f\u0644 \u0628\u062f\u0641\u0639\u0629 \u0623\u062d\u062f\u062b",
    )
    FAILED = (
        "FAILED",
        "\u0641\u0634\u0644\u062a \u0627\u0644\u0639\u0645\u0644\u064a\u0629",
    )


class DistributionBrand(models.Model):
    code = models.CharField(
        "\u0631\u0645\u0632 \u0627\u0644\u0635\u0646\u0641",
        max_length=30,
        validators=[brand_code_validator],
        help_text=(
            "\u0631\u0645\u0632 \u0645\u062e\u062a\u0635\u0631 "
            "\u0648\u0641\u0631\u064a\u062f \u0645\u062b\u0644 "
            "BIFA \u0623\u0648 NITA."
        ),
    )
    name = models.CharField(
        "\u0627\u0633\u0645 \u0627\u0644\u0635\u0646\u0641",
        max_length=120,
        help_text=(
            "\u0627\u0644\u0627\u0633\u0645 \u0627\u0644\u0630\u064a "
            "\u064a\u0638\u0647\u0631 \u0644\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u064a\u0646."
        ),
    )
    is_active = models.BooleanField(
        "\u0646\u0634\u0637",
        default=True,
        db_index=True,
        help_text=(
            "\u0623\u0644\u063a\u0650 \u0627\u0644\u062a\u062d\u062f\u064a\u062f "
            "\u0644\u0625\u064a\u0642\u0627\u0641 \u0627\u0644\u0635\u0646\u0641 "
            "\u062f\u0648\u0646 \u062d\u0630\u0641 \u0628\u064a\u0627\u0646\u0627\u062a\u0647 "
            "\u0627\u0644\u062a\u0627\u0631\u064a\u062e\u064a\u0629."
        ),
    )
    notes = models.TextField(
        "\u0645\u0644\u0627\u062d\u0638\u0627\u062a",
        blank=True,
    )
    created_at = models.DateTimeField(
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0625\u0646\u0634\u0627\u0621",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "\u0622\u062e\u0631 \u062a\u0639\u062f\u064a\u0644",
        auto_now=True,
    )

    class Meta:
        verbose_name = "\u0635\u0646\u0641 \u062a\u062c\u0627\u0631\u064a"
        verbose_name_plural = "\u0627\u0644\u0623\u0635\u0646\u0627\u0641 \u0627\u0644\u062a\u062c\u0627\u0631\u064a\u0629"
        ordering = ["name", "code"]

        indexes = [
            models.Index(
                Lower("name"),
                name="dist_brand_name_ci_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                Lower("code"),
                name="dist_brand_code_ci_uniq",
                violation_error_message=(
                    "\u064a\u0648\u062c\u062f \u0635\u0646\u0641 "
                    "\u0622\u062e\u0631 \u064a\u0633\u062a\u0639\u0645\u0644 "
                    "\u0646\u0641\u0633 \u0627\u0644\u0631\u0645\u0632."
                ),
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if self.code:
            self.code = self.code.strip().upper()

        if self.name:
            self.name = " ".join(self.name.split())

        if not self.code:
            errors["code"] = (
                "\u0631\u0645\u0632 \u0627\u0644\u0635\u0646\u0641 "
                "\u0645\u0637\u0644\u0648\u0628."
            )

        if not self.name:
            errors["name"] = (
                "\u0627\u0633\u0645 \u0627\u0644\u0635\u0646\u0641 "
                "\u0645\u0637\u0644\u0648\u0628."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()

        if self.name:
            self.name = " ".join(self.name.split())

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} \u2014 {self.name}"



class ImportSourceSystem(models.Model):
    code = models.CharField(
        max_length=40,
    )
    name = models.CharField(
        max_length=120,
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )
    notes = models.TextField(
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name", "code"]

        constraints = [
            models.UniqueConstraint(
                Lower("code"),
                name="import_source_system_code_ci_uniq",
                violation_error_message=(
                    "\u064a\u0648\u062c\u062f "
                    "\u0646\u0638\u0627\u0645 "
                    "\u0645\u0635\u062f\u0631 "
                    "\u0622\u062e\u0631 "
                    "\u064a\u0633\u062a\u0639\u0645\u0644 "
                    "\u0646\u0641\u0633 "
                    "\u0627\u0644\u0631\u0645\u0632."
                ),
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if self.code:
            self.code = self.code.strip().upper()

        if self.name:
            self.name = " ".join(
                self.name.split()
            )

        if not self.code:
            errors["code"] = (
                "\u0631\u0645\u0632 "
                "\u0646\u0638\u0627\u0645 "
                "\u0627\u0644\u0645\u0635\u062f\u0631 "
                "\u0645\u0637\u0644\u0648\u0628."
            )

        if not self.name:
            errors["name"] = (
                "\u0627\u0633\u0645 "
                "\u0646\u0638\u0627\u0645 "
                "\u0627\u0644\u0645\u0635\u062f\u0631 "
                "\u0645\u0637\u0644\u0648\u0628."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()

        if self.name:
            self.name = " ".join(
                self.name.split()
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class ImportSourceUpload(models.Model):
    source_system = models.ForeignKey(
        ImportSourceSystem,
        on_delete=models.PROTECT,
        related_name="source_uploads",
    )
    source_file = models.FileField(
        upload_to="imports/raw/%Y/%m/",
        blank=True,
    )
    original_filename = models.CharField(
        max_length=255,
    )
    worksheet_name = models.CharField(
        max_length=255,
        blank=True,
    )
    file_size_bytes = models.PositiveBigIntegerField(
        default=0,
    )
    file_sha256 = models.CharField(
        max_length=64,
        validators=[sha256_validator],
        db_index=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_import_sources",
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-uploaded_at", "-id"]

        constraints = [
            models.UniqueConstraint(
                fields=["file_sha256"],
                name="import_source_upload_file_sha_uniq",
                violation_error_message=(
                    "\u0633\u0628\u0642 \u0631\u0641\u0639 \u0646\u0641\u0633 "
                    "\u0627\u0644\u0645\u0644\u0641 \u0627\u0644\u062e\u0627\u0645."
                ),
            ),
        ]

    def save(self, *args, **kwargs):
        if self.original_filename:
            self.original_filename = (
                self.original_filename.strip()
            )

        if self.worksheet_name:
            self.worksheet_name = (
                self.worksheet_name.strip()
            )

        if self.file_sha256:
            self.file_sha256 = (
                self.file_sha256.lower()
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.source_system.code} - "
            f"{self.original_filename}"
        )


class SourceTruckMapping(models.Model):
    source_system = models.ForeignKey(
        ImportSourceSystem,
        on_delete=models.PROTECT,
        related_name="truck_mappings",
    )
    source_code = models.CharField(
        max_length=120,
    )
    truck = models.ForeignKey(
        "fleet.Truck",
        on_delete=models.PROTECT,
        related_name="source_mappings",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )
    notes = models.TextField(
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "source_system__code",
            "source_code",
        ]

        constraints = [
            models.UniqueConstraint(
                F("source_system"),
                Lower("source_code"),
                name="source_truck_map_source_code_ci_uniq",
                violation_error_message=(
                    "\u064a\u0648\u062c\u062f "
                    "\u0631\u0628\u0637 "
                    "\u0622\u062e\u0631 "
                    "\u0644\u0646\u0641\u0633 "
                    "\u0643\u0648\u062f "
                    "\u0627\u0644\u0634\u0627\u062d\u0646\u0629 "
                    "\u062f\u0627\u062e\u0644 "
                    "\u0646\u0638\u0627\u0645 "
                    "\u0627\u0644\u0645\u0635\u062f\u0631 "
                    "\u0646\u0641\u0633\u0647."
                ),
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if self.source_code:
            self.source_code = " ".join(
                self.source_code.split()
            ).upper()

        if not self.source_code:
            errors["source_code"] = (
                "\u0643\u0648\u062f "
                "\u0627\u0644\u0634\u0627\u062d\u0646\u0629 "
                "\u0641\u064a "
                "\u0646\u0638\u0627\u0645 "
                "\u0627\u0644\u0645\u0635\u062f\u0631 "
                "\u0645\u0637\u0644\u0648\u0628."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.source_code:
            self.source_code = " ".join(
                self.source_code.split()
            ).upper()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.source_system.code}: "
            f"{self.source_code} -> {self.truck}"
        )


class ImportBatch(models.Model):
    source_upload = models.ForeignKey(
        ImportSourceUpload,
        on_delete=models.PROTECT,
        related_name="derived_batches",
        null=True,
        blank=True,
    )
    brand = models.ForeignKey(
        DistributionBrand,
        verbose_name="\u0627\u0644\u0635\u0646\u0641 \u0627\u0644\u062a\u062c\u0627\u0631\u064a",
        on_delete=models.PROTECT,
        related_name="import_batches",
    )
    replaces_batch = models.ForeignKey(
        "self",
        verbose_name="\u064a\u0633\u062a\u0628\u062f\u0644 \u062f\u0641\u0639\u0629",
        on_delete=models.PROTECT,
        related_name="replacement_batches",
        null=True,
        blank=True,
        help_text=(
            "\u062a\u062d\u062f\u062f \u0627\u0644\u062f\u0641\u0639\u0629 "
            "\u0627\u0644\u0642\u062f\u064a\u0645\u0629 \u0639\u0646\u062f "
            "\u0627\u0639\u062a\u0645\u0627\u062f \u0645\u0644\u0641 "
            "\u0645\u0635\u062d\u062d."
        ),
    )
    report_type = models.CharField(
        "\u0646\u0648\u0639 \u0627\u0644\u0645\u0644\u0641",
        max_length=30,
        choices=ImportReportType.choices,
        db_index=True,
    )
    period_start = models.DateField(
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0628\u062f\u0627\u064a\u0629",
        db_index=True,
    )
    period_end = models.DateField(
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0646\u0647\u0627\u064a\u0629",
        db_index=True,
    )
    opening_month = models.DateField(
        "\u0634\u0647\u0631 \u0627\u0644\u0645\u062e\u0632\u0648\u0646 \u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a",
        null=True,
        blank=True,
        editable=False,
        db_index=True,
        help_text=(
            "\u062d\u0642\u0644 \u062a\u0642\u0646\u064a \u064a\u062d\u062f\u062f "
            "\u0623\u0648\u0644 \u064a\u0648\u0645 \u0645\u0646 "
            "\u0634\u0647\u0631 \u0627\u0644\u0645\u062e\u0632\u0648\u0646 "
            "\u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a."
        ),
    )
    source_file = models.FileField(
        "\u0627\u0644\u0645\u0644\u0641 \u0627\u0644\u0645\u0631\u0641\u0648\u0639",
        upload_to="imports/pending/%Y/%m/",
        blank=True,
        help_text=(
            "\u064a\u062d\u0641\u0638 \u0645\u0624\u0642\u062a\u064b\u0627 "
            "\u0648\u064a\u062d\u0630\u0641 \u0628\u0639\u062f "
            "\u0646\u062c\u0627\u062d \u0627\u0644\u0627\u0639\u062a\u0645\u0627\u062f."
        ),
    )
    original_filename = models.CharField(
        "\u0627\u0633\u0645 \u0627\u0644\u0645\u0644\u0641 \u0627\u0644\u0623\u0635\u0644\u064a",
        max_length=255,
    )
    worksheet_name = models.CharField(
        "\u0627\u0633\u0645 \u0648\u0631\u0642\u0629 Excel",
        max_length=255,
        blank=True,
    )
    file_size_bytes = models.PositiveBigIntegerField(
        "\u062d\u062c\u0645 \u0627\u0644\u0645\u0644\u0641 \u0628\u0627\u0644\u0628\u0627\u064a\u062a",
        default=0,
    )
    file_sha256 = models.CharField(
        "\u0628\u0635\u0645\u0629 \u0627\u0644\u0645\u0644\u0641 SHA-256",
        max_length=64,
        validators=[sha256_validator],
        blank=True,
        db_index=True,
    )
    content_sha256 = models.CharField(
        "\u0628\u0635\u0645\u0629 \u0627\u0644\u0645\u062d\u062a\u0648\u0649 \u0627\u0644\u0645\u0646\u0638\u0641",
        max_length=64,
        validators=[sha256_validator],
        blank=True,
        db_index=True,
    )
    status = models.CharField(
        "\u062d\u0627\u0644\u0629 \u0627\u0644\u0627\u0633\u062a\u064a\u0631\u0627\u062f",
        max_length=20,
        choices=ImportBatchStatus.choices,
        default=ImportBatchStatus.PENDING,
        db_index=True,
    )
    total_rows = models.PositiveIntegerField(
        "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0635\u0641\u0648\u0641",
        default=0,
    )
    accepted_rows = models.PositiveIntegerField(
        "\u0627\u0644\u0635\u0641\u0648\u0641 \u0627\u0644\u0645\u0642\u0628\u0648\u0644\u0629",
        default=0,
    )
    excluded_rows = models.PositiveIntegerField(
        "\u0627\u0644\u0635\u0641\u0648\u0641 \u0627\u0644\u0645\u0633\u062a\u0628\u0639\u062f\u0629",
        default=0,
    )
    stopped_rows = models.PositiveIntegerField(
        "\u0627\u0644\u0635\u0641\u0648\u0641 \u0627\u0644\u0645\u062a\u0648\u0642\u0641\u0629",
        default=0,
        help_text=(
            "\u0635\u0641\u0648\u0641 \u062a\u0645\u062b\u0644 "
            "\u0634\u0627\u062d\u0646\u0627\u062a \u0645\u062a\u0648\u0642\u0641\u0629 "
            "\u0648\u0644\u0627 \u062a\u062f\u062e\u0644 \u0641\u064a "
            "\u062d\u0633\u0627\u0628 \u0627\u0644\u0641\u0634\u0644."
        ),
    )
    warning_count = models.PositiveIntegerField(
        "\u0639\u062f\u062f \u0627\u0644\u062a\u062d\u0630\u064a\u0631\u0627\u062a",
        default=0,
    )
    error_count = models.PositiveIntegerField(
        "\u0639\u062f\u062f \u0627\u0644\u0623\u062e\u0637\u0627\u0621",
        default=0,
    )
    review_summary = models.JSONField(
        "\u0645\u0644\u062e\u0635 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
        default=dict,
        blank=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="\u0631\u0641\u0639\u0647 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645",
        on_delete=models.PROTECT,
        related_name="uploaded_import_batches",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="\u0631\u0627\u062c\u0639\u0647 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645",
        on_delete=models.PROTECT,
        related_name="reviewed_import_batches",
        null=True,
        blank=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="\u0627\u0639\u062a\u0645\u062f\u0647 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645",
        on_delete=models.PROTECT,
        related_name="approved_import_batches",
        null=True,
        blank=True,
    )
    notes = models.TextField(
        "\u0645\u0644\u0627\u062d\u0638\u0627\u062a",
        blank=True,
    )
    uploaded_at = models.DateTimeField(
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0631\u0641\u0639",
        auto_now_add=True,
    )
    reviewed_at = models.DateTimeField(
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0627\u0639\u062a\u0645\u0627\u062f",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(
        "\u0622\u062e\u0631 \u062a\u0639\u062f\u064a\u0644",
        auto_now=True,
    )

    class Meta:
        verbose_name = "\u062f\u0641\u0639\u0629 \u0627\u0633\u062a\u064a\u0631\u0627\u062f"
        verbose_name_plural = "\u062f\u0641\u0639\u0627\u062a \u0627\u0644\u0627\u0633\u062a\u064a\u0631\u0627\u062f"
        ordering = ["-uploaded_at", "-id"]

        indexes = [
            models.Index(
                fields=["brand", "report_type", "period_start"],
                name="import_brand_type_start_idx",
            ),
            models.Index(
                fields=["status", "uploaded_at"],
                name="import_status_uploaded_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(source_upload__isnull=True)
                        & ~Q(file_sha256="")
                    )
                    |
                    (
                        Q(source_upload__isnull=False)
                        & Q(file_sha256="")
                    )
                ),
                name="import_batch_one_source_identity",
                violation_error_message=(
                    "\u064a\u062c\u0628 \u0623\u0646 \u062a\u0639\u062a\u0645\u062f "
                    "\u0627\u0644\u062f\u0641\u0639\u0629 \u0639\u0644\u0649 \u0645\u0644\u0641 "
                    "\u0645\u0628\u0627\u0634\u0631 \u0623\u0648 \u0645\u0644\u0641 \u062e\u0627\u0645 "
                    "\u0645\u0634\u062a\u0642\u060c \u0648\u0644\u064a\u0633 \u0627\u0644\u0627\u062b\u0646\u064a\u0646 \u0645\u0639\u064b\u0627."
                ),
            ),
            models.UniqueConstraint(
                fields=[
                    "source_upload",
                    "brand",
                    "report_type",
                    "period_start",
                    "period_end",
                ],
                condition=(
                    Q(source_upload__isnull=False)
                    & Q(
                        status__in=[
                            ImportBatchStatus.PENDING,
                            ImportBatchStatus.REVIEWED,
                            ImportBatchStatus.BLOCKED,
                            ImportBatchStatus.FAILED,
                        ]
                    )
                ),
                name="import_src_scope_mutable_uniq",
                violation_error_message=(
                    "\u0633\u0628\u0642 \u0625\u0646\u0634\u0627\u0621 "
                    "\u062f\u0641\u0639\u0629 \u0645\u0634\u062a\u0642\u0629 "
                    "\u0642\u0627\u0628\u0644\u0629 \u0644\u0644\u062a\u0639\u062f\u064a\u0644 "
                    "\u0644\u0646\u0641\u0633 \u0627\u0644\u0645\u0644\u0641 "
                    "\u0648\u0627\u0644\u0635\u0646\u0641 "
                    "\u0648\u0627\u0644\u0646\u0648\u0639 "
                    "\u0648\u0627\u0644\u0641\u062a\u0631\u0629."
                ),
            ),
            models.UniqueConstraint(
                fields=[
                    "source_upload",
                    "brand",
                    "report_type",
                    "period_start",
                    "period_end",
                ],
                condition=(
                    Q(source_upload__isnull=False)
                    & Q(status=ImportBatchStatus.APPROVED)
                ),
                name="import_src_scope_approved_uniq",
                violation_error_message=(
                    "\u0633\u0628\u0642 \u0627\u0639\u062a\u0645\u0627\u062f "
                    "\u062f\u0641\u0639\u0629 \u0645\u0634\u062a\u0642\u0629 "
                    "\u0644\u0646\u0641\u0633 \u0627\u0644\u0645\u0644\u0641 "
                    "\u0648\u0627\u0644\u0635\u0646\u0641 "
                    "\u0648\u0627\u0644\u0646\u0648\u0639 "
                    "\u0648\u0627\u0644\u0641\u062a\u0631\u0629."
                ),
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="import_period_end_not_before_start",
                violation_error_message=(
                    "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0646\u0647\u0627\u064a\u0629 "
                    "\u0644\u0627 \u064a\u0645\u0643\u0646 \u0623\u0646 "
                    "\u064a\u0643\u0648\u0646 \u0642\u0628\u0644 \u0627\u0644\u0628\u062f\u0627\u064a\u0629."
                ),
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(report_type=ImportReportType.OPENING_STOCK)
                    | Q(period_end=F("period_start"))
                ),
                name="opening_stock_single_date",
                violation_error_message=(
                    "\u064a\u062c\u0628 \u0623\u0646 \u064a\u0643\u0648\u0646 "
                    "\u0627\u0644\u0645\u062e\u0632\u0648\u0646 \u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a "
                    "\u0645\u0631\u062a\u0628\u0637\u064b\u0627 \u0628\u062a\u0627\u0631\u064a\u062e \u0648\u0627\u062d\u062f."
                ),
            ),
            models.UniqueConstraint(
                fields=[
                    "brand",
                    "opening_month",
                ],
                condition=Q(
                    report_type=ImportReportType.OPENING_STOCK,
                    status=ImportBatchStatus.APPROVED,
                    opening_month__isnull=False,
                ),
                name="import_approved_opening_month_uniq",
                violation_error_message=(
                    "\u0633\u0628\u0642 \u0627\u0639\u062a\u0645\u0627\u062f "
                    "\u0645\u062e\u0632\u0648\u0646 \u0627\u0641\u062a\u062a\u0627\u062d\u064a "
                    "\u0644\u0647\u0630\u0627 \u0627\u0644\u0635\u0646\u0641 "
                    "\u062e\u0644\u0627\u0644 \u0646\u0641\u0633 \u0627\u0644\u0634\u0647\u0631."
                ),
            ),
            models.UniqueConstraint(
                fields=["replaces_batch"],
                condition=(
                    Q(replaces_batch__isnull=False)
                    & Q(
                        status__in=[
                            ImportBatchStatus.APPROVED,
                            ImportBatchStatus.SUPERSEDED,
                        ]
                    )
                ),
                name="import_replaced_batch_once_uniq",
                violation_error_message=(
                    "\u0633\u0628\u0642 \u0631\u0628\u0637 "
                    "\u0647\u0630\u0647 \u0627\u0644\u062f\u0641\u0639\u0629 "
                    "\u0628\u062f\u0641\u0639\u0629 \u0645\u0635\u062d\u062d\u0629 "
                    "\u0645\u0639\u062a\u0645\u062f\u0629."
                ),
            ),
            models.UniqueConstraint(
                fields=["file_sha256"],
                condition=(
                    Q(status=ImportBatchStatus.APPROVED)
                    & ~Q(file_sha256="")
                ),
                name="import_approved_file_sha_uniq",
                violation_error_message=(
                    "\u0633\u0628\u0642 \u0627\u0639\u062a\u0645\u0627\u062f "
                    "\u0646\u0641\u0633 \u0627\u0644\u0645\u0644\u0641."
                ),
            ),
            models.UniqueConstraint(
                fields=[
                    "brand",
                    "report_type",
                    "period_start",
                    "period_end",
                    "content_sha256",
                ],
                condition=(
                    Q(status=ImportBatchStatus.APPROVED)
                    & ~Q(content_sha256="")
                ),
                name="import_approved_content_uniq",
                violation_error_message=(
                    "\u0633\u0628\u0642 \u0627\u0639\u062a\u0645\u0627\u062f "
                    "\u0646\u0641\u0633 \u0627\u0644\u0645\u062d\u062a\u0648\u0649 "
                    "\u0644\u0647\u0630\u0627 \u0627\u0644\u0635\u0646\u0641 "
                    "\u0648\u0627\u0644\u0641\u062a\u0631\u0629."
                ),
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if (
            self.report_type == ImportReportType.OPENING_STOCK
            and self.period_start
        ):
            self.opening_month = self.period_start.replace(day=1)
        else:
            self.opening_month = None

        if (
            self.period_start
            and self.period_end
            and self.period_end < self.period_start
        ):
            errors["period_end"] = (
                "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0646\u0647\u0627\u064a\u0629 "
                "\u0644\u0627 \u064a\u0645\u0643\u0646 \u0623\u0646 "
                "\u064a\u0643\u0648\u0646 \u0642\u0628\u0644 \u0627\u0644\u0628\u062f\u0627\u064a\u0629."
            )

        if (
            self.report_type == ImportReportType.OPENING_STOCK
            and self.period_start
            and self.period_end
            and self.period_start != self.period_end
        ):
            errors["period_end"] = (
                "\u0627\u0644\u0645\u062e\u0632\u0648\u0646 \u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a "
                "\u064a\u0631\u062a\u0628\u0637 \u0628\u062a\u0627\u0631\u064a\u062e "
                "\u0648\u0627\u062d\u062f \u0641\u0642\u0637."
            )

        accounted_rows = (
            self.accepted_rows
            + self.excluded_rows
            + self.stopped_rows
        )

        if accounted_rows > self.total_rows:
            errors["total_rows"] = (
                "\u0645\u062c\u0645\u0648\u0639 \u0627\u0644\u0635\u0641\u0648\u0641 "
                "\u0627\u0644\u0645\u0642\u0628\u0648\u0644\u0629 \u0648\u0627\u0644\u0645\u0633\u062a\u0628\u0639\u062f\u0629 "
                "\u0648\u0627\u0644\u0645\u062a\u0648\u0642\u0641\u0629 \u0644\u0627 \u064a\u0645\u0643\u0646 "
                "\u0623\u0646 \u064a\u062a\u062c\u0627\u0648\u0632 \u0625\u062c\u0645\u0627\u0644\u064a "
                "\u0627\u0644\u0635\u0641\u0648\u0641."
            )
        elif (
            self.status
            in {
                ImportBatchStatus.REVIEWED,
                ImportBatchStatus.BLOCKED,
                ImportBatchStatus.APPROVED,
                ImportBatchStatus.SUPERSEDED,
            }
            and accounted_rows != self.total_rows
        ):
            errors["total_rows"] = (
                "\u064a\u062c\u0628 \u0623\u0646 \u064a\u0633\u0627\u0648\u064a "
                "\u0645\u062c\u0645\u0648\u0639 \u0627\u0644\u0635\u0641\u0648\u0641 "
                "\u0627\u0644\u0645\u0642\u0628\u0648\u0644\u0629 \u0648\u0627\u0644\u0645\u0633\u062a\u0628\u0639\u062f\u0629 "
                "\u0648\u0627\u0644\u0645\u062a\u0648\u0642\u0641\u0629 \u0625\u062c\u0645\u0627\u0644\u064a "
                "\u0627\u0644\u0635\u0641\u0648\u0641 \u0628\u0639\u062f "
                "\u0627\u0646\u062a\u0647\u0627\u0621 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629."
            )

        if self.replaces_batch_id:
            if (
                self.pk
                and self.replaces_batch_id == self.pk
            ):
                errors["replaces_batch"] = (
                    "\u0644\u0627 \u064a\u0645\u0643\u0646 \u0644\u0644\u062f\u0641\u0639\u0629 "
                    "\u0623\u0646 \u062a\u0633\u062a\u0628\u062f\u0644 \u0646\u0641\u0633\u0647\u0627."
                )
            elif self.replaces_batch.status not in {
                ImportBatchStatus.APPROVED,
                ImportBatchStatus.SUPERSEDED,
            }:
                errors["replaces_batch"] = (
                    "\u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 "
                    "\u0627\u0644\u062f\u0641\u0639\u0629 \u0627\u0644\u0642\u062f\u064a\u0645\u0629 "
                    "\u0645\u0639\u062a\u0645\u062f\u0629 \u0623\u0648 "
                    "\u0645\u0633\u062a\u0628\u062f\u0644\u0629."
                )
            elif (
                self.brand_id
                and self.replaces_batch.brand_id != self.brand_id
            ):
                errors["replaces_batch"] = (
                    "\u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 "
                    "\u0627\u0644\u062f\u0641\u0639\u0629 \u0627\u0644\u0642\u062f\u064a\u0645\u0629 "
                    "\u0645\u0646 \u0646\u0641\u0633 \u0627\u0644\u0635\u0646\u0641."
                )
            elif (
                self.report_type
                and self.replaces_batch.report_type != self.report_type
            ):
                errors["replaces_batch"] = (
                    "\u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 "
                    "\u0627\u0644\u062f\u0641\u0639\u0629 \u0627\u0644\u0642\u062f\u064a\u0645\u0629 "
                    "\u0645\u0646 \u0646\u0641\u0633 \u0646\u0648\u0639 \u0627\u0644\u0645\u0644\u0641."
                )
            elif (
                self.period_start
                and self.period_end
                and (
                    self.replaces_batch.period_start != self.period_start
                    or self.replaces_batch.period_end != self.period_end
                )
            ):
                errors["replaces_batch"] = (
                    "\u064a\u062c\u0628 \u0623\u0646 \u062a\u062e\u0635 "
                    "\u0627\u0644\u062f\u0641\u0639\u0629 \u0627\u0644\u0645\u0635\u062d\u062d\u0629 "
                    "\u0646\u0641\u0633 \u0627\u0644\u0641\u062a\u0631\u0629."
                )

        if (
            self.status == ImportBatchStatus.APPROVED
            and self.error_count > 0
        ):
            errors["status"] = (
                "\u0644\u0627 \u064a\u0645\u0643\u0646 \u0627\u0639\u062a\u0645\u0627\u062f "
                "\u062f\u0641\u0639\u0629 \u062a\u062d\u062a\u0648\u064a "
                "\u0639\u0644\u0649 \u0623\u062e\u0637\u0627\u0621 \u0645\u0627\u0646\u0639\u0629."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if (
            self.report_type == ImportReportType.OPENING_STOCK
            and self.period_start
        ):
            self.opening_month = self.period_start.replace(day=1)
        else:
            self.opening_month = None

        if self.original_filename:
            self.original_filename = self.original_filename.strip()

        if self.worksheet_name:
            self.worksheet_name = self.worksheet_name.strip()

        if self.file_sha256:
            self.file_sha256 = self.file_sha256.lower()

        if self.content_sha256:
            self.content_sha256 = self.content_sha256.lower()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.brand.code} \u2014 "
            f"{self.get_report_type_display()} \u2014 "
            f"{self.period_start} \u0625\u0644\u0649 {self.period_end}"
        )


class ImportRowStatus(models.TextChoices):
    ACCEPTED = (
        "ACCEPTED",
        "\u0645\u0642\u0628\u0648\u0644",
    )
    EXCLUDED = (
        "EXCLUDED",
        "\u0645\u0633\u062a\u0628\u0639\u062f",
    )
    STOPPED = (
        "STOPPED",
        "\u0645\u0624\u0634\u0631 \u062a\u0648\u0642\u0641",
    )


class ImportRow(models.Model):
    batch = models.ForeignKey(
        ImportBatch,
        verbose_name="\u062f\u0641\u0639\u0629 \u0627\u0644\u0627\u0633\u062a\u064a\u0631\u0627\u062f",
        on_delete=models.CASCADE,
        related_name="rows",
    )
    excel_row_number = models.PositiveIntegerField(
        "\u0631\u0642\u0645 \u0627\u0644\u0635\u0641 \u0641\u064a Excel",
    )
    status = models.CharField(
        "\u062d\u0627\u0644\u0629 \u0627\u0644\u0635\u0641",
        max_length=20,
        choices=ImportRowStatus.choices,
        db_index=True,
    )
    raw_data = models.JSONField(
        "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0623\u0635\u0644\u064a\u0629",
        default=dict,
        encoder=DjangoJSONEncoder,
    )
    cleaned_data = models.JSONField(
        "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0645\u0646\u0638\u0641\u0629",
        default=dict,
        encoder=DjangoJSONEncoder,
    )
    issues = models.JSONField(
        "\u0627\u0644\u0623\u062e\u0637\u0627\u0621 \u0648\u0627\u0644\u062a\u062d\u0630\u064a\u0631\u0627\u062a",
        default=list,
        blank=True,
        encoder=DjangoJSONEncoder,
    )
    row_sha256 = models.CharField(
        "\u0628\u0635\u0645\u0629 \u0627\u0644\u0635\u0641 SHA-256",
        max_length=64,
        validators=[sha256_validator],
        db_index=True,
        editable=False,
    )
    created_at = models.DateTimeField(
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0625\u0646\u0634\u0627\u0621",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "\u0635\u0641 \u0627\u0633\u062a\u064a\u0631\u0627\u062f"
        verbose_name_plural = "\u0635\u0641\u0648\u0641 \u0627\u0644\u0627\u0633\u062a\u064a\u0631\u0627\u062f"
        ordering = [
            "batch_id",
            "excel_row_number",
        ]

        indexes = [
            models.Index(
                fields=["batch", "status"],
                name="import_row_batch_status_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "batch",
                    "excel_row_number",
                ],
                name="import_row_batch_excel_uniq",
                violation_error_message=(
                    "\u0644\u0627 \u064a\u0645\u0643\u0646 \u062d\u0641\u0638 "
                    "\u0646\u0641\u0633 \u0631\u0642\u0645 \u0635\u0641 Excel "
                    "\u0623\u0643\u062b\u0631 \u0645\u0646 \u0645\u0631\u0629 "
                    "\u062f\u0627\u062e\u0644 \u0646\u0641\u0633 \u0627\u0644\u062f\u0641\u0639\u0629."
                ),
            ),
            models.CheckConstraint(
                condition=Q(excel_row_number__gte=2),
                name="import_row_excel_number_gte_2",
                violation_error_message=(
                    "\u064a\u062c\u0628 \u0623\u0646 \u064a\u0643\u0648\u0646 "
                    "\u0631\u0642\u0645 \u0635\u0641 Excel 2 "
                    "\u0623\u0648 \u0623\u0643\u062b\u0631."
                ),
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if not isinstance(self.raw_data, dict):
            errors["raw_data"] = (
                "\u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 "
                "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0623\u0635\u0644\u064a\u0629 "
                "\u0643\u0627\u0626\u0646 JSON."
            )

        if not isinstance(self.cleaned_data, dict):
            errors["cleaned_data"] = (
                "\u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 "
                "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0645\u0646\u0638\u0641\u0629 "
                "\u0643\u0627\u0626\u0646 JSON."
            )

        if not isinstance(self.issues, list):
            errors["issues"] = (
                "\u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 "
                "\u0627\u0644\u0623\u062e\u0637\u0627\u0621 \u0648\u0627\u0644\u062a\u062d\u0630\u064a\u0631\u0627\u062a "
                "\u0642\u0627\u0626\u0645\u0629 JSON."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.row_sha256:
            self.row_sha256 = self.row_sha256.lower()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.batch_id} \u2014 "
            f"Excel row {self.excel_row_number} \u2014 "
            f"{self.get_status_display()}"
        )

