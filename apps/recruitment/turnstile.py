import json
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.parse import urlencode
from urllib.request import (
    Request,
    urlopen,
)

from django.conf import settings


TURNSTILE_VERIFY_URL = (
    "https://challenges.cloudflare.com/"
    "turnstile/v0/siteverify"
)


def verify_turnstile(token):
    token = (token or "").strip()

    if not token:
        return False

    secret = getattr(
        settings,
        "TURNSTILE_SECRET_KEY",
        "",
    ).strip()

    expected_hostname = getattr(
        settings,
        "TURNSTILE_EXPECTED_HOSTNAME",
        "",
    ).strip().lower()

    if not secret:
        return False

    payload = urlencode(
        {
            "secret": secret,
            "response": token,
        }
    ).encode("utf-8")

    request = Request(
        TURNSTILE_VERIFY_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": (
                "application/x-www-form-urlencoded"
            ),
        },
    )

    try:
        with urlopen(
            request,
            timeout=5,
        ) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return False

    if data.get("success") is not True:
        return False

    if expected_hostname:
        response_hostname = (
            data.get("hostname") or ""
        ).strip().lower()

        if response_hostname != expected_hostname:
            return False

    return True
