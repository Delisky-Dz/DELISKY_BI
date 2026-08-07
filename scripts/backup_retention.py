#!/usr/bin/env python3
"""Safe retention planner for DELISKY local backups.

The script defaults to dry-run mode. It only considers strict YYYY-MM-DD
directories directly below PostgreSQL, Project, and Media.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

CATEGORIES = ("PostgreSQL", "Project", "Media", "Secrets")
DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class BackupDay:
    day: date
    paths: tuple[Path, ...]
    size_bytes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or apply DELISKY backup retention.")
    parser.add_argument("--backup-root", required=True, type=Path)
    parser.add_argument("--keep-all-days", type=int, default=30)
    parser.add_argument("--keep-weekly-weeks", type=int, default=12)
    parser.add_argument("--keep-monthly-months", type=int, default=12)
    parser.add_argument("--minimum-protected-days", type=int, default=14)
    parser.add_argument("--emergency-free-gb", type=float, default=50.0)
    parser.add_argument("--emergency-target-gb", type=float, default=75.0)
    parser.add_argument("--today", help="Override current date as YYYY-MM-DD.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Report only; delete nothing.")
    mode.add_argument("--apply", action="store_true", help="Delete eligible dated directories.")
    return parser.parse_args()


def parse_day_dir(path: Path) -> date | None:
    if not path.is_dir() or path.is_symlink():
        return None
    try:
        parsed = datetime.strptime(path.name, DATE_FORMAT).date()
    except ValueError:
        return None
    return parsed if parsed.strftime(DATE_FORMAT) == path.name else None


def directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file() and not item.is_symlink():
            total += item.stat().st_size
    return total


def discover_backup_days(root: Path) -> list[BackupDay]:
    grouped: dict[date, list[Path]] = defaultdict(list)

    for category in CATEGORIES:
        category_root = root / category
        if not category_root.exists():
            continue
        if not category_root.is_dir() or category_root.is_symlink():
            raise RuntimeError(f"Unsafe category path: {category_root}")

        for child in category_root.iterdir():
            parsed = parse_day_dir(child)
            if parsed is not None:
                grouped[parsed].append(child)

    result: list[BackupDay] = []
    for backup_day, paths in grouped.items():
        ordered_paths = tuple(sorted(paths, key=lambda value: str(value).lower()))
        size = sum(directory_size(path) for path in ordered_paths)
        result.append(BackupDay(backup_day, ordered_paths, size))

    return sorted(result, key=lambda item: item.day, reverse=True)


def month_age(today: date, candidate: date) -> int:
    return (today.year - candidate.year) * 12 + (today.month - candidate.month)


def choose_retention(days: list[BackupDay], today: date, args: argparse.Namespace) -> tuple[set[date], dict[date, str]]:
    kept: set[date] = set()
    reasons: dict[date, str] = {}

    def keep(day: date, reason: str) -> None:
        if day not in kept:
            kept.add(day)
            reasons[day] = reason

    # Always protect the most recent distinct backup dates.
    for item in days[: args.minimum_protected_days]:
        keep(item.day, "minimum-protected")

    # Keep every backup date inside the recent all-days window.
    recent_cutoff = today - timedelta(days=max(args.keep_all_days - 1, 0))
    for item in days:
        if item.day >= recent_cutoff:
            keep(item.day, "recent-all")

    # Keep the newest available backup date in each ISO week.
    weekly_cutoff = today - timedelta(weeks=max(args.keep_weekly_weeks, 0))
    weekly_candidates: dict[tuple[int, int], date] = {}
    for item in days:
        if weekly_cutoff <= item.day < recent_cutoff:
            iso = item.day.isocalendar()
            key = (iso.year, iso.week)
            weekly_candidates.setdefault(key, item.day)
    for selected in weekly_candidates.values():
        keep(selected, "weekly")

    # Keep the newest available backup date in each calendar month.
    monthly_candidates: dict[tuple[int, int], date] = {}
    for item in days:
        age = month_age(today, item.day)
        if 0 <= age < args.keep_monthly_months and item.day < weekly_cutoff:
            key = (item.day.year, item.day.month)
            monthly_candidates.setdefault(key, item.day)
    for selected in monthly_candidates.values():
        keep(selected, "monthly")

    return kept, reasons


def validate_args(args: argparse.Namespace) -> None:
    integer_options = (
        ("keep-all-days", args.keep_all_days),
        ("keep-weekly-weeks", args.keep_weekly_weeks),
        ("keep-monthly-months", args.keep_monthly_months),
        ("minimum-protected-days", args.minimum_protected_days),
    )
    for name, value in integer_options:
        if value < 0:
            raise ValueError(f"--{name} cannot be negative.")

    if args.emergency_free_gb < 0 or args.emergency_target_gb < 0:
        raise ValueError("Emergency free-space values cannot be negative.")
    if args.emergency_target_gb < args.emergency_free_gb:
        raise ValueError("--emergency-target-gb must be >= --emergency-free-gb.")


def ensure_safe_root(root: Path) -> Path:
    resolved = root.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise RuntimeError(f"Backup root does not exist: {resolved}")
    if resolved.name.casefold() != "delisky_backups":
        raise RuntimeError(f"Refusing unexpected backup root: {resolved}")
    return resolved


def format_mb(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def remove_backup_day(item: BackupDay, root: Path) -> None:
    allowed_parents = {(root / category).resolve() for category in CATEGORIES}
    for path in item.paths:
        resolved = path.resolve()
        if resolved.parent not in allowed_parents:
            raise RuntimeError(f"Refusing unsafe deletion path: {resolved}")
        if resolved.name != item.day.strftime(DATE_FORMAT):
            raise RuntimeError(f"Refusing non-date directory: {resolved}")
        if resolved.is_symlink():
            raise RuntimeError(f"Refusing symbolic link: {resolved}")
        shutil.rmtree(resolved)


def main() -> int:
    args = parse_args()
    validate_args(args)
    root = ensure_safe_root(args.backup_root)
    today = datetime.strptime(args.today, DATE_FORMAT).date() if args.today else date.today()
    dry_run = not args.apply

    days = discover_backup_days(root)
    kept, reasons = choose_retention(days, today, args)
    normal_delete = [item for item in days if item.day not in kept]

    usage = shutil.disk_usage(root)
    free_gb = usage.free / (1024 ** 3)
    emergency = free_gb < args.emergency_free_gb

    protected_dates = {item.day for item in days[: args.minimum_protected_days]}
    recent_cutoff = today - timedelta(days=max(args.keep_all_days - 1, 0))

    # Emergency candidates may sacrifice weekly/monthly representatives, but never
    # the minimum protected dates or any date in the recent all-days window.
    emergency_extra = [
        item
        for item in reversed(days)
        if item.day in kept
        and item.day not in protected_dates
        and item.day < recent_cutoff
    ]

    print(f"RETENTION_MODE={'DRY_RUN' if dry_run else 'APPLY'}")
    print(f"RETENTION_TODAY={today.isoformat()}")
    print(f"RETENTION_BACKUP_DATES={len(days)}")
    print(f"RETENTION_FREE_GB={free_gb:.2f}")
    print(f"RETENTION_EMERGENCY={'YES' if emergency else 'NO'}")

    for item in days:
        if item.day in kept:
            print(f"KEEP {item.day.isoformat()} reason={reasons[item.day]} size={format_mb(item.size_bytes)}")
        else:
            print(f"DELETE_NORMAL {item.day.isoformat()} size={format_mb(item.size_bytes)}")

    deleted = 0
    reclaimed = 0

    for item in sorted(normal_delete, key=lambda value: value.day):
        if dry_run:
            continue
        remove_backup_day(item, root)
        deleted += 1
        reclaimed += item.size_bytes

    if args.apply and emergency:
        current_free = shutil.disk_usage(root).free / (1024 ** 3)
        for item in emergency_extra:
            if current_free >= args.emergency_target_gb:
                break
            if any(not path.exists() for path in item.paths):
                continue
            print(f"DELETE_EMERGENCY {item.day.isoformat()} size={format_mb(item.size_bytes)}")
            remove_backup_day(item, root)
            deleted += 1
            reclaimed += item.size_bytes
            current_free = shutil.disk_usage(root).free / (1024 ** 3)

        if current_free < args.emergency_target_gb:
            print(
                "RETENTION_WARNING=Free space remains below emergency target; "
                "protected recent backups were not deleted."
            )

    print(f"RETENTION_DELETE_CANDIDATES={len(normal_delete)}")
    print(f"RETENTION_DELETED_DATES={deleted}")
    print(f"RETENTION_RECLAIMED_MB={reclaimed / (1024 * 1024):.2f}")
    print("RETENTION_RESULT=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"RETENTION_RESULT=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
