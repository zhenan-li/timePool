from __future__ import annotations

from datetime import date

QT_API = ""

try:
    from PySide6.QtCore import QDate, QLocale, QThread, QTimer, Qt, Signal
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDateEdit,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSizePolicy,
        QSpinBox,
        QSplitter,
        QStackedWidget,
        QTabWidget,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "PySide6"
except Exception as pyside_error:
    try:
        from PyQt6.QtCore import QDate, QLocale, QThread, QTimer, Qt, pyqtSignal as Signal
        from PyQt6.QtWidgets import (
            QApplication,
            QAbstractItemView,
            QButtonGroup,
            QCheckBox,
            QComboBox,
            QDateEdit,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QSizePolicy,
            QSpinBox,
            QSplitter,
            QStackedWidget,
            QTabWidget,
            QTreeWidget,
            QTreeWidgetItem,
            QVBoxLayout,
            QWidget,
        )

        QT_API = "PyQt6"
    except Exception as pyqt_error:
        raise ImportError(
            "No working PySide6 or PyQt6 installation. Run: python -m pip install -r requirements.txt\n"
            f"PySide6: {pyside_error}\n"
            f"PyQt6: {pyqt_error}"
        ) from pyqt_error


def qdate_to_date(value: QDate) -> date:
    if hasattr(value, "toPyDate"):
        return value.toPyDate()
    if hasattr(value, "toPython"):
        converted = value.toPython()
        if isinstance(converted, date):
            return converted
    return date(value.year(), value.month(), value.day())


__all__ = [
    "QT_API",
    "QApplication",
    "QAbstractItemView",
    "QButtonGroup",
    "QCheckBox",
    "QComboBox",
    "QDate",
    "QDateEdit",
    "QDialog",
    "QDialogButtonBox",
    "QDoubleSpinBox",
    "QFileDialog",
    "QFormLayout",
    "QFrame",
    "QGridLayout",
    "QGroupBox",
    "QHBoxLayout",
    "QHeaderView",
    "QLabel",
    "QLineEdit",
    "QMainWindow",
    "QMessageBox",
    "QPlainTextEdit",
    "QPushButton",
    "QSizePolicy",
    "QSpinBox",
    "QSplitter",
    "QStackedWidget",
    "QTabWidget",
    "QThread",
    "QTimer",
    "QTreeWidget",
    "QTreeWidgetItem",
    "QVBoxLayout",
    "QWidget",
    "Qt",
    "Signal",
    "qdate_to_date",
]
