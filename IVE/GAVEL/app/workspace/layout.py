"""Where course data lives on disk.

Everything here is path arithmetic. The only method that touches the
filesystem is ``Workspace.list_courses`` (and the ``find_*`` helpers on
``DataTree``), and those only list directories. Nothing here writes.

The layout, with one course as an example:

    <workspace root>
    ├── courses/
    │   └── ser222_25sc_12345/          CourseFolder (CourseKey.folder_name)
    │       ├── manifest.json
    │       ├── ground_truth/
    │       ├── original/
    │       │   ├── roster.csv
    │       │   ├── gradebook.csv
    │       │   ├── consent_form.csv
    │       │   ├── quizzes/<quiz id>.csv
    │       │   └── assignments/<assignment id>_m<module>/   AssignmentFolder
    │       │       ├── rubric_definition.json
    │       │       ├── rubric_assessments.json
    │       │       ├── submissions.zip
    │       │       └── autograder.zip
    │       └── anonymized/             DataTree, same shape as original/
    ├── autograders/
    └── runs/

See ``docs/workspace_layout.md`` for the rules behind each name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.roster import ClassSection

COURSES_DIR = "courses"
AUTOGRADERS_DIR = "autograders"
RUNS_DIR = "runs"

MANIFEST_FILE = "manifest.json"
GROUND_TRUTH_DIR = "ground_truth"
ORIGINAL_DIR = "original"
ANONYMIZED_DIR = "anonymized"

ROSTER_FILE = "roster.csv"
GRADEBOOK_FILE = "gradebook.csv"
CONSENT_FORM_FILE = "consent_form.csv"
QUIZZES_DIR = "quizzes"
ASSIGNMENTS_DIR = "assignments"

RUBRIC_DEFINITION_FILE = "rubric_definition.json"
RUBRIC_ASSESSMENTS_FILE = "rubric_assessments.json"
SUBMISSIONS_FILE = "submissions.zip"
AUTOGRADER_FILE = "autograder.zip"

# myASU term code digit -> folder letter. 2267 is Fall 2026.
TERM_DIGIT_LETTERS = {"1": "s", "4": "u", "7": "f", "9": "w"}
# Canvas course code term word -> folder letter. "2026FallC-X-SER402-87275".
TERM_WORD_LETTERS = {"spring": "s", "summer": "u", "fall": "f", "winter": "w"}
TERM_LETTERS = frozenset(TERM_DIGIT_LETTERS.values())

_TERM_CODE = re.compile(r"^2\d\d[1479]$")
_CANVAS_TERM_TOKEN = re.compile(r"^(\d{4})(Spring|Summer|Fall|Winter)([A-Za-z]?)$")
_CANVAS_COURSE_TOKEN = re.compile(r"^([A-Za-z]{2,4})(\d{3}[A-Za-z]?)$")
_CLASS_NUMBER = re.compile(r"^\d{5}$")
_SUBJECT = re.compile(r"^[A-Z]{2,4}$")
_CATALOG_NUMBER = re.compile(r"^\d{3}[A-Z]?$")
_SESSION = re.compile(r"^[a-z]?$")
_FOLDER_NAME = re.compile(r"^([a-z]{2,4})(\d{3}[a-z]?)_(\d{2})([sufw])([a-z]?)_(\d{5})$")
_MODULE_NUMBER = re.compile(r"^\s*mod(?:ule)?\s*(\d+)\b", re.IGNORECASE)
_ASSIGNMENT_FOLDER = re.compile(r"^(\d+)(?:_m(\d+))?$")


def module_number_from_name(name: str | None) -> int | None:
    """Module number from a Canvas assignment name, or None.

    Canvas assignment names in these courses start with the module they belong
    to: ``"Module 4: Cairn"`` and ``"Mod 4: ADJ Problem Set"`` both give 4.
    Anything else (``"Final Exam"``) gives None and the assignment folder is
    named by id alone.
    """
    if not name:
        return None
    match = _MODULE_NUMBER.match(name)
    return int(match[1]) if match else None


def assignment_folder_name(assignment_id: int, module_number: int | None = None) -> str:
    """``7216983_m4`` when the module is known, ``7216983`` when it is not."""
    if module_number is None:
        return str(assignment_id)
    return f"{assignment_id}_m{module_number}"


@dataclass(frozen=True)
class CourseKey:
    """Identity of one course offering; its ``folder_name`` is the course folder.

    ``ser222_25sc_12345`` is subject + catalog number, two-digit year + term
    letter + session letter, and the myASU class number. Fields are
    normalised on construction (subject upper, term and session lower) so two
    keys built from different sources compare equal.
    """

    subject: str
    catalog_number: str
    year: int
    term: str
    session: str
    class_number: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject", self.subject.strip().upper())
        object.__setattr__(self, "catalog_number", self.catalog_number.strip().upper())
        object.__setattr__(self, "term", self.term.strip().lower())
        object.__setattr__(self, "session", self.session.strip().lower())
        object.__setattr__(self, "class_number", self.class_number.strip())

        if not _SUBJECT.fullmatch(self.subject):
            raise ValueError(f"subject must be 2-4 letters, got {self.subject!r}")
        if not _CATALOG_NUMBER.fullmatch(self.catalog_number):
            raise ValueError(
                f"catalog_number must look like 222 or 222A, got {self.catalog_number!r}"
            )
        if not 2000 <= self.year <= 2099:
            raise ValueError(f"year must be a four-digit year in this century, got {self.year}")
        if self.term not in TERM_LETTERS:
            raise ValueError(f"term must be one of {sorted(TERM_LETTERS)}, got {self.term!r}")
        if not _SESSION.fullmatch(self.session):
            raise ValueError(f"session must be one letter or empty, got {self.session!r}")
        if not _CLASS_NUMBER.fullmatch(self.class_number):
            raise ValueError(f"class_number must be five digits, got {self.class_number!r}")

    @property
    def folder_name(self) -> str:
        return (
            f"{self.subject.lower()}{self.catalog_number.lower()}"
            f"_{self.year % 100:02d}{self.term}{self.session}"
            f"_{self.class_number}"
        )

    @property
    def course_label(self) -> str:
        """``SER 222`` for messages."""
        return f"{self.subject} {self.catalog_number}"

    @classmethod
    def from_canvas_course_code(
        cls, course_code: str | None, class_number: str | None = None
    ) -> CourseKey | None:
        """Key from a SIS-created Canvas course code, or None when it has no such shape.

        ``2026FallC-X-SER402-87275`` carries term, session, subject, catalog
        number and one class number per cross-listed section. ``class_number``
        picks the section when the roster side has already chosen one;
        otherwise the first class number in the code is used. Training courses
        and renamed courses do not match and give None.
        """
        if not course_code:
            return None
        parts = [p.strip() for p in course_code.split("-")]
        term_match = _CANVAS_TERM_TOKEN.fullmatch(parts[0])
        if term_match is None:
            return None
        course_match = next(
            (m for p in parts[1:] if (m := _CANVAS_COURSE_TOKEN.fullmatch(p)) is not None),
            None,
        )
        if course_match is None:
            return None
        numbers = [p for p in parts[1:] if _CLASS_NUMBER.fullmatch(p)]
        chosen = class_number.strip() if class_number else (numbers[0] if numbers else "")
        if not chosen:
            return None
        return cls(
            subject=course_match[1],
            catalog_number=course_match[2],
            year=int(term_match[1]),
            term=TERM_WORD_LETTERS[term_match[2].lower()],
            session=term_match[3],
            class_number=chosen,
        )

    @classmethod
    def from_roster(cls, term_code: str, section: ClassSection) -> CourseKey:
        """Key from a myASU term code and a catalog search result."""
        term_code = term_code.strip()
        if not _TERM_CODE.fullmatch(term_code):
            raise ValueError(f"term code must look like 2267, got {term_code!r}")
        session = section.session.strip()
        return cls(
            subject=section.subject,
            catalog_number=section.catalog_number,
            year=2000 + int(term_code[1:3]),
            term=TERM_DIGIT_LETTERS[term_code[3]],
            session=session if len(session) == 1 else "",
            class_number=section.class_number,
        )

    @classmethod
    def parse(cls, folder_name: str) -> CourseKey:
        """Inverse of ``folder_name``. Raises ValueError for anything else."""
        match = _FOLDER_NAME.fullmatch(folder_name.strip())
        if match is None:
            raise ValueError(f"{folder_name!r} is not a course folder name like ser222_25sc_12345")
        return cls(
            subject=match[1],
            catalog_number=match[2],
            year=2000 + int(match[3]),
            term=match[4],
            session=match[5],
            class_number=match[6],
        )


@dataclass(frozen=True)
class AssignmentFolder:
    """One ``assignments/<id>_m<module>/`` folder inside a ``DataTree``."""

    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def assignment_id(self) -> int:
        match = _ASSIGNMENT_FOLDER.fullmatch(self.path.name)
        if match is None:
            raise ValueError(f"{self.path.name!r} is not an assignment folder name")
        return int(match[1])

    @property
    def module_number(self) -> int | None:
        match = _ASSIGNMENT_FOLDER.fullmatch(self.path.name)
        if match is None or match[2] is None:
            return None
        return int(match[2])

    @property
    def rubric_definition_json(self) -> Path:
        return self.path / RUBRIC_DEFINITION_FILE

    @property
    def rubric_assessments_json(self) -> Path:
        return self.path / RUBRIC_ASSESSMENTS_FILE

    @property
    def submissions_zip(self) -> Path:
        return self.path / SUBMISSIONS_FILE

    @property
    def autograder_zip(self) -> Path:
        return self.path / AUTOGRADER_FILE

    def exists(self) -> bool:
        return self.path.is_dir()


@dataclass(frozen=True)
class DataTree:
    """The inside of ``original/`` or ``anonymized/``. Both have this shape."""

    root: Path

    @property
    def roster_csv(self) -> Path:
        return self.root / ROSTER_FILE

    @property
    def gradebook_csv(self) -> Path:
        return self.root / GRADEBOOK_FILE

    @property
    def consent_form_csv(self) -> Path:
        return self.root / CONSENT_FORM_FILE

    @property
    def quizzes_dir(self) -> Path:
        return self.root / QUIZZES_DIR

    @property
    def assignments_dir(self) -> Path:
        return self.root / ASSIGNMENTS_DIR

    def quiz_csv(self, quiz_id: int) -> Path:
        return self.quizzes_dir / f"{quiz_id}.csv"

    def assignment(self, assignment_id: int, module_number: int | None = None) -> AssignmentFolder:
        """The folder an assignment *should* be written to. Does not touch disk."""
        return AssignmentFolder(
            self.assignments_dir / assignment_folder_name(assignment_id, module_number)
        )

    def find_assignment(self, assignment_id: int) -> AssignmentFolder | None:
        """The folder an assignment *was* written to, whatever its module tag."""
        for folder in self.list_assignments():
            if folder.assignment_id == assignment_id:
                return folder
        return None

    def list_assignments(self) -> list[AssignmentFolder]:
        if not self.assignments_dir.is_dir():
            return []
        return [
            AssignmentFolder(child)
            for child in sorted(self.assignments_dir.iterdir())
            if child.is_dir() and _ASSIGNMENT_FOLDER.fullmatch(child.name)
        ]

    def exists(self) -> bool:
        return self.root.is_dir()


@dataclass(frozen=True)
class CourseFolder:
    """``courses/<CourseKey.folder_name>/`` and everything inside it."""

    path: Path
    key: CourseKey

    @property
    def manifest_path(self) -> Path:
        return self.path / MANIFEST_FILE

    @property
    def ground_truth_dir(self) -> Path:
        return self.path / GROUND_TRUTH_DIR

    @property
    def original(self) -> DataTree:
        return DataTree(self.path / ORIGINAL_DIR)

    @property
    def anonymized(self) -> DataTree:
        return DataTree(self.path / ANONYMIZED_DIR)

    def exists(self) -> bool:
        return self.path.is_dir()


@dataclass(frozen=True)
class Workspace:
    """The root that ``DEFAULT_OUTPUT_DIR`` points at."""

    root: Path

    @property
    def courses_dir(self) -> Path:
        return self.root / COURSES_DIR

    @property
    def autograders_dir(self) -> Path:
        return self.root / AUTOGRADERS_DIR

    @property
    def runs_dir(self) -> Path:
        return self.root / RUNS_DIR

    def course(self, key: CourseKey) -> CourseFolder:
        return CourseFolder(self.courses_dir / key.folder_name, key)

    def list_courses(self) -> list[CourseFolder]:
        """Course folders under ``courses/`` whose names parse; anything else is ignored."""
        if not self.courses_dir.is_dir():
            return []
        found: list[CourseFolder] = []
        for child in sorted(self.courses_dir.iterdir()):
            if not child.is_dir():
                continue
            try:
                key = CourseKey.parse(child.name)
            except ValueError:
                continue
            found.append(CourseFolder(child, key))
        return found
