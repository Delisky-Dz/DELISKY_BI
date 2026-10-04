import os
from collections.abc import Mapping

from django.conf import settings

from .config import (
    AskDeliskyProviderMode,
    load_ask_delisky_provider_config,
)
from .local_provider import (
    LocalAskDeliskyProvider,
    LocalLlmTransport,
)
from .ollama_transport import OllamaTransport
from .provider import AskDeliskyProvider


# Allow a short analysis to include its evidence and limitations.
ASK_DELISKY_NUM_PREDICT = 256


class AskDeliskyProviderDisabledError(RuntimeError):
    """Ask DELISKY provider execution is disabled."""


class AskDeliskyProviderConfigurationError(RuntimeError):
    """Ask DELISKY provider configuration is invalid."""


def build_ask_delisky_provider(
    *,
    environ: Mapping[str, str] | None = None,
    local_transport: LocalLlmTransport | None = None,
) -> AskDeliskyProvider:
    """
    Build the configured Ask DELISKY provider.

    Configuration is loaded from the environment unless an
    explicit mapping is supplied. Network access does not occur
    while building the provider.
    """
    # Ask-only override; the legacy shared timeout and Marketing are unchanged.
    source = os.environ if environ is None else environ
    timeout = source.get("ASK_DELISKY_REQUEST_TIMEOUT_SECONDS")
    if timeout is None and environ is None and settings.configured:
        timeout = getattr(settings, "ASK_DELISKY_REQUEST_TIMEOUT_SECONDS", None)
    if timeout is not None:
        source = {**source, "ASK_DELISKY_TIMEOUT_SECONDS": str(timeout)}
    try:
        config = load_ask_delisky_provider_config(
            environ=source
        )
    except ValueError as exc:
        raise AskDeliskyProviderConfigurationError(
            "Ask DELISKY provider configuration is invalid."
        ) from exc

    if config.mode == AskDeliskyProviderMode.DISABLED:
        raise AskDeliskyProviderDisabledError(
            "Ask DELISKY provider is disabled."
        )

    if config.mode == AskDeliskyProviderMode.LOCAL:
        transport = local_transport

        if transport is None:
            transport = OllamaTransport(
                num_predict=ASK_DELISKY_NUM_PREDICT
            )

        return LocalAskDeliskyProvider(
            config=config,
            transport=transport,
        )

    raise RuntimeError(
        "Unsupported Ask DELISKY provider configuration."
    )
