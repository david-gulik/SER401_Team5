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
If Chrome is not already signed in to ASU, you will be prompted to log in to Canvas and authenticate via Duo.
The login is shared with the roster download and remembered between runs; see "Staying signed in" in 
`docs/roster_download_guide.md` for how that works and how to turn it off.
The gradescope_client will download the bulk submission export to the given folder.

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

Exports are staged under the course folder and then filed by module
(see `docs/workspace_layout.md`):

```
<workspace>/courses/<course folder>/original/submissions/m<module>/submissions.zip
<workspace>/courses/<course folder>/original/submissions/m<module>/extracted/
<workspace>/autograders/<subject><catalog>/m<module>/<course folder>/autograder.zip
```

The module comes from the Gradescope assignment name (`Module 2: Programming`), or
failing that from the Canvas assignment with the same name. An export whose module
cannot be told is kept in `original/submissions/_unmatched/` and still recorded in
`manifest.json`, so nothing downloaded is lost.

`gradescope download` takes the shared `--workspace`, `--course-folder` and
`--overwrite` arguments. The course folder is derived from `--course-id` through the
Canvas course code; `SUBMISSIONS_FOLDER` is no longer used by this command.
