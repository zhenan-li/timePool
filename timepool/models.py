from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


DAY_MINUTES = 24 * 60
UNALLOCATED_LABEL = "\u672a\u5206\u914d"

UNIT_MINUTES = "minutes"
UNIT_HOURS = "hours"

VIEW_DAY = "day"
VIEW_WEEK = "week"
VIEW_MONTH = "month"
VIEW_QUARTER = "quarter"
VIEW_YEAR = "year"

VIEW_LABELS = {
    VIEW_DAY: "Day",
    VIEW_WEEK: "Week",
    VIEW_MONTH: "Month",
    VIEW_QUARTER: "Quarter",
    VIEW_YEAR: "Year",
}


@dataclass(slots=True)
class Entry:
    title: str
    description: str
    minutes: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Entry":
        return cls(
            title=str(raw.get("title", "")).strip(),
            description=str(raw.get("description", "")).strip(),
            minutes=int(round(float(raw.get("minutes", 0)))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "minutes": int(self.minutes),
        }


@dataclass(slots=True)
class SummaryResult:
    start: date | None
    end: date | None
    title_totals: dict[str, int] = field(default_factory=dict)
    description_totals: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def day_count(self) -> int:
        if self.start is None or self.end is None or self.end < self.start:
            return 0
        return (self.end - self.start).days + 1

    @property
    def capacity_minutes(self) -> int:
        return self.day_count * DAY_MINUTES
