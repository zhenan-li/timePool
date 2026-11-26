from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from timepool.backup_manager import BackupManager
from timepool.data_manager import DataManager, ValidationError
from timepool.models import DAY_MINUTES, UNALLOCATED_LABEL, VIEW_MONTH, VIEW_QUARTER, VIEW_YEAR


class DataManagerTests(unittest.TestCase):
    def make_manager(self, root: Path, *, today: date, start: date) -> DataManager:
        return DataManager(
            root / "time_pool_data.json",
            BackupManager(root / "backup"),
            today_provider=lambda: today,
            default_start_date=start,
        )

    def test_year_month_and_quarter_ranges_are_clipped_to_start_and_today(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            manager = self.make_manager(
                Path(tmp_name),
                today=date(2026, 7, 22),
                start=date(2026, 5, 22),
            )

            year = manager.get_summary(VIEW_YEAR, {"year": 2026})
            self.assertEqual(year.start, date(2026, 5, 22))
            self.assertEqual(year.end, date(2026, 7, 22))

            month = manager.get_summary(VIEW_MONTH, {"year": 2026, "month": 7})
            self.assertEqual(month.start, date(2026, 7, 1))
            self.assertEqual(month.end, date(2026, 7, 22))

            quarter = manager.get_summary(VIEW_QUARTER, {"year": 2026, "quarter": 3})
            self.assertEqual(quarter.start, date(2026, 7, 1))
            self.assertEqual(quarter.end, date(2026, 7, 22))

    def test_add_entry_updates_unallocated_and_rejects_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            manager = self.make_manager(
                Path(tmp_name),
                today=date(2026, 7, 22),
                start=date(2026, 7, 22),
            )

            manager.add_entry(date(2026, 7, 22), "工作", "深度工作", 120)
            self.assertEqual(manager.get_unallocated_minutes(date(2026, 7, 22)), DAY_MINUTES - 120)

            with self.assertRaises(ValidationError):
                manager.add_entry(date(2026, 7, 22), "学习", "阅读", DAY_MINUTES)

    def test_summary_includes_unallocated_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            manager = self.make_manager(
                Path(tmp_name),
                today=date(2026, 7, 22),
                start=date(2026, 7, 22),
            )

            manager.add_entry(date(2026, 7, 22), "工作", "深度工作", 60)
            summary = manager.get_summary(VIEW_YEAR, {"year": 2026})

            self.assertEqual(summary.title_totals["工作"], 60)
            self.assertEqual(summary.title_totals[UNALLOCATED_LABEL], DAY_MINUTES - 60)
            self.assertEqual(summary.description_totals["工作"]["深度工作"], 60)

    def test_daily_backup_is_created_once_per_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            manager = self.make_manager(
                Path(tmp_name),
                today=date(2026, 7, 22),
                start=date(2026, 7, 22),
            )

            manager.add_entry(date(2026, 7, 22), "工作", "深度工作", 30)
            manager.add_entry(date(2026, 7, 22), "学习", "阅读", 30)

            backups = list((Path(tmp_name) / "backup").glob("backup_*.json"))
            self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
