from __future__ import annotations

from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.ports.roster_client import RosterClient
from GAVEL.infra.canvas.http_canvas_client import CanvasApiConfig, HttpCanvasClient
from GAVEL.infra.canvas.unconfigured_canvas_client import UnconfiguredCanvasClient
from GAVEL.infra.roster.unconfigured_roster_client import UnconfiguredRosterClient
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


def build_roster_client(cfg: AppConfig, logger: AppLogger) -> RosterClient:
    roster_cfg = cfg.roster
    method = (roster_cfg.auth_method or "").lower()

    if method == "selenium":
        from GAVEL.infra.roster.asu_roster_adapter import build_selenium_roster_client

        logger.info("Configuring ASU Roster client (Selenium auth)")
        return build_selenium_roster_client(roster_cfg=roster_cfg)

    if method == "cookies":
        if not roster_cfg.cookie_file:
            logger.warning(
                "ROSTER_AUTH_METHOD=cookies but ROSTER_COOKIE_FILE not set; "
                "roster features disabled"
            )
            return UnconfiguredRosterClient(
                "ROSTER_COOKIE_FILE is required when ROSTER_AUTH_METHOD=cookies."
            )
        from GAVEL.infra.roster.asu_roster_adapter import build_cookie_roster_client

        logger.info("Configuring ASU Roster client (cookie-file auth)")
        return build_cookie_roster_client(roster_cfg=roster_cfg)

    logger.warning("ROSTER_AUTH_METHOD not set; roster features disabled")
    return UnconfiguredRosterClient()
