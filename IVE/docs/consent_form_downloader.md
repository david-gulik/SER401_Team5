# Consent Form Downloader

## 1. Environment Setup

Before running any commands, create a `.env` file in the `IVE/` directory with the following variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `CANVAS_BASE_URL`   | Yes | Base URL of your Canvas LMS instance (e.g. `https://canvas.asu.edu`) |
| `CANVAS_TOKEN`      | Yes | Your Canvas API access token |

---

## 2. Running the Quiz Download Command

Run the following from the `IVE/` directory:

```bash
python -m GAVEL.cli.main consent_form download \
    --course-id <ID> \
    --quiz-id <ID>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--course-id` | Yes | Canvas course ID — found in the URL: `canvas.asu.edu/courses/<course-id>` |
| `--quiz-id` | Yes | Canvas quiz ID — found in the URL: `.../quizzes/<quiz-id>` |
| `--workspace` | No | Workspace root. Defaults to `DEFAULT_OUTPUT_DIR` from `.env`, else `~/Downloads/GAVEL` |
| `--course-folder` | See note | Course folder name such as `ser222_25sc_12345`. Canvas commands derive it from `--course-id` when omitted |
| `--overwrite` | No | Replace files already downloaded into the course folder; without it a second download is refused |

### Example

```bash
python -m GAVEL.cli.main consent_form download \
    --course-id 253450 \
    --quiz-id 1960789
```

---

## 3. How It Works

The Canvas Quiz Reports API is asynchronous. The client does not receive the CSV immediately — it must initiate report generation, poll for completion, then download the result. GAVEL handles this automatically in four steps:

### Step 1 — Initiate Report Generation

```http
POST /api/v1/courses/{course_id}/quizzes/{quiz_id}/reports

{
  "quiz_report": {
    "report_type": "student_analysis",
    "includes_all_versions": true,
    "includes_sis_ids": true
  }
}
```

> `includes_sis_ids: true` ensures the `sis_id` column is present in the CSV output. If a report already exists in Canvas for this quiz, the existing report is returned rather than generating a new one — this is expected Canvas behaviour.

### Step 2 — Poll Progress URL

The POST response includes a `progress_url`. GAVEL polls this endpoint every 2 seconds until `workflow_state` reaches `completed`. A `failed` state raises an error. Polling times out after 30 attempts (60 seconds).

```http
GET {progress_url}

Response: { "workflow_state": "queued" | "running" | "completed" | "failed" }
```

### Step 3 — Fetch Report Metadata

```http
GET /api/v1/courses/{course_id}/quizzes/{quiz_id}/reports/{report_id}

Response includes: { "file": { "url": "https://canvas.asu.edu/files/..." } }
```

### Step 4 — Download CSV

The signed file URL from Step 3 is fetched with Bearer token authentication. The raw CSV bytes are written to `original/consent_form.csv` inside the course folder (`<workspace>/courses/<course folder>/`, see `docs/workspace_layout.md`) and recorded in `manifest.json` with the quiz id.

---

## 4. Expected Console Output

On a successful run:

```
[INFO] GAVEL.cli: Configuring Canvas HTTP client
[INFO] GAVEL.cli: AppServices: initializing use cases
[CONSENT_FORM] Downloading consent form for course=253450, quiz=1960789...
[CONSENT_FORM] Consent form for course 253450 saved to C:\Users\you\Downloads\GAVEL\courses\ser222_25sc_12345\original\consent_form.csv
```

---

## 5. Expected CSV Output

The downloaded file is the raw Canvas Quiz Student Analysis CSV. The following shows a sample output from the SER222 SC26 Study Consent Form (Quiz ID 1960789, Course ID 253450):

| Column | Example Value | Description |
|--------|---------------|-------------|
| `name` | Lindy Crain | Student display name in Canvas |
| `id` | 494030 | Canvas internal user ID |
| `sis_id` | 1219749063 | Student SIS ID |
| `section` | TRN-2026Spring-IVECapstone | Course section name |
| `section_id` | 385739 | Canvas section ID |
| `section_sis_id` | TRN-2026Spring-... | Section SIS ID |
| `submitted` | 2026-04-09 03:28:49 UTC | Submission timestamp |
| `attempt` | 1 | Attempt number |
| `...leave blank if you do not consent` | Lindy Crain | Student typed name — consent name field |
| `Do you consent to be included in the study?` | TRUE | Boolean consent answer |
| `n correct` | 2 | Number of correct answers |
| `n incorrect` | 0 | Number of incorrect answers |
| `score` | 0 | Quiz score |

> The question column names are derived directly from the quiz question text in Canvas. No custom formatting is applied — GAVEL returns the raw bytes from the Canvas API.

---

## 6. Known Limitations

| Limitation | Detail |
|------------|--------|
| Canvas API Token | The token must have read access to the specified course and quiz. |
| Polling Timeout | Report generation is polled for up to 60 seconds (30 attempts at 2-second intervals). Very large quizzes may exceed this window. |
