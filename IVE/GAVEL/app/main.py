import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from GAVEL.app_context import AppContext
from GAVEL.app_services import AppServices
from GAVEL.bootstrap import build_canvas_client
from GAVEL.core.main_window import MainWindow
from GAVEL.core.page_registry import PageRegistry
from GAVEL.pages.canvas_course.page import CanvasCoursePage  # noqa: F401
from GAVEL.pages.home.page import HomePage  # noqa: F401
from GAVEL.pages.settings.page import SettingsPage  # noqa: F401
from GAVEL.services.config_service import ConfigService
from GAVEL.services.logger import AppLogger
from GAVEL.theme.context import ThemeContext
from GAVEL.theme.qss_builder import build_app_qss
from GAVEL.theme.tokens import load_tokens


def main() -> None:
    app = QApplication(sys.argv)

    tokens_path = Path(__file__).resolve().parents[1] / "theme" / "tokens_dark.json"
    tokens = load_tokens(tokens_path)
    app.setStyleSheet(build_app_qss(tokens))
    icon_path = Path(__file__).resolve().parents[1] / "assets" / "icons" / "GAVEL_logo.ico"
    app_icon = QIcon(str(icon_path))
    app.setWindowIcon(app_icon)

    theme = ThemeContext(tokens=tokens)
    config_service = ConfigService()
    logger = AppLogger()

    canvas_client = build_canvas_client(config_service.get(), logger)
    services = AppServices.build(canvas_client, logger)

    ctx = AppContext(
        theme=theme,
        config=config_service,
        logger=logger,
        services=services,
    )

    registry = PageRegistry.get()
    window = MainWindow(registry, ctx)
    window.resize(1200, 800)
    window.setWindowIcon(app_icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
