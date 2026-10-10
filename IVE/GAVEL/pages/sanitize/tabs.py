from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QUrl
from PyQt6.QtGui import QBrush, QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from GAVEL.app.dtos.course_summary import (
    AnonymizationStatus,
    CourseSummary,
    FileState,
    TrackedFile,
)
from GAVEL.app.workspace.layout import ANONYMIZED_DIR, ORIGINAL_DIR
from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.sanitize.viewmodel import (
    CourseFilter,
    SanitizeUiState,
    SanitizeViewModel,
    course_label,
    term_label,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing
from GAVEL.ui_components.section_card import SectionCard

COURSE_COLUMNS = ("Course", "Term", "Consent form", "Last anonymized", "Status")
_CONSENT_COLUMN = 2
_ANONYMIZED_COLUMN = 3
_STATUS_COLUMN = 4
# Course folder name, on every row, so a click anywhere selects that course.
_FOLDER_ROLE = Qt.ItemDataRole.UserRole
# Unique id of an expandable row, so expansion survives a rebuild.
_NODE_ROLE = Qt.ItemDataRole.UserRole + 1
# Absolute path of the folder or file a row stands for, whether or not it exists.
_PATH_ROLE = Qt.ItemDataRole.UserRole + 2

OPEN_LOCATION_TEXT = "Open folder location"


def show_in_file_manager(path: Path) -> None:
    """Open the system file manager at a folder, or at a file's folder with the file selected."""
    if path.is_file() and sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{path}"')
        return
    folder = path if path.is_dir() else path.parent
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


_STATUS_TEXT = {
    AnonymizationStatus.NO_CONSENT_FORM: "No consent form",
    AnonymizationStatus.NOT_ANONYMIZED: "Not anonymized",
    AnonymizationStatus.OUT_OF_DATE: "Out of date",
    AnonymizationStatus.UP_TO_DATE: "Up to date",
}
_STATUS_COLOR_TOKEN = {
    AnonymizationStatus.NO_CONSENT_FORM: "status_critical",
    AnonymizationStatus.NOT_ANONYMIZED: "interactive",
    AnonymizationStatus.OUT_OF_DATE: "status_caution",
    AnonymizationStatus.UP_TO_DATE: "status_nominal",
}
_FILE_STATE_TEXT = {
    FileState.CURRENT: "●  Up to date",
    FileState.OUT_OF_DATE: "●  Out of date",
    FileState.MISSING: "○  Missing",
}
_FILE_STATE_COLOR_TOKEN = {
    FileState.CURRENT: "status_nominal",
    FileState.OUT_OF_DATE: "status_caution",
    FileState.MISSING: "text_secondary",
}
_FILTER_LABELS = {
    CourseFilter.ALL: "All",
    CourseFilter.NOT_UP_TO_DATE: "Not up to date",
    CourseFilter.UP_TO_DATE: "Up to date",
}
_REANONYMIZE_NOTE = "Running again replaces anonymized/ and gives every student a new anonymous ID."


def _when(moment: datetime | None) -> str:
    return moment.strftime("%Y-%m-%d %H:%M") if moment else "Never"


def banner_text(course: CourseSummary) -> str:
    """Warning shown under the tree for the selected course, or "" when there is none."""
    status = course.status
    if status is AnonymizationStatus.NO_CONSENT_FORM:
        return (
            "No consent form in original/, so nobody can be included. "
            "Download it on the Download page, then choose Reload."
        )
    if status is AnonymizationStatus.OUT_OF_DATE:
        return (
            "Out of date: files in original/ changed or were added after the last "
            f"anonymization on {_when(course.anonymized_at)}. {_REANONYMIZE_NOTE}"
        )
    if status is AnonymizationStatus.UP_TO_DATE:
        return f"Already anonymized on {_when(course.anonymized_at)}. {_REANONYMIZE_NOTE}"
    return ""


def consent_text(course: CourseSummary) -> str:
    if course.consent is not None:
        return f"{course.consent.included} of {course.consent.total} consented"
    return "Unreadable" if course.consent_unreadable else "Missing"


def _side_state(file: TrackedFile, side: str) -> FileState:
    return file.original_state if side == ORIGINAL_DIR else file.anonymized_state


def _folder_state(states: list[FileState]) -> FileState:
    """A folder is missing when everything under it is, and out of date when anything is."""
    if all(state is FileState.MISSING for state in states):
        return FileState.MISSING
    if any(state is FileState.OUT_OF_DATE for state in states):
        return FileState.OUT_OF_DATE
    return FileState.CURRENT


def _file_tooltip(file: TrackedFile, side: str) -> str:
    state = _side_state(file, side)
    if state is FileState.MISSING:
        return f"Not in {side}/"
    moment = file.original_at if side == ORIGINAL_DIR else file.anonymized_at
    note = (
        "\nThe original changed after this was written." if state is FileState.OUT_OF_DATE else ""
    )
    return f"Modified {_when(moment)}{note}"


def _set_role(widget: QWidget, role: str) -> None:
    """Switch a widget's style role and re-apply the stylesheet so it takes effect."""
    if widget.property("role") == role:
        return
    widget.setProperty("role", role)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


class SanitizeTab(ScrollableTab):
    """Review consent and anonymize a course's downloaded data."""

    def __init__(
        self,
        theme: ThemeContext,
        vm: SanitizeViewModel,
        open_location: Callable[[Path], None] = show_in_file_manager,
    ) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm
        self._open_location = open_location
        # Kept so the open right-click menu is not garbage collected.
        self._context_menu: QMenu | None = None
        self._rendering = False
        self._shown_courses: tuple[CourseSummary, ...] | None = None
        self._expanded: set[str] = set()

        self._build_widgets()
        self._connect_signals()

        self.add_section(self._build_courses_card())
        self.add_stretch()

        self._vm.state_changed.connect(self.render)
        self.render(self._vm.get_state())

    @property
    def course_tree(self) -> QTreeWidget:
        return self._tree

    @property
    def workspace_input(self) -> QLineEdit:
        return self._workspace_path

    @property
    def banner_label(self) -> QLabel:
        return self._banner

    @property
    def empty_label(self) -> QLabel:
        return self._empty_label

    def filter_button(self, course_filter: CourseFilter) -> QPushButton:
        return self._filter_buttons[course_filter]

    def _build_widgets(self) -> None:
        self._workspace_path = QLineEdit()
        self._workspace_path.setPlaceholderText("Folder that holds courses/")
        self._change_workspace_btn = QPushButton("Change…")
        self._change_workspace_btn.setProperty("role", "secondary")
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.setProperty("role", "secondary")

        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        self._filter_buttons: dict[CourseFilter, QPushButton] = {}
        positions = ("first", "middle", "last")
        for course_filter, pos in zip(CourseFilter, positions, strict=True):
            btn = QPushButton(_FILTER_LABELS[course_filter])
            btn.setCheckable(True)
            btn.setProperty("role", "segment")
            btn.setProperty("segment_pos", pos)
            self._filter_group.addButton(btn)
            self._filter_buttons[course_filter] = btn

        self._search = QLineEdit()
        self._search.setPlaceholderText("Course, term, or class number")
        self._search.setClearButtonEnabled(True)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(len(COURSE_COLUMNS))
        self._tree.setHeaderLabels(COURSE_COLUMNS)
        self._tree.setRootIsDecorated(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.setMinimumHeight(420)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(COURSE_COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        self._empty_label = QLabel()
        self._empty_label.setProperty("role", "text_muted")
        self._empty_label.setWordWrap(True)

        self._scan_error = QLabel()
        self._scan_error.setProperty("role", "warning")
        self._scan_error.setWordWrap(True)

        self._selected_dot = QLabel("●")
        self._selected_dot.setProperty("role", "status_dot")
        self._selected_key = QLabel("SELECTED")
        self._selected_key.setProperty("role", "readout_key")
        self._selected_value = QLabel()
        self._selected_value.setWordWrap(True)

        self._banner = QLabel()
        # Set before the first polish: a role added later keeps its border but not its padding.
        self._banner.setProperty("role", "caution")
        self._banner.setWordWrap(True)

        self._hint = QLabel(
            "Courses are read from the workspace's courses/ folder. Select one to review "
            "consent and anonymize it. Files in original/ are never changed."
        )
        self._hint.setProperty("role", "text_muted")
        self._hint.setWordWrap(True)

    def _connect_signals(self) -> None:
        self._change_workspace_btn.clicked.connect(self._choose_workspace)
        self._reload_btn.clicked.connect(self._vm.reload)
        self._workspace_path.editingFinished.connect(
            lambda: self._vm.set_workspace_root(self._workspace_path.text())
        )
        for course_filter, btn in self._filter_buttons.items():
            btn.clicked.connect(lambda _=False, f=course_filter: self._vm.set_course_filter(f))
        self._search.textChanged.connect(self._vm.set_course_search)
        self._tree.itemSelectionChanged.connect(self._on_tree_selection)
        self._tree.itemExpanded.connect(self._on_expanded)
        self._tree.itemCollapsed.connect(self._on_collapsed)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)

    def _build_courses_card(self) -> QWidget:
        card = SectionCard(self._theme, "Courses")

        workspace_row = QWidget()
        workspace_layout = QHBoxLayout(workspace_row)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(workspace_layout, self._theme, 8)
        workspace_key = QLabel("Workspace")
        workspace_key.setProperty("role", "text_muted")
        workspace_layout.addWidget(workspace_key)
        workspace_layout.addWidget(self._workspace_path, 1)
        workspace_layout.addWidget(self._change_workspace_btn)
        workspace_layout.addWidget(self._reload_btn)

        filter_row = QWidget()
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(0)
        for btn in self._filter_buttons.values():
            filter_layout.addWidget(btn)
        filter_layout.addStretch(1)
        filter_layout.addSpacing(self._theme.tokens.sp(16))
        filter_layout.addWidget(self._search, 1)

        selected_row = QWidget()
        selected_layout = QHBoxLayout(selected_row)
        selected_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(selected_layout, self._theme, 8)
        selected_layout.addWidget(self._selected_dot)
        selected_layout.addWidget(self._selected_key)
        selected_layout.addWidget(self._selected_value, 1)

        card.add_row(workspace_row)
        card.add_row(filter_row)
        card.add_row(self._scan_error)
        card.add_row(self._tree)
        card.add_row(self._empty_label)
        card.add_row(selected_row)
        card.add_row(self._banner)
        card.add_row(self._hint)
        return card

    def render(self, state: SanitizeUiState) -> None:
        """Paint the widgets from state. The view model is the only source of truth."""
        if self._rendering:
            return
        self._rendering = True
        try:
            self._render(state)
        finally:
            self._rendering = False

    def _render(self, state: SanitizeUiState) -> None:
        colors = self._theme.tokens.color

        if not self._workspace_path.hasFocus():
            self._workspace_path.setText(state.workspace_root)
        self._workspace_path.setToolTip(state.workspace_root)

        for course_filter, btn in self._filter_buttons.items():
            btn.setText(f"{_FILTER_LABELS[course_filter]} ({state.filter_count(course_filter)})")
            btn.setChecked(course_filter is state.course_filter)
        if self._search.text() != state.course_search:
            self._search.setText(state.course_search)

        self._scan_error.setText(state.scan_error or "")
        self._scan_error.setVisible(bool(state.scan_error))

        visible = state.visible_courses
        if visible != self._shown_courses:
            self._rebuild_tree(visible)
            self._shown_courses = visible
        self._select_in_tree(state.selected_course)

        if not state.courses and not state.scan_error:
            empty = (
                f"No course folders found in {state.workspace_root}. Download a course on the "
                "Download page first, or choose a different workspace."
            )
        elif state.courses and not visible:
            empty = "No courses match the filter or search."
        else:
            empty = ""
        self._empty_label.setText(empty)
        self._empty_label.setVisible(bool(empty))

        selected = state.selected_summary
        if selected is None:
            self._selected_value.setText("No course selected yet")
            self._selected_dot.setStyleSheet(f"color: {colors['status_unknown']};")
            _set_role(self._selected_value, "text_muted")
        else:
            self._selected_value.setText(
                f"{course_label(selected.key)}  ·  {term_label(selected.key)}"
                f"  ·  {selected.folder_name}"
            )
            self._selected_dot.setStyleSheet(
                f"color: {colors[_STATUS_COLOR_TOKEN[selected.status]]};"
            )
            _set_role(self._selected_value, "readout_value")

        banner = banner_text(selected) if selected is not None else ""
        self._banner.setText(banner)
        self._banner.setVisible(bool(banner))
        if selected is not None:
            critical = selected.status is AnonymizationStatus.NO_CONSENT_FORM
            _set_role(self._banner, "warning" if critical else "caution")

    def _rebuild_tree(self, courses: tuple[CourseSummary, ...]) -> None:
        colors = self._theme.tokens.color
        self._tree.blockSignals(True)
        try:
            self._tree.clear()
            for course in courses:
                item = QTreeWidgetItem(
                    [
                        course_label(course.key),
                        term_label(course.key),
                        consent_text(course),
                        _when(course.anonymized_at),
                        f"●  {_STATUS_TEXT[course.status]}",
                    ]
                )
                item.setData(0, _FOLDER_ROLE, course.folder_name)
                item.setData(0, _NODE_ROLE, course.folder_name)
                item.setData(0, _PATH_ROLE, str(course.path))
                item.setForeground(
                    _STATUS_COLUMN,
                    QBrush(QColor(colors[_STATUS_COLOR_TOKEN[course.status]])),
                )
                if course.consent is None:
                    token = "text_secondary" if course.consent_unreadable else "status_critical"
                    item.setForeground(_CONSENT_COLUMN, QBrush(QColor(colors[token])))
                if course.anonymized_at is None:
                    item.setForeground(_ANONYMIZED_COLUMN, QBrush(QColor(colors["text_secondary"])))
                tooltip = "\n".join(
                    part for part in (course.canvas_course_name, str(course.path)) if part
                )
                for column in range(len(COURSE_COLUMNS)):
                    item.setToolTip(column, tooltip)
                self._tree.addTopLevelItem(item)

                for side in (ORIGINAL_DIR, ANONYMIZED_DIR):
                    self._add_side(item, course, side)

                item.setExpanded(course.folder_name in self._expanded)
        finally:
            self._tree.blockSignals(False)

    def _add_side(self, course_item: QTreeWidgetItem, course: CourseSummary, side: str) -> None:
        """original/ or anonymized/ under a course, mirroring the folders on disk."""
        side_key = f"{course.folder_name}/{side}"
        side_path = course.path / side
        side_item = self._file_row(course_item, course.folder_name, f"{side}/", side_path, side_key)
        folders: dict[str, QTreeWidgetItem] = {side_key: side_item}
        states: dict[str, list[FileState]] = {side_key: []}

        for file in course.files:
            state = _side_state(file, side)
            parent_key, parent, parent_path = side_key, side_item, side_path
            *dirs, name = file.path.split("/")
            states[side_key].append(state)
            for directory in dirs:
                key = f"{parent_key}/{directory}"
                parent_path = parent_path / directory
                if key not in folders:
                    folders[key] = self._file_row(
                        parent, course.folder_name, f"{directory}/", parent_path, key
                    )
                    states[key] = []
                states[key].append(state)
                parent_key, parent = key, folders[key]
            leaf = self._file_row(parent, course.folder_name, name, parent_path / name)
            self._paint_state(leaf, state)
            leaf.setToolTip(0, _file_tooltip(file, side))

        for key, folder in folders.items():
            self._paint_state(folder, _folder_state(states[key]))
            folder.setExpanded(key in self._expanded)

    def _file_row(
        self,
        parent: QTreeWidgetItem,
        folder_name: str,
        text: str,
        path: Path,
        node_key: str | None = None,
    ) -> QTreeWidgetItem:
        row = QTreeWidgetItem([text])
        row.setData(0, _FOLDER_ROLE, folder_name)
        row.setData(0, _PATH_ROLE, str(path))
        if node_key is not None:
            row.setData(0, _NODE_ROLE, node_key)
        parent.addChild(row)
        return row

    def _paint_state(self, row: QTreeWidgetItem, state: FileState) -> None:
        color = QColor(self._theme.tokens.color[_FILE_STATE_COLOR_TOKEN[state]])
        row.setText(_STATUS_COLUMN, _FILE_STATE_TEXT[state])
        row.setForeground(_STATUS_COLUMN, QBrush(color))
        if state is FileState.MISSING:
            row.setForeground(0, QBrush(color))

    def _select_in_tree(self, folder_name: str | None) -> None:
        self._tree.blockSignals(True)
        try:
            for index in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(index)
                if item is not None and item.data(0, _FOLDER_ROLE) == folder_name:
                    self._tree.setCurrentItem(item)
                    return
            self._tree.clearSelection()
            self._tree.setCurrentItem(None)
        finally:
            self._tree.blockSignals(False)

    def _on_tree_selection(self) -> None:
        items = self._tree.selectedItems()
        if not items:
            return
        item = items[0]
        course_item = item
        while course_item.parent() is not None:
            course_item = course_item.parent()
        folder_name = course_item.data(0, _FOLDER_ROLE)
        course_item.setExpanded(True)
        self._vm.select_course(folder_name)
        # A click on a file row still selects its course, so show the course row as selected.
        if item is not course_item:
            self._select_in_tree(folder_name)

    def _on_expanded(self, item: QTreeWidgetItem) -> None:
        self._expanded.add(item.data(0, _NODE_ROLE))

    def _on_collapsed(self, item: QTreeWidgetItem) -> None:
        self._expanded.discard(item.data(0, _NODE_ROLE))

    def context_menu_for(self, item: QTreeWidgetItem) -> QMenu:
        """The right-click menu for a row. Opening is disabled when the row is missing on disk."""
        # No parent: inside a card, the frames' transparency rule would reach the popup.
        menu = QMenu()
        target = Path(item.data(0, _PATH_ROLE))
        action = menu.addAction(OPEN_LOCATION_TEXT)
        if target.exists():
            action.triggered.connect(lambda: self._open_location(target))
        else:
            action.setEnabled(False)
        self._context_menu = menu
        return menu

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return
        self.context_menu_for(item).exec(self._tree.viewport().mapToGlobal(pos))

    def _choose_workspace(self) -> None:
        start = self._vm.get_state().workspace_root
        chosen = QFileDialog.getExistingDirectory(self, "Select workspace folder", start)
        if chosen:
            self._vm.set_workspace_root(os.path.normpath(chosen))
