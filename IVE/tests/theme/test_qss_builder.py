from __future__ import annotations

import pytest

from GAVEL.theme.qss_builder import build_app_qss


@pytest.fixture(scope="module")
def qss(theme) -> str:
    return build_app_qss(theme.tokens)


def test_qss_builds_without_unfilled_placeholders(qss: str):
    assert "{{" not in qss
    assert "}}" not in qss


def test_input_mode_toggle_roles_are_styled(qss: str):
    assert 'QPushButton[role="segment"]' in qss
    assert 'QPushButton[role="segment"]:checked' in qss
    assert 'QPushButton[role="segment"][segment_pos="first"]' in qss
    assert 'QLabel[role="error_text"]' in qss
    assert 'QLabel[role="readout_key"]' in qss
    assert 'QLabel[role="readout_value"]' in qss


def test_segment_rules_outrank_surface_button_overrides(qss: str):
    surface_rule = 'QFrame[role="surface"] QPushButton,'
    segment_rule = 'QFrame[role="surface"] QPushButton[role="segment"]'
    assert surface_rule in qss
    assert segment_rule in qss
    assert qss.index(segment_rule) > qss.index(surface_rule)
