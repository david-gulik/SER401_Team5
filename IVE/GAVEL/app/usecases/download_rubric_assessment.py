from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.workspace.layout import (
    AssignmentFolder,
    CourseFolder,
    DataTree,
    module_number_from_name,
)
from GAVEL.app.workspace.manifest import AssignmentEntry
from GAVEL.app.workspace.recording import (
    guard_not_downloaded,
    note_assignment,
    note_course,
    record,
)
from GAVEL.infra.json.rubric_json import assessments_to_json, definition_to_json


@dataclass(frozen=True)
class DownloadRubricAssessmentRequest:
    course_id: int
    assignment: CanvasAssignment
    folder: CourseFolder
    overwrite: bool = False


@dataclass(frozen=True)
class DownloadRubricAssessmentResult:
    saved_path: Path
    definition_saved_path: Path | None
    assignment_folder: AssignmentFolder
    message: str


def assignment_folder_for(tree: DataTree, assignment: CanvasAssignment) -> AssignmentFolder:
    """The folder an assignment's files belong in.

    Reuses a folder already on disk for this id (whatever its module tag) so a
    download by typed id and a download from the loaded list never produce two
    folders for one assignment.
    """
    existing = tree.find_assignment(assignment.id)
    if existing is not None:
        return existing
    return tree.assignment(assignment.id, module_number_from_name(assignment.name))


class DownloadRubricAssessmentUseCase:
    """Saves one assignment's rubric definition and assessments under ``assignments/``."""

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadRubricAssessmentRequest) -> DownloadRubricAssessmentResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")
        assignment = request.assignment
        if assignment.id <= 0:
            raise ValueError("assignment_id must be greater than zero")

        target_folder = assignment_folder_for(request.folder.original, assignment)
        assessments_path = target_folder.rubric_assessments_json
        guard_not_downloaded(request.folder, assessments_path, request.overwrite)

        assessments = self._canvas_client.fetch_rubric_assessments(request.course_id, assignment.id)
        definition = self._canvas_client.fetch_rubric_definition(request.course_id, assignment.id)

        target_folder.path.mkdir(parents=True, exist_ok=True)
        assessments_path.write_text(assessments_to_json(assessments) + "\n", encoding="utf-8")
        record(request.folder, "rubric_assessments", assessments_path, source_id=assignment.id)

        definition_path: Path | None = None
        if definition is not None:
            definition_path = target_folder.rubric_definition_json
            definition_path.write_text(definition_to_json(definition) + "\n", encoding="utf-8")
            record(request.folder, "rubric_definition", definition_path, source_id=assignment.id)

        note_assignment(
            request.folder,
            AssignmentEntry(
                canvas_id=assignment.id,
                name=assignment.name,
                module_number=target_folder.module_number,
                has_rubric=definition is not None,
            ),
        )
        note_course(request.folder, canvas_course_id=request.course_id)

        message = (
            f"Rubric assessment for course {request.course_id}, assignment {assignment.id} "
            f"saved to {assessments_path}"
        )
        return DownloadRubricAssessmentResult(
            saved_path=assessments_path,
            definition_saved_path=definition_path,
            assignment_folder=target_folder,
            message=message,
        )
