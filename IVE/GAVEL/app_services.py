from __future__ import annotations

from dataclasses import dataclass

from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.canvas_download_course import DownloadCourseDataUseCase
from GAVEL.services.logger import AppLogger


@dataclass(frozen=True)
class AppServices:
    canvas_client: CanvasClient
    download_course_data_uc: DownloadCourseDataUseCase

    @classmethod
    def build(cls, canvas_client: CanvasClient, logger: AppLogger) -> "AppServices":
        logger.info("AppServices: initializing download_course_data use case")
        download_uc = DownloadCourseDataUseCase(canvas_client)
        return cls(
            canvas_client=canvas_client,
            download_course_data_uc=download_uc,
        )
