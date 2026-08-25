from __future__ import annotations

from dataclasses import dataclass

# Shown wherever the catalog API omits a session designator for a section.
SESSION_PLACEHOLDER = "N/A"


@dataclass(frozen=True)
class ClassSection:
    """A single class section as returned by the ASU catalog API."""

    class_number: str
    subject: str
    catalog_number: str
    title: str
    instructor: str
    days_times: str
    session: str = ""
    campus: str = ""
    seats_open: int = 0
    component: str = ""

    @property
    def session_display(self) -> str:
        """Session designator (A, B, C, ...) or a placeholder when unavailable."""
        return self.session.strip() or SESSION_PLACEHOLDER

    @property
    def display_label(self) -> str:
        """Human-readable one-liner for selection menus."""
        return (
            f"{self.subject} {self.catalog_number} "
            f"[{self.class_number}] - {self.title} "
            f"(Session {self.session_display}, {self.instructor}, {self.days_times})"
        )


@dataclass(frozen=True)
class RosterRequest:
    """Parameters needed to fetch a single roster CSV."""

    term: str
    class_number: str


@dataclass(frozen=True)
class TermInfo:
    """An academic term from the ASU catalog API."""

    code: str
    name: str
    default: bool = False
