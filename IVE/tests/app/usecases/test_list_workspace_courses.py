from __future__ import annotations

from pathlib import Path

from GAVEL.app.dtos.course_summary import (
    AnonymizationStatus,
    ConsentTally,
    CourseSummary,
    FileState,
)
from GAVEL.app.usecases.list_workspace_courses import (
    ListWorkspaceCoursesRequest,
    ListWorkspaceCoursesUseCase,
)
from tests.pages.sanitize.course_folders import (
    ANONYMIZED,
    CHANGED_AFTER,
    DOWNLOADED,
    build_course,
    set_modified,
)

RUBRIC = "assignments/7216970_m1/rubric_assessments.json"


def list_courses(root: Path) -> tuple[CourseSummary, ...]:
    return ListWorkspaceCoursesUseCase().execute(ListWorkspaceCoursesRequest(root)).courses


def only_course(root: Path) -> CourseSummary:
    courses = list_courses(root)
    assert len(courses) == 1
    return courses[0]


class TestFindingCourses:
    def test_missing_workspace_has_no_courses(self, tmp_path: Path):
        assert list_courses(tmp_path / "nowhere") == ()

    def test_courses_are_sorted_by_folder_name(self, tmp_path: Path):
        build_course(tmp_path, "ser334_26u_33333")
        build_course(tmp_path, "ser222_26f_11111")

        names = [course.folder_name for course in list_courses(tmp_path)]

        assert names == ["ser222_26f_11111", "ser334_26u_33333"]

    def test_folders_that_are_not_course_names_are_ignored(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111")
        (tmp_path / "courses" / "scratch").mkdir()

        assert [course.folder_name for course in list_courses(tmp_path)] == ["ser222_26f_11111"]


class TestTrackedFiles:
    def test_top_level_files_are_always_listed_then_rubrics(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111", gradebook=False, rubric_assessments=2)

        paths = [file.path for file in only_course(tmp_path).files]

        assert paths == [
            "consent_form.csv",
            "roster.csv",
            "gradebook.csv",
            "assignments/7216970_m1/rubric_assessments.json",
            "assignments/7216971_m2/rubric_assessments.json",
        ]

    def test_missing_file_has_no_original_time(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111", gradebook=False)

        gradebook = only_course(tmp_path).file("gradebook.csv")

        assert gradebook.original_state is FileState.MISSING
        assert gradebook.anonymized_state is FileState.MISSING

    def test_copies_written_after_the_original_are_current(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111", anonymized_at=ANONYMIZED)

        roster = only_course(tmp_path).file("roster.csv")

        assert roster.original_at == DOWNLOADED
        assert roster.anonymized_at == ANONYMIZED
        assert roster.anonymized_state is FileState.CURRENT

    def test_original_changed_after_its_copy_makes_the_copy_out_of_date(self, tmp_path: Path):
        course_dir = build_course(tmp_path, "ser222_26f_11111", anonymized_at=ANONYMIZED)
        set_modified(course_dir / "original" / "roster.csv", CHANGED_AFTER)

        course = only_course(tmp_path)

        assert course.file("roster.csv").anonymized_state is FileState.OUT_OF_DATE
        assert course.file("consent_form.csv").anonymized_state is FileState.CURRENT

    def test_copy_left_behind_by_a_deleted_original_is_out_of_date(self, tmp_path: Path):
        course_dir = build_course(
            tmp_path, "ser222_26f_11111", rubric_assessments=1, anonymized_at=ANONYMIZED
        )
        (course_dir / "original" / RUBRIC).unlink()

        rubric = only_course(tmp_path).file(RUBRIC)

        assert rubric.original_state is FileState.MISSING
        assert rubric.anonymized_state is FileState.OUT_OF_DATE


class TestConsentTally:
    def test_counts_consenting_students_out_of_everyone(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111", students=5, consented=3)

        assert only_course(tmp_path).consent == ConsentTally(included=3, total=5)

    def test_roster_students_who_never_responded_count_toward_the_total(self, tmp_path: Path):
        course_dir = build_course(tmp_path, "ser222_26f_11111", students=3, consented=2)
        roster = course_dir / "original" / "roster.csv"
        roster.write_text(
            roster.read_text(encoding="utf-8")
            + "1099,1099-001,Late,Joiner,Enrolled,3,Standard,SER,Senior,ljoiner,Resident,"
            "ljoiner@example.com\n",
            encoding="utf-8",
        )

        assert only_course(tmp_path).consent == ConsentTally(included=2, total=4)

    def test_no_consent_form_has_no_tally(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111", consent_form=False)

        course = only_course(tmp_path)

        assert course.consent is None
        assert not course.consent_unreadable

    def test_unreadable_consent_form_is_flagged_not_fatal(self, tmp_path: Path):
        course_dir = build_course(tmp_path, "ser222_26f_11111")
        (course_dir / "original" / "consent_form.csv").write_text("nonsense\n", encoding="utf-8")

        course = only_course(tmp_path)

        assert course.consent is None
        assert course.consent_unreadable


class TestManifest:
    def test_canvas_course_name_comes_from_the_manifest(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111", canvas_course_name="SER 222 Fall 2026")

        assert only_course(tmp_path).canvas_course_name == "SER 222 Fall 2026"

    def test_unreadable_manifest_only_loses_the_name(self, tmp_path: Path):
        course_dir = build_course(tmp_path, "ser222_26f_11111")
        (course_dir / "manifest.json").write_text("{not json", encoding="utf-8")

        assert only_course(tmp_path).canvas_course_name is None


class TestStatus:
    def test_missing_consent_form_cannot_be_anonymized(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111", consent_form=False)

        assert only_course(tmp_path).status is AnonymizationStatus.NO_CONSENT_FORM

    def test_no_anonymized_copies_is_not_anonymized(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111")

        course = only_course(tmp_path)

        assert course.anonymized_at is None
        assert course.status is AnonymizationStatus.NOT_ANONYMIZED

    def test_every_copy_current_is_up_to_date(self, tmp_path: Path):
        build_course(tmp_path, "ser222_26f_11111", rubric_assessments=2, anonymized_at=ANONYMIZED)

        course = only_course(tmp_path)

        assert course.anonymized_at == ANONYMIZED
        assert course.status is AnonymizationStatus.UP_TO_DATE

    def test_one_changed_input_makes_the_course_out_of_date(self, tmp_path: Path):
        course_dir = build_course(tmp_path, "ser222_26f_11111", anonymized_at=ANONYMIZED)
        set_modified(course_dir / "original" / "gradebook.csv", CHANGED_AFTER)

        assert only_course(tmp_path).status is AnonymizationStatus.OUT_OF_DATE

    def test_input_added_after_anonymizing_makes_the_course_out_of_date(self, tmp_path: Path):
        course_dir = build_course(tmp_path, "ser222_26f_11111", anonymized_at=ANONYMIZED)
        rubric = course_dir / "original" / RUBRIC
        rubric.parent.mkdir(parents=True)
        rubric.write_text("[]\n", encoding="utf-8")

        assert only_course(tmp_path).status is AnonymizationStatus.OUT_OF_DATE

    def test_files_the_anonymizer_does_not_read_are_ignored(self, tmp_path: Path):
        course_dir = build_course(tmp_path, "ser222_26f_11111", anonymized_at=ANONYMIZED)
        quiz = course_dir / "original" / "quizzes" / "1951349.csv"
        quiz.parent.mkdir(parents=True)
        quiz.write_text("x\n", encoding="utf-8")

        assert only_course(tmp_path).status is AnonymizationStatus.UP_TO_DATE
