from typing import Protocol

from .config import (
    AskDeliskyProviderConfig,
    AskDeliskyProviderMode,
)
from .local_provider import LocalLlmTransport
from .marketing_helper import (
    MARKETING_HELPER_SYSTEM_PROMPT,
    MarketingHelperRequest,
    MarketingHelperResponse,
    build_marketing_helper_user_prompt,
)


class MarketingHelperProvider(Protocol):
    def generate(
        self,
        request: MarketingHelperRequest,
    ) -> MarketingHelperResponse:
        ...


class LocalMarketingHelperProvider:
    def __init__(
        self,
        *,
        config: AskDeliskyProviderConfig,
        transport: LocalLlmTransport,
    ) -> None:
        if config.mode != AskDeliskyProviderMode.LOCAL:
            raise ValueError(
                "LocalMarketingHelperProvider requires local mode."
            )

        self._config = config
        self._transport = transport

    def generate(
        self,
        request: MarketingHelperRequest,
    ) -> MarketingHelperResponse:
        answer = self._transport.generate(
            base_url=self._config.base_url,
            model_name=self._config.model_name,
            timeout_seconds=self._config.timeout_seconds,
            system_prompt=MARKETING_HELPER_SYSTEM_PROMPT,
            user_prompt=(
                build_marketing_helper_user_prompt(
                    request
                )
            ),
        )

        return MarketingHelperResponse(
            answer=answer,
            provider_name="local",
            model_name=self._config.model_name,
        )
