"""
shoggoth-validation - preparation.py

Contains various helpers for manipulating autograder submissions in bulk.

Requires a local configuration to be specified, see after imports.

The most common task is to generate JSON for a folder of submissions. The typical workflow is:
1) Use rename_canvas_submission_files to do initial processing (module_0raw -> module_1renamed).
2) Make a manual copy of module_1renamed to module_2patched.
3) Make any needed corrections to the files in module_2patched.
4) Run run_shoggoth_bulk to run the local shoggoth to generate JSON for all submissions.

where module is a placeholder for something more speific like (ser334_24sc_m2).

See main for an example.

"""

__author__ = "Ruben Acuna"
__copyright__ = "Copyright 2024-25, Ruben Acuna"

import glob
import os
import platform
import shutil
import sys
import subprocess
import json
import zipfile
from enum import Enum
from pathlib import Path

import constants

# LOCAL CONFIGURATION
if platform.system() == "Windows":
    FOLDER_SER222_AUTOGRADERS = (
        "C:\\Users\\Ruben\\Dropbox\\Git\\ser222\\homework_projects"
    )
    FOLDER_SER334_AUTOGRADERS = None
elif platform.system() == "Linux":
    FOLDER_SER222_AUTOGRADERS = None
    FOLDER_SER334_AUTOGRADERS = "/home/ruben/Git/ser334/homework_projects"
else:
    print(f"Unsupported OS found: {platform.system()}")
    exit()


class Language(Enum):
    JAVA = 1  # only tested on Windows
    C = 2  # only tested on Linux


def rename_canvas_submission_files(input_folder, output_folder):
    r"""
    This function converts the default Canvas files into the simpler form listed in the assignment. Trims the prefix and
    removes -# from the end of files. Assumes that the input is a folder of source files, one file per submission.

    The usual usage is to process a folder of submissions (input_folder) from Canvas:
        Example: data_original\submissions\ser334_24sc_m2_0raw
    and then put the renamed files into a new folder (output_folder):
        Example: data_original\submissions\ser334_24sc_m2_1renamed

    :param input_folder: Folder of submissions from Canvas.
    :param output_folder: Folder for renamed files.
    """
    # TODO: delete previous contents of output folder.

    for filename in os.listdir(input_folder):
        new_name = filename.replace("-1", "")
        new_name = new_name.replace("-2", "")

        new_name = new_name.split("_")[-1]

        if os.path.exists(output_folder + os.sep + new_name):
            print(f"target file name {new_name} already exists.")
            continue

        shutil.copy(input_folder + os.sep + filename, output_folder + os.sep + new_name)


def strip_gradescope_comments(assignment_in: str) -> str:
    """
    Method for taking in a C or Java file and stripping it of comments for privacy purposes

    :param assignment_in: string representation of assignment, to be stripped of comments
    :return: that same assignment but without comments
    """

    # instantiate some stuff; an output string, a counter, the length of the original string, a "normal" state,
    # and a blocker for following quotes

    out = []
    i = 0
    n = len(assignment_in)
    state = "normal"
    quote_char = None

    # go through string and set state based on a combination of present state and incoming characters

    while i < n:
        # set pointers
        c = assignment_in[i]
        nxt = assignment_in[i + 1] if i + 1 < n else ""

        # if "normal" state (that is, in a state of parsing code)
        if state == "normal":
            # if "//" detected, change state to line_comment and bypass the "//"
            if c == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            # if "/*" detected, change state to block_comment and bypass the "/*"
            if c == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            # if apostrophes detected, change state to "string" and add to output
            if c in ('"', "'"):
                state = "string"
                quote_char = c
                out.append(c)
                i += 1
                continue
            # finally, append output with current character and move on
            out.append(c)
            i += 1

        # escape condition for line_comment
        elif state == "line_comment":
            if c == "\n":
                state = "normal"
                out.append(c)
            i += 1

        # escape condition for block_comment
        elif state == "block_comment":
            # add line spaces if newlines appear in block comment
            if c == "\n":
                out.append("\n")
                i += 1
                continue
            if c == "*" and nxt == "/":
                state = "normal"
                i += 2
            else:
                i += 1

        # escape condition for string
        elif state == "string":
            out.append(c)
            if c == "\\":  # escape next char
                if i + 1 < n:
                    out.append(assignment_in[i + 1])
                    i += 2
                else:
                    i += 1
            elif c == quote_char:
                state = "normal"
                i += 1
            else:
                i += 1

    # return output without comments!
    return "".join(out)


def anonymize_gradescope_submissions(input_folder: str, output_folder: str):
    """
    Method for scanning input_folder for Java/C files, stripping out comments, and writing anonymized
    versions to output_folder with '_anon' suffixes.
    """
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    # Create output folder if it doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)

    file_extensions = {".java", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp"}

    if not input_folder.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_folder}")

    # for each file, if either the file is NOT a file (that is, a folder, shortcut, etc.), OR if the file is
    # not a Java or C/C++ file, skip it
    for path in input_folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in file_extensions:
            continue

        # Read text from file
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")

        # Strip comments
        cleaned = strip_gradescope_comments(text)

        # Add _anon suffix to filename, create output path using provided folder
        rel = path.relative_to(input_folder)
        anon_name = rel.with_name(rel.stem + "_anon" + rel.suffix)
        out_path = output_folder / anon_name

        # Ensure directory exists
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Write anonymized file
        out_path.write_text(cleaned, encoding="utf-8")

        print(f"Gradescope Submissions Processed: {path} -> {out_path}")


