import argparse
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_git(*arguments, text=False):
    return subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )


def git_text(*arguments):
    return run_git(*arguments, text=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Create a snapshot of the DELISKY working tree."
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Destination ZIP file.",
    )

    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    listed = run_git(
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ).stdout

    relative_paths = sorted(
        {
            os.fsdecode(raw_path)
            for raw_path in listed.split(b"\0")
            if raw_path
        }
    )

    status = git_text(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )

    branch = git_text(
        "rev-parse",
        "--abbrev-ref",
        "HEAD",
    )

    commit = git_text(
        "rev-parse",
        "HEAD",
    )

    working_diff = run_git(
        "diff",
        "--binary",
    ).stdout

    staged_diff = run_git(
        "diff",
        "--cached",
        "--binary",
    ).stdout

    stored_files = []
    missing_files = []

    with zipfile.ZipFile(
        output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative_path in relative_paths:
            source_path = PROJECT_ROOT / relative_path

            if not source_path.is_file():
                missing_files.append(relative_path)
                continue

            archive_name = (
                "working-tree/"
                + relative_path.replace("\\", "/")
            )

            archive.write(
                source_path,
                arcname=archive_name,
            )

            stored_files.append(relative_path)

        archive.writestr(
            "metadata/git-status.txt",
            status + ("\n" if status else ""),
        )

        archive.writestr(
            "metadata/git-diff.patch",
            working_diff,
        )

        archive.writestr(
            "metadata/git-diff-cached.patch",
            staged_diff,
        )

        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "project_root": str(PROJECT_ROOT),
            "branch": branch,
            "commit": commit,
            "stored_file_count": len(stored_files),
            "missing_tracked_files": missing_files,
            "ignored_files_included": False,
        }

        archive.writestr(
            "metadata/manifest.json",
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            ),
        )

    with zipfile.ZipFile(output_path, mode="r") as archive:
        corrupt_entry = archive.testzip()

        if corrupt_entry is not None:
            raise RuntimeError(
                f"Working-tree ZIP verification failed: {corrupt_entry}"
            )

    print(f"WORKING_TREE_CREATED={output_path}")
    print(f"WORKING_TREE_FILES={len(stored_files)}")
    print(f"WORKING_TREE_SIZE={output_path.stat().st_size}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"WORKING_TREE_BACKUP_ERROR={exc}",
            file=sys.stderr,
        )
        sys.exit(1)
