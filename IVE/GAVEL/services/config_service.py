from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class CanvasConfig:
    base_url: Optional[str] = None
    token: Optional[str] = None


@dataclass(frozen=True)
class RosterConfig:
    auth_method: Optional[str] = None   # "selenium" or "cookies"
    cookie_file: Optional[str] = None   # path for cookie-based auth
    token: Optional[str] = None         # pre-existing catalog API token


@dataclass(frozen=True)
class AppConfig:
    environment: str = "DEV"
    version: str = "0.1.0"
    canvas: CanvasConfig = field(default_factory=CanvasConfig)
    roster: RosterConfig = field(default_factory=RosterConfig)


class ConfigService:
    def __init__(self, env: Optional[Mapping[str, str]] = None) -> None:
        if env is None:
            _project_root = Path(__file__).resolve().parents[2]
            load_dotenv(_project_root / ".env")
        source = env or os.environ
        canvas_cfg = CanvasConfig(
            base_url=source.get("CANVAS_BASE_URL"),
            token=source.get("CANVAS_TOKEN"),
        )
        roster_cfg = RosterConfig(
            auth_method=source.get("ROSTER_AUTH_METHOD"),
            cookie_file=source.get("ROSTER_COOKIE_FILE"),
            token=source.get("ROSTER_TOKEN"),
        )
        self._config = AppConfig(canvas=canvas_cfg, roster=roster_cfg)

    def get(self) -> AppConfig:
        return self._config
