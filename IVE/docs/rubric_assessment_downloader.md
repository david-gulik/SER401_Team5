# Rubric Assessment Downloader

## 1. Environment Setup

Before running any commands, create a `.env` file in the `IVE/` directory with the following variables:

| Variable         | Required | Description                                              |
|------------------|----------|----------------------------------------------------------|
| `CANVAS_BASE_URL` | Yes      | Base URL of your Canvas LMS instance (e.g. `https://canvas.asu.edu`) |
| `CANVAS_TOKEN`    | Yes      | Your Canvas API access token                             |

---

## 2. Running the Rubric Assessment Download Command

Run the following from the `IVE/` directory:

```
python -m GAVEL.cli.main rubric download \
    --course-id <ID> \
    --assignment-id <ID> \
    --output <PATH>
```

### Arguments

| Argument        | Required | Description                                                                 |
|-----------------|----------|-----------------------------------------------------------------------------|
| `--course-id`   | Yes      | Canvas course ID — found in the URL: `canvas.asu.edu/courses/<course-id>`  |
| `--assignment-id` | Yes    | Canvas assignment ID — found in the URL: `.../assignments/<assignment-id>` |
| `--output / -o` | Yes      | Directory path to save the JSON output (e.g. `rubric_assessments/`)        |

### Example

```
python -m GAVEL.cli.main rubric download \
    --course-id 253450 \
    --assignment-id 7216983 \
    --output rubric_assessments/
```

---

## 3. How It Works

The Canvas Submissions API returns rubric assessment data inline with each submission. GAVEL fetches all submissions for the specified assignment with rubric assessment and user data included, then serializes the results to JSON.

### Step 1 — Fetch Rubric Assessments

```
GET /api/v1/courses/{course_id}/assignments/{assignment_id}/submissions
    ?include[]=rubric_assessment
    &include[]=user
```

Each submission object in the response contains a `rubric_assessment` hash keyed by criterion ID. Submissions that have not yet been graded will not have a `rubric_assessment` key present — these are excluded from the output.

### Step 2 — Serialize to JSON

The assessments are serialized into a flat JSON array and written to:

```
<output_dir>/rubric_assessment_{course_id}_{assignment_id}.json
```

---

## 4. Expected Console Output

On a successful run:

```
[INFO] my_app.cli: Configuring Canvas HTTP client
[INFO] AppServices: Initializing use cases
[RUBRIC] Downloading rubric assessments for course=253450, assignment=7216983...
[RUBRIC] Rubric assessment for course 253450, assignment 7216983 saved to rubric_assessments/rubric_assessment_253450_7216983.json
```

---

## 5. Expected JSON Output

The downloaded file is a JSON array of rubric assessment objects. The following shows the structure of each entry:

```json
[
  {
    "student_id": 309780,
    "submission_id": 9001,
    "criteria": [
      {
        "criterion_id": "340525_8699",
        "points": 2.0,
        "comments": "Q2 Justification: Alignment comment."
      },
      {
        "criterion_id": "340525_5682",
        "points": 2.0,
        "comments": ""
      }
    ]
  }
]
```

### Field Descriptions

| Field          | Description                                                              |
|----------------|--------------------------------------------------------------------------|
| `student_id`   | Canvas internal user ID for the student                                  |
| `submission_id`| Canvas submission artifact ID                                            |
| `criteria`     | List of per-criterion rubric scores                                      |
| `criterion_id` | Canvas rubric criterion ID                                               |
| `points`       | Points awarded for this criterion. `null` if criterion not yet graded    |
| `comments`     | Grader free-text comment. Empty string `""` when no comment was entered  |

> `student_id` is the Canvas internal user ID, not the SIS ID. This is the ID used by `AnonymizeRubricAssessmentUseCase` for consent filtering and ID mapping.

---

## 6. Known Limitations

| Limitation            | Detail                                                                                      |
|-----------------------|---------------------------------------------------------------------------------------------|
| Canvas API Token      | The token must have read access to the specified course and assignment.                     |
| Ungraded Submissions  | Submissions without a rubric assessment are excluded from the output automatically.         |
| Single Assignment     | Each command run downloads assessments for one assignment. Run once per assignment ID.      |