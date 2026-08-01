import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse


class AskDeliskyProviderMode(StrEnum):
    DISABLED = "disabled"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class AskDeliskyProviderConfig:
    mode: AskDeliskyProviderMode
    model_name: str = ""
    base_url: str = ""
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, int)
            or self.timeout_seconds < 1
        ):
            raise ValueError(
                "Ask DELISKY timeout must be a positive integer."
            )

        if self.mode == AskDeliskyProviderMode.DISABLED:
            return

        if self.mode != AskDeliskyProviderMode.LOCAL:
            raise ValueError(
                "Unsupported Ask DELISKY provider mode."
            )

        model_name = self.model_name.strip()
        base_url = self.base_url.strip().rstrip("/")

        if not model_name:
            raise ValueError(
                "Local Ask DELISKY model name cannot be empty."
            )

        if not base_url:
            raise ValueError(
                "Local Ask DELISKY base URL cannot be empty."
            )

        parsed = urlparse(base_url)

        if parsed.scheme not in {"http", "https"}:
            raise ValueError(
                "Local Ask DELISKY base URL must use HTTP or HTTPS."
            )

        if parsed.username is not None or parsed.password is not None:
            raise ValueError(
                "Credentials are not allowed in the local "
                "Ask DELISKY base URL."
            )

        if parsed.path not in {"", "/"}:
            raise ValueError(
                "Local Ask DELISKY base URL cannot contain "
                "a path."
            )

        if parsed.query or parsed.fragment:
            raise ValueError(
                "Local Ask DELISKY base URL cannot contain "
                "a query or fragment."
            )

        if parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError(
                "Local Ask DELISKY endpoint must use a "
                "loopback host."
            )

        object.__setattr__(
            self,
            "model_name",
            model_name,
        )
        object.__setattr__(
            self,
            "base_url",
            base_url,
        )


def _parse_timeout(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "ASK_DELISKY_TIMEOUT_SECONDS must be an integer."
        ) from exc

    if value < 1:
        raise ValueError(
            "ASK_DELISKY_TIMEOUT_SECONDS must be positive."
        )

    return value


def load_ask_delisky_provider_config(
    *,
    environ: Mapping[str, str] | None = None,
) -> AskDeliskyProviderConfig:
    """
    Load Ask DELISKY provider configuration from environment.

    Provider execution is disabled by default. No API keys or
    credentials are read by this local configuration contract.
    """
    source = os.environ if environ is None else environ

    raw_mode = source.get(
        "ASK_DELISKY_PROVIDER",
        AskDeliskyProviderMode.DISABLED.value,
    ).strip().lower()

    try:
        mode = AskDeliskyProviderMode(raw_mode)
    except ValueError as exc:
        raise ValueError(
            "ASK_DELISKY_PROVIDER must be "
            "'disabled' or 'local'."
        ) from exc

    timeout_seconds = _parse_timeout(
        source.get(
            "ASK_DELISKY_TIMEOUT_SECONDS",
            "30",
        )
    )

    if mode == AskDeliskyProviderMode.DISABLED:
        return AskDeliskyProviderConfig(
            mode=mode,
            timeout_seconds=timeout_seconds,
        )

    return AskDeliskyProviderConfig(
        mode=mode,
        model_name=source.get(
            "ASK_DELISKY_LOCAL_MODEL",
            "",
        ),
        base_url=source.get(
            "ASK_DELISKY_LOCAL_BASE_URL",
            "http://127.0.0.1:11434",
        ),
        timeout_seconds=timeout_seconds,
    )
