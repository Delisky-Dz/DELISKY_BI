from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Worker


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
