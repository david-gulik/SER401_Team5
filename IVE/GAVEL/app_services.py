from __future__ import annotations

from dataclasses import dataclass

from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.ports.roster_client import RosterClient
from GAVEL.app.usecases.canvas_download_course import DownloadCourseDataUseCase
from GAVEL.app.workspace.dataset import DatasetReaders
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.services.logger import AppLogger


@dataclass(frozen=True)
class AppServices:
    canvas_client: CanvasClient
    roster_client: RosterClient
    download_course_data_uc: DownloadCourseDataUseCase
    dataset_readers: DatasetReaders

    @classmethod
    def build(
        cls,
        canvas_client: CanvasClient,
        roster_client: RosterClient,
        logger: AppLogger,
        dataset_readers: DatasetReaders | None = None,
    ) -> AppServices:
        logger.info("AppServices: initializing use cases")
        download_uc = DownloadCourseDataUseCase(canvas_client)
        return cls(
            canvas_client=canvas_client,
            roster_client=roster_client,
            download_course_data_uc=download_uc,
            dataset_readers=dataset_readers or build_dataset_readers(),
        )
