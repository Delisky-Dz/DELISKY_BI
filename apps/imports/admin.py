from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .forms import ImportBatchUploadForm

from .models import (
    DistributionBrand,
    ImportBatch,
    ImportBatchStatus,
    ImportRow,
)

from .services import (
    ImportBatchApprovalError,
    ImportBatchReviewError,
    approve_import_batch,
    create_or_update_import_review,
)


LABEL_EDIT = "\u062a\u0639\u062f\u064a\u0644"


@admin.register(DistributionBrand)
class DistributionBrandAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "is_active",
        "created_at",
        "edit_link",
    )

    list_display_links = (
        "code",
        "name",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "code",
        "name",
    )

    ordering = (
        "name",
        "code",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fields = (
        "code",
        "name",
        "is_active",
        "notes",
        "created_at",
        "updated_at",
    )

    @admin.display(description=LABEL_EDIT)
    def edit_link(self, obj):
        url = reverse(
            "admin:imports_distributionbrand_change",
            args=[obj.pk],
        )

        return format_html(
            '<a class="button" href="{}">{}</a>',
            url,
            LABEL_EDIT,
        )


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    actions = (
        "approve_selected_batches",
    )

    add_fieldsets = (
        (
            "\u0631\u0641\u0639 \u0645\u0644\u0641 Excel",
            {
                "fields": (
                    "source_file",
                    "replaces_batch",
                    "notes",
                )
            },
        ),
    )

    list_display = (
        "original_filename",
        "brand",
        "report_type",
        "period_start",
        "period_end",
        "status",
        "total_rows",
        "accepted_rows",
        "excluded_rows",
        "stopped_rows",
        "error_count",
        "warning_count",
        "uploaded_at",
        "edit_link",
    )

    list_display_links = (
        "original_filename",
        "brand",
    )

    list_filter = (
        "status",
        "report_type",
        "brand",
        "period_start",
        "uploaded_at",
    )

    search_fields = (
        "original_filename",
        "worksheet_name",
        "file_sha256",
        "content_sha256",
        "brand__code",
        "brand__name",
    )

    ordering = (
        "-uploaded_at",
        "-id",
    )

    date_hierarchy = "uploaded_at"

    autocomplete_fields = (
        "brand",
        "replaces_batch",
    )

    list_select_related = (
        "brand",
        "uploaded_by",
        "reviewed_by",
        "approved_by",
    )

    base_readonly_fields = (
        "opening_month",
        "worksheet_name",
        "file_size_bytes",
        "file_sha256",
        "content_sha256",
        "status",
        "total_rows",
        "accepted_rows",
        "excluded_rows",
        "stopped_rows",
        "warning_count",
        "error_count",
        "review_summary",
        "uploaded_by",
        "reviewed_by",
        "approved_by",
        "uploaded_at",
        "reviewed_at",
        "approved_at",
        "updated_at",
    )

    fieldsets = (
        (
            "\u0647\u0648\u064a\u0629 \u0627\u0644\u062f\u0641\u0639\u0629",
            {
                "fields": (
                    "brand",
                    "report_type",
                    "period_start",
                    "period_end",
                    "opening_month",
                    "replaces_batch",
                )
            },
        ),
        (
            "\u0627\u0644\u0645\u0644\u0641",
            {
                "fields": (
                    "source_file",
                    "original_filename",
                    "worksheet_name",
                    "file_size_bytes",
                    "file_sha256",
                    "content_sha256",
                )
            },
        ),
        (
            "\u0646\u062a\u064a\u062c\u0629 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
            {
                "fields": (
                    "status",
                    "total_rows",
                    "accepted_rows",
                    "excluded_rows",
                    "stopped_rows",
                    "warning_count",
                    "error_count",
                    "review_summary",
                )
            },
        ),
        (
            "\u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0648\u0646 "
            "\u0648\u0627\u0644\u062a\u0648\u0627\u0631\u064a\u062e",
            {
                "fields": (
                    "uploaded_by",
                    "reviewed_by",
                    "approved_by",
                    "uploaded_at",
                    "reviewed_at",
                    "approved_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "\u0645\u0644\u0627\u062d\u0638\u0627\u062a",
            {
                "fields": (
                    "notes",
                )
            },
        ),
    )

    def get_form(
        self,
        request,
        obj=None,
        change=False,
        **kwargs,
    ):
        if obj is None:
            kwargs["form"] = ImportBatchUploadForm

        return super().get_form(
            request,
            obj,
            change=change,
            **kwargs,
        )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets

        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.base_readonly_fields

        if obj.status != ImportBatchStatus.PENDING:
            return tuple(
                field.name
                for field in self.model._meta.fields
            )

        return self.base_readonly_fields


    def save_form(
        self,
        request,
        form,
        change,
    ):
        if change:
            return super().save_form(
                request,
                form,
                change,
            )

        # ????? ??????? ??? ??? ImportBatch ?????.
        form.save(commit=False)

        source_file = form.cleaned_data["source_file"]

        result = create_or_update_import_review(
            source_file,
            uploaded_by=request.user,
            reviewed_by=request.user,
            original_filename=source_file.name,
        )

        batch = result.batch
        batch.replaces_batch = form.cleaned_data.get(
            "replaces_batch"
        )
        batch.notes = form.cleaned_data.get(
            "notes",
            "",
        )

        batch.save(
            update_fields=[
                "replaces_batch",
                "notes",
                "updated_at",
            ]
        )

        form.instance = batch
        request._import_review_result = result

        return batch

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if change:
            super().save_model(
                request,
                obj,
                form,
                change,
            )
            return

        result = getattr(
            request,
            "_import_review_result",
            None,
        )

        if result is None:
            raise RuntimeError(
                "Import review result is missing."
            )

        if obj.pk != result.batch.pk:
            raise RuntimeError(
                "Admin object does not match reviewed batch."
            )

        # ?? ???? ???? ???? ???????? ???? ?????? ???????.
        return

    def add_view(
        self,
        request,
        form_url="",
        extra_context=None,
    ):
        try:
            return super().add_view(
                request,
                form_url=form_url,
                extra_context=extra_context,
            )
        except ImportBatchReviewError as exc:
            self.message_user(
                request,
                (
                    "\u0641\u0634\u0644\u062a "
                    "\u0645\u0631\u0627\u062c\u0639\u0629 "
                    "\u0627\u0644\u0645\u0644\u0641: "
                    f"{exc.message} ({exc.code})"
                ),
                level=messages.ERROR,
            )

            return redirect(request.path)

    @admin.action(
        description="\u0627\u0639\u062a\u0645\u0627\u062f "
        "\u0627\u0644\u062f\u0641\u0639\u0627\u062a "
        "\u0627\u0644\u0645\u062d\u062f\u062f\u0629",
        permissions=["change"],
    )
    def approve_selected_batches(
        self,
        request,
        queryset,
    ):
        approved_count = 0
        failed_count = 0

        for batch in queryset.order_by("pk"):
            try:
                approve_import_batch(
                    batch,
                    approved_by=request.user,
                )
            except ImportBatchApprovalError as exc:
                failed_count += 1

                self.message_user(
                    request,
                    (
                        f"{batch.original_filename}: "
                        f"{exc.message} ({exc.code})"
                    ),
                    level=messages.ERROR,
                )
            else:
                approved_count += 1

        if approved_count:
            self.message_user(
                request,
                (
                    "\u062a\u0645 \u0627\u0639\u062a\u0645\u0627\u062f "
                    f"{approved_count} "
                    "\u062f\u0641\u0639\u0629 \u0628\u0646\u062c\u0627\u062d."
                ),
                level=messages.SUCCESS,
            )

        if failed_count:
            self.message_user(
                request,
                (
                    "\u062a\u0639\u0630\u0631 \u0627\u0639\u062a\u0645\u0627\u062f "
                    f"{failed_count} "
                    "\u062f\u0641\u0639\u0629."
                ),
                level=messages.WARNING,
            )

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=LABEL_EDIT)
    def edit_link(self, obj):
        url = reverse(
            "admin:imports_importbatch_change",
            args=[obj.pk],
        )

        return format_html(
            '<a class="button" href="{}">{}</a>',
            url,
            LABEL_EDIT,
        )


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = (
        "batch",
        "excel_row_number",
        "status",
        "row_sha256",
        "created_at",
    )

    list_filter = (
        "status",
        "batch__report_type",
        "batch__brand",
    )

    search_fields = (
        "batch__original_filename",
        "batch__brand__code",
        "batch__brand__name",
        "row_sha256",
    )

    ordering = (
        "-batch_id",
        "excel_row_number",
    )

    list_select_related = (
        "batch",
        "batch__brand",
    )

    readonly_fields = (
        "batch",
        "excel_row_number",
        "status",
        "raw_data",
        "cleaned_data",
        "issues",
        "row_sha256",
        "created_at",
    )

    fields = (
        "batch",
        "excel_row_number",
        "status",
        "row_sha256",
        "raw_data",
        "cleaned_data",
        "issues",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