def run_shoggoth_bulk(course, lang, config_file, semester):
    r"""
    Runs a local installation of a shoggoth java or c autograder on a folder of submissions and saves the results in
    JSON. Supports either single source file submission or .zip containers.

    For this to function, there must a local copy of the shoggoth autograder. Its location has to be configured at the
    top of this file.

    There must also be a folder of submissions at:
        constants.FOLDER_SUBMISSIONS + os.sep + "{course}_{semester}_{module}_2patched"
    For example:
        data_original\submissions\ser334_24sc_m2_2patched

    :param course: Short name for the course.
    :param lang: the programming used for the assignment.
    :param config_file: Config from autograder.
    :param semester: Semester ID for data (e.g., 24sc).
    """

    print("run_shoggoth_bulk:")

    with open(config_file) as file:
        config = json.load(file)

    module = config["module"]
    uid = config["uid"]
    config_proj_loc = config["project_location"][:-1].replace("/", os.sep)

    input_folder = (
        constants.FOLDER_SUBMISSIONS + os.sep + f"{course}_{semester}_{module}_2patched"
    )
    output_folder = (
        constants.FOLDER_EVALUATIONS + os.sep + f"{course}_{semester}_{module}"
    )

    if lang == Language.JAVA:
        autograder_root = (
            FOLDER_SER222_AUTOGRADERS + os.sep + f"{course}_{uid}_hw02_autograder"
        )
        autograder_src = autograder_root + os.sep + config_proj_loc[19:]

    else:  # C
        autograder_root = (
            FOLDER_SER334_AUTOGRADERS + os.sep + f"{course}_{uid}_hw02_autograder"
        )
        autograder_src = FOLDER_SER334_AUTOGRADERS + os.sep + config_proj_loc[12:]

    # TODO: support optional files
    if "files_optional" in config and len(config["files_optional"]) > 0:
        raise Exception("run_shoggoth_bulk() does not support optional files.")

    # check if output folder exists
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)

    # check if target folder for submission source code exists
    if not os.path.exists(autograder_src):
        os.mkdir(autograder_src)

    for filename in os.listdir(input_folder):
        if not (".java" in filename or ".c" in filename or ".zip" in filename):
            continue

        print("Processing " + filename)
        output_filename = filename.split(".")[0] + ".json"

        # clean the project folder of existing files.
        if lang == Language.C:
            existing_files = glob.glob(autograder_src + os.sep + "*")
            for file_path in existing_files:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)

        if ".java" in filename or ".c" in filename:
            target_file_path = autograder_src + os.sep + config["files_required"][0]

            if os.path.exists(target_file_path):
                os.remove(target_file_path)

            shutil.copy(input_folder + os.sep + filename, target_file_path)
        else:  # must be .zip
            # remove existing files. to ensure that all files are refreshed (even if zip is incomplete).
            for required_file in config["files_required"]:
                expected_file = autograder_src + os.sep + required_file

                if os.path.exists(expected_file):
                    os.remove(expected_file)

            # extract files into target file. probably check if all are there
            with zipfile.ZipFile(input_folder + os.sep + filename, "r") as zipf:
                compressed_files = zipf.namelist()
                selected_files = [
                    x for x in compressed_files if x in config["files_required"]
                ]
                skipped_files = [
                    x for x in compressed_files if x not in config["files_required"]
                ]

                if len(skipped_files):
                    print(
                        f"  Skipping {len(skipped_files)} files in ZIP ({skipped_files})."
                    )

                zipf.extractall(autograder_src, members=selected_files)

        output_path = output_folder + os.sep + output_filename
        print("  output_path:", output_path)

        # check if we actually need to generate JSON
        if not os.path.exists(output_path):
            if lang == Language.JAVA:
                # the console output of shoggoth-c is the JSON result.
                with open(output_path, "w") as output_stream:
                    arg = [
                        "mvn",
                        "-q",
                        "compile",
                        "exec:java",
                    ]  # force recompile so that tests don't run with previous bins.
                    p = subprocess.run(
                        arg, shell=True, cwd=autograder_root, stdout=output_stream
                    )

            else:  # C
                # the console output of shoggoth-c is the human-readable test summery.
                log_path = os.path.splitext(output_path)[0] + "_stdout.txt"

                # shoggoth-c saves the results to a separate JSON file.
                results_path = (
                    FOLDER_SER334_AUTOGRADERS
                    + os.sep
                    + "results"
                    + os.sep
                    + "results.json"
                )

                if os.path.exists(results_path):
                    os.remove(results_path)

                with open(log_path, "w") as output_stream:
                    arg = [sys.executable, "main.py"]
                    p = subprocess.run(
                        arg, shell=False, cwd=autograder_root, stdout=output_stream
                    )

                shutil.copy(results_path, output_path)

        else:
            print("  JSON output already exists, skipping autograder.")


# testing area
if __name__ == "__main__":
    # SER222
    # run_shoggoth_bulk("ser222", Language.JAVA, "config_m12.json", "24su")

    # SER334
    # rename_canvas_submission_files(constants.FOLDER_SUBMISSIONS + os.sep + "ser334_24sc_m2_0raw", constants.FOLDER_SUBMISSIONS + os.sep + "ser334_24sc_m2_1renamed")
    # run_shoggoth_bulk("ser334", Language.C, constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_config_m2.json", "24sc")

    # SER334 M3 (developmental test set)
    # run_shoggoth_bulk("ser334", Language.C, constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_config_m3.json", "00dv")

    # fall c 2024
    run_shoggoth_bulk(
        "ser334",
        Language.C,
        constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_config_m3.json",
        "24fc",
    )
