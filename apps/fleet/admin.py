from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Truck, WorkerTruckAssignment


LABEL_EDIT = "\u062a\u0639\u062f\u064a\u0644"

TRUCK_INFO = (
    "\u0645\u0639\u0644\u0648\u0645\u0627\u062a "
    "\u0627\u0644\u0634\u0627\u062d\u0646\u0629"
)

STATUS_AND_NOTES = (
    "\u0627\u0644\u062d\u0627\u0644\u0629 "
    "\u0648\u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0627\u062a"
)

SYSTEM_INFO = (
    "\u0645\u0639\u0644\u0648\u0645\u0627\u062a "
    "\u0627\u0644\u0646\u0638\u0627\u0645"
)

ASSIGNMENT_INFO = (
    "\u0645\u0639\u0644\u0648\u0645\u0627\u062a "
    "\u0627\u0644\u062a\u0639\u064a\u064a\u0646"
)

NOTES_LABEL = "\u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0627\u062a"

CURRENT_ASSIGNMENT = (
    "\u062a\u0639\u064a\u064a\u0646 "
    "\u062d\u0627\u0644\u064a"
)

ACTIVATE_TRUCKS = (
    "\u062a\u0641\u0639\u064a\u0644 "
    "\u0627\u0644\u0634\u0627\u062d\u0646\u0627\u062a "
    "\u0627\u0644\u0645\u062d\u062f\u062f\u0629"
)

DEACTIVATE_TRUCKS = (
    "\u062a\u0639\u0637\u064a\u0644 "
    "\u0627\u0644\u0634\u0627\u062d\u0646\u0627\u062a "
    "\u0627\u0644\u0645\u062d\u062f\u062f\u0629"
)

ACTIVATED_MESSAGE = "\u062a\u0645 \u062a\u0641\u0639\u064a\u0644"
DEACTIVATED_MESSAGE = "\u062a\u0645 \u062a\u0639\u0637\u064a\u0644"
TRUCK_WORD = "\u0634\u0627\u062d\u0646\u0629."


@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = (
        "internal_code",
        "registration_number",
        "brand",
        "model",
        "manufacturing_year",
        "is_active",
        "edit_link",
    )

    list_display_links = (
        "internal_code",
        "registration_number",
    )

    list_filter = (
        "is_active",
        "brand",
        "manufacturing_year",
        "created_at",
    )

    search_fields = (
        "internal_code",
        "registration_number",
        "brand",
        "model",
    )

    ordering = ("registration_number",)

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    actions = (
        "activate_trucks",
        "deactivate_trucks",
    )

    fieldsets = (
        (
            TRUCK_INFO,
            {
                "fields": (
                    "internal_code",
                    "registration_number",
                    "brand",
                    "model",
                    "manufacturing_year",
                )
            },
        ),
        (
            STATUS_AND_NOTES,
            {
                "fields": (
                    "is_active",
                    "notes",
                )
            },
        ),
        (
            SYSTEM_INFO,
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description=LABEL_EDIT)
    def edit_link(self, obj):
        url = reverse(
            "admin:fleet_truck_change",
            args=[obj.pk],
        )

        return format_html(
            '<a class="button" href="{}">{}</a>',
            url,
            LABEL_EDIT,
        )

    @admin.action(description=ACTIVATE_TRUCKS)
    def activate_trucks(self, request, queryset):
        updated = queryset.update(is_active=True)

        self.message_user(
            request,
            f"{ACTIVATED_MESSAGE} {updated} {TRUCK_WORD}",
        )

    @admin.action(description=DEACTIVATE_TRUCKS)
    def deactivate_trucks(self, request, queryset):
        updated = queryset.update(is_active=False)

        self.message_user(
            request,
            f"{DEACTIVATED_MESSAGE} {updated} {TRUCK_WORD}",
        )


@admin.register(WorkerTruckAssignment)
class WorkerTruckAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "worker",
        "truck",
        "start_date",
        "end_date",
        "assignment_status",
        "edit_link",
    )

    list_display_links = (
        "worker",
        "truck",
    )

    list_filter = (
        "start_date",
        "end_date",
        "truck",
    )

    search_fields = (
        "worker__employee_code",
        "worker__first_name",
        "worker__last_name",
        "truck__internal_code",
        "truck__registration_number",
        "truck__brand",
        "truck__model",
    )

    autocomplete_fields = (
        "worker",
        "truck",
    )

    ordering = ("-start_date",)
    date_hierarchy = "start_date"

    list_select_related = (
        "worker",
        "truck",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            ASSIGNMENT_INFO,
            {
                "fields": (
                    "worker",
                    "truck",
                    "start_date",
                    "end_date",
                )
            },
        ),
        (
            NOTES_LABEL,
            {
                "fields": ("notes",)
            },
        ),
        (
            SYSTEM_INFO,
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(
        description=CURRENT_ASSIGNMENT,
        boolean=True,
    )
    def assignment_status(self, obj):
        return obj.is_current

    @admin.display(description=LABEL_EDIT)
    def edit_link(self, obj):
        url = reverse(
            "admin:fleet_workertruckassignment_change",
            args=[obj.pk],
        )

        return format_html(
            '<a class="button" href="{}">{}</a>',
            url,
            LABEL_EDIT,
        )
