from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> int:
    # Some dependencies still write console output in a windowed executable.
    for stream in ("stdout", "stderr"):
        if getattr(sys, stream) is None:
            setattr(sys, stream, open(os.devnull, "w", encoding="utf-8"))

    parser = argparse.ArgumentParser(description="Start Time Pool.")
    parser.add_argument("--demo", action="store_true", help="Use disposable sample data.")
    parser.add_argument("--check-runtime", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    from timepool.qt_compat import QApplication

    app = QApplication(sys.argv[:1])
    if args.check_runtime is not None:
        from timepool.runtime_check import check_runtime

        return check_runtime(app, args.check_runtime)
    if args.demo:
        from timepool.demo import seed_demo_data
        from timepool.utils import today_local

        with TemporaryDirectory(prefix="timepool-demo-") as directory:
            root = Path(directory)
            seed_demo_data(root, today_local())
            return run_window(app, root, demo=True)

    return run_window(app)


def run_window(app, root: Path | None = None, *, demo: bool = False) -> int:
    from timepool.main_window import MainWindow

    def rebuild() -> None:
        nonlocal window
        old = window
        window = MainWindow(root, demo=demo)
        window.setGeometry(old.geometry())
        window.ai_date_edit.setDate(old.ai_date_edit.date())
        window.ai_text.setPlainText(old.ai_text.toPlainText())
        window.ai_drafts = old.ai_drafts
        window._pending_audio = old._pending_audio
        window.display_unit = old.display_unit
        window.view_combo.setCurrentIndex(old.view_combo.currentIndex())
        window.day_date_edit.setDate(old.day_date_edit.date())
        window.week_year_spin.setValue(old.week_year_spin.value())
        window.week_spin.setValue(old.week_spin.value())
        window.month_year_spin.setValue(old.month_year_spin.value())
        window.month_combo.setCurrentIndex(old.month_combo.currentIndex())
        window.quarter_year_spin.setValue(old.quarter_year_spin.value())
        window.quarter_combo.setCurrentIndex(old.quarter_combo.currentIndex())
        window.year_spin.setValue(old.year_spin.value())
        window._populate_ai_preview()
        window.refresh()
        window._update_ai_controls()
        window.language_changed.connect(rebuild)
        window.show()
        old.close()
        old.deleteLater()

    window = MainWindow(root, demo=demo)
    window.language_changed.connect(rebuild)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
