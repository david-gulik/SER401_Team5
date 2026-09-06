"""Picker half of the roster Section input: search by subject and catalog number."""

from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.input_mode_toggle import ComboPicker, PickerWidget
from GAVEL.ui_components.layout import set_spacing


class SectionSearchPicker(PickerWidget):
    """Subject + catalog number, a Find Sections action, then a results dropdown.

    Items are ``(class_number, label)`` pairs. ``load_requested`` fires on
    Find Sections; the caller runs the search and hands results back through
    ``set_items``. ``value()`` is the class number of the chosen section.
    """

    def __init__(self, theme: ThemeContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._subject = QLineEdit(self)
        self._subject.setPlaceholderText("e.g. SER")
        self._catalog = QLineEdit(self)
        self._catalog.setPlaceholderText("e.g. 401")

        self._results = ComboPicker(
            theme, load_text="Find Sections", empty_text="No sections found yet", parent=self
        )

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        set_spacing(grid, theme, 8)
        grid.addWidget(QLabel("Subject"), 0, 0)
        grid.addWidget(QLabel("Catalog #"), 0, 1)
        grid.addWidget(self._subject, 1, 0)
        grid.addWidget(self._catalog, 1, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        set_spacing(root, theme, 8)
        root.addLayout(grid)
        root.addWidget(self._results)

        self._results.value_changed.connect(self.value_changed)
        self._results.load_requested.connect(self.load_requested)

    # ---------- Controls exposed to the tab and to tests ----------

    @property
    def subject_field(self) -> QLineEdit:
        return self._subject

    @property
    def catalog_field(self) -> QLineEdit:
        return self._catalog

    @property
    def find_button(self) -> QPushButton:
        return self._results.load_button

    @property
    def combo(self) -> QComboBox:
        return self._results.combo

    # ---------- PickerWidget contract ----------

    def set_items(self, items: Sequence[tuple[str, str]], select: str = "") -> None:
        self._results.set_items(items, select=select)

    def value(self) -> str:
        return self._results.value()

    def display_value(self) -> str:
        return self._results.display_value()

    def set_busy(self, busy: bool) -> None:
        self._subject.setEnabled(not busy)
        self._catalog.setEnabled(not busy)
        self._results.set_busy(busy)
