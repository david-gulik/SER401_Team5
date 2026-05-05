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
