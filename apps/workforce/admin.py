from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Worker,
    WorkerCapability,
    WorkerCategory,
)


@admin.register(WorkerCategory)
class WorkerCategoryAdmin(
    admin.ModelAdmin
):
    list_display = (
        "name",
        "code",
        "is_active",
        "is_system",
        "sort_order",
        "updated_at",
    )

    list_display_links = (
        "name",
        "code",
    )

    list_filter = (
        "is_active",
        "is_system",
        "default_capabilities",
    )

    filter_horizontal = (
        "default_capabilities",
    )

    search_fields = (
        "name",
        "code",
        "description",
    )

    ordering = (
        "sort_order",
        "name",
    )

    readonly_fields = (
        "code",
        "is_system",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    )

    actions = (
        "activate_categories",
        "deactivate_categories",
    )

    fieldsets = (
        (
            "\u0645\u0639\u0644\u0648\u0645\u0627\u062a "
            "\u0627\u0644\u0635\u0646\u0641",
            {
                "fields": (
                    "name",
                    "code",
                    "description",
                    "sort_order",
                    "is_active",
                    "is_system",
                )
            },
        ),
        (
            "القدرات الافتراضية",
            {
                "fields": (
                    "default_capabilities",
                ),
                "description": (
                    "قدرات مقترحة للصنف، "
                    "ولا تغيّر قدرات العمال "
                    "تلقائيًا."
                ),
            },
        ),
        (
            "\u0645\u0639\u0644\u0648\u0645\u0627\u062a "
            "\u0627\u0644\u0646\u0638\u0627\u0645",
            {
                "fields": (
                    "created_by",
                    "updated_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.action(
        description=(
            "\u062a\u0641\u0639\u064a\u0644 "
            "\u0627\u0644\u0623\u0635\u0646\u0627\u0641 "
            "\u0627\u0644\u0645\u062d\u062f\u062f\u0629"
        )
    )
    def activate_categories(
        self,
        request,
        queryset,
    ):
        updated = queryset.update(
            is_active=True
        )

        self.message_user(
            request,
            (
                f"\u062a\u0645 \u062a\u0641\u0639\u064a\u0644 "
                f"{updated} \u0635\u0646\u0641."
            ),
        )

    @admin.action(
        description=(
            "\u062a\u0639\u0637\u064a\u0644 "
            "\u0627\u0644\u0623\u0635\u0646\u0627\u0641 "
            "\u0627\u0644\u0645\u062d\u062f\u062f\u0629"
        )
    )
    def deactivate_categories(
        self,
        request,
        queryset,
    ):
        updated = queryset.update(
            is_active=False
        )

        self.message_user(
            request,
            (
                f"\u062a\u0645 \u062a\u0639\u0637\u064a\u0644 "
                f"{updated} \u0635\u0646\u0641."
            ),
        )


@admin.register(WorkerCapability)
class WorkerCapabilityAdmin(
    admin.ModelAdmin
):
    list_display = (
        "name",
        "code",
        "is_active",
        "is_system",
        "sort_order",
        "updated_at",
    )

    list_display_links = (
        "name",
        "code",
    )

    list_filter = (
        "is_active",
        "is_system",
    )

    search_fields = (
        "name",
        "code",
        "description",
    )

    ordering = (
        "sort_order",
        "name",
    )

    readonly_fields = (
        "code",
        "is_system",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "معلومات القدرة",
            {
                "fields": (
                    "name",
                    "code",
                    "description",
                    "sort_order",
                    "is_active",
                    "is_system",
                )
            },
        ),
        (
            "معلومات النظام",
            {
                "fields": (
                    "created_by",
                    "updated_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    actions = (
        "activate_capabilities",
        "deactivate_capabilities",
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.created_by_id:
            obj.created_by = request.user

        obj.updated_by = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    @admin.action(
        description="تفعيل القدرات المحددة"
    )
    def activate_capabilities(
        self,
        request,
        queryset,
    ):
        updated = queryset.update(
            is_active=True,
            updated_by=request.user,
        )

        self.message_user(
            request,
            f"تم تفعيل {updated} قدرة.",
        )

    @admin.action(
        description="تعطيل القدرات المحددة"
    )
    def deactivate_capabilities(
        self,
        request,
        queryset,
    ):
        updated = queryset.update(
            is_active=False,
            updated_by=request.user,
        )

        self.message_user(
            request,
            f"تم تعطيل {updated} قدرة.",
        )


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code",
        "worker_full_name",
        "phone",
        "is_active",
        "created_at",
        "edit_link",
    )

    list_display_links = (
        "employee_code",
        "worker_full_name",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "employee_code",
        "first_name",
        "last_name",
        "phone",
    )

    ordering = (
        "last_name",
        "first_name",
    )

    readonly_fields = (
        "employee_code",
        "created_at",
        "updated_at",
    )

    actions = (
        "activate_workers",
        "deactivate_workers",
    )

    filter_horizontal = (
        "capabilities",
    )

    fieldsets = (
        (
            "معلومات العامل",
            {
                "fields": (
                    "employee_code",
                    "first_name",
                    "last_name",
                    "phone",
                )
            },
        ),
        (
            "قدرات العامل",
            {
                "fields": (
                    "capabilities",
                ),
                "description": (
                    "القدرات الفعلية للعامل "
                    "مستقلة عن منصبه الرسمي."
                ),
            },
        ),
        (
            "الحالة والملاحظات",
            {
                "fields": (
                    "is_active",
                    "notes",
                )
            },
        ),
        (
            "معلومات النظام",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="العامل", ordering="last_name")
    def worker_full_name(self, obj):
        return obj.full_name

    @admin.display(description="تعديل")
    def edit_link(self, obj):
        url = reverse(
            "admin:workforce_worker_change",
            args=[obj.pk],
        )
        return format_html(
            '<a class="button" href="{}">تعديل</a>',
            url,
        )

    @admin.action(description="تفعيل العمال المحددين")
    def activate_workers(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"تم تفعيل {updated} عامل.",
        )

    @admin.action(description="تعطيل العمال المحددين")
    def deactivate_workers(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"تم تعطيل {updated} عامل.",
        )
