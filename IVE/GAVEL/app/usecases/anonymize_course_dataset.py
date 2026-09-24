from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from GAVEL.app.usecases.downselect_consented_students import (
    DownselectConsentedStudentsRequest,
    DownselectConsentedStudentsUseCase,
)
from GAVEL.app.usecases.generate_anonymous_id_map import (
    GenerateAnonymousIdMapRequest,
    GenerateAnonymousIdMapUseCase,
)
from GAVEL.infra.csv.canvas_consent_form_csv_reader import (
    CanvasConsentFormCSVReader,
)
from GAVEL.app.usecases.anonymize_roster import (
    AnonymizeRosterRequest,
    AnonymizeRosterUseCase,
)
from GAVEL.infra.csv.canvas_roster_csv_reader import CanvasRosterCSVReader
from GAVEL.app.usecases.anonymize_gradebook import (
    AnonymizeGradebookRequest,
    AnonymizeGradebookUseCase,
)
from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader
from GAVEL.app.usecases.anonymize_consent_form import (
    AnonymizeConsentFormRequest,
    AnonymizeConsentFormUseCase,
)


@dataclass(frozen=True)
class AnonymizeCourseDatasetRequest:
    snapshot_dir: Path
    seed: int | None = None


@dataclass(frozen=True)
class ArtifactReport:
    processed_count: int = 0
    skipped_count: int = 0
    excluded_count: int = 0


@dataclass(frozen=True)
class AnonymizeCourseDatasetResult:
    output_dir: Path
    consent_form: ArtifactReport
    roster: ArtifactReport
    gradebook: ArtifactReport
    rubric_assessment: ArtifactReport


class AnonymizeCourseDatasetUseCase:
    def __init__(
        self,
        consent_form_reader: CanvasConsentFormCSVReader,
        downselect_use_case: DownselectConsentedStudentsUseCase,
        id_map_use_case: GenerateAnonymousIdMapUseCase,
        roster_reader: CanvasRosterCSVReader,
        anonymize_roster_use_case: AnonymizeRosterUseCase,
        gradebook_reader: LegacyGradebookCSVReader,
        anonymize_gradebook_use_case: AnonymizeGradebookUseCase,
        anonymize_consent_form_use_case: AnonymizeConsentFormUseCase,
    ) -> None:
        self._consent_form_reader = consent_form_reader
        self._downselect_use_case = downselect_use_case
        self._id_map_use_case = id_map_use_case
        self._roster_reader = roster_reader
        self._anonymize_roster_use_case = anonymize_roster_use_case
        self._gradebook_reader = gradebook_reader
        self._anonymize_gradebook_use_case = anonymize_gradebook_use_case
        self._anonymize_consent_form_use_case = anonymize_consent_form_use_case

    def execute(
        self,
        request: AnonymizeCourseDatasetRequest,
    ) -> AnonymizeCourseDatasetResult:
        original_dir = request.snapshot_dir / "original"
        consent_form_path = original_dir / "consent_form.csv"
        roster_path = original_dir / "roster.csv"
        gradebook_path = original_dir / "gradebook.csv"

        consent_entries = tuple(self._consent_form_reader.read(str(consent_form_path)))

        consent_result = self._downselect_use_case.execute(
            DownselectConsentedStudentsRequest(
                entries=consent_entries,
            )
        )

        id_map_result = self._id_map_use_case.execute(
            GenerateAnonymousIdMapRequest(
                student_ids=set(consent_result.consented_ids),
                seed=request.seed,
            )
        )

        id_map = tuple(id_map_result.id_map.items())

        consent_form_result = self._anonymize_consent_form_use_case.execute(
            AnonymizeConsentFormRequest(
                entries=consent_entries,
                id_map=id_map,
            )
        )

        roster_students = tuple(self._roster_reader.read(roster_path))

        roster_result = self._anonymize_roster_use_case.execute(
            AnonymizeRosterRequest(
                students=roster_students,
                consented_ids=consent_result.consented_ids,
                id_map=id_map,
            )
        )

        gradebook = self._gradebook_reader.parse(gradebook_path)

        gradebook_result = self._anonymize_gradebook_use_case.execute(
            AnonymizeGradebookRequest(
                gradebook=gradebook,
                consented_ids=consent_result.consented_ids,
                id_map=id_map,
            )
        )

        raise NotImplementedError
