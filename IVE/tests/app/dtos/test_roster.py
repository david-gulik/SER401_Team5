"""
Unit tests for the ClassSection session designator (SCRUM-214).
"""

from __future__ import annotations

import pytest

from GAVEL.app.dtos.roster import SESSION_PLACEHOLDER, ClassSection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_section(session: str = "A") -> ClassSection:
    return ClassSection(
        class_number="12345",
        subject="SER",
        catalog_number="401",
        title="Software Enterprise: Project and Process",
        instructor="Ruben Acuna",
        days_times="TTh 12:00PM-1:15PM",
        session=session,
    )


# ---------------------------------------------------------------------------
# session_display
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("session", ["A", "B", "C", "DYN"])
def test_session_display_returns_designator(session: str) -> None:
    assert make_section(session).session_display == session


def test_session_display_strips_surrounding_whitespace() -> None:
    assert make_section(" B ").session_display == "B"


@pytest.mark.parametrize("session", ["", "   "])
def test_session_display_falls_back_to_placeholder(session: str) -> None:
    assert make_section(session).session_display == SESSION_PLACEHOLDER


def test_session_defaults_to_placeholder_when_upstream_omits_it() -> None:
    section = ClassSection(
        class_number="12345",
        subject="SER",
        catalog_number="401",
        title="Software Enterprise: Project and Process",
        instructor="Ruben Acuna",
        days_times="TTh 12:00PM-1:15PM",
    )
    assert section.session == ""
    assert section.session_display == SESSION_PLACEHOLDER


# ---------------------------------------------------------------------------
# display_label
# ---------------------------------------------------------------------------


def test_display_label_includes_session_designator() -> None:
    assert "Session A" in make_section("A").display_label


def test_display_label_includes_placeholder_when_session_missing() -> None:
    assert f"Session {SESSION_PLACEHOLDER}" in make_section("").display_label


def test_display_label_keeps_existing_section_information() -> None:
    label = make_section("B").display_label
    assert "SER 401" in label
    assert "[12345]" in label
    assert "Ruben Acuna" in label
    assert "TTh 12:00PM-1:15PM" in label
