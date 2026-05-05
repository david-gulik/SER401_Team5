# Gradebook CSV Download Guide

This guide walks through downloading a Canvas course gradebook CSV using the GAVEL CLI.

---

## Prerequisites checklist

- [ ] Python environment is set up and `GAVEL` is installed/runnable
- [ ] `IVE/.env` contains the required Canvas configuration (see Configuration below)
- [ ] You have access to a valid Canvas API token
- [ ] You know the Canvas course ID for the course you want to export

---

## Configuration

Add the following values to `IVE/.env`:

CANVAS_BASE_URL=https://canvas.asu.edu  
CANVAS_TOKEN=YOUR_CANVAS_API_TOKEN  


---

## Step-by-step checklist

### 1. Confirm your course ID

Make sure you know the numeric Canvas course ID.

Example:
- 253450

---

### 2. Run the gradebook download command

From the project root, run:
```bash
python -m GAVEL.cli.main canvas-gradebook download \
  --course-id <COURSE_ID> \
  --output <OUTPUT_FILE>
```

Example:
```bash
python -m GAVEL.cli.main canvas-gradebook download \
  --course-id 253450 \
  --output gradebook.csv
```
---

### 3. Verify the output

- The CLI prints: `Gradebook CSV saved to gradebook.csv`
-  The CSV file is created at the path you specified
-  Open the file in Excel or a text editor
-  Confirm expected student rows and grade columns are present

---

## Flags reference

| Flag | Required | Description |
|------|----------|------------|
| --course-id | Yes | Numeric Canvas course identifier |
| --output | Yes | Path where the CSV file will be written |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|--------|--------------|-----|
| course_id must be a valid integer. | Invalid input | Use a numeric course ID |
| course_id must be greater than zero. | Invalid input | Use a positive course ID |
| Failed to download gradebook CSV: ... | API/auth issue | Check CANVAS_BASE_URL and CANVAS_TOKEN |
| CSV file not created | Invalid output path or runtime error | Verify path and rerun |

---

## Environment variable reference

All variables go in `IVE/.env`.

| Variable | Required | Description |
|----------|----------|------------|
| CANVAS_BASE_URL | Yes | Base Canvas URL (e.g., https://canvas.asu.edu) |
| CANVAS_TOKEN | Yes | Canvas API token used for authentication |
| CANVAS_ACCOUNT_ID | No | Not required for gradebook CSV export |

---

## Notes

- The CSV is written directly to the specified output path.
- Both `--course-id` and `--output` are required.
- Output directories must exist prior to running the command.