from collections.abc import Mapping

from .config import (
    AskDeliskyProviderMode,
    load_ask_delisky_provider_config,
)
from .local_provider import LocalLlmTransport
from .marketing_provider import (
    LocalMarketingHelperProvider,
    MarketingHelperProvider,
)
from .ollama_transport import OllamaTransport


MARKETING_HELPER_NUM_PREDICT = 256


class MarketingHelperProviderDisabledError(
    RuntimeError
):
    """Marketing helper provider execution is disabled."""


class MarketingHelperProviderConfigurationError(
    RuntimeError
):
    """Marketing helper provider configuration is invalid."""


def build_marketing_helper_provider(
    *,
    environ: Mapping[str, str] | None = None,
    local_transport: LocalLlmTransport | None = None,
) -> MarketingHelperProvider:
    try:
        config = load_ask_delisky_provider_config(
            environ=environ
        )
    except ValueError as exc:
        raise MarketingHelperProviderConfigurationError(
            "Marketing helper provider configuration "
            "is invalid."
        ) from exc

    if config.mode == AskDeliskyProviderMode.DISABLED:
        raise MarketingHelperProviderDisabledError(
            "Marketing helper provider is disabled."
        )

    if config.mode == AskDeliskyProviderMode.LOCAL:
        transport = local_transport

        if transport is None:
            transport = OllamaTransport(
                num_predict=MARKETING_HELPER_NUM_PREDICT
            )

        return LocalMarketingHelperProvider(
            config=config,
            transport=transport,
        )

    raise RuntimeError(
        "Unsupported marketing helper provider configuration."
    )
