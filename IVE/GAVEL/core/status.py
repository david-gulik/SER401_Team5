from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from GAVEL.theme.context import ThemeContext


class Status(Enum):
    NOMINAL = "nominal"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StatusStyle:
    label: str
    icon: str
    color: str  # hex color from tokens


def get_status_style(theme: ThemeContext, status: Status) -> StatusStyle:
    c = theme.tokens.color
    if status == Status.NOMINAL:
        return StatusStyle(label="Nominal", icon="●", color=c["status_nominal"])
    if status == Status.CAUTION:
        return StatusStyle(label="Caution", icon="●", color=c["status_caution"])
    if status == Status.WARNING:
        return StatusStyle(label="Warning", icon="●", color=c["status_warning"])
    if status == Status.CRITICAL:
        return StatusStyle(label="Critical", icon="●", color=c["status_critical"])
    return StatusStyle(label="Unknown", icon="●", color=c["status_unknown"])
