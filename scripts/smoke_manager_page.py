import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Render the DELISKY manager landing page through Django using "
            "an existing manager account. This is a read-only smoke test."
        )
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Existing Manager username used for the authenticated request.",
    )
    parser.add_argument(
        "--settings",
        default="config.settings.production",
        help="Django settings module.",
    )
    parser.add_argument(
        "--host",
        default="app.delisky-dz.com",
        help="HTTP host supplied to the RequestFactory request.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    os.environ["DJANGO_SETTINGS_MODULE"] = args.settings

    import django

    django.setup()

    from django.contrib.auth import get_user_model
    from django.test import RequestFactory

    from apps.dashboard.access import (
        can_access_manager_dashboard,
    )
    from apps.dashboard.manager_views import (
        manager_dashboard,
    )

    user_model = get_user_model()

    try:
        user = user_model.objects.get(
            username=args.username
        )
    except user_model.DoesNotExist as exc:
        raise RuntimeError(
            f"Manager smoke user not found: {args.username}"
        ) from exc

    if not can_access_manager_dashboard(user):
        raise RuntimeError(
            "Manager smoke user does not have manager dashboard access: "
            f"{args.username}"
        )

    request = RequestFactory().get(
        "/manager/",
        secure=True,
        HTTP_HOST=args.host,
    )
    request.user = user

    response = manager_dashboard(request)

    print(f"MANAGER_SMOKE_USER={user.username}")
    print(f"MANAGER_SMOKE_STATUS={response.status_code}")

    if response.status_code != 200:
        raise RuntimeError(
            "Manager page smoke test returned unexpected status: "
            f"{response.status_code}"
        )

    print("MANAGER_SMOKE_RESULT=PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"MANAGER_SMOKE_ERROR={exc}",
            file=sys.stderr,
        )
        sys.exit(1)
