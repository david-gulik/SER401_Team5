# Rubric Assessment Anonymizer

## 1. Overview

`AnonymizeRubricAssessmentUseCase` supports rubric-level grade data. It handles filtering, ID masking, and output randomization for per-criterion Canvas rubric assessments so that palantir can include rubric data in its anonymized research dataset.

---

## 2. Location

| Item         | Path                                                                 |
|--------------|----------------------------------------------------------------------|
| Use case     | `IVE/GAVEL/app/usecases/anonymize_rubric_assessment.py`             |
| DTO          | `IVE/GAVEL/app/dtos/rubric_assessment.py`                           |

---

## 3. How to Call It

```python
from GAVEL.app.usecases.anonymize_rubric_assessment import (
    AnonymizeRubricAssessmentRequest,
    AnonymizeRubricAssessmentUseCase,
)

result = AnonymizeRubricAssessmentUseCase().execute(
    AnonymizeRubricAssessmentRequest(
        assessments=tuple(assessments),  # tuple[RubricAssessment, ...]
        consented_ids=tuple(consented),  # tuple[int, ...] — real Canvas user IDs
        id_map=tuple(map_ids.items()),  # tuple[tuple[int, int], ...] — real → anonymous
    )
)

# result.assessments      — anonymized tuple[RubricAssessment, ...]
# result.skipped_count    — assessments whose student_id was not found in id_map
# result.excluded_count   — assessments whose student_id was not in consented_ids
```

### Parameters

| Parameter       | Type                            | Description                                                          |
|-----------------|---------------------------------|----------------------------------------------------------------------|
| `assessments`   | `tuple[RubricAssessment, ...]`  | Raw rubric assessments fetched from Canvas                           |
| `consented_ids` | `tuple[int, ...]`               | Real Canvas user IDs for students who consented to participate       |
| `id_map`        | `tuple[tuple[int, int], ...]`   | Mapping of real Canvas user ID → 4-digit anonymous ID               |

### Result Fields

| Field            | Type                            | Description                                                          |
|------------------|---------------------------------|----------------------------------------------------------------------|
| `assessments`    | `tuple[RubricAssessment, ...]`  | Anonymized assessments in randomized order                           |
| `skipped_count`  | `int`                           | Number of assessments skipped because student_id was not in id_map  |
| `excluded_count` | `int`                           | Number of assessments excluded because student_id was not consented  |

---

## 4. What It Does

### Transformations

| Field          | Transformation                                          |
|----------------|---------------------------------------------------------|
| `student_id`   | Replaced with 4-digit anonymous ID from `id_map`       |
| `submission_id`| Replaced with synthetic ID: `30000 + anonymous_id`     |
| `criteria`     | Preserved unchanged — not PII                          |

### Filtering Logic

- **Unmapped IDs** — if `student_id` is not present in `id_map`, the assessment is skipped and counted in `skipped_count`. This is not raised as an error.
- **Non-consented students** — if `student_id` is not present in `consented_ids`, the assessment is excluded and counted in `excluded_count`.
- **Empty criteria** — assessments with no criteria are retained and passed through unchanged.

### Output

- Returns a `tuple[RubricAssessment, ...]` in randomized order
- Does not write any files — the caller is responsible for persisting the output



This use case is intended to be wired into the `process()` function in palantir-util-public. The caller should:

1. Fetch rubric assessments from Canvas using its existing mechanism
2. Build `consented_ids` from the output of `find_consented()`
3. Build `id_map` from the output of `generate_id_map()`
4. Call `AnonymizeRubricAssessmentUseCase().execute()` with those inputs
5. Serialize and write `result.assessments` to `data_processed/`

> **Note:** `student_id` in `RubricAssessment` is the Canvas internal user ID. Confirm this aligns with how `map_ids` is keyed in palantir before wiring in the integration.