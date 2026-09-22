import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

settings_module = os.environ.get(
    "DELISKY_STATIC_VERIFY_DJANGO_SETTINGS",
    "config.settings.production",
)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    settings_module,
)

import django

django.setup()

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage


STATIC_TAG_PATTERN = re.compile(
    r"""{%\s*static\s+['"]([^'"]+)['"]\s*%}"""
)


def template_files():
    apps_root = Path(settings.BASE_DIR) / "apps"

    if not apps_root.is_dir():
        raise RuntimeError(f"Apps directory not found: {apps_root}")

    for path in apps_root.rglob("*.html"):
        if "templates" in path.parts:
            yield path


def referenced_static_assets():
    references = {}

    for template_path in template_files():
        text = template_path.read_text(
            encoding="utf-8-sig",
        )

        for asset_path in STATIC_TAG_PATTERN.findall(text):
            references.setdefault(asset_path, set()).add(
                template_path.relative_to(settings.BASE_DIR)
            )

    return references


def main():
    references = referenced_static_assets()

    if not references:
        raise RuntimeError(
            "No literal Django static template references were found."
        )

    failures = []

    for asset_path in sorted(references):
        try:
            resolved_url = staticfiles_storage.url(asset_path)
        except Exception as exc:
            failures.append(
                (
                    asset_path,
                    references[asset_path],
                    str(exc),
                )
            )
            continue

        print(
            "STATIC_MANIFEST_OK="
            f"{asset_path} -> {resolved_url}"
        )

    print(
        "STATIC_TEMPLATE_REFERENCE_COUNT="
        f"{len(references)}"
    )

    if failures:
        for asset_path, templates, error in failures:
            template_list = ", ".join(
                str(path)
                for path in sorted(templates)
            )
            print(
                "STATIC_MANIFEST_ERROR="
                f"{asset_path} | templates={template_list} | {error}",
                file=sys.stderr,
            )

        raise RuntimeError(
            f"Static manifest verification failed for {len(failures)} asset(s)."
        )

    print("STATIC_MANIFEST_RESULT=PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"STATIC_MANIFEST_VERIFY_ERROR={exc}",
            file=sys.stderr,
        )
        sys.exit(1)
