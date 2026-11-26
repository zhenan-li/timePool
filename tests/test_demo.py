import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from timepool.backup_manager import BackupManager
from timepool.data_manager import DataManager
from timepool.demo import seed_demo_data
from timepool.models import DAY_MINUTES, VIEW_WEEK


class DemoDataTests(unittest.TestCase):
    def test_sample_has_valid_records_and_supports_edits(self) -> None:
        today = date(2026, 11, 24)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed_demo_data(root, today)
            manager = DataManager(
                root / "time_pool_data.json",
                BackupManager(root / "backup"),
                today_provider=lambda: today,
            )
            self.assertEqual(manager.start_date, today - timedelta(days=41))
            for offset in range(42):
                total = manager.get_day_total(today - timedelta(days=offset))
                self.assertGreater(total, 0)
                self.assertLess(total, DAY_MINUTES)

            iso = today.isocalendar()
            summary = manager.get_summary(VIEW_WEEK, {"year": iso.year, "week": iso.week})
            self.assertEqual(summary.end, today)
            self.assertTrue(any(len(groups) > 1 for groups in summary.description_totals.values()))

            manager.add_entry(today, "Test", "Trial edit", 10)
            self.assertEqual(manager.get_entries(today)[-1].minutes, 10)
            self.assertEqual(len(list((root / "backup").glob("backup_*.json"))), 1)
            with self.assertRaises(FileExistsError):
                seed_demo_data(root, today)
