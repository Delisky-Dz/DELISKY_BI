import json

from .contracts import (
    AskDeliskyProviderRequest,
    AskDeliskyRequest,
    AskDeliskyResponse,
)
from .provider import AskDeliskyProvider


def ask_delisky(
    *,
    request: AskDeliskyRequest,
    provider: AskDeliskyProvider,
) -> AskDeliskyResponse:
    """
    Execute an Ask DELISKY request through a provider-neutral
    boundary.

    The provider receives only the user question and the JSON-safe
    payload produced by AskDeliskyContext. It never receives the
    original manager analytics objects.
    """
    context_payload = request.context.to_payload()

    context_json = json.dumps(
        context_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    provider_request = AskDeliskyProviderRequest(
        question=request.question,
        context_json=context_json,
        context_schema_version=(
            request.context.schema_version
        ),
    )

    provider_result = provider.generate(
        provider_request
    )

    return AskDeliskyResponse(
        answer=provider_result.answer,
        provider_name=provider_result.provider_name,
        model_name=provider_result.model_name,
        context_schema_version=(
            request.context.schema_version
        ),
    )
