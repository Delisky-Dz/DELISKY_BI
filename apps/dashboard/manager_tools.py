from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render

from .access import (
    can_use_ai_assistants,
    manager_required,
)
from .forms import ManagerDashboardFilterForm
from .manager_filters import manager_filter_query


TOOL_TEMPLATE_NAME = "dashboard/manager_tool.html"
TOOL_LABELS = {
    "ask-delisky": "Ask DELISKY",
    "marketing-helper": "المستشار التجاري",
}


@manager_required
def manager_tool(request, tool):
    if tool not in TOOL_LABELS:
        raise Http404

    if not can_use_ai_assistants(request.user):
        raise PermissionDenied

    filter_form = ManagerDashboardFilterForm(
        data=request.GET,
    )

    response_status = 200

    if not filter_form.is_valid():
        response_status = 400

    context = {
        "active_section": tool,
        "active_item": tool,
        "manager_query": manager_filter_query(
            request
        ),
        "filter_reset_url": request.path,
        "filter_requested": bool(request.GET),
        "filter_form": filter_form,
        "can_use_ai_assistants": True,
        "tool": tool,
        "tool_label": TOOL_LABELS[tool],
    }

    return render(
        request,
        TOOL_TEMPLATE_NAME,
        context,
        status=response_status,
    )
