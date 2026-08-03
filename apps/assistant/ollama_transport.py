import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)


OLLAMA_KEEP_ALIVE = "5m"
OLLAMA_TEMPERATURE = 0.2
OLLAMA_NUM_PREDICT = 96
OLLAMA_MAX_NUM_PREDICT = 512


class OllamaTransportError(RuntimeError):
    """Normalized failure from the local Ollama transport."""


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        raise OllamaTransportError(
            "Ollama redirects are not allowed."
        )


def _validate_local_origin(
    base_url: str,
) -> str:
    normalized = base_url.strip().rstrip("/")

    if not normalized:
        raise ValueError(
            "Ollama base URL cannot be empty."
        )

    parsed = urlparse(normalized)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            "Ollama base URL must use HTTP or HTTPS."
        )

    if parsed.username is not None or parsed.password is not None:
        raise ValueError(
            "Credentials are not allowed in the "
            "Ollama base URL."
        )

    if parsed.path not in {"", "/"}:
        raise ValueError(
            "Ollama base URL cannot contain a path."
        )

    if parsed.query or parsed.fragment:
        raise ValueError(
            "Ollama base URL cannot contain "
            "a query or fragment."
        )

    if parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError(
            "Ollama endpoint must use a loopback host."
        )

    try:
        parsed.port
    except ValueError as exc:
        raise ValueError(
            "Ollama base URL contains an invalid port."
        ) from exc

    return normalized


def _validate_generation_inputs(
    *,
    model_name: str,
    timeout_seconds: int,
    system_prompt: str,
    user_prompt: str,
) -> None:
    if not model_name.strip():
        raise ValueError(
            "Ollama model name cannot be empty."
        )

    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or timeout_seconds < 1
    ):
        raise ValueError(
            "Ollama timeout must be a positive integer."
        )

    if not system_prompt.strip():
        raise ValueError(
            "Ollama system prompt cannot be empty."
        )

    if not user_prompt.strip():
        raise ValueError(
            "Ollama user prompt cannot be empty."
        )


class OllamaTransport:
    """
    Local HTTP transport for Ollama /api/generate.

    Only loopback origins are accepted. Environment/system HTTP
    proxies are disabled, and HTTP redirects are rejected.
    """

    def __init__(
        self,
        *,
        num_predict: int = OLLAMA_NUM_PREDICT,
    ) -> None:
        if (
            isinstance(num_predict, bool)
            or not isinstance(num_predict, int)
            or num_predict < 1
            or num_predict > OLLAMA_MAX_NUM_PREDICT
        ):
            raise ValueError(
                "Ollama num_predict must be an integer "
                "between 1 and "
                f"{OLLAMA_MAX_NUM_PREDICT}."
            )

        self._num_predict = num_predict

    def generate(
        self,
        *,
        base_url: str,
        model_name: str,
        timeout_seconds: int,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        normalized_base_url = _validate_local_origin(
            base_url
        )

        _validate_generation_inputs(
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        endpoint = (
            f"{normalized_base_url}/api/generate"
        )

        request_payload = {
            "model": model_name.strip(),
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": OLLAMA_TEMPERATURE,
                "num_predict": self._num_predict,
            },
        }

        request = Request(
            endpoint,
            data=json.dumps(
                request_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        opener = build_opener(
            ProxyHandler({}),
            _RejectRedirectHandler(),
        )

        try:
            with opener.open(
                request,
                timeout=timeout_seconds,
            ) as response:
                raw_body = response.read()
        except HTTPError as exc:
            raise OllamaTransportError(
                "Ollama request failed with "
                f"HTTP status {exc.code}."
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise OllamaTransportError(
                "Could not connect to the local "
                "Ollama server."
            ) from exc

        try:
            decoded_body = raw_body.decode("utf-8")
            payload = json.loads(decoded_body)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise OllamaTransportError(
                "Ollama returned an invalid JSON response."
            ) from exc

        if not isinstance(payload, dict):
            raise OllamaTransportError(
                "Ollama returned an unexpected response."
            )

        if payload.get("error"):
            raise OllamaTransportError(
                "Ollama returned an error response."
            )

        answer = payload.get("response")

        if not isinstance(answer, str):
            raise OllamaTransportError(
                "Ollama response is missing generated text."
            )

        if not answer.strip():
            raise OllamaTransportError(
                "Ollama returned an empty generated response."
            )

        return answer
