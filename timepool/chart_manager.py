from __future__ import annotations

from .i18n import tr

import matplotlib
from matplotlib import font_manager
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .models import SummaryResult, UNIT_HOURS, UNALLOCATED_LABEL
from .qt_compat import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Signal,
)
from .utils import format_minutes


def configure_chinese_font() -> None:
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
        "WenQuanYi Micro Hei",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in candidates:
        if candidate in available:
            matplotlib.rcParams["font.sans-serif"] = [candidate, "DejaVu Sans"]
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


class ChartManager(QWidget):
    title_selected = Signal(str)
    blank_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        configure_chinese_font()

        self.summary = SummaryResult(None, None)
        self.display_unit = "minutes"
        self.selected_title: str | None = None
        self.detail_mode = False
        self.artist_labels: dict[object, str] = {}

        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItem(tr("Bar chart"), "bar")
        self.chart_type_combo.addItem(tr("Pie chart"), "pie")

        self.include_unallocated_checkbox = QCheckBox(tr("Include unallocated"))
        self.include_unallocated_checkbox.setChecked(True)

        self.drill_controls = QWidget()
        self.macro_button = QPushButton(tr("Categories"))
        self.detail_button = QPushButton(tr("Subcategories"))
        self.macro_button.setCheckable(True)
        self.detail_button.setCheckable(True)
        self.detail_button.setChecked(True)
        self.drill_group = QButtonGroup(self)
        self.drill_group.addButton(self.macro_button)
        self.drill_group.addButton(self.detail_button)
        self.drill_group.setExclusive(True)

        drill_layout = QHBoxLayout(self.drill_controls)
        drill_layout.setContentsMargins(0, 0, 0, 0)
        drill_layout.addWidget(self.macro_button)
        drill_layout.addWidget(self.detail_button)
        self.drill_controls.hide()

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.chart_type_combo)
        top_layout.addWidget(self.include_unallocated_checkbox)
        top_layout.addStretch(1)
        top_layout.addWidget(self.drill_controls)

        self.figure = Figure(figsize=(6, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ax = self.figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addWidget(self.canvas)

        self.chart_type_combo.currentIndexChanged.connect(self.render)
        self.include_unallocated_checkbox.stateChanged.connect(self.render)
        self.macro_button.clicked.connect(self._show_macro_for_selected)
        self.detail_button.clicked.connect(self._show_detail_for_selected)
        self.canvas.mpl_connect("pick_event", self._on_pick)
        self.canvas.mpl_connect("button_press_event", self._on_button_press)

    def set_summary(self, summary: SummaryResult) -> None:
        self.summary = summary
        self.render()

    def set_display_unit(self, unit: str) -> None:
        self.display_unit = unit
        self.render()

    def set_selected_title(self, title: str) -> None:
        self.selected_title = title
        self.detail_mode = True
        self.detail_button.setChecked(True)
        self.drill_controls.show()
        self.render()

    def clear_selected_title(self) -> None:
        self.selected_title = None
        self.detail_mode = False
        self.drill_controls.hide()
        self.render()

    def _show_macro_for_selected(self) -> None:
        self.detail_mode = False
        self.render()

    def _show_detail_for_selected(self) -> None:
        self.detail_mode = True
        self.render()

    def _filtered_title_totals(self) -> dict[str, int]:
        data = dict(self.summary.title_totals)
        if not self.include_unallocated_checkbox.isChecked():
            data.pop(UNALLOCATED_LABEL, None)
        return data

    def _current_chart_data(self) -> tuple[str, dict[str, int]]:
        if self.selected_title and self.detail_mode:
            details = self.summary.description_totals.get(self.selected_title, {})
            return tr("{title}: subcategory breakdown", title=self.selected_title), dict(details)
        return tr("Time by category"), self._filtered_title_totals()

    def _to_display_value(self, minutes: int) -> float:
        if self.display_unit == UNIT_HOURS:
            return round(minutes / 60, 2)
        return float(minutes)

    def _axis_unit_label(self) -> str:
        return tr("Hours") if self.display_unit == UNIT_HOURS else tr("Minutes")

    def render(self) -> None:
        self.ax.clear()
        self.artist_labels.clear()
        title, raw_data = self._current_chart_data()
        raw_data = {key: value for key, value in raw_data.items() if value > 0}

        if not raw_data:
            self.ax.text(0.5, 0.5, tr("No data"), ha="center", va="center", transform=self.ax.transAxes)
            self.ax.set_axis_off()
            self.canvas.draw_idle()
            return

        labels = list(raw_data.keys())
        minutes_values = list(raw_data.values())
        display_values = [self._to_display_value(value) for value in minutes_values]
        chart_type = self.chart_type_combo.currentData()

        if chart_type == "pie":
            self._render_pie(title, labels, minutes_values)
        else:
            self._render_bar(title, labels, minutes_values, display_values)

        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _render_bar(
        self,
        title: str,
        labels: list[str],
        minutes_values: list[int],
        display_values: list[float],
    ) -> None:
        positions = range(len(labels))
        bars = self.ax.bar(positions, display_values, color="#4b8bbe", picker=True)
        self.ax.set_xticks(positions, labels=[tr("Unallocated") if label == UNALLOCATED_LABEL else label for label in labels])
        for bar, label, minutes in zip(bars, labels, minutes_values):
            self.artist_labels[bar] = label
            height = bar.get_height()
            self.ax.annotate(
                format_minutes(minutes, self.display_unit),
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
            )
        self.ax.set_title(title)
        self.ax.set_ylabel(self._axis_unit_label())
        self.ax.tick_params(axis="x", labelrotation=25)
        self.ax.grid(axis="y", alpha=0.25)

    def _render_pie(self, title: str, labels: list[str], minutes_values: list[int]) -> None:
        total = sum(minutes_values)

        def autopct(percent: float) -> str:
            minutes = int(round(total * percent / 100))
            return f"{percent:.1f}%\n{format_minutes(minutes, self.display_unit)}"

        wedges, _texts, _autotexts = self.ax.pie(
            minutes_values,
            labels=[tr("Unallocated") if label == UNALLOCATED_LABEL else label for label in labels],
            autopct=autopct,
            startangle=90,
            counterclock=False,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        for wedge, label in zip(wedges, labels):
            wedge.set_picker(True)
            self.artist_labels[wedge] = label
        self.ax.set_title(title)
        self.ax.axis("equal")

    def _on_pick(self, event) -> None:
        label = self.artist_labels.get(event.artist)
        if not label or label == UNALLOCATED_LABEL:
            return
        if not self.detail_mode:
            self.title_selected.emit(label)

    def _on_button_press(self, event) -> None:
        if event.button != 1:
            return
        if event.inaxes != self.ax:
            self.blank_clicked.emit()
            return
        for artist in self.artist_labels:
            contains, _details = artist.contains(event)
            if contains:
                return
        self.blank_clicked.emit()
