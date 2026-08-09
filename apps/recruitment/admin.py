from django.contrib import admin

from .models import JobApplication


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "requested_position",
        "phone",
        "status",
        "submitted_at",
    )
    list_filter = (
        "status",
        "requested_position",
        "marital_status",
    )
    search_fields = (
        "first_name",
        "last_name",
        "phone",
        "email",
    )
    readonly_fields = (
        "submitted_at",
        "updated_at",
    )
