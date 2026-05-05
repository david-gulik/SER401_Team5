from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from GAVEL.services.env_service import SCHEMA_NAMES


@dataclass(frozen=True)
class CanvasConfig:
    base_url: str | None = None
    token: str | None = None
    account_id: int | None = None


@dataclass(frozen=True)
class RosterConfig:
    auth_method: str | None = None  # "selenium" or "cookies"
    cookie_file: str | None = None  # path for cookie-based auth
    token: str | None = None  # pre-existing catalog API token
    mfa_timeout: int = 120  # seconds to wait for CAS + Duo MFA
    session_ttl: int = 600  # seconds before cached session expires
    http_timeout: int = 30  # seconds for HTTP requests
    page_load_timeout: int = 30  # seconds to wait for initial page load
    token_exchange_timeout: int = 30  # seconds for SPA to exchange code for JWT


@dataclass(frozen=True)
class AppConfig:
    environment: str = "DEV"
    version: str = "0.1.0"
    canvas: CanvasConfig = field(default_factory=CanvasConfig)
    roster: RosterConfig = field(default_factory=RosterConfig)


class ConfigService:
    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env_path = Path(__file__).resolve().parents[2] / ".env"
        self._env_override = env
        if env is None:
            load_dotenv(self._env_path)
        self._config = self._build()

    @property
    def env_path(self) -> Path:
        return self._env_path

    def get(self) -> AppConfig:
        return self._config

    def reload(self) -> None:
        """Re-read .env from disk and rebuild the AppConfig snapshot."""
        if self._env_override is None:
            load_dotenv(self._env_path, override=True)
        self._config = self._build()

    def _build(self) -> AppConfig:
        source = self._resolve_source()
        canvas_cfg = CanvasConfig(
            base_url=source.get("CANVAS_BASE_URL") or "https://canvas.asu.edu",
            token=source.get("CANVAS_TOKEN"),
            account_id=int(source.get("CANVAS_ACCOUNT_ID"))
            if source.get("CANVAS_ACCOUNT_ID")
            else None,
        )
        roster_cfg = RosterConfig(
            auth_method=source.get("ROSTER_AUTH_METHOD", "selenium"),
            cookie_file=source.get("ROSTER_COOKIE_FILE"),
            token=source.get("ROSTER_TOKEN"),
            mfa_timeout=int(source.get("ROSTER_MFA_TIMEOUT", "120")),
            session_ttl=int(source.get("ROSTER_SESSION_TTL", "600")),
            http_timeout=int(source.get("ROSTER_HTTP_TIMEOUT", "30")),
            page_load_timeout=int(source.get("ROSTER_PAGE_LOAD_TIMEOUT", "30")),
            token_exchange_timeout=int(source.get("ROSTER_TOKEN_EXCHANGE_TIMEOUT", "30")),
        )
        return AppConfig(canvas=canvas_cfg, roster=roster_cfg)

    def _resolve_source(self) -> Mapping[str, str]:
        if self._env_override is not None:
            return self._env_override
        # File is authoritative for documented schema keys; for anything else
        # (e.g. CANVAS_ACCOUNT_ID set in the shell, CI overrides) fall back
        # to the process environment.
        try:
            file_values = {
                k: v for k, v in dict(dotenv_values(self._env_path) or {}).items() if v is not None
            }
        except OSError:
            file_values = {}
        merged: dict[str, str] = {**os.environ}
        merged.update(file_values)
        for name in SCHEMA_NAMES:
            if name not in file_values:
                merged.pop(name, None)
        return merged
