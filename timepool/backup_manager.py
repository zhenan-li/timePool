from __future__ import annotations

from .i18n import tr

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .utils import now_local


@dataclass(slots=True)
class BackupResult:
    performed: bool
    message: str
    path: Path | None = None


class BackupManager:
    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir

    def backup_if_needed(self, data: dict[str, Any], today: date) -> BackupResult:
        meta = data.setdefault("meta", {})
        today_key = today.isoformat()
        if meta.get("last_backup_date") == today_key:
            return BackupResult(False, tr("Already backed up today"))

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = now_local().strftime("%Y-%m-%d_%H%M%S_%f")
        backup_path = self.backup_dir / f"backup_{stamp}.json"
        counter = 1
        while backup_path.exists():
            backup_path = self.backup_dir / f"backup_{stamp}_{counter}.json"
            counter += 1

        backup_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        meta["last_backup_date"] = today_key
        meta["last_backup_at"] = now_local().isoformat(timespec="seconds")
        meta["last_backup_file"] = str(backup_path)
        return BackupResult(True, tr("Backup saved: {name}", name=backup_path.name), backup_path)
