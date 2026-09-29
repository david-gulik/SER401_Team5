# Workspace Layout

Where GAVEL puts downloaded course data, and how to read it back.

This layout was agreed with Dr. Acuña on 2026-09-10.

## 1. The tree

```
<workspace root>                       # DEFAULT_OUTPUT_DIR, defaults to ~/Downloads/GAVEL
├── courses/
│   └── ser222_25sc_12345/             # one folder per course offering
│       ├── manifest.json              # what was downloaded, when, checksums
│       ├── ground_truth/              # reserved: human grade corrections
│       ├── original/                  # data as downloaded; contains PII
│       │   ├── roster.csv             # myASU roster
│       │   ├── gradebook.csv          # Canvas gradebook export
│       │   ├── consent_form.csv       # Canvas consent quiz, student analysis export
│       │   ├── quizzes/
│       │   │   └── <quiz id>.csv      # other quiz exports, keyed by Canvas quiz id
│       │   ├── assignments/
│       │   │   └── <assignment id>_m<module>/     # e.g. 7216983_m4
│       │   │       ├── rubric_definition.json     # criteria, ratings, points
│       │   │       └── rubric_assessments.json    # one entry per graded submission
│       │   └── submissions/
│       │       ├── m<module>/                     # Gradescope exports, grouped by module
│       │       │   ├── submissions.zip            # the bulk export as downloaded
│       │       │   └── extracted/                 # the same, unzipped
│       │       └── _unmatched/<name>.zip          # exports whose module could not be told
│       └── anonymized/                # same shape as original/, consented students only, Anon ids
├── autograders/
│   └── <subject><catalog>/m<module>/<course folder>/autograder.zip   # Gradescope autograder snapshots
└── runs/                              # reserved: autograder executions and comparisons
```

`original/` and `anonymized/` have exactly the same shape. Sharing a course
means zipping the course folder and deleting `original/` first.

## 2. Course folder name

`ser222_25sc_12345` is three parts joined by `_`:

| Part | Meaning | Source |
| --- | --- | --- |
| `ser222` | subject and catalog number, lower case | Canvas course code, or the myASU catalog search |
| `25sc` | two-digit year, term letter, session letter | Canvas course code `2026FallC-…` or myASU term code `2267` plus the section's session |
| `12345` | myASU class number (the section); any run of digits | Canvas course code, or the roster selection |

Term letters: `s` Spring, `u` Summer, `f` Fall, `w` Winter. The session letter
is omitted when unknown (`ser222_25s_12345`).


## 3. Assignment folder name

`<canvas assignment id>_m<module number>`, for example `7216983_m4`. The module
number is parsed from the assignment name (`"Module 4: Cairn"`, `"Mod 4: ADJ
Problem Set"`); an assignment whose name does not start that way is stored as
the id alone (`7216983`).

## 4. manifest.json

Written by GAVEL, updated after every download.
`docs/manifest.schema.json` is the formal schema. Top level:

| Field | Meaning |
| --- | --- |
| `schema_version` | `1`. Bump when the shape changes. |
| `course` | The folder name parts plus `term_code`, `canvas_course_id`, `canvas_course_name`, `canvas_course_code`. |
| `created_at`, `updated_at` | ISO 8601 UTC. |
| `gavel_version` | The GAVEL build that last wrote the file. |
| `modules` | Canvas modules (`id`, `name`) for the course. |
| `assignments` | One entry per Canvas assignment seen: `canvas_id`, `name`, `module_number`, `has_rubric`, and `due_at`, `points_possible`, `gradescope_name` when known. |
| `artifacts` | One entry per downloaded file: `kind`, `path` (relative to the course folder, `/` separators), `downloaded_at`, `sha256`, `size_bytes`, `source_id` (quiz or assignment id), `label` (quiz title or Gradescope assignment name when the path alone does not say). |

Artifact kinds: `roster`, `gradebook`, `consent_form`, `quiz`,
`rubric_definition`, `rubric_assessments`, `submissions`, `autograder`.

## 5. Re-downloading

A course is downloaded once. If a file is already present on disk or listed in
the manifest, the download stops with:

> `original/gradebook.csv` was already downloaded for SER 222 (ser222_25sc_12345).
> To refresh it, delete the course folder … and download again.

## 6. Reading a course folder from code

```python
from pathlib import Path
from GAVEL.app.workspace import CourseDataset, CourseKey, Workspace

folder = Workspace(Path("~/Downloads/GAVEL").expanduser()).course(
    CourseKey.parse("ser222_25sc_12345")
)
data = CourseDataset.original(folder, ctx.services.dataset_readers)

roster = data.roster()  # list[RosterStudent]
gradebook = data.gradebook()  # CanvasGradebook
consent = data.consent_form()  # Sequence[ConsentFormEntry]
for entry in data.assignments():  # AssignmentEntry, from the manifest
    definition = data.rubric_definition(entry.canvas_id)  # RubricDefinition | None
    scores = data.rubric_assessments(entry.canvas_id)  # tuple[RubricAssessment, ...]
    submissions = data.gradescope_submissions(entry.canvas_id)  # list[GradescopeSubmission]
```

`CourseDataset.anonymized(folder, readers)` reads the other tree with the same
calls. A file that was never downloaded raises `MissingArtifactError`.

## 7. Writing into a course folder from a use case

```python
from GAVEL.app.workspace import guard_not_downloaded, record

target = folder.original.gradebook_csv
guard_not_downloaded(folder, target, overwrite=request.overwrite)  # ArtifactExistsError
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(csv_bytes)
record(folder, "gradebook", target)  # updates manifest.json
```

Use cases take a `CourseFolder`
## 8. From the GUI and the CLI

The Download page names the course folder from its selections and shows the result
under the workspace path as `Course folder: courses/ser222_25sc_12345`, or the reason
it cannot yet. The order is: the selected Canvas course SIS code (with the roster
class number picking the section of a cross-listed course), then the roster term plus a
catalog search result. A Canvas id or class number typed by hand is not enough, but a
course folder name typed into the override field under the workspace path always wins;
use it for training courses and renamed courses.

Every CLI download command takes `--workspace` (default `DEFAULT_OUTPUT_DIR`),
`--course-folder` (for example `ser222_25sc_12345`) and `--overwrite`. Canvas commands
derive the course folder from `--course-id` when `--course-folder` is omitted;
`roster download` derives it from the term and the looked-up section, and needs
`--course-folder` in `--class-number` mode.

Gradescope exports are grouped by the module number in the Gradescope assignment name
(`Module 2: Programming` goes to `submissions/m2/`), because the assignment that carries
the rubric and the one Gradescope grades are usually different Canvas assignments in
the same module. The zip is kept and also extracted next to itself. An export whose
module cannot be told is kept in `original/submissions/_unmatched/` and still recorded
in the manifest. Autograder zips go to the workspace-level `autograders/` area; their
manifest paths are relative to the workspace root and start with `autograders/`.
