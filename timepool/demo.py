import json
from datetime import date, timedelta
from pathlib import Path

from .models import Entry
from .utils import iter_dates


def seed_demo_data(root: Path, today: date) -> None:
    start = today - timedelta(days=41)
    days = {}
    for index, day in enumerate(iter_dates(start, today)):
        weekend = day.weekday() >= 5
        entries = [
            Entry("Personal", "Sleep", 450 + 15 * (index % 4)),
            Entry("Personal", "Meals", 90),
            Entry("Study", "Physics", 45 if weekend else 120 + 15 * (index % 3)),
            Entry("Study", "Reading", 60 if weekend else 30),
            Entry("Projects", "Programming", 150 if weekend else 75),
            Entry("Projects", "Design", 30 + 10 * (index % 3)),
            Entry("Exercise", "Running", 60 if weekend else 30),
        ]
        days[day.isoformat()] = {"entries": [entry.to_dict() for entry in entries]}

    sample = {"meta": {"start_date": start.isoformat()}, "days": days}
    with (root / "time_pool_data.json").open("x", encoding="utf-8") as handle:
        json.dump(sample, handle, ensure_ascii=False, indent=2)
