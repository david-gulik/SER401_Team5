from __future__ import annotations

from GAVEL.app.ports.canvas_client import CanvasClient, UnconfiguredCanvasClient
from GAVEL.infra.canvas.http_canvas_client import CanvasApiConfig, HttpCanvasClient
from GAVEL.services.config_service import AppConfig
from GAVEL.services.logger import AppLogger


def build_canvas_client(cfg: AppConfig, logger: AppLogger) -> CanvasClient:
    canvas_cfg = cfg.canvas
    if canvas_cfg.base_url and canvas_cfg.token:
        logger.info("Configuring Canvas HTTP client")
        return HttpCanvasClient(
            CanvasApiConfig(
                base_url=canvas_cfg.base_url,
                token=canvas_cfg.token,
            )
        )
    logger.warning("Canvas configuration missing; Canvas features disabled")
    return UnconfiguredCanvasClient()
