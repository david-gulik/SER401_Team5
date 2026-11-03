
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from enum import Enum
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import logging

#TODO: figure out C stuff

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
    JAVA = 1
    C = 2


def grade_one_submission(filename, config, lang, autograder_root, input_folder, output_folder):
    """
    Runs the autograder for a single submission in a fully isolated worker directory.
    """

    print(f"Starting autograder for {filename}...")

    # clone workspace
    worker_root = os.path.join(
        "/tmp",
        f"autograder_worker_{filename.split('.')[0]}_{os.getpid()}"
    )
    shutil.copytree(autograder_root, worker_root)

    #
    # config_proj_loc = config["project_location"][:-1].replace("/", os.sep)
    #
    # if lang == Language.JAVA:
    #     worker_src = os.path.join(worker_root, config_proj_loc[19:])
    # else:
    #     worker_src = os.path.join(worker_root, config_proj_loc[12:])
    project_location = config["project_location"].rstrip("/").replace("/", os.sep)
    worker_src = os.path.join(worker_root, project_location)


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
                print(f"  Missing required file: {req} in {filename}")
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
                    print(f"  Skipping {len(skipped)} files in ZIP ({skipped})")

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
                shell=True
            )

            parsed = json.loads(result.stdout)
            parsed.append("hello!")
            with open(output_path, "w") as out:
                json.dump(parsed, out, indent=4)

        else:  # C autograder
            log_path = os.path.splitext(output_path)[0] + "_stdout.txt"
            results_path = os.path.join(worker_root, "results", "results.json")

            if os.path.exists(results_path):
                os.remove(results_path)

            with open(log_path, "w") as out:
                subprocess.run(
                    [sys.executable, "main.py"],
                    cwd=worker_root,
                    stdout=out,
                    shell=False
                )

            shutil.copy(results_path, output_path)

    finally:
        # clean up directory
        shutil.rmtree(worker_root, ignore_errors=True)

    return f"{filename}: done"


def autograde_submissions_folder(lang, input_folder, output_folder, autograder_folder_arg):

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    log = logging.getLogger("autograder_client")
    log.info(f"Autograding started on {input_folder}...")

    start = time.perf_counter()

    config_file_location = os.path.join(autograder_folder_arg, "config.json")

    with open(config_file_location) as file:
        config = json.load(file)

    # Determine autograder root
    autograder_root = autograder_folder_arg

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Collect submissions
    # submissions = [
    #     f for f in os.listdir(input_folder)
    #     if f.endswith(".java") or f.endswith(".c") or f.endswith(".zip")
    # ]
    submissions = [
        f for f in os.listdir(input_folder)
        if os.path.isdir(os.path.join(input_folder, f))
    ]

    log.info(f"Found {len(submissions)} submissions.")

    # Parallel execution
    #TODO: is this max_workers count acceptable? Problems would start here...

    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        futures = [
            pool.submit(
                grade_one_submission,
                filename,
                config,
                lang,
                autograder_root,
                input_folder,
                output_folder
            )
            for filename in submissions
        ]

        for fut in as_completed(futures):
            print(fut.result())

    print(f"Time taken: {time.perf_counter() - start}")

# testing area
if __name__ == "__main__":
    autograde_submissions_folder(
        Language.JAVA,
        "../../../../data_original/10_24_autograder_test",
        "../../../../data_original/10_24_autograder_test/output",
        "../../../../data_original/10_22_autograder"
    )
