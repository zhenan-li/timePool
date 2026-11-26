from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Iterable

from .i18n import tr

from .models import (
    UNIT_HOURS,
    UNIT_MINUTES,
    VIEW_DAY,
    VIEW_MONTH,
    VIEW_QUARTER,
    VIEW_WEEK,
    VIEW_YEAR,
)


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def today_local() -> date:
    return date.today()


def now_local() -> datetime:
    return datetime.now()


def iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def iso_weeks_in_year(year: int) -> int:
    return date(year, 12, 28).isocalendar().week


def week_range(year: int, week: int) -> tuple[date, date]:
    max_week = iso_weeks_in_year(year)
    safe_week = max(1, min(week, max_week))
    start = date.fromisocalendar(year, safe_week, 1)
    return start, start + timedelta(days=6)


def month_range(year: int, month: int) -> tuple[date, date]:
    safe_month = max(1, min(month, 12))
    last_day = calendar.monthrange(year, safe_month)[1]
    return date(year, safe_month, 1), date(year, safe_month, last_day)


def quarter_range(year: int, quarter: int) -> tuple[date, date]:
    safe_quarter = max(1, min(quarter, 4))
    start_month = (safe_quarter - 1) * 3 + 1
    end_month = start_month + 2
    start = date(year, start_month, 1)
    end = date(year, end_month, calendar.monthrange(year, end_month)[1])
    return start, end


def year_range(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def period_range(view_mode: str, selection: dict[str, object]) -> tuple[date, date]:
    if view_mode == VIEW_DAY:
        selected_date = selection["date"]
        if not isinstance(selected_date, date):
            raise TypeError("day selection requires a date object")
        return selected_date, selected_date
    if view_mode == VIEW_WEEK:
        return week_range(int(selection["year"]), int(selection["week"]))
    if view_mode == VIEW_MONTH:
        return month_range(int(selection["year"]), int(selection["month"]))
    if view_mode == VIEW_QUARTER:
        return quarter_range(int(selection["year"]), int(selection["quarter"]))
    if view_mode == VIEW_YEAR:
        return year_range(int(selection["year"]))
    raise ValueError(f"unknown view mode: {view_mode}")


def clip_range(start: date, end: date, minimum: date, maximum: date) -> tuple[date | None, date | None]:
    clipped_start = max(start, minimum)
    clipped_end = min(end, maximum)
    if clipped_end < clipped_start:
        return None, None
    return clipped_start, clipped_end


def format_minutes(minutes: int, unit: str) -> str:
    if unit == UNIT_HOURS:
        hours = round(minutes / 60, 2)
        return tr("{value:g} hr", value=hours)
    return tr("{value} min", value=int(minutes))


def convert_to_minutes(value: float, unit: str) -> int:
    if unit == UNIT_HOURS:
        return int(round(value * 60))
    if unit == UNIT_MINUTES:
        return int(round(value))
    raise ValueError(f"unknown unit: {unit}")
