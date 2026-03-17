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
    mfa_timeout: int = 120              # seconds to wait for CAS + Duo MFA
    session_ttl: int = 600              # seconds before cached session expires
    http_timeout: int = 30              # seconds for HTTP requests
    page_load_timeout: int = 30         # seconds to wait for initial page load
    token_exchange_timeout: int = 30    # seconds for SPA to exchange code for JWT


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
            mfa_timeout=int(source.get("ROSTER_MFA_TIMEOUT", "120")),
            session_ttl=int(source.get("ROSTER_SESSION_TTL", "600")),
            http_timeout=int(source.get("ROSTER_HTTP_TIMEOUT", "30")),
            page_load_timeout=int(source.get("ROSTER_PAGE_LOAD_TIMEOUT", "30")),
            token_exchange_timeout=int(source.get("ROSTER_TOKEN_EXCHANGE_TIMEOUT", "30")),
        )
        self._config = AppConfig(canvas=canvas_cfg, roster=roster_cfg)

    def get(self) -> AppConfig:
        return self._config
