from __future__ import annotations

from typing import TYPE_CHECKING

from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.ports.roster_client import RosterClient
from GAVEL.app.workspace.dataset import DatasetReaders
from GAVEL.infra.canvas.http_canvas_client import CanvasApiConfig, HttpCanvasClient
from GAVEL.infra.canvas.unconfigured_canvas_client import UnconfiguredCanvasClient
from GAVEL.infra.csv.canvas_consent_form_csv_reader import CanvasConsentFormCSVReader
from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader
from GAVEL.infra.csv.canvas_roster_csv_reader import CanvasRosterCSVReader
from GAVEL.infra.json.rubric_json_reader import (
    JsonRubricAssessmentReader,
    JsonRubricDefinitionReader,
)
from GAVEL.infra.roster.unconfigured_roster_client import UnconfiguredRosterClient
from GAVEL.infra.yaml.yaml_gradescope_reader import YamlGradescopeReader
from GAVEL.services.config_service import AppConfig
from GAVEL.services.logger import AppLogger

if TYPE_CHECKING:
    from GAVEL.infra.asu_auth.browser_session import AsuBrowserSession


def build_canvas_client(cfg: AppConfig, logger: AppLogger) -> CanvasClient:
    canvas_cfg = cfg.canvas
    if canvas_cfg.base_url and canvas_cfg.token:
        logger.info("Configuring Canvas HTTP client")
        return HttpCanvasClient(
            CanvasApiConfig(
                base_url=canvas_cfg.base_url,
                token=canvas_cfg.token,
                account_id=canvas_cfg.account_id,
            ),
            logger=AppLogger("GAVEL.gradebook", propagate=False),
        )
    logger.warning("Canvas configuration missing; Canvas features disabled")
    return UnconfiguredCanvasClient()


def build_asu_browser(cfg: AppConfig, logger: AppLogger) -> AsuBrowserSession:
    """The one login browser shared by every feature that signs in to ASU.

    Nothing is opened here; the browser starts the first time a download
    needs it. The caller owns it and closes it when the app exits.
    """
    from GAVEL.infra.asu_auth.browser_session import AsuBrowserSession
    from GAVEL.infra.asu_auth.cookie_store import CookieStore

    store = CookieStore()
    if not cfg.asu_login.remember:
        # Switching the setting off also discards a login saved while it was on.
        if store.clear():
            logger.info("Removed the saved ASU login")
        return AsuBrowserSession(mfa_timeout=cfg.roster.mfa_timeout)
    return AsuBrowserSession(store, mfa_timeout=cfg.roster.mfa_timeout)


def build_roster_client(
    cfg: AppConfig, logger: AppLogger, asu_browser: AsuBrowserSession | None = None
) -> RosterClient:
    roster_cfg = cfg.roster
    method = (roster_cfg.auth_method or "").lower()

    if method == "selenium":
        from GAVEL.infra.roster.asu_roster_adapter import build_selenium_roster_client

        logger.info("Configuring ASU Roster client (Selenium auth)")
        return build_selenium_roster_client(
            roster_cfg=roster_cfg,
            browser=asu_browser or build_asu_browser(cfg, logger),
        )

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


def build_dataset_readers() -> DatasetReaders:
    """One reader per file type in a course folder; see ``CourseDataset``."""
    return DatasetReaders(
        roster=CanvasRosterCSVReader(),
        gradebook=LegacyGradebookCSVReader(),
        consent_form=CanvasConsentFormCSVReader(),
        rubric_definition=JsonRubricDefinitionReader(),
        rubric_assessments=JsonRubricAssessmentReader(),
        gradescope=YamlGradescopeReader(),
    )
