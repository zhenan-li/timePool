from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from timepool.ai_services import AIServiceError, LLMTimeParser, RealtimeSTTClient, extract_json_object
from timepool.settings_manager import SettingsManager


class AIServiceTests(unittest.TestCase):
    def test_realtime_connection_refused_points_to_local_recording(self) -> None:
        client = RealtimeSTTClient({"realtime_url": "ws://127.0.0.1:8000"}, "")
        with patch("websocket.create_connection", side_effect=ConnectionRefusedError(10061, "refused")):
            with self.assertRaisesRegex(AIServiceError, "Record locally"):
                client.listen(lambda _text: None, threading.Event())

    def test_extract_json_object_from_fenced_text(self) -> None:
        parsed = extract_json_object('```json\n{"entries":[],"warnings":[]}\n```')
        self.assertEqual(parsed["entries"], [])

    def test_normalize_filters_out_of_range_entries(self) -> None:
        parser = LLMTimeParser({"model": "test", "base_url": "http://localhost"}, "")
        entries, warnings = parser._normalize(
            {
                "entries": [
                    {"date": "2026-07-07", "title": "工作", "description": "写代码", "minutes": 90},
                    {"date": "2026-07-08", "title": "未来", "description": "无效", "minutes": 30},
                ]
            },
            default_date=date(2026, 7, 7),
            start_date=date(2026, 7, 1),
            today=date(2026, 7, 7),
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].minutes, 90)
        self.assertTrue(any("out of allowed range" in item for item in warnings))

    def test_settings_manager_merges_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text('{"llm":{"base_url":"http://127.0.0.1:11434/v1"}}', encoding="utf-8")
            manager = SettingsManager(path)
            self.assertEqual(manager.get("llm")["base_url"], "http://127.0.0.1:11434/v1")
            self.assertIn("model", manager.get("llm"))
            self.assertIn("mode", manager.get("stt"))


if __name__ == "__main__":
    unittest.main()
