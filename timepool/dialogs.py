from __future__ import annotations

from .i18n import tr

from datetime import date

from .models import Entry, UNIT_HOURS, UNIT_MINUTES
from .qt_compat import (
    QComboBox,
    QDate,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    qdate_to_date,
)
from .utils import convert_to_minutes


def to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


class RecordDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        title: str | None = None,
        entry: Entry | None = None,
        show_date: bool = False,
        selected_date: date | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title if title is not None else tr("Add an entry"))
        self._last_unit = UNIT_MINUTES
        self._syncing_unit = False
        self._date_visible = show_date

        self.title_edit = QLineEdit()
        self.description_edit = QLineEdit()
        self.amount_spin = QDoubleSpinBox()
        self.unit_combo = QComboBox()
        self.date_edit: QDateEdit | None = None

        self.unit_combo.addItem(tr("Minutes"), UNIT_MINUTES)
        self.unit_combo.addItem(tr("Hours"), UNIT_HOURS)

        form = QFormLayout()
        if show_date:
            self.date_edit = QDateEdit()
            self.date_edit.setCalendarPopup(True)
            if min_date is not None and max_date is not None:
                self.date_edit.setDateRange(to_qdate(min_date), to_qdate(max_date))
            self.date_edit.setDate(to_qdate(selected_date or max_date or date.today()))
            form.addRow(tr("Date"), self.date_edit)

        form.addRow(tr("Category"), self.title_edit)
        form.addRow(tr("Subcategory"), self.description_edit)
        form.addRow(tr("Duration"), self.amount_spin)
        form.addRow(tr("Unit"), self.unit_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("OK"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel"))

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._configure_amount_spin(UNIT_MINUTES)
        if entry is not None:
            self.title_edit.setText(entry.title)
            self.description_edit.setText(entry.description)
            self.amount_spin.setValue(entry.minutes)
        else:
            self.amount_spin.setValue(30)

        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)

    def _configure_amount_spin(self, unit: str) -> None:
        if unit == UNIT_HOURS:
            self.amount_spin.setDecimals(2)
            self.amount_spin.setRange(0.01, 24.0)
            self.amount_spin.setSingleStep(0.25)
            self.amount_spin.setSuffix(tr(" hrs"))
        else:
            self.amount_spin.setDecimals(0)
            self.amount_spin.setRange(1, 1440)
            self.amount_spin.setSingleStep(5)
            self.amount_spin.setSuffix(tr(" min"))

    def _on_unit_changed(self) -> None:
        if self._syncing_unit:
            return
        old_unit = self._last_unit
        new_unit = self.unit_combo.currentData()
        old_minutes = convert_to_minutes(self.amount_spin.value(), old_unit)

        self._syncing_unit = True
        self._configure_amount_spin(new_unit)
        if new_unit == UNIT_HOURS:
            self.amount_spin.setValue(round(old_minutes / 60, 2))
        else:
            self.amount_spin.setValue(old_minutes)
        self._last_unit = new_unit
        self._syncing_unit = False

    def selected_date(self) -> date | None:
        if self.date_edit is None:
            return None
        return qdate_to_date(self.date_edit.date())

    def values(self) -> tuple[str, str, int]:
        unit = self.unit_combo.currentData()
        return (
            self.title_edit.text().strip(),
            self.description_edit.text().strip(),
            convert_to_minutes(self.amount_spin.value(), unit),
        )

    def accept(self) -> None:
        title, _description, minutes = self.values()
        if not title:
            QMessageBox.warning(self, tr("Could not save"), tr("A category is required."))
            return
        if minutes <= 0:
            QMessageBox.warning(self, tr("Could not save"), tr("Duration must be greater than zero."))
            return
        super().accept()
