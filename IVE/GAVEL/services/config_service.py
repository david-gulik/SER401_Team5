from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional


@dataclass(frozen=True)
class CanvasConfig:
    base_url: Optional[str] = None
    token: Optional[str] = None


@dataclass(frozen=True)
class AppConfig:
    environment: str = "DEV"
    version: str = "0.1.0"
    canvas: CanvasConfig = field(default_factory=CanvasConfig)


class ConfigService:
    def __init__(self, env: Optional[Mapping[str, str]] = None) -> None:
        source = env or os.environ
        canvas_cfg = CanvasConfig(
            base_url=source.get("CANVAS_BASE_URL"),
            token=source.get("CANVAS_TOKEN"),
        )
        self._config = AppConfig(canvas=canvas_cfg)

    def get(self) -> AppConfig:
        return self._config
