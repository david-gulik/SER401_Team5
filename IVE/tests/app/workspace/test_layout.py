from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.roster import ClassSection
from GAVEL.app.workspace.layout import (
    AssignmentFolder,
    CourseKey,
    DataTree,
    Workspace,
    assignment_folder_name,
    module_number_from_name,
)

KEY = CourseKey(
    subject="SER", catalog_number="222", year=2025, term="s", session="c", class_number="12345"
)


def section(**overrides: str) -> ClassSection:
    fields = {
        "class_number": "12345",
        "subject": "SER",
        "catalog_number": "222",
        "title": "Data Structures",
        "instructor": "Acuna",
        "days_times": "",
        "session": "C",
    }
    fields.update(overrides)
    return ClassSection(**fields)


class TestCourseKey:
    def test_folder_name(self) -> None:
        assert KEY.folder_name == "ser222_25sc_12345"

    def test_parse_round_trips(self) -> None:
        assert CourseKey.parse(KEY.folder_name) == KEY

    def test_fields_are_normalised(self) -> None:
        key = CourseKey("ser", "222", 2025, "S", "C", " 12345 ")
        assert key == KEY

    def test_session_may_be_empty(self) -> None:
        key = CourseKey("SER", "222", 2025, "f", "", "12345")
        assert key.folder_name == "ser222_25f_12345"
        assert CourseKey.parse("ser222_25f_12345") == key

    def test_catalog_suffix_letter(self) -> None:
        key = CourseKey("CSE", "110A", 2026, "u", "a", "67890")
        assert CourseKey.parse(key.folder_name) == key

    @pytest.mark.parametrize(
        "bad",
        [
            "ser222_25xc_12345",  # unknown term letter
            "ser222_25sc_1234",  # four-digit class number
            "SER222_25sc_12345",  # upper case
            "ser222-25sc-12345",
            "roster_2251_12345.csv",
        ],
    )
    def test_parse_rejects(self, bad: str) -> None:
        with pytest.raises(ValueError):
            CourseKey.parse(bad)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"subject": "S"},
            {"catalog_number": "22"},
            {"year": 1999},
            {"term": "x"},
            {"session": "cc"},
            {"class_number": "123456"},
        ],
    )
    def test_constructor_rejects(self, kwargs: dict) -> None:
        fields = {
            "subject": "SER",
            "catalog_number": "222",
            "year": 2025,
            "term": "s",
            "session": "c",
            "class_number": "12345",
        }
        fields.update(kwargs)
        with pytest.raises(ValueError):
            CourseKey(**fields)

    def test_course_label(self) -> None:
        assert KEY.course_label == "SER 222"


class TestFromCanvasCourseCode:
    def test_sis_code(self) -> None:
        key = CourseKey.from_canvas_course_code("2026FallC-X-SER402-87275")
        assert key == CourseKey("SER", "402", 2026, "f", "c", "87275")

    def test_no_session_letter(self) -> None:
        key = CourseKey.from_canvas_course_code("2026Spring-X-SER222-12345")
        assert key is not None
        assert key.session == ""

    def test_cross_listed_uses_first_class_number_by_default(self) -> None:
        key = CourseKey.from_canvas_course_code("2026FallC-X-SER402-87275-87276")
        assert key is not None
        assert key.class_number == "87275"

    def test_cross_listed_honours_roster_selection(self) -> None:
        key = CourseKey.from_canvas_course_code("2026FallC-X-SER402-87275-87276", "87276")
        assert key is not None
        assert key.class_number == "87276"

    def test_class_number_argument_wins_even_when_absent_from_code(self) -> None:
        # section_match already warns about this; the user's choice is respected.
        key = CourseKey.from_canvas_course_code("2026FallC-X-SER402-87275", "11111")
        assert key is not None
        assert key.class_number == "11111"

    @pytest.mark.parametrize(
        "code",
        [None, "", "TRN-2026Spring-IVECapstone", "My Renamed Course", "2026FallC-X-SER402"],
    )
    def test_unusable_codes_give_none(self, code: str | None) -> None:
        assert CourseKey.from_canvas_course_code(code) is None

    def test_class_number_argument_rescues_code_without_one(self) -> None:
        key = CourseKey.from_canvas_course_code("2026FallC-X-SER402", "87275")
        assert key == CourseKey("SER", "402", 2026, "f", "c", "87275")


class TestFromRoster:
    def test_term_code_and_section(self) -> None:
        key = CourseKey.from_roster("2251", section())
        assert key == KEY

    def test_fall_2026(self) -> None:
        key = CourseKey.from_roster("2267", section(session=""))
        assert key.folder_name == "ser222_26f_12345"

    def test_placeholder_session_is_dropped(self) -> None:
        key = CourseKey.from_roster("2251", section(session="N/A"))
        assert key.session == ""

    @pytest.mark.parametrize("bad", ["", "225", "3251", "2252", "Fall 2026"])
    def test_bad_term_code(self, bad: str) -> None:
        with pytest.raises(ValueError):
            CourseKey.from_roster(bad, section())


