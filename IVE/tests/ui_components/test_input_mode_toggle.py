from __future__ import annotations

import pytest

from GAVEL.ui_components.input_mode_toggle import ComboPicker, InputMode, InputModeToggle

TERMS = [("2267", "2267  Fall 2026"), ("2271", "2271  Spring 2027")]


def four_digit_code(text: str) -> str | None:
    if len(text) == 4 and text.isdigit():
        return None
    return "Term codes are four digits, like 2267."


@pytest.fixture
def toggle(qapp, theme) -> InputModeToggle:
    picker = ComboPicker(theme, load_text="Load Terms", empty_text="No terms loaded")
    return InputModeToggle(
        theme,
        "Term",
        picker=picker,
        manual_field_label="Term code",
        picker_label="Choose from list",
        manual_label="Enter code",
        picker_hint="Terms load from myASU.",
        manual_hint="Format 2[YY][T].",
        validator=four_digit_code,
    )


@pytest.fixture
def loaded(toggle: InputModeToggle) -> InputModeToggle:
    toggle.picker().set_items(TERMS)
    return toggle


def record(signal) -> list:
    seen: list = []
    signal.connect(seen.append)
    return seen


def test_combo_picker_starts_empty_and_disabled(qapp, theme):
    picker = ComboPicker(theme, load_text="Load")
    assert picker.value() == ""
    assert picker.display_value() == ""
    assert not picker.combo.isEnabled()


def test_combo_picker_set_items_selects_first_by_default(qapp, theme):
    picker = ComboPicker(theme, load_text="Load")
    seen = record(picker.value_changed)
    picker.set_items(TERMS)
    assert picker.value() == "2267"
    assert picker.display_value() == "2267  Fall 2026"
    assert picker.combo.isEnabled()
    assert seen == ["2267"]


def test_combo_picker_set_items_honours_select(qapp, theme):
    picker = ComboPicker(theme, load_text="Load")
    picker.set_items(TERMS, select="2271")
    assert picker.value() == "2271"


def test_combo_picker_set_items_falls_back_when_select_missing(qapp, theme):
    picker = ComboPicker(theme, load_text="Load")
    picker.set_items(TERMS, select="9999")
    assert picker.value() == "2267"


def test_combo_picker_clearing_items_resets_value(qapp, theme):
    picker = ComboPicker(theme, load_text="Load")
    picker.set_items(TERMS)
    seen = record(picker.value_changed)
    picker.set_items([])
    assert picker.value() == ""
    assert not picker.combo.isEnabled()
    assert seen == [""]


def test_combo_picker_load_button_emits_load_requested(qapp, theme):
    picker = ComboPicker(theme, load_text="Load")
    hits: list[bool] = []
    picker.load_requested.connect(lambda: hits.append(True))
    picker.load_button.click()
    assert hits == [True]


def test_combo_picker_busy_disables_controls_and_restores(qapp, theme):
    picker = ComboPicker(theme, load_text="Load")
    picker.set_items(TERMS)
    picker.set_busy(True)
    assert not picker.load_button.isEnabled()
    assert not picker.combo.isEnabled()
    picker.set_busy(False)
    assert picker.load_button.isEnabled()
    assert picker.combo.isEnabled()


def test_defaults_to_picker_mode_with_empty_value(toggle: InputModeToggle):
    assert toggle.mode() is InputMode.PICKER
    assert toggle.value() == ""
    assert toggle.is_valid()
    assert toggle.readout_text() == InputModeToggle.EMPTY_PICKER_TEXT


def test_picker_mode_resolves_picker_and_ignores_manual_text(loaded: InputModeToggle):
    loaded.manual_field().setText("2251")
    assert loaded.mode() is InputMode.PICKER
    assert loaded.value() == "2267"
    assert loaded.display_value() == "2267  Fall 2026"


def test_manual_mode_resolves_text_and_ignores_picker(loaded: InputModeToggle):
    loaded.set_mode(InputMode.MANUAL)
    loaded.manual_field().setText("2251")
    assert loaded.value() == "2251"
    assert loaded.display_value() == "2251"
    assert loaded.picker().value() == "2267"  # still selected, just not used


def test_manual_text_is_stripped(toggle: InputModeToggle):
    toggle.set_mode(InputMode.MANUAL)
    toggle.manual_field().setText("  2251 ")
    assert toggle.value() == "2251"


def test_invalid_manual_text_resolves_empty(toggle: InputModeToggle):
    toggle.set_mode(InputMode.MANUAL)
    toggle.manual_field().setText("22F")
    assert toggle.value() == ""
    assert not toggle.is_valid()
    assert toggle.readout_text() == InputModeToggle.INVALID_TEXT


def test_empty_manual_text_is_not_an_error(toggle: InputModeToggle):
    toggle.set_mode(InputMode.MANUAL)
    assert toggle.value() == ""
    assert toggle.is_valid()
    assert toggle.readout_text() == InputModeToggle.EMPTY_MANUAL_TEXT


