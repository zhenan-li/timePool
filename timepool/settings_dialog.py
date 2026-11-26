from __future__ import annotations

from .i18n import tr

from .qt_compat import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from .settings_manager import SettingsManager


class SettingsDialog(QDialog):
    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle(tr("Settings"))
        self.resize(620, 480)

        tabs = QTabWidget()
        tabs.addTab(self._build_llm_tab(), "LLM")
        tabs.addTab(self._build_stt_tab(), "STT")
        tabs.addTab(self._build_ai_tab(), tr("Entry options"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("Save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel"))

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        self._load_values()

    def _build_llm_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox(tr("OpenAI-compatible LLM"))
        form = QFormLayout(group)

        self.llm_base_url = QLineEdit()
        self.llm_model = QLineEdit()
        self.llm_api_key = QLineEdit()
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.llm_api_key_env = QLineEdit()
        self.llm_timeout = QSpinBox()
        self.llm_timeout.setRange(5, 600)
        self.llm_response_format = QCheckBox(tr("Request JSON response format"))

        form.addRow(tr("Base URL"), self.llm_base_url)
        form.addRow(tr("Model"), self.llm_model)
        form.addRow(tr("API Key"), self.llm_api_key)
        form.addRow(tr("API Key Env"), self.llm_api_key_env)
        form.addRow(tr("Timeout (s)"), self.llm_timeout)
        form.addRow("", self.llm_response_format)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_stt_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox(tr("STT API"))
        form = QFormLayout(group)

        self.stt_mode = QComboBox()
        self.stt_mode.addItem(tr("External audio file"), "non_realtime")
        self.stt_mode.addItem(tr("External WebSocket transcript"), "realtime")
        self.stt_base_url = QLineEdit()
        self.stt_model = QLineEdit()
        self.stt_language = QLineEdit()
        self.stt_api_key = QLineEdit()
        self.stt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.stt_api_key_env = QLineEdit()
        self.stt_timeout = QSpinBox()
        self.stt_timeout.setRange(5, 1200)
        self.stt_realtime_url = QLineEdit()

        form.addRow(tr("Mode"), self.stt_mode)
        form.addRow(tr("Base URL"), self.stt_base_url)
        form.addRow(tr("Model"), self.stt_model)
        form.addRow(tr("Language"), self.stt_language)
        form.addRow(tr("API Key"), self.stt_api_key)
        form.addRow(tr("API Key Env"), self.stt_api_key_env)
        form.addRow(tr("Timeout (s)"), self.stt_timeout)
        form.addRow(tr("Realtime URL"), self.stt_realtime_url)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_ai_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox(tr("Smart entry"))
        form = QFormLayout(group)

        self.default_target = QComboBox()
        self.default_target.addItem(tr("Use the selected date"), "selected_date")
        self.default_target.addItem(tr("Let the LLM infer the date"), "llm_only")
        self.auto_apply = QCheckBox(tr("Save automatically after extraction"))

        form.addRow(tr("Default date"), self.default_target)
        form.addRow("", self.auto_apply)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _load_values(self) -> None:
        llm = self.settings_manager.get("llm")
        self.llm_base_url.setText(str(llm.get("base_url", "")))
        self.llm_model.setText(str(llm.get("model", "")))
        self.llm_api_key.setText(str(llm.get("api_key", "")))
        self.llm_api_key_env.setText(str(llm.get("api_key_env", "")))
        self.llm_timeout.setValue(int(llm.get("timeout_seconds", 60)))
        self.llm_response_format.setChecked(bool(llm.get("use_response_format", True)))

        stt = self.settings_manager.get("stt")
        self._set_combo_value(self.stt_mode, str(stt.get("mode", "non_realtime")))
        self.stt_base_url.setText(str(stt.get("base_url", "")))
        self.stt_model.setText(str(stt.get("model", "")))
        self.stt_language.setText(str(stt.get("language", "")))
        self.stt_api_key.setText(str(stt.get("api_key", "")))
        self.stt_api_key_env.setText(str(stt.get("api_key_env", "")))
        self.stt_timeout.setValue(int(stt.get("timeout_seconds", 120)))
        self.stt_realtime_url.setText(str(stt.get("realtime_url", "")))

        ai = self.settings_manager.get("ai")
        self._set_combo_value(self.default_target, str(ai.get("default_target", "selected_date")))
        self.auto_apply.setChecked(bool(ai.get("auto_apply_after_extract", False)))

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def accept(self) -> None:
        self.settings_manager.update_section(
            "llm",
            {
                "provider": "openai_compatible",
                "base_url": self.llm_base_url.text().strip(),
                "model": self.llm_model.text().strip(),
                "api_key": self.llm_api_key.text().strip(),
                "api_key_env": self.llm_api_key_env.text().strip(),
                "timeout_seconds": self.llm_timeout.value(),
                "use_response_format": self.llm_response_format.isChecked(),
            },
        )
        self.settings_manager.update_section(
            "stt",
            {
                "provider": "openai_compatible",
                "mode": self.stt_mode.currentData(),
                "base_url": self.stt_base_url.text().strip(),
                "model": self.stt_model.text().strip(),
                "language": self.stt_language.text().strip(),
                "api_key": self.stt_api_key.text().strip(),
                "api_key_env": self.stt_api_key_env.text().strip(),
                "timeout_seconds": self.stt_timeout.value(),
                "realtime_url": self.stt_realtime_url.text().strip(),
            },
        )
        self.settings_manager.update_section(
            "ai",
            {
                "default_target": self.default_target.currentData(),
                "auto_apply_after_extract": self.auto_apply.isChecked(),
            },
        )
        super().accept()