class TestModuleNumberFromName:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Module 4: Cairn", 4),
            ("Mod 4: ADJ Problem Set", 4),
            ("module 12 programming", 12),
            ("  Module 3: Activity (12345; Online)", 3),
            ("Final Exam", None),
            ("Modules overview", None),
            ("", None),
            (None, None),
        ],
    )
    def test_cases(self, name: str | None, expected: int | None) -> None:
        assert module_number_from_name(name) == expected


class TestPaths:
    def test_workspace_top_level(self, tmp_path: Path) -> None:
        ws = Workspace(tmp_path)
        assert ws.courses_dir == tmp_path / "courses"
        assert ws.autograders_dir == tmp_path / "autograders"
        assert ws.runs_dir == tmp_path / "runs"

    def test_course_folder(self, tmp_path: Path) -> None:
        folder = Workspace(tmp_path).course(KEY)
        assert folder.path == tmp_path / "courses" / "ser222_25sc_12345"
        assert folder.key == KEY
        assert folder.manifest_path == folder.path / "manifest.json"
        assert folder.ground_truth_dir == folder.path / "ground_truth"
        assert folder.original.root == folder.path / "original"
        assert folder.anonymized.root == folder.path / "anonymized"
        assert not folder.exists()

    def test_data_tree_files(self, tmp_path: Path) -> None:
        tree = DataTree(tmp_path / "original")
        assert tree.roster_csv == tree.root / "roster.csv"
        assert tree.gradebook_csv == tree.root / "gradebook.csv"
        assert tree.consent_form_csv == tree.root / "consent_form.csv"
        assert tree.quiz_csv(99) == tree.root / "quizzes" / "99.csv"
        assert tree.assignments_dir == tree.root / "assignments"

    def test_assignment_folder_naming(self) -> None:
        assert assignment_folder_name(7216983, 4) == "7216983_m4"
        assert assignment_folder_name(7216983, None) == "7216983"

    def test_assignment_folder_files(self, tmp_path: Path) -> None:
        folder = DataTree(tmp_path).assignment(7216983, 4)
        assert folder.path == tmp_path / "assignments" / "7216983_m4"
        assert folder.assignment_id == 7216983
        assert folder.module_number == 4
        assert folder.rubric_definition_json == folder.path / "rubric_definition.json"
        assert folder.rubric_assessments_json == folder.path / "rubric_assessments.json"
        assert folder.submissions_zip == folder.path / "submissions.zip"
        assert folder.autograder_zip == folder.path / "autograder.zip"

    def test_assignment_folder_without_module(self, tmp_path: Path) -> None:
        folder = DataTree(tmp_path).assignment(7216983)
        assert folder.name == "7216983"
        assert folder.module_number is None

    def test_malformed_assignment_folder_name(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            _ = AssignmentFolder(tmp_path / "_staging").assignment_id


class TestDiscovery:
    def test_find_assignment_ignores_module_tag(self, tmp_path: Path) -> None:
        tree = DataTree(tmp_path)
        (tree.assignments_dir / "7216983_m4").mkdir(parents=True)
        (tree.assignments_dir / "7216974").mkdir()
        (tree.assignments_dir / "_staging").mkdir()
        (tree.assignments_dir / "notes.txt").write_text("x")

        found = tree.find_assignment(7216983)
        assert found is not None and found.name == "7216983_m4"
        assert tree.find_assignment(7216974) is not None
        assert tree.find_assignment(1) is None
        assert [f.name for f in tree.list_assignments()] == ["7216974", "7216983_m4"]

    def test_find_assignment_does_not_prefix_match(self, tmp_path: Path) -> None:
        tree = DataTree(tmp_path)
        (tree.assignments_dir / "72169830_m1").mkdir(parents=True)
        assert tree.find_assignment(7216983) is None

    def test_find_assignment_without_folder(self, tmp_path: Path) -> None:
        assert DataTree(tmp_path / "missing").find_assignment(1) is None

    def test_list_courses_skips_unparseable(self, tmp_path: Path) -> None:
        ws = Workspace(tmp_path)
        (ws.courses_dir / "ser222_25sc_12345").mkdir(parents=True)
        (ws.courses_dir / "ser334_26fc_67890").mkdir()
        (ws.courses_dir / "old_dump").mkdir()
        (ws.courses_dir / "stray.csv").write_text("x")

        courses = ws.list_courses()
        assert [c.key.folder_name for c in courses] == ["ser222_25sc_12345", "ser334_26fc_67890"]
        assert courses[0].key == KEY

    def test_list_courses_without_root(self, tmp_path: Path) -> None:
        assert Workspace(tmp_path / "nothing").list_courses() == []
