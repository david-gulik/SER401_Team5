from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QSettings

from GAVEL.app_services import AppServices
from GAVEL.core.active_assignment import ActiveAssignment
from GAVEL.core.active_course import ActiveCourse
from GAVEL.services.config_service import ConfigService
from GAVEL.services.logger import AppLogger
from GAVEL.theme.context import ThemeContext


@dataclass(frozen=True)
class AppContext:
    theme: ThemeContext
    config: ConfigService
    logger: AppLogger
    services: AppServices
    active_course: ActiveCourse
    settings: QSettings
    # The assignment (and student) one Verification page hands to another.
    active_assignment: ActiveAssignment = field(default_factory=ActiveAssignment)
