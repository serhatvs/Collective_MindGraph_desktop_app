"""Session detail panel for the companion app."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QTextListFormat
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import (
    MainCategory,
    SessionDetail,
    SessionFlowItem,
    SessionGraphNode,
    SubCategory,
    WorkspaceMapItem,
)
from ..services import CollectiveMindGraphCompanionService, DEFAULT_TEMPLATE, TEMPLATE_OPTIONS
from .widgets import (
    ActionEmptyStateWidget,
    CardWidget,
    CategoryDialog,
    MOOD_OPTIONS,
    NotesTextEdit,
    SessionDialog,
)


class SessionDetailPanel(QWidget):
    new_session_requested = Signal()
    seed_demo_requested = Signal()
    session_structure_changed = Signal(int, str)
    session_selected_from_map = Signal(int)
    status_message = Signal(str)

    def __init__(
        self,
        service: CollectiveMindGraphCompanionService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._current_session_id: int | None = None
        self._loading_detail = False
        self._last_saved_note_html = ""
        self._category_options: dict[str, list[str]] = {}

        self._note_save_timer = QTimer(self)
        self._note_save_timer.setSingleShot(True)
        self._note_save_timer.setInterval(700)
        self._note_save_timer.timeout.connect(self._save_note_if_needed)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.stack_host = QWidget()
        self.stack_layout = QStackedLayout(self.stack_host)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.stack_host)

        self.empty_state = ActionEmptyStateWidget(
            "Start a session branch",
            "Create the first session to build a flow and a mindgraph around it, or load demo data to inspect a ready-made branch.",
            "New Session",
            "Seed Demo Data",
        )
        self.empty_state.primary_button.clicked.connect(self.new_session_requested.emit)
        if self.empty_state.secondary_button is not None:
            self.empty_state.secondary_button.clicked.connect(self.seed_demo_requested.emit)
        self.stack_layout.addWidget(self.empty_state)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.scroll_area.setWidget(self.content_widget)
        self.stack_layout.addWidget(self.scroll_area)

        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self._build_overview_card(content_layout)
        self._build_quick_capture_card(content_layout)
        self._build_flow_card(content_layout)
        self._build_graph_card(content_layout)
        self._build_notes_card(content_layout)
        self._build_workspace_map_card(content_layout)
        content_layout.addStretch(1)

        self.set_session(None)

    def set_session(self, session_id: int | None) -> None:
        self._current_session_id = session_id
        if session_id is None:
            self.stack_layout.setCurrentWidget(self.empty_state)
            self._clear_detail_fields()
            return
        self._reload_current_session()

    def current_session_id(self) -> int | None:
        return self._current_session_id

    def focus_overview_editor(self) -> None:
        if self._current_session_id is not None:
            self.title_edit.setFocus()
            self.title_edit.selectAll()

    def _reload_current_session(self) -> None:
        if self._current_session_id is None:
            self.stack_layout.setCurrentWidget(self.empty_state)
            return
        detail = self._service.get_session_detail(self._current_session_id)
        if detail is None:
            self._current_session_id = None
            self.stack_layout.setCurrentWidget(self.empty_state)
            return
        self._apply_detail(detail)

    def _apply_detail(self, detail: SessionDetail) -> None:
        self._loading_detail = True
        self.stack_layout.setCurrentWidget(self.scroll_area)

        self.title_edit.setText(detail.session.title)
        self.template_combo.setCurrentText(detail.session.template_name or DEFAULT_TEMPLATE)
        self.mood_combo.setCurrentText(detail.session.mood)
        self.created_value.setText(detail.session.created_at)
        self.updated_value.setText(detail.session.updated_at)
        self.path_value.setText(
            self._category_path_label(detail.session.main_category_name, detail.session.sub_category_name)
        )

        self._set_category_options(
            detail.main_categories,
            detail.sub_categories,
            detail.session.main_category_name,
            detail.session.sub_category_name,
        )

        note_html = detail.note.content if detail.note is not None else ""
        self.notes_editor.setHtml(note_html)
        self._last_saved_note_html = self.notes_editor.toHtml()
        self.quick_idea_edit.clear()

        self._populate_flow(detail.session_flow)
        self._populate_graph(detail.session_graph)
        self._populate_workspace_map(detail.workspace_map)
        self._loading_detail = False

    def _clear_detail_fields(self) -> None:
        self._loading_detail = True
        self.title_edit.clear()
        self.main_category_combo.clear()
        self.sub_category_combo.clear()
        self.template_combo.setCurrentText(DEFAULT_TEMPLATE)
        self.mood_combo.setCurrentText("Focused")
        self.created_value.setText("-")
        self.updated_value.setText("-")
        self.path_value.setText("-")
        self.quick_idea_edit.clear()
        self.notes_editor.clear()
        self._last_saved_note_html = ""
        self.flow_list.clear()
        self.graph_tree.clear()
        self.workspace_tree.clear()
        self._loading_detail = False

    def _build_overview_card(self, content_layout: QVBoxLayout) -> None:
        self.overview_card = CardWidget("Session Overview")
        helper = QLabel(
            "A session is the main unit of work. Categories and templates shape it, but the graph grows from the session itself."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #66788a;")
        self.overview_card.body_layout.addWidget(helper)

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(10)

        self.title_edit = QLineEdit()
        self.main_category_combo = QComboBox()
        self.main_category_combo.setEditable(True)
        self.main_category_combo.currentTextChanged.connect(self._refresh_sub_category_options)

        self.sub_category_combo = QComboBox()
        self.sub_category_combo.setEditable(True)

        self.template_combo = QComboBox()
        self.template_combo.setEditable(True)
        self.template_combo.addItems(TEMPLATE_OPTIONS)

        self.mood_combo = QComboBox()
        self.mood_combo.setEditable(True)
        self.mood_combo.addItems(MOOD_OPTIONS)

        self.path_value = QLabel("-")
        self.created_value = QLabel("-")
        self.updated_value = QLabel("-")

        form_layout.addRow("Title", self.title_edit)
        form_layout.addRow("Main Category", self.main_category_combo)
        form_layout.addRow("Sub Category", self.sub_category_combo)
        form_layout.addRow("Template", self.template_combo)
        form_layout.addRow("Mood", self.mood_combo)
        form_layout.addRow("Branch Path", self.path_value)
        form_layout.addRow("Created", self.created_value)
        form_layout.addRow("Updated", self.updated_value)
        self.overview_card.body_layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        self.save_overview_button = QPushButton("Save Session")
        button_row.addStretch(1)
        button_row.addWidget(self.save_overview_button)
        self.overview_card.body_layout.addLayout(button_row)
        self.save_overview_button.clicked.connect(self._save_overview)

        content_layout.addWidget(self.overview_card)

    def _build_quick_capture_card(self, content_layout: QVBoxLayout) -> None:
        self.quick_capture_card = CardWidget("Quick Capture")
        helper = QLabel(
            "Capture a new idea fast. It can become a note fragment now or a sibling session in the same branch."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #66788a;")
        self.quick_capture_card.body_layout.addWidget(helper)

        row = QHBoxLayout()
        self.quick_idea_edit = QLineEdit()
        self.quick_idea_edit.setPlaceholderText("Type a thought, hypothesis, prompt, or next branch title")
        self.add_idea_to_notes_button = QPushButton("Add to Flow")
        self.new_session_from_idea_button = QPushButton("Branch Session")
        self.new_session_from_idea_button.setProperty("secondary", True)
        row.addWidget(self.quick_idea_edit, 1)
        row.addWidget(self.add_idea_to_notes_button)
        row.addWidget(self.new_session_from_idea_button)
        self.quick_capture_card.body_layout.addLayout(row)

        self.add_idea_to_notes_button.clicked.connect(self._add_quick_idea_to_notes)
        self.new_session_from_idea_button.clicked.connect(self._create_session_from_idea)

        content_layout.addWidget(self.quick_capture_card)

    def _build_flow_card(self, content_layout: QVBoxLayout) -> None:
        self.flow_card = CardWidget("Session Flow")
        helper = QLabel(
            "This is the readable progression of the session: when it started, which template drives it, where it sits, and which ideas were captured."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #66788a;")
        self.flow_card.body_layout.addWidget(helper)

        self.flow_list = QListWidget()
        self.flow_card.body_layout.addWidget(self.flow_list)

        content_layout.addWidget(self.flow_card)

    def _build_graph_card(self, content_layout: QVBoxLayout) -> None:
        self.graph_card = CardWidget("Session MindGraph")
        helper = QLabel(
            "The selected session sits at the center. Under it you can read context, idea branches, and related sessions on the same branch."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #66788a;")
        self.graph_card.body_layout.addWidget(helper)

        self.graph_tree = QTreeWidget()
        self.graph_tree.setColumnCount(3)
        self.graph_tree.setHeaderLabels(["MindGraph", "Type", "Details"])
        self.graph_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.graph_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.graph_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.graph_tree.itemActivated.connect(self._handle_graph_item_activated)
        self.graph_tree.itemDoubleClicked.connect(self._handle_graph_item_activated)
        self.graph_card.body_layout.addWidget(self.graph_tree)

        button_row = QHBoxLayout()
        self.open_graph_session_button = QPushButton("Open Linked Session")
        self.open_graph_session_button.setProperty("secondary", True)
        button_row.addStretch(1)
        button_row.addWidget(self.open_graph_session_button)
        self.graph_card.body_layout.addLayout(button_row)

        self.open_graph_session_button.clicked.connect(self._open_selected_graph_session)

        content_layout.addWidget(self.graph_card)

    def _build_notes_card(self, content_layout: QVBoxLayout) -> None:
        self.notes_card = CardWidget("Working Notes")
        helper = QLabel(
            "This is the raw canvas. The flow and graph above are derived from what you keep here."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #66788a;")
        self.notes_card.body_layout.addWidget(helper)

        toolbar = QHBoxLayout()
        self.bold_button = QPushButton("Bold")
        self.italic_button = QPushButton("Italic")
        self.bullets_button = QPushButton("Bullets")
        self.clear_formatting_button = QPushButton("Plain")
        for button in (
            self.bold_button,
            self.italic_button,
            self.bullets_button,
            self.clear_formatting_button,
        ):
            button.setProperty("secondary", True)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        self.notes_card.body_layout.addLayout(toolbar)

        self.notes_editor = NotesTextEdit()
        self.notes_editor.setPlaceholderText(
            "Write the session as free notes. Important lines become visible in the flow and graph."
        )
        self.notes_editor.textChanged.connect(self._schedule_note_save)
        self.notes_editor.focus_lost.connect(self._save_note_if_needed)
        self.notes_card.body_layout.addWidget(self.notes_editor)

        self.bold_button.clicked.connect(self._toggle_bold)
        self.italic_button.clicked.connect(self._toggle_italic)
        self.bullets_button.clicked.connect(self._insert_bullets)
        self.clear_formatting_button.clicked.connect(self._clear_formatting)

        content_layout.addWidget(self.notes_card)

    def _build_workspace_map_card(self, content_layout: QVBoxLayout) -> None:
        self.workspace_map_card = CardWidget("Workspace Context")
        helper = QLabel(
            "This is the broader branch map. Use it to manage main categories, sub categories, and nearby sessions around the selected session."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #66788a;")
        self.workspace_map_card.body_layout.addWidget(helper)

        self.workspace_tree = QTreeWidget()
        self.workspace_tree.setColumnCount(3)
        self.workspace_tree.setHeaderLabels(["Workspace", "Type", "Details"])
        self.workspace_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.workspace_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.workspace_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.workspace_tree.itemActivated.connect(self._handle_workspace_item_activated)
        self.workspace_tree.itemDoubleClicked.connect(self._handle_workspace_item_activated)
        self.workspace_map_card.body_layout.addWidget(self.workspace_tree)

        button_row = QHBoxLayout()
        self.add_main_category_button = QPushButton("New Main Category")
        self.add_sub_category_button = QPushButton("New Sub Category")
        self.add_session_here_button = QPushButton("New Session Here")
        self.rename_map_item_button = QPushButton("Rename")
        self.delete_map_item_button = QPushButton("Delete")
        for button in (
            self.add_main_category_button,
            self.add_sub_category_button,
            self.add_session_here_button,
            self.rename_map_item_button,
            self.delete_map_item_button,
        ):
            button.setProperty("secondary", True)
            button_row.addWidget(button)
        button_row.addStretch(1)
        self.workspace_map_card.body_layout.addLayout(button_row)

        self.add_main_category_button.clicked.connect(self._create_main_category)
        self.add_sub_category_button.clicked.connect(self._create_sub_category)
        self.add_session_here_button.clicked.connect(self._create_session_from_map)
        self.rename_map_item_button.clicked.connect(self._rename_selected_map_item)
        self.delete_map_item_button.clicked.connect(self._delete_selected_map_item)

        content_layout.addWidget(self.workspace_map_card)

    def _save_overview(self) -> None:
        if self._current_session_id is None:
            return
        try:
            updated = self._service.update_session(
                self._current_session_id,
                self.title_edit.text(),
                self.main_category_combo.currentText(),
                self.sub_category_combo.currentText(),
                self.template_combo.currentText(),
                self.mood_combo.currentText(),
            )
            self._current_session_id = updated.id
            self._reload_current_session()
            self.session_structure_changed.emit(updated.id, "Session details saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Save Session", str(exc))

    def _schedule_note_save(self) -> None:
        if self._loading_detail or self._current_session_id is None:
            return
        self._note_save_timer.start()

    def _save_note_if_needed(self) -> None:
        if self._loading_detail or self._current_session_id is None:
            return
        current_html = self.notes_editor.toHtml()
        if current_html == self._last_saved_note_html:
            return
        try:
            note = self._service.save_note(self._current_session_id, current_html)
            self._last_saved_note_html = current_html
            self.updated_value.setText(note.updated_at)
            self._reload_current_session()
            self.status_message.emit("Notes saved and graph refreshed.")
        except Exception as exc:
            QMessageBox.critical(self, "Save Notes", str(exc))

    def _add_quick_idea_to_notes(self) -> None:
        if self._current_session_id is None:
            return
        try:
            note = self._service.append_quick_idea(self._current_session_id, self.quick_idea_edit.text())
            self.quick_idea_edit.clear()
            self.updated_value.setText(note.updated_at)
            self._reload_current_session()
            self.session_structure_changed.emit(self._current_session_id, "Idea added to the session flow.")
        except Exception as exc:
            QMessageBox.critical(self, "Quick Capture", str(exc))

    def _create_session_from_idea(self) -> None:
        if self._current_session_id is None:
            return
        try:
            session = self._service.create_related_session(self._current_session_id, self.quick_idea_edit.text())
            self.quick_idea_edit.clear()
            self.session_structure_changed.emit(session.id, f"Created '{session.title}'.")
        except Exception as exc:
            QMessageBox.critical(self, "Branch Session", str(exc))

    def _toggle_bold(self) -> None:
        self._merge_note_format(
            lambda fmt: fmt.setFontWeight(
                QFont.Weight.Normal
                if self.notes_editor.fontWeight() >= QFont.Weight.Bold
                else QFont.Weight.Bold
            )
        )

    def _toggle_italic(self) -> None:
        self._merge_note_format(lambda fmt: fmt.setFontItalic(not self.notes_editor.fontItalic()))

    def _insert_bullets(self) -> None:
        cursor = self.notes_editor.textCursor()
        cursor.beginEditBlock()
        cursor.insertList(QTextListFormat.Style.ListDisc)
        cursor.endEditBlock()

    def _clear_formatting(self) -> None:
        plain_text = self.notes_editor.toPlainText()
        self.notes_editor.setPlainText(plain_text)

    def _merge_note_format(self, configure) -> None:
        cursor = self.notes_editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        fmt = QTextCharFormat()
        configure(fmt)
        cursor.mergeCharFormat(fmt)
        self.notes_editor.mergeCurrentCharFormat(fmt)

    def _set_category_options(
        self,
        main_categories: list[MainCategory],
        sub_categories: list[SubCategory],
        selected_main: str,
        selected_sub: str | None,
    ) -> None:
        mapping = {category.name: [] for category in main_categories}
        main_name_by_id = {category.id: category.name for category in main_categories}
        for sub_category in sub_categories:
            main_name = main_name_by_id.get(sub_category.main_category_id)
            if main_name is None:
                continue
            mapping.setdefault(main_name, []).append(sub_category.name)
        if selected_main and selected_main not in mapping:
            mapping[selected_main] = []
        self._category_options = {
            name: sorted(values, key=str.casefold)
            for name, values in sorted(mapping.items())
        }

        self.main_category_combo.blockSignals(True)
        self.main_category_combo.clear()
        self.main_category_combo.addItems(list(self._category_options))
        self.main_category_combo.setCurrentText(selected_main)
        self.main_category_combo.blockSignals(False)
        self._refresh_sub_category_options(selected_main, selected_sub)

    def _refresh_sub_category_options(self, main_category_name: str, selected_sub: str | None = None) -> None:
        if selected_sub is None:
            selected_sub = self.sub_category_combo.currentText()
        values = self._category_options.get(main_category_name.strip(), [])
        self.sub_category_combo.blockSignals(True)
        self.sub_category_combo.clear()
        self.sub_category_combo.addItem("")
        self.sub_category_combo.addItems(values)
        self.sub_category_combo.setCurrentText(selected_sub or "")
        self.sub_category_combo.blockSignals(False)
        self.path_value.setText(self._category_path_label(main_category_name, selected_sub))

    def _populate_flow(self, items: list[SessionFlowItem]) -> None:
        self.flow_list.clear()
        for item in items:
            row = QListWidgetItem(f"{item.title}\n{item.detail}")
            row.setData(Qt.ItemDataRole.UserRole, item.kind)
            row.setToolTip(item.detail)
            font = row.font()
            if item.kind != "idea":
                font.setBold(True)
            row.setFont(font)
            self.flow_list.addItem(row)

    def _populate_graph(self, nodes: list[SessionGraphNode]) -> None:
        self.graph_tree.clear()
        node_lookup: dict[str, QTreeWidgetItem] = {}
        for node in nodes:
            item = QTreeWidgetItem([node.title, self._graph_kind_label(node.kind), node.subtitle])
            item.setData(0, Qt.ItemDataRole.UserRole, node.session_id)
            item.setData(1, Qt.ItemDataRole.UserRole, node.kind)
            if node.kind == "session_root":
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            if node.parent_key is None:
                self.graph_tree.addTopLevelItem(item)
            else:
                parent_item = node_lookup.get(node.parent_key)
                if parent_item is not None:
                    parent_item.addChild(item)
                else:
                    self.graph_tree.addTopLevelItem(item)
            node_lookup[node.key] = item
        self.graph_tree.expandAll()

    def _populate_workspace_map(self, items: list[WorkspaceMapItem]) -> None:
        self.workspace_tree.clear()
        item_lookup: dict[str, QTreeWidgetItem] = {}
        selected_item: QTreeWidgetItem | None = None
        for map_item in items:
            tree_item = QTreeWidgetItem(
                [map_item.title, self._workspace_kind_label(map_item.kind), map_item.subtitle]
            )
            tree_item.setData(0, Qt.ItemDataRole.UserRole, (map_item.kind, map_item.entity_id))
            tree_item.setToolTip(0, map_item.subtitle)
            if map_item.parent_key is None:
                self.workspace_tree.addTopLevelItem(tree_item)
            else:
                parent_item = item_lookup.get(map_item.parent_key)
                if parent_item is not None:
                    parent_item.addChild(tree_item)
                else:
                    self.workspace_tree.addTopLevelItem(tree_item)
            if map_item.is_selected:
                font = tree_item.font(0)
                font.setBold(True)
                tree_item.setFont(0, font)
                selected_item = tree_item
            item_lookup[map_item.key] = tree_item

        self.workspace_tree.expandAll()
        if selected_item is not None:
            self.workspace_tree.setCurrentItem(selected_item)

    def _create_main_category(self) -> None:
        dialog = CategoryDialog("New Main Category", "Main Category", parent=self)
        if dialog.exec() != CategoryDialog.DialogCode.Accepted:
            return
        try:
            self._service.create_main_category(dialog.value())
            self._reload_current_session()
            if self._current_session_id is not None:
                self.session_structure_changed.emit(self._current_session_id, "Main branch added.")
        except Exception as exc:
            QMessageBox.critical(self, "New Main Category", str(exc))

    def _create_sub_category(self) -> None:
        main_category = self._selected_main_category_context()
        if main_category is None:
            QMessageBox.information(self, "New Sub Category", "Select a main branch first.")
            return
        dialog = CategoryDialog("New Sub Category", "Sub Category", parent=self)
        if dialog.exec() != CategoryDialog.DialogCode.Accepted:
            return
        try:
            self._service.create_sub_category(main_category.id, dialog.value())
            self._reload_current_session()
            if self._current_session_id is not None:
                self.session_structure_changed.emit(self._current_session_id, "Sub branch added.")
        except Exception as exc:
            QMessageBox.critical(self, "New Sub Category", str(exc))

    def _create_session_from_map(self) -> None:
        main_category_name, sub_category_name = self._selected_category_names()
        dialog = SessionDialog(
            "New Session",
            category_options=self._service.get_category_options(),
            main_category=main_category_name,
            sub_category=sub_category_name,
            parent=self,
        )
        if dialog.exec() != SessionDialog.DialogCode.Accepted:
            return
        try:
            title, main_category, sub_category, template_name, mood = dialog.values()
            session = self._service.create_session(
                title,
                main_category,
                sub_category,
                template_name,
                mood,
            )
            self.session_structure_changed.emit(session.id, f"Created '{session.title}'.")
        except Exception as exc:
            QMessageBox.critical(self, "New Session", str(exc))

    def _rename_selected_map_item(self) -> None:
        payload = self._selected_tree_payload()
        if payload is None:
            return
        kind, entity_id = payload
        try:
            if kind == "main_category":
                category = self._service.main_categories.get(entity_id)
                if category is None:
                    raise ValueError("Main category not found.")
                dialog = CategoryDialog(
                    "Rename Main Category",
                    "Main Category",
                    category.name,
                    self,
                )
                if dialog.exec() != CategoryDialog.DialogCode.Accepted:
                    return
                self._service.rename_main_category(entity_id, dialog.value())
            elif kind == "sub_category":
                category = self._service.sub_categories.get(entity_id)
                if category is None:
                    raise ValueError("Sub category not found.")
                dialog = CategoryDialog(
                    "Rename Sub Category",
                    "Sub Category",
                    category.name,
                    self,
                )
                if dialog.exec() != CategoryDialog.DialogCode.Accepted:
                    return
                self._service.rename_sub_category(entity_id, dialog.value())
            elif kind == "session":
                self.session_selected_from_map.emit(entity_id)
                self.focus_overview_editor()
                self.status_message.emit("Use the overview card to rename this session.")
                return
            self._reload_current_session()
            if self._current_session_id is not None:
                self.session_structure_changed.emit(self._current_session_id, "Workspace context updated.")
        except Exception as exc:
            QMessageBox.critical(self, "Rename", str(exc))

    def _delete_selected_map_item(self) -> None:
        payload = self._selected_tree_payload()
        if payload is None:
            return
        kind, entity_id = payload
        if kind == "session":
            QMessageBox.information(self, "Delete", "Delete sessions from the list on the left.")
            return
        title = self.workspace_tree.currentItem().text(0) if self.workspace_tree.currentItem() else "this item"
        result = QMessageBox.question(
            self,
            "Delete",
            f"Delete '{title}' from the workspace context?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        try:
            if kind == "main_category":
                self._service.delete_main_category(entity_id)
            elif kind == "sub_category":
                self._service.delete_sub_category(entity_id)
            self._reload_current_session()
            if self._current_session_id is not None:
                self.session_structure_changed.emit(self._current_session_id, "Workspace context updated.")
        except Exception as exc:
            QMessageBox.critical(self, "Delete", str(exc))

    def _open_selected_graph_session(self) -> None:
        item = self.graph_tree.currentItem()
        if item is None:
            return
        session_id = item.data(0, Qt.ItemDataRole.UserRole)
        node_kind = item.data(1, Qt.ItemDataRole.UserRole)
        if session_id is None or node_kind != "related_session":
            QMessageBox.information(self, "Open Linked Session", "Select a linked session node first.")
            return
        if int(session_id) != self._current_session_id:
            self.session_selected_from_map.emit(int(session_id))

    def _handle_graph_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        session_id = item.data(0, Qt.ItemDataRole.UserRole)
        node_kind = item.data(1, Qt.ItemDataRole.UserRole)
        if session_id is None or node_kind != "related_session":
            return
        if int(session_id) != self._current_session_id:
            self.session_selected_from_map.emit(int(session_id))

    def _handle_workspace_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if payload is None:
            return
        kind, entity_id = payload
        if kind == "session" and entity_id != self._current_session_id:
            self.session_selected_from_map.emit(int(entity_id))

    def _selected_tree_payload(self) -> tuple[str, int] | None:
        item = self.workspace_tree.currentItem()
        if item is None:
            return None
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if payload is None:
            return None
        kind, entity_id = payload
        return str(kind), int(entity_id)

    def _selected_main_category_context(self) -> MainCategory | None:
        payload = self._selected_tree_payload()
        if payload is None:
            return None
        kind, entity_id = payload
        if kind == "main_category":
            return self._service.main_categories.get(entity_id)
        if kind == "sub_category":
            sub_category = self._service.sub_categories.get(entity_id)
            if sub_category is None:
                return None
            return self._service.main_categories.get(sub_category.main_category_id)
        if kind == "session":
            session = self._service.sessions.get(entity_id)
            if session is None:
                return None
            return self._service.main_categories.get(session.main_category_id)
        return None

    def _selected_category_names(self) -> tuple[str, str]:
        payload = self._selected_tree_payload()
        if payload is None and self._current_session_id is not None:
            session = self._service.sessions.get(self._current_session_id)
            if session is not None:
                return session.main_category_name, session.sub_category_name or ""
            return "", ""
        if payload is None:
            return "", ""
        kind, entity_id = payload
        if kind == "main_category":
            category = self._service.main_categories.get(entity_id)
            return (category.name, "") if category else ("", "")
        if kind == "sub_category":
            category = self._service.sub_categories.get(entity_id)
            if category is None:
                return "", ""
            main_category = self._service.main_categories.get(category.main_category_id)
            return (main_category.name if main_category else "", category.name)
        if kind == "session":
            session = self._service.sessions.get(entity_id)
            if session is None:
                return "", ""
            return session.main_category_name, session.sub_category_name or ""
        return "", ""

    @staticmethod
    def _workspace_kind_label(kind: str) -> str:
        return {
            "main_category": "Main",
            "sub_category": "Sub",
            "session": "Session",
        }.get(kind, kind.title())

    @staticmethod
    def _graph_kind_label(kind: str) -> str:
        return {
            "session_root": "Session",
            "context_group": "Context",
            "category": "Branch",
            "template": "Template",
            "idea_group": "Ideas",
            "idea": "Idea",
            "related_group": "Links",
            "related_session": "Session",
        }.get(kind, kind.replace("_", " ").title())

    @staticmethod
    def _category_path_label(main_category_name: str, sub_category_name: str | None) -> str:
        cleaned_main = main_category_name.strip() or "-"
        cleaned_sub = (sub_category_name or "").strip()
        return f"{cleaned_main} / {cleaned_sub}" if cleaned_sub else cleaned_main
