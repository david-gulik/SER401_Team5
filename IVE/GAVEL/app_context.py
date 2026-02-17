from __future__ import annotations

from dataclasses import dataclass

from GAVEL.app_services import AppServices
from GAVEL.services.config_service import ConfigService
from GAVEL.services.logger import AppLogger
from GAVEL.theme.context import ThemeContext


@dataclass(frozen=True)
class AppContext:
    theme: ThemeContext
    config: ConfigService
    logger: AppLogger
    services: AppServices
