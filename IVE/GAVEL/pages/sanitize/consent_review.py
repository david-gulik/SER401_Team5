"""The Consent Review card: who in the selected course is kept, and why the rest are not."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.consent_decision import ConsentDecision, ConsentStatus
from GAVEL.pages.sanitize.viewmodel import (
    NAME_PROBLEM_STATUSES,
    ConsentFilter,
    SanitizeUiState,
    SanitizeViewModel,
    course_label,
    term_label,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing
from GAVEL.ui_components.section_card import SectionCard

CONSENT_COLUMNS = ("Student", "SIS ID", "Attempt", "Typed name", "Consent", "Result")

# (filter, label, hint, color token) for each summary tile, left to right.
TILES = (
    (ConsentFilter.INCLUDED, "Included", "Will be anonymized", "status_nominal"),
    (ConsentFilter.DECLINED, "Declined", "Answered no", "status_warning"),
    (ConsentFilter.NAME_PROBLEM, "Name problem", "Said yes, name did not match", "status_caution"),
    (ConsentFilter.NO_RESPONSE, "No response", "On roster, not on consent form", "status_unknown"),
)
_SEGMENTS = (
    (ConsentFilter.ALL, "All", "first"),
    (ConsentFilter.INCLUDED, "Included", "middle"),
    (ConsentFilter.EXCLUDED, "Excluded", "last"),
)

# A plain triangle: Windows draws U+26A0 as an emoji that ignores the text color.
_WARNING = "▲"

# (glyph and text, color token) shown in the Result column.
RESULT_TEXT = {
    ConsentStatus.INCLUDED: ("✓  Included", "status_nominal"),
    ConsentStatus.DECLINED: ("✕  Declined", "status_warning"),
    ConsentStatus.NAME_BLANK: (f"{_WARNING}  Name blank", "status_caution"),
    ConsentStatus.POSSIBLE_TYPO: (f"{_WARNING}  Possible typo", "status_caution"),
    ConsentStatus.NAME_MISMATCH: (f"{_WARNING}  Name mismatch", "status_caution"),
    ConsentStatus.NO_RESPONSE: ("—  No response", "status_unknown"),
}

# Text a copied cell puts on the clipboard when it differs from what is shown.
_COPY_ROLE = Qt.ItemDataRole.UserRole
# What a cell sorts by when its column header is clicked.
_SORT_ROLE = Qt.ItemDataRole.UserRole + 1
# Result column order: kept first, then each reason for leaving a student out.
_RESULT_ORDER = tuple(RESULT_TEXT)

FOOTNOTE = (
    "Only each student's latest attempt counts. A student is included only if they said yes "
    "and typed a name that matches their Canvas name. Everyone else is removed from every "
    "anonymized file."
)
NO_COURSE_TEXT = "Select a course above to review who consented."
NO_CONSENT_FORM_TEXT = (
    "No consent form for this course. Nobody can be included until original/consent_form.csv "
    "exists. Download it on the Download page, then choose Reload."
)


def row_cells(decision: ConsentDecision) -> tuple[str, ...]:
    """The text in each column for one student."""
    if decision.name_response is None:
        typed = "—"
    else:
        typed = decision.name_response.strip() or "(blank)"
    if decision.consented is None:
        consent = "—"
    else:
        consent = "Yes" if decision.consented else "No"
    return (
        decision.name,
        str(decision.sis_id),
        "—" if decision.attempt is None else str(decision.attempt),
        typed,
        consent,
        RESULT_TEXT[decision.status][0],
    )


def sort_keys(decision: ConsentDecision) -> tuple[tuple, ...]:
    """Per-column sort keys. Missing values sort after real ones (ascending); ties go by name."""
    name = decision.name.lower()
    typed = decision.name_response
    if typed is None:
        typed_key: tuple = (2, "")
    elif not typed.strip():
        typed_key = (1, "")
    else:
        typed_key = (0, typed.strip().lower())
    consent_key = {True: 0, False: 1, None: 2}[decision.consented]
    return (
        (name,),
        (decision.sis_id, name),
        (decision.attempt is None, decision.attempt or 0, name),
        (*typed_key, name),
        (consent_key, name),
        (_RESULT_ORDER.index(decision.status), name),
    )


class _SortableItem(QTableWidgetItem):
    """A cell that sorts by its _SORT_ROLE key instead of its display text."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        mine, theirs = self.data(_SORT_ROLE), other.data(_SORT_ROLE)
        if mine is None or theirs is None:
            return super().__lt__(other)
        return mine < theirs


