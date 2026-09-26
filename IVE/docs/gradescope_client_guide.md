# Gradescope_Client Guide

This guide walks through the use of gradescope_client.py to download the bulk submission export for a Canvas course. 
This bulk submission .zip file contains the latest submission from each student in the class along with the submission 
info YML file containing rubric-level autograder results.

## Prerequisites Checklist

- [ ] Python environment is set up and `GAVEL` is installed/runnable
- [ ] Google Chrome is installed
- [ ] ChromeDriver matching your Chrome version is on your `PATH`
- [ ] You have faculty-level access to the course on Canvas

## Usage

From your GAVEL folder, run 

`python3 app/ports/gradescope_client.py [courseID]`

from the Terminal. The [courseID] variable is the six-digit number assigned to the course on Canvas. 
You will be prompted via Chrome to log in to Canvas, and authenticate via Duo. (#TODO: Implement Duo persistence to 
avoid repeated downloads.) The gradescope_client will download the bulk submission export to the given folder.

## Example

`python3 app/ports/gradescope_client.py 253450`

## Download Nomenclature

Download zips are named after their assignment name. 
Future updates will provide more granular naming, including year/semester data.

## Environmental Variable References

Variables are stored in `IVE.env`.

| Variable             | Default | Description                             |
|----------------------| --- |-----------------------------------------|
| `SUBMISSIONS_FOLDER` | _(none)_ | Filepath to desired submissions folder. |

## Where the files go

Exports are staged under the course folder and then filed by Canvas assignment
(see `docs/workspace_layout.md`):

```
<workspace>/courses/<course folder>/original/assignments/<assignment id>_m<module>/submissions.zip
<workspace>/courses/<course folder>/original/assignments/<assignment id>_m<module>/autograder.zip
```

A Gradescope assignment is matched to a Canvas assignment by name (case and
punctuation ignored, a trailing `(Gradescope)` on the Canvas side ignored). Anything
that cannot be matched is kept in `original/assignments/_unmatched/` and still
recorded in `manifest.json`, so nothing downloaded is lost.

`gradescope download` takes the shared `--workspace`, `--course-folder` and
`--overwrite` arguments. The course folder is derived from `--course-id` through the
Canvas course code; `SUBMISSIONS_FOLDER` is no longer used by this command.
