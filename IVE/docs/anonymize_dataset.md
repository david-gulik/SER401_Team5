# Anonymize Course Dataset

## 1. Overview

The `anonymize` CLI command runs GAVEL's anonymization pipeline on a downloaded course dataset.

It uses the consent form to determine which students should be included, generates one shared anonymous ID map, anonymizes the supported course artifacts, and writes the results to a separate `anonymized/` folder.

The original files are not modified.

---

## 2. Running the Command

Run the following from the `IVE/` directory:

```bash
python -m GAVEL.cli.main anonymize run \
    --dataset-dir <PATH>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--dataset-dir` | Yes | Path to the downloaded course snapshot directory |

### Example

```bash
python -m GAVEL.cli.main anonymize run \
    --dataset-dir GAVEL/courses/ser222_25sc_12345/20260901T1430
```

---

## 3. Expected Dataset Structure

The path provided to `--dataset-dir` should point to a course snapshot directory.

Example:

```text
snapshot/
├── original/
│   ├── consent_form.csv
│   ├── roster.csv
│   ├── gradebook.csv
│   └── assignments/
│       └── 7216983_m1/
│           └── rubric_assessment_12345_7216983.json
└── anonymized/
```

The consent form is required.

The roster, gradebook, and rubric assessment files are optional. Missing optional artifacts are skipped and reported in the command summary.

---

## 4. Output

Anonymized files are written to:

```text
snapshot/anonymized/
```

The anonymized output follows the same dataset structure where applicable.

Example:

```text
snapshot/
├── original/
│   └── ...
└── anonymized/
    ├── consent_form.csv
    ├── roster.csv
    ├── gradebook.csv
    └── assignments/
        └── 7216983_m1/
            └── rubric_assessment_12345_7216983.json
```

The original files remain unchanged.

---

## 5. Summary Output

After the pipeline finishes, the CLI prints a summary for each artifact.

Example:

```text
Anonymized dataset written to GAVEL/courses/ser222_25sc_12345/20260901T1430/anonymized

Consent form: 10 processed, 0 skipped, 2 excluded
Roster: 10 processed, 0 skipped, 2 excluded
Gradebook: 10 processed, 0 skipped, 2 excluded
Rubric assessments: 25 processed, 0 skipped, 5 excluded
```

### Summary Fields

| Field | Description |
|-------|-------------|
| `processed` | Records successfully included in the anonymized output |
| `skipped` | Records or artifacts that could not be processed or were missing |
| `excluded` | Records excluded because the student was not included in the consent set |

---

## 6. Errors

### Missing Dataset Directory

If the path provided to `--dataset-dir` does not exist:

```text
Dataset directory does not exist: <PATH>
```

The command exits with code `2`.

### Invalid Dataset Path

If the provided path is not a directory:

```text
Dataset path is not a directory: <PATH>
```

The command exits with code `2`.

### Missing Consent Form

If the dataset does not contain:

```text
original/consent_form.csv
```

the command prints:

```text
Invalid dataset: Consent form is missing from the dataset
```

The command exits with code `2`.

---

## 7. How It Works

The anonymization pipeline performs the following steps:

1. Loads the consent form.
2. Determines the set of consented students.
3. Generates one shared anonymous ID map.
4. Anonymizes the consent form.
5. Anonymizes the roster if present.
6. Anonymizes the gradebook if present.
7. Anonymizes rubric assessments if present.
8. Writes all anonymized output to the `anonymized/` directory.
9. Prints processed, skipped, and excluded counts for each artifact.