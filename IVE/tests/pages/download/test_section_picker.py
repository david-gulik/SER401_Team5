from __future__ import annotations

from GAVEL.app.dtos.roster import ClassSection
from GAVEL.pages.download.section_picker import SectionSearchPicker

SECTIONS = [
    ClassSection("12345", "SER", "401", "Capstone I", "Gary", "TTh 1:30"),
    ClassSection("12346", "SER", "401", "Capstone I", "Ruben", "MW 3:00"),
]
ITEMS = [(s.class_number, s.display_label) for s in SECTIONS]


def test_starts_empty_with_results_disabled(qapp, theme):
    picker = SectionSearchPicker(theme)
    assert picker.value() == ""
    assert picker.display_value() == ""
    assert not picker.combo.isEnabled()
    assert picker.subject_field.isEnabled()
    assert picker.find_button.isEnabled()


def test_find_button_emits_load_requested(qapp, theme):
    picker = SectionSearchPicker(theme)
    hits: list[bool] = []
    picker.load_requested.connect(lambda: hits.append(True))
    picker.find_button.click()
    assert hits == [True]


def test_set_items_selects_first_and_reports_class_number(qapp, theme):
    picker = SectionSearchPicker(theme)
    seen: list[str] = []
    picker.value_changed.connect(seen.append)
    picker.set_items(ITEMS)
    assert picker.value() == "12345"
    assert picker.display_value() == SECTIONS[0].display_label
    assert picker.combo.isEnabled()
    assert seen == ["12345"]


def test_set_items_honours_select(qapp, theme):
    picker = SectionSearchPicker(theme)
    picker.set_items(ITEMS, select="12346")
    assert picker.value() == "12346"


def test_busy_disables_search_controls_and_restores(qapp, theme):
    picker = SectionSearchPicker(theme)
    picker.set_items(ITEMS)
    picker.set_busy(True)
    assert not picker.subject_field.isEnabled()
    assert not picker.catalog_field.isEnabled()
    assert not picker.find_button.isEnabled()
    assert not picker.combo.isEnabled()
    picker.set_busy(False)
    assert picker.subject_field.isEnabled()
    assert picker.catalog_field.isEnabled()
    assert picker.find_button.isEnabled()
    assert picker.combo.isEnabled()
