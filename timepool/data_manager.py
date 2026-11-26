from __future__ import annotations

from .i18n import tr

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .backup_manager import BackupManager, BackupResult
from .models import DAY_MINUTES, UNALLOCATED_LABEL, Entry, SummaryResult
from .utils import clip_range, iter_dates, parse_iso_date, period_range, today_local


class ValidationError(ValueError):
    pass


class DataManager:
    def __init__(
        self,
        data_path: Path,
        backup_manager: BackupManager,
        today_provider: Callable[[], date] = today_local,
        default_start_date: date | None = None,
    ):
        self.data_path = data_path
        self.backup_manager = backup_manager
        self.today_provider = today_provider
        self.default_start_date = default_start_date
        self.data: dict[str, Any] = {}
        self.last_backup_result = BackupResult(False, tr("Not yet backed up"))
        self.load()

    @property
    def today(self) -> date:
        return self.today_provider()

    @property
    def start_date(self) -> date:
        return parse_iso_date(self.data["meta"]["start_date"])

    def load(self) -> None:
        file_existed = self.data_path.exists()
        if file_existed:
            self.data = json.loads(self.data_path.read_text(encoding="utf-8"))
        else:
            initial_start = self.default_start_date or self.today
            self.data = {
                "meta": {
                    "schema_version": 1,
                    "start_date": initial_start.isoformat(),
                    "created_at": initial_start.isoformat(),
                    "last_backup_date": None,
                    "last_backup_at": None,
                    "last_backup_file": None,
                },
                "days": {},
            }

        changed = self._normalize_structure()
        crossed_day = file_existed and self._latest_recorded_day() < self.today
        if crossed_day:
            self.last_backup_result = self.backup_manager.backup_if_needed(self.data, self.today)
            changed = True

        if self.ensure_days_until(self.today):
            changed = True

        if changed or not file_existed:
            self.save()

    def save(self) -> None:
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.data_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.data_path)

    def _normalize_structure(self) -> bool:
        changed = False
        if not isinstance(self.data, dict):
            self.data = {}
            changed = True

        meta = self.data.setdefault("meta", {})
        days = self.data.setdefault("days", {})
        if "schema_version" not in meta:
            meta["schema_version"] = 1
            changed = True
        if "start_date" not in meta:
            first_day = min(days.keys()) if days else (self.default_start_date or self.today).isoformat()
            meta["start_date"] = first_day
            changed = True
        for key in ("last_backup_date", "last_backup_at", "last_backup_file"):
            if key not in meta:
                meta[key] = None
                changed = True

        for day_key, payload in list(days.items()):
            if not isinstance(payload, dict):
                days[day_key] = {"entries": []}
                changed = True
            elif "entries" not in payload or not isinstance(payload["entries"], list):
                payload["entries"] = []
                changed = True
            normalized_entries = []
            for raw in payload["entries"]:
                entry = Entry.from_dict(raw)
                if entry.minutes > 0 and entry.title:
                    normalized_entries.append(entry.to_dict())
            if normalized_entries != payload["entries"]:
                payload["entries"] = normalized_entries
                changed = True
        return changed

    def _latest_recorded_day(self) -> date:
        keys = list(self.data.get("days", {}).keys())
        if not keys:
            return self.start_date
        return max(parse_iso_date(key) for key in keys)

    def ensure_days_until(self, end_date: date) -> bool:
        if end_date < self.start_date:
            return False
        changed = False
        for current in iter_dates(self.start_date, min(end_date, self.today)):
            key = current.isoformat()
            if key not in self.data["days"]:
                self.data["days"][key] = {"entries": []}
                changed = True
        return changed

    def _ensure_day(self, day: date) -> None:
        if day < self.start_date:
            raise ValidationError(tr("Dates before tracking started are not supported."))
        if day > self.today:
            raise ValidationError(tr("Future dates are not supported."))
        key = day.isoformat()
        if key not in self.data["days"]:
            self.data["days"][key] = {"entries": []}

    def get_entries(self, day: date) -> list[Entry]:
        key = day.isoformat()
        payload = self.data.get("days", {}).get(key, {"entries": []})
        return [Entry.from_dict(raw) for raw in payload.get("entries", [])]

    def get_day_total(self, day: date) -> int:
        return sum(entry.minutes for entry in self.get_entries(day))

    def get_unallocated_minutes(self, day: date) -> int:
        return DAY_MINUTES - self.get_day_total(day)

    def _validate_entry(self, title: str, description: str, minutes: int) -> Entry:
        clean_title = title.strip()
        clean_description = description.strip() or "\u672a\u547d\u540d\u5c0f\u7c7b"
        if not clean_title:
            raise ValidationError(tr("A category is required."))
        if minutes <= 0:
            raise ValidationError(tr("Duration must be greater than zero."))
        return Entry(clean_title, clean_description, int(minutes))

    def _validate_day_total(self, entries: list[Entry]) -> None:
        total = sum(entry.minutes for entry in entries)
        if total > DAY_MINUTES:
            overflow = total - DAY_MINUTES
            raise ValidationError(
                tr("This day exceeds 24 hours by {minutes} minutes.", minutes=overflow)
            )

    def _backup_before_mutation(self) -> None:
        self.last_backup_result = self.backup_manager.backup_if_needed(self.data, self.today)

    def add_entry(self, day: date, title: str, description: str, minutes: int) -> None:
        self._ensure_day(day)
        entry = self._validate_entry(title, description, minutes)
        entries = self.get_entries(day)
        entries.append(entry)
        self._validate_day_total(entries)

        self._backup_before_mutation()
        self.data["days"][day.isoformat()]["entries"] = [item.to_dict() for item in entries]
        self.save()

    def update_entry(self, day: date, index: int, title: str, description: str, minutes: int) -> None:
        self._ensure_day(day)
        entries = self.get_entries(day)
        if index < 0 or index >= len(entries):
            raise ValidationError(tr("Entry not found."))
        entries[index] = self._validate_entry(title, description, minutes)
        self._validate_day_total(entries)

        self._backup_before_mutation()
        self.data["days"][day.isoformat()]["entries"] = [item.to_dict() for item in entries]
        self.save()

    def delete_entry(self, day: date, index: int) -> None:
        self._ensure_day(day)
        entries = self.get_entries(day)
        if index < 0 or index >= len(entries):
            raise ValidationError(tr("Entry not found."))

        del entries[index]
        self._backup_before_mutation()
        self.data["days"][day.isoformat()]["entries"] = [item.to_dict() for item in entries]
        self.save()

    def get_clipped_range(
        self,
        view_mode: str,
        selection: dict[str, object],
    ) -> tuple[date | None, date | None]:
        raw_start, raw_end = period_range(view_mode, selection)
        return clip_range(raw_start, raw_end, self.start_date, self.today)

    def get_summary(
        self,
        view_mode: str,
        selection: dict[str, object],
        include_unallocated: bool = True,
    ) -> SummaryResult:
        start, end = self.get_clipped_range(view_mode, selection)
        result = SummaryResult(start, end)
        if start is None or end is None:
            return result

        self.ensure_days_until(end)
        for current in iter_dates(start, end):
            entries = self.get_entries(current)
            day_total = 0
            for entry in entries:
                day_total += entry.minutes
                result.title_totals[entry.title] = result.title_totals.get(entry.title, 0) + entry.minutes
                descriptions = result.description_totals.setdefault(entry.title, {})
                descriptions[entry.description] = descriptions.get(entry.description, 0) + entry.minutes

            if include_unallocated:
                unallocated = DAY_MINUTES - day_total
                result.title_totals[UNALLOCATED_LABEL] = result.title_totals.get(UNALLOCATED_LABEL, 0) + unallocated
                result.description_totals.setdefault(UNALLOCATED_LABEL, {UNALLOCATED_LABEL: 0})
                result.description_totals[UNALLOCATED_LABEL][UNALLOCATED_LABEL] += unallocated

        result.title_totals = dict(sorted(result.title_totals.items(), key=lambda item: item[1], reverse=True))
        result.description_totals = {
            title: dict(sorted(descriptions.items(), key=lambda item: item[1], reverse=True))
            for title, descriptions in result.description_totals.items()
        }
        return result
