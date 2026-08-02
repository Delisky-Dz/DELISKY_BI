from collections.abc import Mapping
from datetime import date

from apps.analytics.services.ask_delisky_context import (
    build_ask_delisky_context,
)
from apps.analytics.services.manager_insights_orchestrator import (
    build_manager_insights,
)

from .contracts import (
    AskDeliskyRequest,
    AskDeliskyResponse,
)
from .provider_factory import (
    build_ask_delisky_provider,
)
from .service import ask_delisky


def ask_manager_delisky(
    *,
    question: str,
    period_start: date | None = None,
    period_end: date | None = None,
    brand_id: int | None = None,
    environ: Mapping[str, str] | None = None,
) -> AskDeliskyResponse:
    """
    Run the complete Ask DELISKY manager workflow.

    Provider availability is resolved before analytical work so
    disabled or invalid provider configuration fails early.
    """
    provider = build_ask_delisky_provider(
        environ=environ
    )

    insights_result = build_manager_insights(
        period_start=period_start,
        period_end=period_end,
        brand_id=brand_id,
    )

    context = build_ask_delisky_context(
        insights_result=insights_result
    )

    request = AskDeliskyRequest(
        question=question,
        context=context,
    )

    return ask_delisky(
        request=request,
        provider=provider,
    )
