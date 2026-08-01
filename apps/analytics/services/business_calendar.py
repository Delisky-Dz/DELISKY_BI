from datetime import date, timedelta


# Python weekday():
# Monday=0 ... Sunday=6
#
# DELISKY works Saturday through Wednesday.
# Thursday and Friday are regular non-working days.
DELISKY_WORKING_WEEKDAYS = frozenset(
    {
        0,  # Monday
        1,  # Tuesday
        2,  # Wednesday
        5,  # Saturday
        6,  # Sunday
    }
)


def is_delisky_working_day(day: date) -> bool:
    return day.weekday() in DELISKY_WORKING_WEEKDAYS


def delisky_working_dates(
    period_start: date,
    period_end: date,
) -> tuple[date, ...]:
    if period_end < period_start:
        raise ValueError(
            "period_end cannot be before period_start."
        )

    result: list[date] = []
    current = period_start

    while current <= period_end:
        if is_delisky_working_day(current):
            result.append(current)

        current += timedelta(days=1)

    return tuple(result)
