from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QComboBox

from GAVEL.ui_components.input_mode_toggle import ComboPicker
from GAVEL.ui_components.no_wheel_combo_box import NoWheelComboBox

TERMS = [("2267", "2267  Fall 2026"), ("2271", "2271  Spring 2027")]


def wheel_down(combo: QComboBox) -> QWheelEvent:
    """One notch of scroll-wheel-down over the combo's centre."""
    pos = QPointF(combo.rect().center())
    event = QWheelEvent(
        pos,
        combo.mapToGlobal(pos.toPoint()).toPointF(),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(combo, event)
    return event


def test_plain_combo_changes_selection_on_wheel(qapp):
    """Sanity check: the stock widget really does step on wheel, so the test means something."""
    combo = QComboBox()
    for value, label in TERMS:
        combo.addItem(label, value)
    combo.setCurrentIndex(0)
    wheel_down(combo)
    assert combo.currentIndex() == 1


def test_no_wheel_combo_keeps_selection_and_ignores_event(qapp):
    combo = NoWheelComboBox()
    for value, label in TERMS:
        combo.addItem(label, value)
    combo.setCurrentIndex(0)
    event = wheel_down(combo)
    assert combo.currentIndex() == 0
    assert not event.isAccepted()


def test_no_wheel_combo_does_not_take_wheel_focus(qapp):
    combo = NoWheelComboBox()
    assert combo.focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_combo_picker_uses_no_wheel_combo(qapp, theme):
    picker = ComboPicker(theme, load_text="Load")
    picker.set_items(TERMS)
    assert isinstance(picker.combo, NoWheelComboBox)
    wheel_down(picker.combo)
    assert picker.value() == "2267"
