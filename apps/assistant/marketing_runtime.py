from collections.abc import Mapping

from .marketing_helper import (
    MarketingHelperRequest,
    MarketingHelperResponse,
)
from .marketing_provider_factory import (
    build_marketing_helper_provider,
)


def ask_marketing_helper(
    *,
    question: str,
    environ: Mapping[str, str] | None = None,
) -> MarketingHelperResponse:
    """
    Run the DELISKY commercial and marketing helper.

    This runtime intentionally has no analytics, ORM, or
    AskDeliskyContext dependency.
    """
    provider = build_marketing_helper_provider(
        environ=environ
    )

    request = MarketingHelperRequest(
        question=question
    )

    return provider.generate(
        request
    )