def test_no_validator_accepts_any_text(qapp, theme):
    widget = InputModeToggle(
        theme,
        "Course",
        picker=ComboPicker(theme, load_text="Reload"),
        manual_field_label="Course ID",
        default_mode=InputMode.MANUAL,
    )
    widget.manual_field().setText("abc-123")
    assert widget.value() == "abc-123"
    assert widget.is_valid()


def test_picker_selection_emits_value_changed(loaded: InputModeToggle):
    seen = record(loaded.value_changed)
    loaded.picker().combo.setCurrentIndex(1)
    assert seen == ["2271"]


def test_manual_edit_emits_value_changed_only_when_valid_value_changes(
    toggle: InputModeToggle,
):
    toggle.set_mode(InputMode.MANUAL)
    seen = record(toggle.value_changed)
    toggle.manual_field().setText("2")  # invalid -> resolved stays ""
    toggle.manual_field().setText("22")  # still invalid
    toggle.manual_field().setText("2267")  # valid
    assert seen == ["2267"]


def test_switching_mode_emits_value_changed_once_with_new_value(loaded: InputModeToggle):
    loaded.manual_field().setText("2251")
    seen = record(loaded.value_changed)
    modes = record(loaded.mode_changed)
    loaded.set_mode(InputMode.MANUAL)
    assert seen == ["2251"]
    assert modes == [InputMode.MANUAL]


def test_switching_to_same_mode_is_a_no_op(loaded: InputModeToggle):
    seen = record(loaded.value_changed)
    modes = record(loaded.mode_changed)
    loaded.set_mode(InputMode.PICKER)
    assert seen == []
    assert modes == []


def test_hidden_panel_does_not_emit(loaded: InputModeToggle):
    seen = record(loaded.value_changed)
    loaded.manual_field().setText("2251")  # hidden while in picker mode
    assert seen == []


# ---------- Panels ----------


def test_only_active_panel_is_visible(loaded: InputModeToggle):
    assert loaded.picker().isVisibleTo(loaded)
    assert not loaded.manual_field().isVisibleTo(loaded)
    loaded.set_mode(InputMode.MANUAL)
    assert not loaded.picker().isVisibleTo(loaded)
    assert loaded.manual_field().isVisibleTo(loaded)


def test_switching_away_and_back_restores_hidden_input(loaded: InputModeToggle):
    loaded.picker().combo.setCurrentIndex(1)
    loaded.set_mode(InputMode.MANUAL)
    loaded.manual_field().setText("2251")
    loaded.set_mode(InputMode.PICKER)
    assert loaded.value() == "2271"
    assert loaded.manual_field().text() == "2251"
    loaded.set_mode(InputMode.MANUAL)
    assert loaded.value() == "2251"
    assert loaded.picker().value() == "2271"


# ---------- Availability and busy ----------


def test_picker_unavailable_forces_manual_and_blocks_picker(loaded: InputModeToggle):
    seen = record(loaded.value_changed)
    loaded.set_picker_available(False, "Course list needs CANVAS_TOKEN.")
    assert loaded.mode() is InputMode.MANUAL
    assert loaded.value() == ""
    assert seen == [""]
    loaded.set_mode(InputMode.PICKER)  # ignored while unavailable
    assert loaded.mode() is InputMode.MANUAL


def test_picker_available_again_allows_switching_back(loaded: InputModeToggle):
    loaded.set_picker_available(False, "no token")
    loaded.set_picker_available(True)
    assert loaded.mode() is InputMode.MANUAL  # does not switch back on its own
    loaded.set_mode(InputMode.PICKER)
    assert loaded.mode() is InputMode.PICKER
    assert loaded.value() == "2267"


def test_busy_disables_inputs_but_keeps_value(loaded: InputModeToggle):
    loaded.set_busy(True)
    assert not loaded.manual_field().isEnabled()
    assert not loaded.picker().combo.isEnabled()
    assert loaded.value() == "2267"
    loaded.set_busy(False)
    assert loaded.manual_field().isEnabled()
    assert loaded.picker().combo.isEnabled()


def test_mode_changed_is_emitted_after_value_changed(loaded: InputModeToggle):
    order: list[str] = []
    loaded.value_changed.connect(lambda v: order.append(f"value:{v}"))
    loaded.mode_changed.connect(lambda m: order.append(f"mode:{m.name}"))
    loaded.manual_field().setText("2251")
    loaded.set_mode(InputMode.MANUAL)
    assert order == ["value:2251", "mode:MANUAL"]


def test_busy_does_not_reenable_unavailable_picker(loaded: InputModeToggle):
    loaded.set_picker_available(False, "no token")
    loaded.set_busy(True)
    loaded.set_busy(False)
    loaded.set_mode(InputMode.PICKER)
    assert loaded.mode() is InputMode.MANUAL
