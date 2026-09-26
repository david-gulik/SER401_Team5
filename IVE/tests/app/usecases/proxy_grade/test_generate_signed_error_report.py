from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook, GradebookStudentRow
from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.ports.gradescope_reader import GradescopeReader
from GAVEL.app.usecases.proxy_grade.generate_signed_error_report import (
    GenerateSignedErrorReportRequest,
    GenerateSignedErrorReportUseCase,
)

# A small mapping used only by these tests. Full marks are 5.0.
_MAPPING = ProxyGradeMapping(
    name="toy",
    criteria=(
        Criterion("first", (Tier(2.0, all_of=("Test A", "Test B")),)),
        Criterion("second", (Tier(3.0, all_of=("Test C",)),)),
    ),
)
_ALL_TEST_NAMES = list(_MAPPING.test_names())

_GRADEBOOK_COLUMN = "Module 2: Programming (123456)"


def _submission(
    sid: str, email: str, passing: set[str], names: list[str] | None = None
) -> GradescopeSubmission:
    tests = [
        GradescopeTestScore(
            name=f"{name} [Hint: ...]",
            score=1.0 if name in passing else 0.0,
            max_score=1.0,
        )
        for name in (names if names is not None else _ALL_TEST_NAMES)
    ]
    return GradescopeSubmission(
        submission_key=f"submission_{sid}",
        submitter=GradescopeSubmitter(sid=sid, email=email, name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


class FakeGradescopeReader(GradescopeReader):
    def __init__(self, by_path: dict[Path, list[GradescopeSubmission]]) -> None:
        self._by_path = by_path

    def read(self, path: Path) -> list[GradescopeSubmission]:
        return self._by_path[path]


class FakeGradebookReader:
    def __init__(self, gradebook: CanvasGradebook) -> None:
        self._gradebook = gradebook

    def parse(self, path: Path) -> CanvasGradebook:
        return self._gradebook


def _gradebook(rows: list[GradebookStudentRow]) -> CanvasGradebook:
    return CanvasGradebook(columns=(), rows=tuple(rows))


def test_matches_by_email_local_part_and_computes_signed_error(tmp_path: Path) -> None:
    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    yaml_path = submissions_dir / "student1.yml"
    yaml_path.write_text("placeholder")

    submission = _submission("1", "student1@asu.edu", set(_ALL_TEST_NAMES))  # proxy total = 5.0
    gradebook = _gradebook(
        [
            GradebookStudentRow(
                student_name="One, Student",
                canvas_id=1,
                sis_login_id="Student1",  # case differs on purpose
                section="001",
                assignment_scores={_GRADEBOOK_COLUMN: 4.0},
            )
        ]
    )

    use_case = GenerateSignedErrorReportUseCase(
        gradescope_reader=FakeGradescopeReader({yaml_path: [submission]}),
        gradebook_reader=FakeGradebookReader(gradebook),
    )
    output_path = tmp_path / "report.json"

    result = use_case.execute(
        GenerateSignedErrorReportRequest(
            submissions_dir=submissions_dir,
            mapping=_MAPPING,
            gradebook_path=tmp_path / "gradebook.csv",
            gradebook_column=_GRADEBOOK_COLUMN,
            output_path=output_path,
        )
    )

    assert result.unmatched_submissions == ()
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.student_identifier == "student1"
    assert row.human_score == 4.0
    assert row.proxy_score == 5.0
    assert row.signed_error == -1.0
    assert output_path.exists()


def test_submission_with_no_matching_gradebook_row_is_reported_as_unmatched(tmp_path: Path) -> None:
    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    yaml_path = submissions_dir / "student2.yml"
    yaml_path.write_text("placeholder")

    submission = _submission("2", "nobody@asu.edu", set())
    gradebook = _gradebook(
        [
            GradebookStudentRow(
                student_name="One, Student",
                canvas_id=1,
                sis_login_id="student1",
                section="001",
                assignment_scores={_GRADEBOOK_COLUMN: 28.0},
            )
        ]
    )

    use_case = GenerateSignedErrorReportUseCase(
        gradescope_reader=FakeGradescopeReader({yaml_path: [submission]}),
        gradebook_reader=FakeGradebookReader(gradebook),
    )

    result = use_case.execute(
        GenerateSignedErrorReportRequest(
            submissions_dir=submissions_dir,
            mapping=_MAPPING,
            gradebook_path=tmp_path / "gradebook.csv",
            gradebook_column=_GRADEBOOK_COLUMN,
            output_path=tmp_path / "report.json",
        )
    )

    assert result.rows == ()
    assert result.unmatched_submissions == ("2",)


def test_submission_missing_a_mapped_test_is_reported_and_the_run_continues(tmp_path: Path) -> None:
    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    yaml_path = submissions_dir / "students.yml"
    yaml_path.write_text("placeholder")

    broken = _submission("3", "student3@asu.edu", set(), names=["Test A"])
    good = _submission("1", "student1@asu.edu", set(_ALL_TEST_NAMES))
    gradebook = _gradebook(
        [
            GradebookStudentRow(
                student_name=f"Student {n}",
                canvas_id=n,
                sis_login_id=f"student{n}",
                section="001",
                assignment_scores={_GRADEBOOK_COLUMN: 4.0},
            )
            for n in (1, 3)
        ]
    )

    use_case = GenerateSignedErrorReportUseCase(
        gradescope_reader=FakeGradescopeReader({yaml_path: [broken, good]}),
        gradebook_reader=FakeGradebookReader(gradebook),
    )

    result = use_case.execute(
        GenerateSignedErrorReportRequest(
            submissions_dir=submissions_dir,
            mapping=_MAPPING,
            gradebook_path=tmp_path / "gradebook.csv",
            gradebook_column=_GRADEBOOK_COLUMN,
            output_path=tmp_path / "report.json",
        )
    )

    assert [row.student_identifier for row in result.rows] == ["student1"]
    assert len(result.failed_submissions) == 1
    assert result.failed_submissions[0].submission_id == "3"
    assert result.failed_submissions[0].missing_tests == ("Test B", "Test C")
