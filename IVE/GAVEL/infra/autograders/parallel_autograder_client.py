import json
import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from enum import Enum
from pathlib import Path

# TODO: figure out C stuff

class Language(Enum):
    JAVA = 1
    C = 2


def grade_one_submission(filename, config, lang, autograder_root, input_folder, output_folder):
    """
    Runs the autograder for a single submission in a fully isolated worker directory.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("autograder_client")
    start = time.perf_counter()

    log.info(f"Starting autograder for {Path(filename).name}...")

    # clone workspace
    worker_root = os.path.join("/tmp", f"autograder_worker_{filename.split('.')[0]}_{os.getpid()}")
    shutil.copytree(autograder_root, worker_root)

    # TODO: better version of extracting worker src files
    config_proj_loc = config["project_location"][:-1].replace("/", os.sep)

    if lang == Language.JAVA:
        worker_src = os.path.join(worker_root, config_proj_loc[19:])
    else:
        worker_src = os.path.join(worker_root, config_proj_loc[12:])

    os.makedirs(worker_src, exist_ok=True)

    required_files = config["files_required"]
    submission_path = os.path.join(input_folder, filename)
    if os.path.isdir(submission_path):
        # Folder submission
        for req in required_files:
            src = os.path.join(submission_path, req)
            dst = os.path.join(worker_src, req)

            if os.path.exists(dst):
                os.remove(dst)

            if os.path.exists(src):
                shutil.copy(src, dst)
            else:
                log.info(f"  Missing required file: {req} in {filename}")
    else:
        if filename.endswith(".java") or filename.endswith(".c"):
            target_file = os.path.join(worker_src, required_files[0])
            if os.path.exists(target_file):
                os.remove(target_file)
            shutil.copy(submission_path, target_file)

        else:
            for req in required_files:
                p = os.path.join(worker_src, req)
                if os.path.exists(p):
                    os.remove(p)

            with zipfile.ZipFile(submission_path, "r") as zipf:
                compressed = zipf.namelist()
                selected = [x for x in compressed if x in required_files]
                skipped = [x for x in compressed if x not in required_files]

                if skipped:
                    log.info(f"  Skipping {len(skipped)} files in ZIP ({skipped})")

                zipf.extractall(worker_src, members=selected)

    output_filename = filename.split(".")[0] + ".json"
    output_path = os.path.join(output_folder, output_filename)

    if os.path.exists(output_path):
        shutil.rmtree(worker_root, ignore_errors=True)
        return f"{filename}: already exists"

    try:
        if lang == Language.JAVA:
            result = subprocess.run(
                ["mvn", "-q", "compile", "exec:java"],
                cwd=worker_root,
                capture_output=True,
                text=True,
                shell=True,
            )

            parsed = json.loads(result.stdout)
            with open(output_path, "w") as out:
                json.dump(parsed, out, indent=4)

        else:  # C autograder
            log_path = os.path.splitext(output_path)[0] + "_stdout.txt"
            results_path = os.path.join(worker_root, "results", "results.json")

            if os.path.exists(results_path):
                os.remove(results_path)

            with open(log_path, "w") as out:
                subprocess.run(
                    [sys.executable, "main.py"], cwd=worker_root, stdout=out, shell=False
                )

            shutil.copy(results_path, output_path)

    finally:
        # clean up directory
        shutil.rmtree(worker_root, ignore_errors=True)
    time_elapsed = time.perf_counter() - start
    return f"{filename}: done (elapsed time: {time_elapsed} seconds)"


def autograde_submissions_folder(lang, input_folder, output_folder, autograder_folder_arg) -> float | type[Exception]:

    """
    :param lang: programming language, "Language.JAVA" or "Language.C"
    :param input_folder: submissions input folder
    :param output_folder: desired output folder
    :param autograder_folder_arg: autograder folder
    :return: time elapsed
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("autograder_client")
    log.info(f"Autograding started on {Path(input_folder).name} using {Path(autograder_folder_arg).name}...")

    start = time.perf_counter()

    config_file_location = os.path.join(autograder_folder_arg, "config.json")

    with open(config_file_location) as file:
        config = json.load(file)

    # Determine autograder root
    autograder_root = autograder_folder_arg

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    submissions = [
        f for f in os.listdir(input_folder) if os.path.isdir(os.path.join(input_folder, f))
    ]

    course_specific_output_folder = os.path.join(
        output_folder, os.path.basename(autograder_folder_arg)
    )
    os.makedirs(course_specific_output_folder, exist_ok=True)

    log.info(f"Found {len(submissions)} submissions for {Path(input_folder).name}.")
    completed_tasks = 0
    # Parallel execution
    # TODO: is this max_workers count acceptable? Problems would start here...
    try:
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:

            futures = [
                pool.submit(
                    grade_one_submission,
                    filename,
                    config,
                    lang,
                    autograder_root,
                    input_folder,
                    course_specific_output_folder,
                )
                for filename in submissions
            ]

            for fut in as_completed(futures):
                completed_tasks += 1
                log.info(f"{fut.result()} ({completed_tasks}/{len(futures)})")


        log.info(f"Autograding complete! ({Path(input_folder).name} using autograder {Path(autograder_folder_arg).name}.)")
        return time.perf_counter() - start
    except Exception as e:
        log.warning(f"Autograding failed!! ({Path(input_folder).name} using autograder {Path(autograder_folder_arg).name}.)")
        return Exception


# testing area
if __name__ == "__main__":
    autograde_submissions_folder(
        Language.JAVA,
        "../../../../data_original/10_24_autograder_test",
        "../../../../data_original/10_24_autograder_test/output",
        "../../../../data_original/10_22_autograder",
    )
