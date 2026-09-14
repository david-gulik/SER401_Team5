"""Picker-or-manual input component.

An ``InputModeToggle`` presents one value that can be filled either by a
picker (a dropdown fed from a remote list) or by typing it directly. Only
one of the two panels is shown at a time, selected by a segmented toggle,
so the two inputs can never disagree. The component exposes a single
resolved value and a single ``value_changed`` signal, which lets view
models drop their per-input "typed text or selected item" fallback logic.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_margins, set_spacing
from GAVEL.ui_components.no_wheel_combo_box import NoWheelComboBox

# Returns an error message for the given (stripped, non-empty) text, or None when valid.
Validator = Callable[[str], str | None]


class InputMode(Enum):
    PICKER = "picker"
    MANUAL = "manual"


def _repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property change."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def _set_role(widget: QWidget, role: str) -> None:
    if widget.property("role") != role:
        widget.setProperty("role", role)
        _repolish(widget)


# ---------------------------------------------------------------------------
# Picker slot
# ---------------------------------------------------------------------------


class PickerWidget(QWidget):
    """Base class for the picker half of an ``InputModeToggle``.

    Subclasses own whatever controls they need (a combo box, a search form)
    and must emit ``value_changed`` whenever ``value()`` would change.
    ``load_requested`` is the hook for the caller's load / reload / find action.
    """

    value_changed = pyqtSignal(str)
    load_requested = pyqtSignal()

    def value(self) -> str:
        """Machine value of the current selection, or "" when nothing is selected."""
        raise NotImplementedError

    def display_value(self) -> str:
        """Human label for the readout line. Defaults to ``value()``."""
        return self.value()

    def set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)


class ComboPicker(PickerWidget):
    """Default picker: a combo box with a load button beside it.

    Items are ``(value, label)`` pairs. The combo is disabled with a
    placeholder until ``set_items`` is called with a non-empty list.
    """

    def __init__(
        self,
        theme: ThemeContext,
        *,
        load_text: str,
        empty_text: str = "Nothing loaded yet",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._combo = NoWheelComboBox(self)
        self._combo.setPlaceholderText(empty_text)
        self._combo.setEnabled(False)

        self._load_btn = QPushButton(load_text, self)
        self._load_btn.setProperty("role", "secondary")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        set_spacing(row, theme, 8)
        row.addWidget(self._combo, 1)
        row.addWidget(self._load_btn)

        self._combo.currentIndexChanged.connect(self._on_index_changed)
        self._load_btn.clicked.connect(self._on_load_clicked)

    @property
    def combo(self) -> QComboBox:
        return self._combo

    @property
    def load_button(self) -> QPushButton:
        return self._load_btn

    def set_items(self, items: Sequence[tuple[str, str]], select: str = "") -> None:
        """Replace the list. Selects ``select`` if present, else the first item."""
        self._combo.blockSignals(True)
        try:
            self._combo.clear()
            for value, label in items:
                self._combo.addItem(label, value)
            self._combo.setEnabled(bool(items))
            index = -1
            if items:
                index = 0
                if select:
                    found = self._combo.findData(select)
                    if found >= 0:
                        index = found
            self._combo.setCurrentIndex(index)
        finally:
            self._combo.blockSignals(False)
        self.value_changed.emit(self.value())

    def value(self) -> str:
        data = self._combo.currentData()
        return "" if data is None else str(data)

    def display_value(self) -> str:
        if self._combo.currentIndex() < 0:
            return ""
        return self._combo.currentText()

    def set_busy(self, busy: bool) -> None:
        self._load_btn.setEnabled(not busy)
        self._combo.setEnabled(not busy and self._combo.count() > 0)

    def _on_index_changed(self, _index: int) -> None:
        self.value_changed.emit(self.value())

    def _on_load_clicked(self, _checked: bool = False) -> None:
        self.load_requested.emit()


class CheckListPicker(PickerWidget):
    """Multi-select picker: one check box per item, with load / all / none buttons.

    Items are ``(value, label)`` pairs. ``value()`` is the checked values
    joined by ``SEPARATOR`` in list order, so the toggle still sees a single
    string; callers split it. Nothing is checked until the user asks, so a
    freshly loaded list resolves to "".
    """

    SEPARATOR = ","
    VISIBLE_ROWS = 6

    def __init__(
        self,
        theme: ThemeContext,
        *,
        load_text: str,
        empty_text: str = "Nothing loaded yet",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._boxes: list[QCheckBox] = []
        self._busy = False

        self._empty_label = QLabel(empty_text, self)
        self._empty_label.setProperty("role", "text_muted")

        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(self._list_layout, theme, 4)
        self._list_layout.addStretch(1)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setWidget(self._list_host)
        self._scroll.hide()

        self._load_btn = QPushButton(load_text, self)
        self._load_btn.setProperty("role", "secondary")
        self._all_btn = QPushButton("Select All", self)
        self._all_btn.setProperty("role", "secondary")
        self._none_btn = QPushButton("Clear", self)
        self._none_btn.setProperty("role", "secondary")

        buttons = QVBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        set_spacing(buttons, theme, 8)
        buttons.addWidget(self._load_btn)
        buttons.addWidget(self._all_btn)
        buttons.addWidget(self._none_btn)
        buttons.addStretch(1)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(self._empty_label)
        left.addWidget(self._scroll)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        set_spacing(row, theme, 8)
        row.addLayout(left, 1)
        row.addLayout(buttons)

        self._load_btn.clicked.connect(self._on_load_clicked)
        self._all_btn.clicked.connect(lambda: self._set_all(True))
        self._none_btn.clicked.connect(lambda: self._set_all(False))
        self._sync_controls()

    @property
    def load_button(self) -> QPushButton:
        return self._load_btn

    @property
    def select_all_button(self) -> QPushButton:
        return self._all_btn

    @property
    def clear_button(self) -> QPushButton:
        return self._none_btn

    def boxes(self) -> list[QCheckBox]:
        """The check boxes in list order. Exposed for tests."""
        return list(self._boxes)

    def count(self) -> int:
        return len(self._boxes)

    def set_items(self, items: Sequence[tuple[str, str]], select: str = "") -> None:
        """Replace the list. Checks every value named in ``select`` (SEPARATOR-joined)."""
        wanted = {v.strip() for v in select.split(self.SEPARATOR) if v.strip()}
        for box in self._boxes:
            self._list_layout.removeWidget(box)
            box.deleteLater()
        self._boxes = []
        for value, label in items:
            box = QCheckBox(label, self._list_host)
            box.setProperty("value", value)
            box.setChecked(value in wanted)
            box.toggled.connect(self._on_toggled)
            self._list_layout.insertWidget(self._list_layout.count() - 1, box)
            self._boxes.append(box)
        self._scroll.setVisible(bool(items))
        self._empty_label.setVisible(not items)
        self._fit_height()
        self._sync_controls()
        self.value_changed.emit(self.value())

    def values(self) -> list[str]:
        return [str(b.property("value")) for b in self._boxes if b.isChecked()]

    def value(self) -> str:
        return self.SEPARATOR.join(self.values())

    def display_value(self) -> str:
        return ", ".join(b.text() for b in self._boxes if b.isChecked())

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._sync_controls()

    def _set_all(self, checked: bool) -> None:
        # One value_changed for the whole sweep, not one per box.
        for box in self._boxes:
            box.blockSignals(True)
            try:
                box.setChecked(checked)
            finally:
                box.blockSignals(False)
        self.value_changed.emit(self.value())

    def _fit_height(self) -> None:
        if not self._boxes:
            return
        row = self._boxes[0].sizeHint().height() + self._list_layout.spacing()
        self._scroll.setMaximumHeight(row * self.VISIBLE_ROWS)

    def _sync_controls(self) -> None:
        has_items = bool(self._boxes)
        self._load_btn.setEnabled(not self._busy)
        self._all_btn.setEnabled(not self._busy and has_items)
        self._none_btn.setEnabled(not self._busy and has_items)
        self._list_host.setEnabled(not self._busy)

    def _on_toggled(self, _checked: bool) -> None:
        self.value_changed.emit(self.value())

    def _on_load_clicked(self, _checked: bool = False) -> None:
        self.load_requested.emit()


# ---------------------------------------------------------------------------
# The toggle
# ---------------------------------------------------------------------------


class InputModeToggle(QFrame):
    """One input, two ways to fill it, only one alive at a time.

    Signals:
        value_changed(str): the resolved value changed. Emitted on picker
            selection, manual edit, or mode switch. "" means nothing usable.
        mode_changed(InputMode): the active mode changed. Emitted after the
            value_changed for that switch, so handlers can rely on value()
            and on whatever a value_changed handler already applied.
    """

    value_changed = pyqtSignal(str)
    mode_changed = pyqtSignal(InputMode)

    EMPTY_PICKER_TEXT = "nothing selected yet"
    EMPTY_MANUAL_TEXT = "nothing entered yet"
    INVALID_TEXT = "invalid entry"

    def __init__(
        self,
        theme: ThemeContext,
        title: str,
        *,
        picker: PickerWidget,
        manual_field_label: str,
        picker_label: str = "Choose from list",
        manual_label: str = "Enter manually",
        picker_hint: str = "",
        manual_hint: str = "",
        manual_placeholder: str = "",
        validator: Validator | None = None,
        default_mode: InputMode = InputMode.PICKER,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._picker = picker
        self._picker_hint = picker_hint
        self._manual_hint = manual_hint
        self._validator = validator
        self._picker_available = True
        self._busy = False
        self._focus_return: QWidget | None = None
        self._mode = default_mode
        self._last_value: str | None = None

        self.setProperty("role", "surface")
        root = QVBoxLayout(self)
        set_margins(root, theme, 12)
        set_spacing(root, theme, 8)
        self._root = root

        # 1. Title
        self._title = QLabel(title, self)
        self._title.setProperty("role", "h3")
        root.addWidget(self._title)

        # 2. Mode control
        self._picker_btn = QPushButton(picker_label, self)
        self._manual_btn = QPushButton(manual_label, self)
        for btn, pos in ((self._picker_btn, "first"), (self._manual_btn, "last")):
            btn.setCheckable(True)
            btn.setProperty("role", "segment")
            btn.setProperty("segment_pos", pos)
        self._segments = QButtonGroup(self)
        self._segments.setExclusive(True)
        self._segments.addButton(self._picker_btn)
        self._segments.addButton(self._manual_btn)

        seg_row = QHBoxLayout()
        seg_row.setContentsMargins(0, 0, 0, 0)
        seg_row.setSpacing(0)
        seg_row.addWidget(self._picker_btn)
        seg_row.addWidget(self._manual_btn)
        seg_row.addStretch(1)
        root.addLayout(seg_row)

        # Warning shown when the picker's data source is unavailable.
        self._unavailable_label = QLabel("", self)
        self._unavailable_label.setProperty("role", "warning")
        self._unavailable_label.setWordWrap(True)
        self._unavailable_label.hide()
        root.addWidget(self._unavailable_label)

        # 3. Active panel
        self._manual_field = QLineEdit()
        self._manual_field.setPlaceholderText(manual_placeholder)
        manual_page = QWidget(self)
        manual_form = QFormLayout(manual_page)
        manual_form.setContentsMargins(0, 0, 0, 0)
        set_spacing(manual_form, theme, 8)
        manual_form.addRow(manual_field_label, self._manual_field)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._picker)
        self._stack.addWidget(manual_page)
        root.addWidget(self._stack)

        # 4. Hint / error line
        self._hint_label = QLabel("", self)
        self._hint_label.setProperty("role", "text_muted")
        self._hint_label.setWordWrap(True)
        root.addWidget(self._hint_label)
        self._error_label = QLabel("", self)
        self._error_label.setProperty("role", "error_text")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root.addWidget(self._error_label)

        # 5. Readout
        self._readout_dot = QLabel("●", self)
        self._readout_dot.setProperty("role", "status_dot")
        self._readout_key = QLabel("WILL USE", self)
        self._readout_key.setProperty("role", "readout_key")
        self._readout_value = QLabel("", self)
        self._readout_value.setProperty("role", "text_muted")
        self._readout_value.setWordWrap(True)
        readout_row = QHBoxLayout()
        readout_row.setContentsMargins(0, 0, 0, 0)
        set_spacing(readout_row, theme, 8)
        readout_row.addWidget(self._readout_dot)
        readout_row.addWidget(self._readout_key)
        readout_row.addWidget(self._readout_value, 1)
        root.addLayout(readout_row)

        # Wiring
        self._picker.value_changed.connect(self._refresh)
        self._manual_field.textChanged.connect(self._refresh)
        self._picker_btn.toggled.connect(self._on_picker_toggled)
        self._manual_btn.toggled.connect(self._on_manual_toggled)

        self._apply_mode(default_mode, emit=False)
        self._refresh()

    # ---------- Public API ----------

    def mode(self) -> InputMode:
        return self._mode

    def set_mode(self, mode: InputMode) -> None:
        if mode is InputMode.PICKER and not self._picker_available:
            return
        button = self._picker_btn if mode is InputMode.PICKER else self._manual_btn
        button.setChecked(True)  # drives _apply_mode through the toggled signal

    def set_picker_available(self, available: bool, reason: str = "") -> None:
        """Disable the picker side (and force manual mode) when its source is missing."""
        self._picker_available = available
        self._picker_btn.setEnabled(available and not self._busy)
        self._unavailable_label.setText("" if available else reason)
        self._unavailable_label.setVisible(not available and bool(reason))
        if not available:
            self.set_mode(InputMode.MANUAL)

    def set_busy(self, busy: bool) -> None:
        if busy:
            self._park_focus()
        self._busy = busy
        self._picker_btn.setEnabled(not busy and self._picker_available)
        self._manual_btn.setEnabled(not busy)
        self._picker.set_busy(busy)
        self._manual_field.setEnabled(not busy)
        if not busy:
            self._restore_focus()

    def _park_focus(self) -> None:
        """Take focus off a child before disabling it.

        Disabling the focused widget makes Qt hand focus to the next enabled
        widget anywhere in the window, and an enclosing scroll area then
        scrolls to keep that widget visible. Clearing focus first keeps the
        page where it is; ``_restore_focus`` hands it back once busy ends.
        """
        focused = QApplication.focusWidget()
        if focused is not None and self.isAncestorOf(focused):
            self._focus_return = focused
            focused.clearFocus()

    def _restore_focus(self) -> None:
        widget, self._focus_return = self._focus_return, None
        if widget is not None and widget.isEnabled() and widget.isVisibleTo(self):
            widget.setFocus(Qt.FocusReason.OtherFocusReason)

    def value(self) -> str:
        """Resolved value from the active mode only. "" when empty or invalid."""
        if self._mode is InputMode.PICKER:
            return self._picker.value()
        text = self._manual_text()
        if not text or self._manual_error(text) is not None:
            return ""
        return text

    def display_value(self) -> str:
        if self._mode is InputMode.PICKER:
            return self._picker.display_value()
        return self.value()

    def is_valid(self) -> bool:
        if self._mode is InputMode.PICKER:
            return True
        return self._manual_error(self._manual_text()) is None

    def readout_text(self) -> str:
        """What the readout line currently shows (for tests and logging)."""
        return self._readout_value.text()

    def add_footer(self, widget: QWidget) -> None:
        """Place a widget below the readout, inside the panel.

        Meant for the action that consumes the value, such as a download
        button, so a panel reads as "choose this, then do that".
        """
        self._root.addWidget(widget)

    def picker(self) -> PickerWidget:
        return self._picker

    def manual_field(self) -> QLineEdit:
        return self._manual_field

    # ---------- Internals ----------

    def _manual_text(self) -> str:
        return self._manual_field.text().strip()

    def _manual_error(self, text: str) -> str | None:
        if not text or self._validator is None:
            return None
        return self._validator(text)

    def _on_picker_toggled(self, checked: bool) -> None:
        if checked:
            self._apply_mode(InputMode.PICKER)

    def _on_manual_toggled(self, checked: bool) -> None:
        if checked:
            self._apply_mode(InputMode.MANUAL)

    def _apply_mode(self, mode: InputMode, emit: bool = True) -> None:
        changed = mode is not self._mode
        self._mode = mode
        button = self._picker_btn if mode is InputMode.PICKER else self._manual_btn
        if not button.isChecked():
            button.blockSignals(True)
            try:
                button.setChecked(True)
            finally:
                button.blockSignals(False)
        self._stack.setCurrentIndex(0 if mode is InputMode.PICKER else 1)
        self._fit_stack()
        if emit:
            self._refresh()
        if changed and emit:
            self.mode_changed.emit(mode)

    def _fit_stack(self) -> None:
        """Size the stack to the active page only.

        A QStackedWidget otherwise reserves the tallest page's height, so a
        short manual field would sit above a blank gap the size of a tall
        picker. Hidden pages get an Ignored policy, which the stacked layout
        leaves out of its size hint.
        """
        current = self._stack.currentIndex()
        for index in range(self._stack.count()):
            policy = (
                QSizePolicy.Policy.Preferred if index == current else QSizePolicy.Policy.Ignored
            )
            self._stack.widget(index).setSizePolicy(policy, policy)
        self._stack.adjustSize()

    def _refresh(self, *_args: object) -> None:
        value = self.value()
        self._render_hint()
        self._render_readout(value)
        if value != self._last_value:
            self._last_value = value
            self.value_changed.emit(value)

    def _render_hint(self) -> None:
        error = None
        if self._mode is InputMode.MANUAL:
            error = self._manual_error(self._manual_text())
            hint = self._manual_hint
        else:
            hint = self._picker_hint
        if error:
            self._error_label.setText(error)
            self._error_label.show()
            self._hint_label.hide()
        else:
            self._error_label.hide()
            self._hint_label.setText(hint)
            self._hint_label.setVisible(bool(hint))

    def _render_readout(self, value: str) -> None:
        colors = self._theme.tokens.color
        if value:
            text = self.display_value() or value
            color, role = colors["status_nominal"], "readout_value"
        elif self._mode is InputMode.MANUAL and not self.is_valid():
            text, color, role = self.INVALID_TEXT, colors["status_critical"], "text_muted"
        elif self._mode is InputMode.MANUAL:
            text, color, role = self.EMPTY_MANUAL_TEXT, colors["status_unknown"], "text_muted"
        else:
            text, color, role = self.EMPTY_PICKER_TEXT, colors["status_unknown"], "text_muted"
        self._readout_value.setText(text)
        self._readout_dot.setStyleSheet(f"color: {color};")
        _set_role(self._readout_value, role)