class _ConsentTile(QPushButton):
    """A summary tile: big count, label, and hint. Checked while it filters the table."""

    def __init__(self, theme: ThemeContext, label: str, hint: str, color: str) -> None:
        super().__init__()
        self.setProperty("role", "tile")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._count = QLabel("0")
        self._count.setProperty("role", "h1")
        self._count.setStyleSheet(f"color: {color};")
        self._label = QLabel(label)
        hint_label = QLabel(hint)
        hint_label.setProperty("role", "text_muted")
        hint_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        sp = theme.tokens.sp
        layout.setContentsMargins(sp(12), sp(8), sp(12), sp(8))
        layout.setSpacing(0)
        for widget in (self._count, self._label, hint_label):
            # Clicks land on the button, not the labels drawn on it.
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(widget)
        self.setAccessibleName(label)

    @property
    def count_text(self) -> str:
        return self._count.text()

    def set_count(self, count: int) -> None:
        self._count.setText(str(count))
        self.setAccessibleDescription(f"{count} students")

    def sizeHint(self):  # noqa: N802 (Qt override)
        return self.layout().sizeHint()

    def minimumSizeHint(self):  # noqa: N802 (Qt override)
        return self.layout().minimumSize()


class ConsentReviewCard(SectionCard):
    def __init__(self, theme: ThemeContext, vm: SanitizeViewModel) -> None:
        super().__init__(theme, "Consent Review")
        self._theme = theme
        self._vm = vm
        self._shown_decisions: tuple[ConsentDecision, ...] | None = None
        colors = theme.tokens.color

        self._placeholder = QLabel()
        self._placeholder.setProperty("role", "text_muted")
        self._placeholder.setWordWrap(True)

        self._error = QLabel()
        self._error.setProperty("role", "warning")
        self._error.setWordWrap(True)

        self._tiles: dict[ConsentFilter, _ConsentTile] = {}
        tiles_row = QWidget()
        tiles_layout = QHBoxLayout(tiles_row)
        tiles_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(tiles_layout, theme, 12)
        for consent_filter, label, hint, token in TILES:
            tile = _ConsentTile(theme, label, hint, colors[token])
            tile.clicked.connect(
                lambda _=False, f=consent_filter: self._vm.toggle_consent_filter(f)
            )
            self._tiles[consent_filter] = tile
            tiles_layout.addWidget(tile, 1)

        self._segment_group = QButtonGroup(self)
        self._segment_group.setExclusive(True)
        self._segments: dict[ConsentFilter, QPushButton] = {}
        controls_row = QWidget()
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)
        for consent_filter, label, pos in _SEGMENTS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("role", "segment")
            btn.setProperty("segment_pos", pos)
            btn.clicked.connect(lambda _=False, f=consent_filter: self._vm.set_consent_filter(f))
            self._segment_group.addButton(btn)
            self._segments[consent_filter] = btn
            controls_layout.addWidget(btn)
        controls_layout.addStretch(1)
        controls_layout.addSpacing(theme.tokens.sp(16))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Name or SIS ID")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._vm.set_consent_search)
        controls_layout.addWidget(self._search, 1)

        self._table = QTableWidget(0, len(CONSENT_COLUMNS))
        self._table.setHorizontalHeaderLabels(CONSENT_COLUMNS)
        self._table.verticalHeader().hide()
        self._table.setShowGrid(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._copy_action = QAction("Copy", self._table)
        self._copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self._copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._copy_action.triggered.connect(self.copy_selection)
        self._table.addAction(self._copy_action)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_table_menu)
        self._table_menu: QMenu | None = None
        self._table.setWordWrap(False)
        self._table.setMinimumHeight(420)
        header = self._table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self._table.setSortingEnabled(True)

        self._no_matches = QLabel("No students match the filter or search.")
        self._no_matches.setProperty("role", "text_muted")

        self._footnote = QLabel(FOOTNOTE)
        self._footnote.setProperty("role", "text_muted")
        self._footnote.setWordWrap(True)

        self._review_widgets = (
            tiles_row,
            controls_row,
            self._table,
            self._no_matches,
            self._footnote,
        )
        for widget in (self._placeholder, self._error, *self._review_widgets):
            self.add_row(widget)

    @property
    def table(self) -> QTableWidget:
        return self._table

    @property
    def placeholder(self) -> QLabel:
        return self._placeholder

    @property
    def error_label(self) -> QLabel:
        return self._error

    @property
    def search(self) -> QLineEdit:
        return self._search

    def copied_text(self) -> str:
        """The selected cells as tab-separated rows, ready to paste into a spreadsheet.

        Rows and columns keep their table order; cells between selected ones
        that are not selected themselves come out empty.
        """
        indexes = self._table.selectedIndexes()
        if not indexes:
            return ""
        rows = sorted({index.row() for index in indexes})
        columns = sorted({index.column() for index in indexes})
        selected = {(index.row(), index.column()) for index in indexes}
        lines = []
        for row in rows:
            cells = []
            for column in columns:
                item = self._table.item(row, column)
                if (row, column) not in selected or item is None:
                    cells.append("")
                else:
                    cells.append(item.data(_COPY_ROLE) or item.text())
            lines.append("\t".join(cells))
        return "\n".join(lines)

    def copy_selection(self) -> None:
        text = self.copied_text()
        if text:
            QApplication.clipboard().setText(text)

    def _show_table_menu(self, pos: QPoint) -> None:
        # No parent: inside a card, the frames' transparency rule would reach the popup.
        menu = QMenu()
        menu.addAction(self._copy_action)
        self._copy_action.setEnabled(bool(self._table.selectedIndexes()))
        self._table_menu = menu
        menu.exec(self._table.viewport().mapToGlobal(pos))
        self._copy_action.setEnabled(True)

    def tile(self, consent_filter: ConsentFilter) -> _ConsentTile:
        return self._tiles[consent_filter]

    def segment(self, consent_filter: ConsentFilter) -> QPushButton:
        return self._segments[consent_filter]

    def render(self, state: SanitizeUiState) -> None:
        selected = state.selected_summary
        self.set_subtitle(
            f"{course_label(selected.key)}  ·  {term_label(selected.key)}" if selected else ""
        )

        if selected is None:
            placeholder = NO_COURSE_TEXT
        elif not state.consent_form_found:
            placeholder = NO_CONSENT_FORM_TEXT
        else:
            placeholder = ""
        self._placeholder.setText(placeholder)
        self._placeholder.setVisible(bool(placeholder))
        self._error.setText(state.consent_error or "")
        self._error.setVisible(bool(state.consent_error))

        reviewing = bool(selected and state.consent_form_found and not state.consent_error)
        for widget in self._review_widgets:
            widget.setVisible(reviewing)
        if not reviewing:
            return

        for consent_filter, tile in self._tiles.items():
            tile.set_count(state.consent_count(consent_filter))
            tile.setChecked(state.consent_filter is consent_filter)

        # A tile narrows Excluded, so Excluded stays lit while one is on.
        segment = (
            state.consent_filter
            if state.consent_filter in self._segments
            else ConsentFilter.EXCLUDED
        )
        for consent_filter, btn in self._segments.items():
            label = next(text for f, text, _ in _SEGMENTS if f is consent_filter)
            btn.setText(f"{label} ({state.consent_count(consent_filter)})")
            btn.setChecked(consent_filter is segment)

        if self._search.text() != state.consent_search:
            self._search.blockSignals(True)
            self._search.setText(state.consent_search)
            self._search.blockSignals(False)

        visible = state.visible_decisions
        if visible != self._shown_decisions:
            self._fill_table(visible)
            self._shown_decisions = visible
        self._no_matches.setVisible(not visible)

    def _fill_table(self, decisions: tuple[ConsentDecision, ...]) -> None:
        colors = self._theme.tokens.color
        muted = QBrush(QColor(colors["text_secondary"]))
        # Rows would move while being filled; sort once at the end by the header's column.
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(decisions))
        for row, decision in enumerate(decisions):
            cells = [_SortableItem(text) for text in row_cells(decision)]
            for cell, key in zip(cells, sort_keys(decision), strict=True):
                cell.setData(_SORT_ROLE, key)
            for column in (1, 2, 4):
                cells[column].setForeground(muted)

            typed = cells[3]
            if decision.status in NAME_PROBLEM_STATUSES and decision.name_response:
                typed.setForeground(QBrush(QColor(colors["status_caution"])))
            elif not decision.name_response:
                typed.setForeground(muted)
                if decision.name_response is not None:
                    font = QFont(typed.font())
                    font.setItalic(True)
                    typed.setFont(font)

            result = cells[5]
            result.setForeground(QBrush(QColor(colors[RESULT_TEXT[decision.status][1]])))
            # Copy the word, not the glyph in front of it.
            result.setData(_COPY_ROLE, result.text().split("  ", 1)[-1])

            for column, cell in enumerate(cells):
                self._table.setItem(row, column, cell)
        self._table.setSortingEnabled(True)
