from collections.abc import Mapping

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


class AskDeliskyProviderDisabledError(RuntimeError):
    """Ask DELISKY provider execution is disabled."""


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
    config = load_ask_delisky_provider_config(
        environ=environ
    )

    if config.mode == AskDeliskyProviderMode.DISABLED:
        raise AskDeliskyProviderDisabledError(
            "Ask DELISKY provider is disabled."
        )

    if config.mode == AskDeliskyProviderMode.LOCAL:
        transport = local_transport

        if transport is None:
            transport = OllamaTransport()

        return LocalAskDeliskyProvider(
            config=config,
            transport=transport,
        )

    raise RuntimeError(
        "Unsupported Ask DELISKY provider configuration."
    )
