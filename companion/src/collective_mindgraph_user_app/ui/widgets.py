"""Reusable widgets for the companion app."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import AppSummary
from ..services import DEFAULT_TEMPLATE, TEMPLATE_OPTIONS


MOOD_OPTIONS = ["Focused", "Calm", "Curious", "Reflective", "Busy", "Optimistic"]


class CardWidget(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)

        self.body_layout = QVBoxLayout()
        self.body_layout.setSpacing(10)
        layout.addLayout(self.body_layout)


class MetricPill(QFrame):
    def __init__(self, label_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricPill")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        caption = QLabel(label_text)
        caption.setStyleSheet("color: #60717f;")
        self.value_label = QLabel("0")
        self.value_label.setObjectName("MetricValue")

        layout.addWidget(caption)
        layout.addWidget(self.value_label)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class SummaryBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SummaryBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        self._metrics = {
            "sessions": MetricPill("Sessions"),
            "main_categories": MetricPill("Main Branches"),
            "sub_categories": MetricPill("Sub Branches"),
            "notes": MetricPill("Captured Notes"),
            "nodes": MetricPill("Graph Nodes"),
        }
        for widget in self._metrics.values():
            layout.addWidget(widget)

    def set_summary(self, summary: AppSummary) -> None:
        self._metrics["sessions"].set_value(summary.total_sessions)
        self._metrics["main_categories"].set_value(summary.total_main_categories)
        self._metrics["sub_categories"].set_value(summary.total_sub_categories)
        self._metrics["notes"].set_value(summary.total_notes)
        self._metrics["nodes"].set_value(summary.total_map_nodes)


class EmptyStateWidget(QWidget):
    def __init__(self, title: str, message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("color: #66788a;")

        layout.addWidget(title_label)
        layout.addWidget(message_label)


class ActionEmptyStateWidget(QWidget):
    def __init__(
        self,
        title: str,
        message: str,
        primary_label: str,
        secondary_label: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("color: #66788a;")
        message_label.setMaximumWidth(460)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.primary_button = QPushButton(primary_label)
        button_row.addWidget(self.primary_button)

        self.secondary_button: QPushButton | None = None
        if secondary_label:
            self.secondary_button = QPushButton(secondary_label)
            self.secondary_button.setProperty("secondary", True)
            button_row.addWidget(self.secondary_button)

        layout.addWidget(title_label)
        layout.addWidget(message_label)
        layout.addLayout(button_row)


class NotesTextEdit(QTextEdit):
    focus_lost = Signal()

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        self.focus_lost.emit()
        super().focusOutEvent(event)


class SessionDialog(QDialog):
    def __init__(
        self,
        dialog_title: str,
        category_options: dict[str, list[str]],
        title: str = "",
        main_category: str = "",
        sub_category: str = "",
        template_name: str = DEFAULT_TEMPLATE,
        mood: str = "Focused",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._category_options = category_options
        self.setWindowTitle(dialog_title)
        self.resize(440, 260)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("Give this session a clear title")

        self.main_category_combo = QComboBox()
        self.main_category_combo.setEditable(True)
        self.main_category_combo.addItems(sorted(category_options))
        self.main_category_combo.setCurrentText(main_category)
        self.main_category_combo.currentTextChanged.connect(self._refresh_sub_categories)

        self.sub_category_combo = QComboBox()
        self.sub_category_combo.setEditable(True)

        self.template_combo = QComboBox()
        self.template_combo.setEditable(True)
        self.template_combo.addItems(TEMPLATE_OPTIONS)
        self.template_combo.setCurrentText(template_name or DEFAULT_TEMPLATE)

        self.mood_combo = QComboBox()
        self.mood_combo.setEditable(True)
        self.mood_combo.addItems(MOOD_OPTIONS)
        self.mood_combo.setCurrentText(mood or "Focused")

        form_layout.addRow("Title", self.title_edit)
        form_layout.addRow("Main Category", self.main_category_combo)
        form_layout.addRow("Sub Category", self.sub_category_combo)
        form_layout.addRow("Template", self.template_combo)
        form_layout.addRow("Mood", self.mood_combo)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setProperty("secondary", True)
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._refresh_sub_categories(self.main_category_combo.currentText(), sub_category)

    def values(self) -> tuple[str, str, str, str, str]:
        return (
            self.title_edit.text().strip(),
            self.main_category_combo.currentText().strip(),
            self.sub_category_combo.currentText().strip(),
            self.template_combo.currentText().strip(),
            self.mood_combo.currentText().strip(),
        )

    def _validate_and_accept(self) -> None:
        title, main_category, _sub_category, _template_name, _mood = self.values()
        if not title:
            self.title_edit.setFocus()
            return
        if not main_category:
            self.main_category_combo.setFocus()
            return
        self.accept()

    def _refresh_sub_categories(self, main_category_name: str, selected_sub_category: str | None = None) -> None:
        selected_value = selected_sub_category
        if selected_value is None:
            selected_value = self.sub_category_combo.currentText()

        values = self._category_options.get(main_category_name.strip(), [])
        self.sub_category_combo.blockSignals(True)
        self.sub_category_combo.clear()
        self.sub_category_combo.addItem("")
        self.sub_category_combo.addItems(values)
        self.sub_category_combo.setCurrentText(selected_value or "")
        self.sub_category_combo.blockSignals(False)


class CategoryDialog(QDialog):
    def __init__(
        self,
        dialog_title: str,
        field_label: str,
        value: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(dialog_title)
        self.resize(360, 140)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)

        self.name_edit = QLineEdit(value)
        self.name_edit.setPlaceholderText("Name")
        form_layout.addRow(field_label, self.name_edit)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setProperty("secondary", True)
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def value(self) -> str:
        return self.name_edit.text().strip()

    def _validate_and_accept(self) -> None:
        if not self.value():
            self.name_edit.setFocus()
            return
        self.accept()
