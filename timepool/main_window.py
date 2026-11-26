from __future__ import annotations

from .i18n import set_language, tr

import threading
from collections import defaultdict
from datetime import date
from pathlib import Path
from time import monotonic

from .ai_services import ExtractedTimeEntry, LLMTimeParser, RealtimeSTTClient, STTClient
from .backup_manager import BackupManager
from .chart_manager import ChartManager
from .data_manager import DataManager, ValidationError
from .dialogs import RecordDialog, to_qdate
from .local_stt import SPEECH_LANGUAGES, LocalTranscriber, NoSpeechError
from .microphone import MAX_RECORDING_SECONDS, MicrophoneRecorder, RecordedAudio
from .paths import user_data_root
from .models import (
    UNIT_HOURS,
    UNIT_MINUTES,
    UNALLOCATED_LABEL,
    VIEW_DAY,
    VIEW_LABELS,
    VIEW_MONTH,
    VIEW_QUARTER,
    VIEW_WEEK,
    VIEW_YEAR,
)
from .qt_compat import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLocale,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QThread,
    QTimer,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
    qdate_to_date,
)
from .settings_dialog import SettingsDialog
from .settings_manager import SettingsManager
from .sync_manager import SyncManager
from .utils import format_minutes, iso_weeks_in_year


class BackgroundTask(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action

    def run(self) -> None:
        try:
            self.succeeded.emit(self.action())
        except Exception as exc:
            self.failed.emit(str(exc))


class RealtimeTask(QThread):
    text_received = Signal(str)

    def __init__(self, client: RealtimeSTTClient, parent=None):
        super().__init__(parent)
        self.client = client
        self.stop_event = threading.Event()
        self.error: str | None = None

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        try:
            self.client.listen(lambda text: self.text_received.emit(text), self.stop_event)
        except Exception as exc:
            self.error = str(exc)


class ClearableTreeWidget(QTreeWidget):
    blank_clicked = Signal()

    def mousePressEvent(self, event) -> None:
        point = event.position().toPoint()
        if self.itemAt(point) is None:
            self.clearSelection()
            self.setCurrentItem(None)
            self.blank_clicked.emit()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    language_changed = Signal()

    def __init__(self, data_root: Path | None = None, *, demo: bool = False):
        super().__init__()
        self.resize(1380, 820)

        root = data_root if data_root is not None else user_data_root()
        self.settings_manager = SettingsManager(root / "time_pool_settings.json")
        self.language = "zh" if self.settings_manager.get("ui").get("language") == "zh" else "en"
        set_language(self.language)
        QLocale.setDefault(QLocale("zh_CN" if self.language == "zh" else "en_US"))
        self.setWindowTitle(tr("Time Pool | Trial" if demo else "Time Pool"))
        self.data_manager = DataManager(
            root / "time_pool_data.json",
            BackupManager(root / "backup"),
        )
        self.sync_manager = SyncManager()
        self.display_unit = UNIT_MINUTES
        self.selected_title: str | None = None
        self.current_summary = None
        self.ai_drafts: list[ExtractedTimeEntry] = []
        self._syncing_selection = False
        self._active_task: BackgroundTask | None = None
        self._realtime_task: RealtimeTask | None = None
        self._recorder = MicrophoneRecorder()
        self._transcriber = LocalTranscriber()
        self._downloading_model = False
        self._recording_started: float | None = None
        self._pending_audio: RecordedAudio | None = None
        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(200)
        self._recording_timer.timeout.connect(self._update_recording)

        self._build_ui()
        self._connect_signals()
        self._update_ai_controls()
        self._apply_style()
        self.refresh()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_middle_panel())
        splitter.addWidget(self._build_chart_panel())
        splitter.setSizes([250, 620, 510])

        root_layout.addWidget(splitter, 1)
        root_layout.addWidget(self._build_bottom_bar())
        self.setCentralWidget(central)

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        panel.setMinimumWidth(230)
        panel.setMaximumWidth(310)
        layout = QVBoxLayout(panel)

        title = QLabel(tr("Time Pool"))
        title.setObjectName("appTitle")
        subtitle = QLabel(tr("Local time tracking"))
        subtitle.setObjectName("mutedLabel")
        subtitle.setWordWrap(True)

        self.view_combo = QComboBox()
        for mode in (VIEW_DAY, VIEW_WEEK, VIEW_MONTH, VIEW_QUARTER, VIEW_YEAR):
            self.view_combo.addItem(tr(VIEW_LABELS[mode]), mode)

        self.selector_stack = QStackedWidget()
        self._build_day_selector()
        self._build_week_selector()
        self._build_month_selector()
        self._build_quarter_selector()
        self._build_year_selector()

        self.range_label = QLabel()
        self.range_label.setWordWrap(True)
        self.start_label = QLabel(tr("Started: {date}", date=self.data_manager.start_date.isoformat()))
        self.start_label.setObjectName("mutedLabel")
        self.sync_status_label = QLabel(self.sync_manager.status_text())
        self.sync_status_label.setWordWrap(True)
        self.sync_status_label.setObjectName("mutedLabel")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(12)
        layout.addWidget(QLabel(tr("Period")))
        layout.addWidget(self.view_combo)
        layout.addSpacing(8)
        layout.addWidget(self.selector_stack)
        layout.addSpacing(8)
        layout.addWidget(QLabel(tr("Selected range")))
        layout.addWidget(self.range_label)
        layout.addWidget(self.start_label)
        layout.addStretch(1)
        self.interface_language_combo = QComboBox()
        self.interface_language_combo.addItem("English", "en")
        self.interface_language_combo.addItem("\u7b80\u4f53\u4e2d\u6587", "zh")
        self.interface_language_combo.setCurrentIndex(self.interface_language_combo.findData(self.language))
        layout.addWidget(QLabel(tr("Interface language")))
        layout.addWidget(self.interface_language_combo)
        layout.addWidget(self.sync_status_label)
        return panel

    def _selector_page(self) -> tuple[QWidget, QGridLayout]:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        return page, layout

    def _build_day_selector(self) -> None:
        page, layout = self._selector_page()
        self.day_date_edit = QDateEdit()
        self.day_date_edit.setCalendarPopup(True)
        self.day_date_edit.setDateRange(to_qdate(self.data_manager.start_date), to_qdate(self.data_manager.today))
        self.day_date_edit.setDate(to_qdate(self.data_manager.today))
        layout.addWidget(QLabel(tr("Date")), 0, 0)
        layout.addWidget(self.day_date_edit, 1, 0)
        self.selector_stack.addWidget(page)

    def _build_week_selector(self) -> None:
        page, layout = self._selector_page()
        iso = self.data_manager.today.isocalendar()
        self.week_year_spin = self._year_spin()
        self.week_spin = QSpinBox()
        self.week_spin.setRange(1, iso_weeks_in_year(iso.year))
        self.week_year_spin.setValue(iso.year)
        self.week_spin.setValue(iso.week)
        layout.addWidget(QLabel(tr("Year")), 0, 0)
        layout.addWidget(QLabel(tr("Week")), 0, 1)
        layout.addWidget(self.week_year_spin, 1, 0)
        layout.addWidget(self.week_spin, 1, 1)
        self.selector_stack.addWidget(page)

    def _build_month_selector(self) -> None:
        page, layout = self._selector_page()
        self.month_year_spin = self._year_spin()
        self.month_combo = QComboBox()
        for month in range(1, 13):
            self.month_combo.addItem(tr("{month:02d}", month=month), month)
        self.month_year_spin.setValue(self.data_manager.today.year)
        self.month_combo.setCurrentIndex(self.data_manager.today.month - 1)
        layout.addWidget(QLabel(tr("Year")), 0, 0)
        layout.addWidget(QLabel(tr("Month")), 0, 1)
        layout.addWidget(self.month_year_spin, 1, 0)
        layout.addWidget(self.month_combo, 1, 1)
        self.selector_stack.addWidget(page)

    def _build_quarter_selector(self) -> None:
        page, layout = self._selector_page()
        self.quarter_year_spin = self._year_spin()
        self.quarter_combo = QComboBox()
        for quarter in range(1, 5):
            self.quarter_combo.addItem(tr("Q{quarter}", quarter=quarter), quarter)
        current_quarter = (self.data_manager.today.month - 1) // 3 + 1
        self.quarter_year_spin.setValue(self.data_manager.today.year)
        self.quarter_combo.setCurrentIndex(current_quarter - 1)
        layout.addWidget(QLabel(tr("Year")), 0, 0)
        layout.addWidget(QLabel(tr("Quarter")), 0, 1)
        layout.addWidget(self.quarter_year_spin, 1, 0)
        layout.addWidget(self.quarter_combo, 1, 1)
        self.selector_stack.addWidget(page)

    def _build_year_selector(self) -> None:
        page, layout = self._selector_page()
        self.year_spin = self._year_spin()
        self.year_spin.setValue(self.data_manager.today.year)
        layout.addWidget(QLabel(tr("Year")), 0, 0)
        layout.addWidget(self.year_spin, 1, 0)
        self.selector_stack.addWidget(page)

    def _year_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(self.data_manager.start_date.year, self.data_manager.today.year)
        spin.setValue(self.data_manager.today.year)
        return spin

    def _build_middle_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._build_ai_panel())
        layout.addWidget(self._build_table_panel(), 1)
        return panel

    def _build_ai_panel(self) -> QWidget:
        group = QGroupBox(tr("AI quick entry"))
        layout = QVBoxLayout(group)

        top = QHBoxLayout()
        self.ai_date_edit = QDateEdit()
        self.ai_date_edit.setCalendarPopup(True)
        self.ai_date_edit.setDateRange(to_qdate(self.data_manager.start_date), to_qdate(self.data_manager.today))
        self.ai_date_edit.setDate(to_qdate(self.data_manager.today))
        self.choose_audio_button = QPushButton(tr("File STT"))
        self.realtime_button = QPushButton(tr("External STT"))
        self.realtime_button.setToolTip(tr("Receives transcript text from an external WebSocket. It does not use your microphone."))
        self.extract_button = QPushButton(tr("Preview entries"))
        self.apply_ai_button = QPushButton(tr("Save entries"))
        self.settings_button = QPushButton(tr("Settings"))
        top.addWidget(QLabel(tr("Target date")))
        top.addWidget(self.ai_date_edit)
        top.addStretch(1)
        top.addWidget(self.extract_button)
        top.addWidget(self.apply_ai_button)
        top.addWidget(self.settings_button)

        voice = QHBoxLayout()
        self.record_button = QPushButton(tr("Record locally"))
        self.record_button.setObjectName("recordButton")
        self.record_button.setToolTip(tr("Default microphone. Up to two minutes per recording."))
        self.cancel_record_button = QPushButton(tr("Cancel recording"))
        self.retry_record_button = QPushButton(tr("Retry transcription"))
        self.recording_time = QLabel("00:00")
        self.recording_time.setMinimumWidth(44)
        self.recording_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        voice.addWidget(self.record_button)
        voice.addWidget(self.recording_time)
        voice.addWidget(self.cancel_record_button)
        voice.addWidget(self.retry_record_button)
        voice.addStretch(1)
        voice.addWidget(self.choose_audio_button)
        voice.addWidget(self.realtime_button)

        model_row = QHBoxLayout()
        self.speech_language_combo = QComboBox()
        for code, label in zip(SPEECH_LANGUAGES, ("Auto detect", "English", "Mandarin"), strict=True):
            self.speech_language_combo.addItem(tr(label), code)
        preferred_language = self.settings_manager.get("local_stt").get("language")
        self.speech_language_combo.setCurrentIndex(max(0, self.speech_language_combo.findData(preferred_language)))
        self.download_model_button = QPushButton(tr("Download model"))
        self.model_status_label = QLabel()
        self.model_status_label.setObjectName("mutedLabel")
        self.model_status_label.setWordWrap(True)
        self.model_progress = QProgressBar()
        self.model_progress.setRange(0, 0)
        self.model_progress.setMaximumWidth(70)
        model_row.addWidget(QLabel(tr("Speech language")))
        model_row.addWidget(self.speech_language_combo)
        model_row.addStretch(1)
        model_row.addWidget(self.model_status_label)
        model_row.addWidget(self.model_progress)
        model_row.addWidget(self.download_model_button)

        self.ai_text = QPlainTextEdit()
        self.ai_text.setPlaceholderText(
            tr("Write or record a note, e.g. I studied physics for 90 minutes this morning.")
        )
        self.ai_text.setMaximumHeight(92)

        self.ai_preview = QTreeWidget()
        self.ai_preview.setColumnCount(4)
        self.ai_preview.setHeaderLabels([tr("Date"), tr("Category"), tr("Subcategory"), tr("Duration")])
        self.ai_preview.setMaximumHeight(120)
        header = self.ai_preview.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.ai_status_label = QLabel(tr("Ready"))
        self.ai_status_label.setObjectName("mutedLabel")
        self.ai_status_label.setWordWrap(True)

        layout.addLayout(top)
        layout.addLayout(voice)
        layout.addLayout(model_row)
        layout.addWidget(self.ai_text)
        layout.addWidget(self.ai_preview)
        layout.addWidget(self.ai_status_label)
        return group

    def _build_table_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        toolbar = QHBoxLayout()
        heading = QLabel(tr("Activity log"))
        heading.setObjectName("sectionTitle")
        self.table_unit_button = QPushButton(tr("Table: min"))
        self.table_unit_button.setToolTip(tr("Switch the time unit in the table, chart, and summary."))
        toolbar.addWidget(heading)
        toolbar.addStretch(1)
        toolbar.addWidget(self.table_unit_button)

        self.tree = ClearableTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([tr("Category / subcategory"), tr("Duration"), tr("Share")])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        layout.addLayout(toolbar)
        layout.addWidget(self.tree, 1)
        return panel

    def _build_chart_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        heading = QLabel(tr("Time distribution"))
        heading.setObjectName("sectionTitle")
        self.chart = ChartManager()
        layout.addWidget(heading)
        layout.addWidget(self.chart, 1)
        return panel

    def _build_bottom_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("bottomBar")
        layout = QHBoxLayout(bar)

        self.add_button = QPushButton(tr("Add entry"))
        self.edit_button = QPushButton(tr("Edit entry"))
        self.delete_button = QPushButton(tr("Delete entry"))
        self.backfill_button = QPushButton(tr("Backfill"))
        self.global_unit_button = QPushButton(tr("Unit: min"))
        self.sync_button = QPushButton(tr("Sync"))
        self.backup_status_label = QLabel(tr("Backup: not yet created"))
        self.backup_status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        for button in (
            self.add_button,
            self.edit_button,
            self.delete_button,
            self.backfill_button,
            self.global_unit_button,
            self.sync_button,
        ):
            layout.addWidget(button)
        layout.addWidget(self.backup_status_label, 1)
        return bar

    def _connect_signals(self) -> None:
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        self.day_date_edit.dateChanged.connect(lambda _date: self.refresh())
        self.week_year_spin.valueChanged.connect(self._on_week_year_changed)
        self.week_spin.valueChanged.connect(lambda _value: self.refresh())
        self.month_year_spin.valueChanged.connect(lambda _value: self.refresh())
        self.month_combo.currentIndexChanged.connect(lambda _index: self.refresh())
        self.quarter_year_spin.valueChanged.connect(lambda _value: self.refresh())
        self.quarter_combo.currentIndexChanged.connect(lambda _index: self.refresh())
        self.year_spin.valueChanged.connect(lambda _value: self.refresh())

        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.tree.blank_clicked.connect(lambda: self._clear_selected_title(clear_tree=False))
        self.chart.title_selected.connect(self._select_title_from_chart)
        self.chart.blank_clicked.connect(lambda: self._clear_selected_title(clear_tree=True))

        self.add_button.clicked.connect(self._add_record)
        self.edit_button.clicked.connect(self._edit_record)
        self.delete_button.clicked.connect(self._delete_record)
        self.backfill_button.clicked.connect(self._backfill_record)
        self.global_unit_button.clicked.connect(self._toggle_display_unit)
        self.table_unit_button.clicked.connect(self._toggle_display_unit)
        self.sync_button.clicked.connect(self._show_sync_placeholder)

        self.settings_button.clicked.connect(self._open_settings)
        self.interface_language_combo.currentIndexChanged.connect(self._change_interface_language)
        self.speech_language_combo.currentIndexChanged.connect(self._save_speech_language)
        self.download_model_button.clicked.connect(self._download_speech_model)
        self.record_button.clicked.connect(self._toggle_recording)
        self.cancel_record_button.clicked.connect(self._cancel_recording)
        self.retry_record_button.clicked.connect(self._transcribe_recording)
        self.choose_audio_button.clicked.connect(self._transcribe_audio_file)
        self.realtime_button.clicked.connect(self._toggle_realtime_stt)
        self.extract_button.clicked.connect(self._extract_ai_entries)
        self.apply_ai_button.clicked.connect(self._apply_ai_entries)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f7f9;
                color: #1f2933;
                font-size: 14px;
            }
            QFrame#sidePanel, QFrame#bottomBar, QGroupBox {
                background: #ffffff;
                border: 1px solid #d9dee7;
                border-radius: 6px;
            }
            QGroupBox {
                margin-top: 12px;
                padding: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel#appTitle {
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#sectionTitle {
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#mutedLabel {
                color: #667085;
                font-weight: 400;
            }
            QPushButton, QComboBox, QDateEdit, QSpinBox, QTreeWidget, QPlainTextEdit, QLineEdit {
                background: #ffffff;
                border: 1px solid #cfd6e0;
                border-radius: 5px;
                padding: 5px 7px;
            }
            QPushButton:hover {
                background: #eef4ff;
            }
            QPushButton#recordButton:enabled {
                background: #e4f4ef;
                color: #155548;
                border-color: #a5cfc4;
                font-weight: 600;
            }
            QPushButton#recordButton:enabled:hover {
                background: #d3ede5;
            }
            QPushButton#recordButton[recording="true"]:enabled {
                background: #fbe8e8;
                color: #912e2b;
                border-color: #ebadab;
            }
            QTreeWidget {
                padding: 0;
                alternate-background-color: #f9fbfd;
            }
            QHeaderView::section {
                background: #eef1f5;
                border: 0;
                padding: 6px;
                font-weight: 600;
            }
            """
        )

    def _on_view_changed(self) -> None:
        self.selector_stack.setCurrentIndex(self.view_combo.currentIndex())
        self._clear_selected_title(clear_tree=True)
        self.refresh()

    def _on_week_year_changed(self, year: int) -> None:
        max_week = iso_weeks_in_year(year)
        self.week_spin.setMaximum(max_week)
        if self.week_spin.value() > max_week:
            self.week_spin.setValue(max_week)
        self.refresh()

    def current_view(self) -> str:
        return self.view_combo.currentData()

    def current_selection(self) -> dict[str, object]:
        view = self.current_view()
        if view == VIEW_DAY:
            return {"date": qdate_to_date(self.day_date_edit.date())}
        if view == VIEW_WEEK:
            return {"year": self.week_year_spin.value(), "week": self.week_spin.value()}
        if view == VIEW_MONTH:
            return {"year": self.month_year_spin.value(), "month": self.month_combo.currentData()}
        if view == VIEW_QUARTER:
            return {"year": self.quarter_year_spin.value(), "quarter": self.quarter_combo.currentData()}
        return {"year": self.year_spin.value()}

    def refresh(self) -> None:
        if self.data_manager.ensure_days_until(self.data_manager.today):
            self.data_manager.save()

        view = self.current_view()
        selection = self.current_selection()
        summary = self.data_manager.get_summary(view, selection, include_unallocated=True)
        self.current_summary = summary
        self._update_range_label(summary)
        self._populate_table(summary)

        if self.selected_title not in summary.description_totals or self.selected_title == UNALLOCATED_LABEL:
            self.selected_title = None

        self.chart.set_summary(summary)
        self.chart.set_display_unit(self.display_unit)
        if self.selected_title:
            self.chart.set_selected_title(self.selected_title)
        else:
            self.chart.clear_selected_title()

        day_mode = view == VIEW_DAY
        self.add_button.setEnabled(day_mode)
        self.edit_button.setEnabled(day_mode)
        self.delete_button.setEnabled(day_mode)
        self._update_unit_buttons()
        self._update_backup_status()

    def _update_range_label(self, summary) -> None:
        if summary.start is None or summary.end is None:
            self.range_label.setText(tr("This period is outside the tracking range."))
            return
        self.range_label.setText(
            tr("{start} to {end}\n{days} days, {capacity} available",
               start=summary.start, end=summary.end, days=summary.day_count,
               capacity=format_minutes(summary.capacity_minutes, self.display_unit))
        )

    def _populate_table(self, summary) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        if self.current_view() == VIEW_DAY:
            self._populate_day_table(summary)
        else:
            self._populate_summary_table(summary)
        self.tree.expandAll()
        self.tree.blockSignals(False)

    def _populate_day_table(self, summary) -> None:
        selected_day = self.current_selection()["date"]
        entries = self.data_manager.get_entries(selected_day)
        groups: dict[str, list[tuple[int, object]]] = defaultdict(list)
        title_totals: dict[str, int] = defaultdict(int)
        for index, entry in enumerate(entries):
            groups[entry.title].append((index, entry))
            title_totals[entry.title] += entry.minutes

        for title, total in sorted(title_totals.items(), key=lambda item: item[1], reverse=True):
            top = self._make_item(title, total, summary.capacity_minutes, {"type": "title", "title": title})
            self.tree.addTopLevelItem(top)
            for index, entry in groups[title]:
                child = self._make_item(
                    entry.description,
                    entry.minutes,
                    total,
                    {"type": "entry", "date": selected_day, "index": index, "title": title},
                )
                top.addChild(child)

        unallocated = self.data_manager.get_unallocated_minutes(selected_day)
        label = "timeleak" if selected_day < self.data_manager.today else tr("Unallocated")
        self._add_unallocated_item(label, unallocated, summary.capacity_minutes)

    def _populate_summary_table(self, summary) -> None:
        for title, total in summary.title_totals.items():
            if title == UNALLOCATED_LABEL:
                self._add_unallocated_item(tr("Unallocated / timeleak"), total, summary.capacity_minutes)
                continue
            top = self._make_item(title, total, summary.capacity_minutes, {"type": "title", "title": title})
            self.tree.addTopLevelItem(top)
            for description, minutes in summary.description_totals.get(title, {}).items():
                child = self._make_item(description, minutes, total, {"type": "summary_detail", "title": title})
                top.addChild(child)

    def _add_unallocated_item(self, label: str, minutes: int, denominator: int) -> None:
        item = self._make_item(label, minutes, denominator, {"type": "unallocated", "title": UNALLOCATED_LABEL})
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.tree.addTopLevelItem(item)

    def _make_item(self, label: str, minutes: int, denominator: int, payload: dict[str, object]) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label, format_minutes(minutes, self.display_unit), self._percent_text(minutes, denominator)])
        item.setData(0, Qt.ItemDataRole.UserRole, payload)
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _percent_text(self, minutes: int, denominator: int) -> str:
        if denominator <= 0:
            return "0%"
        return f"{minutes / denominator * 100:.1f}%"

    def _on_tree_selection_changed(self) -> None:
        if self._syncing_selection:
            return
        item = self.tree.currentItem()
        if item is None:
            self._clear_selected_title(clear_tree=False)
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole) or {}
        title = payload.get("title")
        if title and title != UNALLOCATED_LABEL:
            self._apply_selected_title(str(title), select_tree=False)
        else:
            self._clear_selected_title(clear_tree=False)

    def _select_title_from_chart(self, title: str) -> None:
        self._apply_selected_title(title, select_tree=True)

    def _apply_selected_title(self, title: str, *, select_tree: bool) -> None:
        if self.current_summary and title not in self.current_summary.description_totals:
            return
        self.selected_title = title
        if select_tree:
            self._syncing_selection = True
            self._select_tree_title(title)
            self._syncing_selection = False
        self.chart.set_selected_title(title)

    def _select_tree_title(self, title: str) -> None:
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            payload = item.data(0, Qt.ItemDataRole.UserRole) or {}
            if payload.get("title") == title:
                self.tree.setCurrentItem(item)
                return

    def _clear_selected_title(self, *, clear_tree: bool) -> None:
        self.selected_title = None
        if clear_tree:
            self._syncing_selection = True
            self.tree.clearSelection()
            self.tree.setCurrentItem(None)
            self._syncing_selection = False
        self.chart.clear_selected_title()

    def _selected_entry_payload(self) -> dict[str, object] | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        payload = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if payload.get("type") == "entry":
            return payload
        return None

    def _add_record(self) -> None:
        if self.current_view() != VIEW_DAY:
            QMessageBox.information(
                self,
                tr("Add entry"),
                tr("Add entries in the day view, or use Backfill for other dates."),
            )
            return
        selected_day = self.current_selection()["date"]
        dialog = RecordDialog(self, title=tr("Add entry: {date}", date=selected_day))
        if dialog.exec() != RecordDialog.DialogCode.Accepted:
            return
        title, description, minutes = dialog.values()
        self._run_mutation(lambda: self.data_manager.add_entry(selected_day, title, description, minutes))

    def _edit_record(self) -> None:
        payload = self._selected_entry_payload()
        if payload is None:
            QMessageBox.information(self, tr("Edit entry"), tr("Select an individual entry in the day view first."))
            return
        selected_day = payload["date"]
        index = int(payload["index"])
        entry = self.data_manager.get_entries(selected_day)[index]
        dialog = RecordDialog(self, title=tr("Edit entry"), entry=entry)
        if dialog.exec() != RecordDialog.DialogCode.Accepted:
            return
        title, description, minutes = dialog.values()
        self._run_mutation(lambda: self.data_manager.update_entry(selected_day, index, title, description, minutes))

    def _delete_record(self) -> None:
        payload = self._selected_entry_payload()
        if payload is None:
            QMessageBox.information(self, tr("Delete entry"), tr("Select an individual entry in the day view first."))
            return
        reply = QMessageBox.question(
            self,
            tr("Delete entry"),
            tr("Delete the selected entry?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        selected_day = payload["date"]
        index = int(payload["index"])
        self._run_mutation(lambda: self.data_manager.delete_entry(selected_day, index))

    def _backfill_record(self) -> None:
        selected_date = self.current_selection().get("date")
        if not isinstance(selected_date, date):
            selected_date = self.data_manager.today
        dialog = RecordDialog(
            self,
            title=tr("Backfill an entry"),
            show_date=True,
            selected_date=selected_date,
            min_date=self.data_manager.start_date,
            max_date=self.data_manager.today,
        )
        if dialog.exec() != RecordDialog.DialogCode.Accepted:
            return
        target_date = dialog.selected_date()
        if target_date is None:
            return
        title, description, minutes = dialog.values()
        self._run_mutation(lambda: self.data_manager.add_entry(target_date, title, description, minutes))

    def _run_mutation(self, action) -> None:
        try:
            action()
        except ValidationError as exc:
            QMessageBox.warning(self, tr("Could not save"), str(exc))
            return
        self.refresh()

    def _toggle_display_unit(self) -> None:
        self.display_unit = UNIT_HOURS if self.display_unit == UNIT_MINUTES else UNIT_MINUTES
        self.refresh()

    def _update_unit_buttons(self) -> None:
        if self.display_unit == UNIT_HOURS:
            self.global_unit_button.setText(tr("Unit: hours"))
            self.table_unit_button.setText(tr("Table: hours"))
        else:
            self.global_unit_button.setText(tr("Unit: min"))
            self.table_unit_button.setText(tr("Table: min"))

    def _update_backup_status(self) -> None:
        result = self.data_manager.last_backup_result
        self.backup_status_label.setText(tr("Backup: {status}", status=result.message))

    def _show_sync_placeholder(self) -> None:
        QMessageBox.information(self, tr("Sync"), self.sync_manager.sync())

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings_manager, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self._set_ai_status(tr("Settings saved"))

    def _set_ai_status(self, message: str) -> None:
        self.ai_status_label.setText(message)

    def _change_interface_language(self) -> None:
        self.settings_manager.update_section("ui", {"language": self.interface_language_combo.currentData()})
        self.language_changed.emit()

    def _save_speech_language(self) -> None:
        self.settings_manager.update_section("local_stt", {"language": self.speech_language_combo.currentData()})

    def _download_speech_model(self) -> None:
        if self._transcriber.model_cached() or self._active_task is not None:
            return
        self._downloading_model = True
        self._set_ai_status(tr("Downloading model..."))
        self._run_background(self._transcriber.download_model, self._on_speech_model_downloaded)

    def _on_speech_model_downloaded(self, _result: object) -> None:
        self._set_ai_status(tr("Model ready"))

    def _update_ai_controls(self) -> None:
        recording = self._recording_started is not None
        busy = self._active_task is not None or self._realtime_task is not None
        ready = self._transcriber.model_cached()
        self.record_button.setEnabled(not busy and (ready or recording))
        self.speech_language_combo.setEnabled(not busy and not recording)
        self.interface_language_combo.setEnabled(not busy and not recording)
        self.model_progress.setVisible(self._downloading_model)
        self.download_model_button.setVisible(not ready and not self._downloading_model)
        self.download_model_button.setEnabled(not busy and not recording)
        self.model_status_label.setText(tr(
            "Downloading model..." if self._downloading_model else
            "Model ready" if ready else "Model not installed (~148 MB)"
        ))
        self.record_button.setText(tr("Stop and transcribe") if recording else tr("Record locally"))
        self.record_button.setProperty("recording", recording)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.recording_time.setVisible(recording)
        self.cancel_record_button.setVisible(recording)
        self.retry_record_button.setVisible(not recording and not busy and self._pending_audio is not None)
        self.choose_audio_button.setEnabled(not recording and not busy)
        self.extract_button.setEnabled(not recording and not busy)
        self.realtime_button.setEnabled(not recording and self._active_task is None)

    def _toggle_recording(self) -> None:
        if self._recording_started is not None:
            self._stop_recording()
            return
        if not self._transcriber.model_cached():
            self._set_ai_status(tr("Download the speech model to enable local recording."))
            return
        try:
            self._recorder.start()
        except RuntimeError as exc:
            self._set_ai_status(str(exc))
            return
        self._pending_audio = None
        self._recording_started = monotonic()
        self.recording_time.setText("00:00")
        self._update_ai_controls()
        self._recording_timer.start()
        self._set_ai_status(tr("Recording"))

    def _update_recording(self) -> None:
        if self._recording_started is None:
            return
        seconds = int(monotonic() - self._recording_started)
        self.recording_time.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")
        if not self._recorder.active:
            self._cancel_recording()
            self._set_ai_status(tr("Microphone disconnected. Check the input device and try again."))
        elif seconds >= MAX_RECORDING_SECONDS:
            self._stop_recording()

    def _reset_recording_controls(self) -> None:
        self._recording_timer.stop()
        self._recording_started = None
        self._update_ai_controls()

    def _cancel_recording(self) -> None:
        self._recorder.cancel()
        self._reset_recording_controls()
        self._set_ai_status(tr("Recording canceled"))

    def _stop_recording(self) -> None:
        self._reset_recording_controls()
        try:
            self._pending_audio = self._recorder.stop()
        except RuntimeError as exc:
            self._set_ai_status(str(exc))
            return
        self._transcribe_recording()

    def _transcribe_recording(self) -> None:
        audio = self._pending_audio
        if audio is None:
            return
        self._set_ai_status(tr("Transcribing locally..."))
        language = self.speech_language_combo.currentData()

        def transcribe():
            try:
                return self._transcriber.transcribe(audio, language=language)
            except NoSpeechError:
                return ""

        self._run_background(transcribe, self._on_local_transcription_ready)

    def _on_local_transcription_ready(self, text: str) -> None:
        self._pending_audio = None
        if not text:
            self._set_ai_status(tr("No speech detected. Try recording again."))
            return
        self._on_transcription_ready(text)
        self._set_ai_status(tr("Transcription complete. Nothing was uploaded."))

    def _run_background(self, action, on_success) -> None:
        if self._active_task is not None:
            return
        self._active_task = BackgroundTask(action, self)
        self._active_task.succeeded.connect(on_success)
        self._active_task.failed.connect(self._on_background_failure)
        self._active_task.finished.connect(self._finish_background_task)
        self._update_ai_controls()
        self._active_task.start()

    def _on_background_failure(self, message: str) -> None:
        self._set_ai_status(tr("Failed: {error}", error=message))

    def _finish_background_task(self) -> None:
        task, self._active_task = self._active_task, None
        task.deleteLater()
        self._downloading_model = False
        self._update_ai_controls()

    def _transcribe_audio_file(self) -> None:
        file_name, _selected_filter = QFileDialog.getOpenFileName(
            self,
            tr("Choose an audio file"),
            "",
            "Audio (*.wav *.mp3 *.m4a *.flac *.ogg *.webm);;All Files (*)",
        )
        if not file_name:
            return
        self._set_ai_status(tr("Transcribing audio file..."))
        settings = self.settings_manager.get("stt")
        api_key = self.settings_manager.resolved_api_key("stt")
        client = STTClient(settings, api_key)
        self._run_background(lambda: client.transcribe_file(Path(file_name)), self._on_transcription_ready)

    def _on_transcription_ready(self, text: object) -> None:
        current = self.ai_text.toPlainText().strip()
        incoming = str(text).strip()
        if current and incoming:
            self.ai_text.setPlainText(current + "\n" + incoming)
        else:
            self.ai_text.setPlainText(current or incoming)
        self._set_ai_status(tr("Transcript ready"))

    def _toggle_realtime_stt(self) -> None:
        if self._realtime_task is not None:
            self._realtime_task.stop()
            self.realtime_button.setEnabled(False)
            self._set_ai_status(tr("Disconnecting external STT..."))
            return
        settings = self.settings_manager.get("stt")
        api_key = self.settings_manager.resolved_api_key("stt")
        client = RealtimeSTTClient(settings, api_key)
        self._realtime_task = RealtimeTask(client, self)
        self._realtime_task.text_received.connect(self._append_realtime_text)
        self._realtime_task.finished.connect(self._on_realtime_stopped)
        self._realtime_task.start()
        self.realtime_button.setText(tr("Stop external STT"))
        self._update_ai_controls()
        self._set_ai_status(tr("Waiting for an external transcript..."))

    def _append_realtime_text(self, text: str) -> None:
        current = self.ai_text.toPlainText()
        separator = "" if not current or current.endswith(("\n", " ")) else " "
        self.ai_text.setPlainText(current + separator + text)

    def _on_realtime_stopped(self) -> None:
        task, self._realtime_task = self._realtime_task, None
        self.realtime_button.setText(tr("External STT"))
        if task.error and not task.stop_event.is_set():
            self._set_ai_status(tr("External STT failed: {error}", error=task.error))
        else:
            self._set_ai_status(tr("External STT disconnected"))
        task.deleteLater()
        self._update_ai_controls()

    def closeEvent(self, event) -> None:
        if self._active_task is not None or self._realtime_task is not None:
            if self._realtime_task is not None:
                self._realtime_task.stop()
                self.realtime_button.setEnabled(False)
            self._set_ai_status(tr("Wait for the current task to finish before closing."))
            event.ignore()
            return
        if self._recording_started is not None:
            self._cancel_recording()
        self._pending_audio = None
        super().closeEvent(event)

    def _extract_ai_entries(self) -> None:
        text = self.ai_text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "AI", tr("Enter or transcribe a note first."))
            return
        self._set_ai_status(tr("Extracting activities..."))
        settings = self.settings_manager.get("llm")
        api_key = self.settings_manager.resolved_api_key("llm")
        parser = LLMTimeParser(settings, api_key)
        default_date = qdate_to_date(self.ai_date_edit.date())
        self._run_background(
            lambda: parser.extract(
                text,
                default_date=default_date,
                start_date=self.data_manager.start_date,
                today=self.data_manager.today,
            ),
            self._on_ai_entries_extracted,
        )

    def _on_ai_entries_extracted(self, result: object) -> None:
        extraction = result
        self.ai_drafts = list(extraction.entries)
        self._populate_ai_preview()
        warning_text = ""
        if extraction.warnings:
            warning_text = "; " + "; ".join(extraction.warnings[:3])
        self._set_ai_status(tr("Extracted {count} entries{warnings}", count=len(self.ai_drafts), warnings=warning_text))
        if self.settings_manager.get("ai").get("auto_apply_after_extract"):
            self._apply_ai_entries()

    def _populate_ai_preview(self) -> None:
        self.ai_preview.clear()
        for entry in self.ai_drafts:
            item = QTreeWidgetItem(
                [
                    entry.date.isoformat(),
                    entry.title,
                    entry.description,
                    format_minutes(entry.minutes, self.display_unit),
                ]
            )
            self.ai_preview.addTopLevelItem(item)

    def _apply_ai_entries(self) -> None:
        if not self.ai_drafts:
            QMessageBox.information(self, "AI", tr("There are no entries to save."))
            return
        failures: list[str] = []
        applied = 0
        for entry in self.ai_drafts:
            try:
                self.data_manager.add_entry(entry.date, entry.title, entry.description, entry.minutes)
                applied += 1
            except ValidationError as exc:
                failures.append(f"{entry.date.isoformat()} {entry.title}: {exc}")
        self.refresh()
        if failures:
            QMessageBox.warning(
                self,
                "AI",
                tr("Saved {saved}; failed to save {failed}:\n{details}", saved=applied,
                   failed=len(failures), details="\n".join(failures[:5])),
            )
        else:
            self.ai_drafts.clear()
            self.ai_preview.clear()
            self._set_ai_status(tr("Saved {count} AI entries", count=applied))
