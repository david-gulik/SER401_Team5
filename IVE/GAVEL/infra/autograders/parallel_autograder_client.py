import json
import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from enum import Enum
from pathlib import Path

# TODO: figure out why C is failing stability checks while running fine in manual runner page


class Language(Enum):
    JAVA = 1
    C = 2


class AutograderRunFailed(RuntimeError):

    def __init__(
        self,
        message: str,
        returncode: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
    ):
        super().__init__(message)

        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def grade_one_submission(
    filename, config, lang, autograder_root, input_folder, output_folder, timeout=None
):
    """
    Runs the autograder for a single submission in a fully isolated worker directory.

    ``timeout`` caps the autograder process in seconds; when it runs out the
    ``subprocess.TimeoutExpired`` propagates. An autograder that exits with an
    error or leaves no results raises ``AutograderRunFailed`` carrying its output.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("autograder_client")
    start = time.perf_counter()

    log.info(f"Starting autograder for {Path(filename).name}...")

    # clone workspace
    worker_root = tempfile.mkdtemp(
        prefix=f"autograder_worker_{filename.split('.')[0]}_"
    )

    if lang == Language.JAVA:

        shutil.copytree(
            autograder_root,
            worker_root,
            dirs_exist_ok=True,
        )

        worker_src_root = worker_root

    else:

        worker_autograder = Path(worker_root) / "autograder"
        worker_submission = Path(worker_root) / "submission"
        worker_results = Path(worker_root) / "results"

        shutil.copytree(
            autograder_root,
            worker_autograder,
            ignore=shutil.ignore_patterns(
                "venv",
                "__pycache__",
                ".git",
                ".pytest_cache",
            ),
        )

        worker_submission.mkdir(exist_ok=True)
        worker_results.mkdir(exist_ok=True)

        worker_src_root = worker_root
    # shutil.copytree(autograder_root, worker_root, dirs_exist_ok=True)
    # worker_autograder = Path(worker_root) / "autograder"
    # worker_submission = Path(worker_root) / "submission"
    # worker_results = Path(worker_root) / "results"
    #
    # shutil.copytree(
    #     autograder_root,
    #     worker_autograder,
    #     ignore=shutil.ignore_patterns(
    #         "venv",
    #         "__pycache__",
    #         ".git",
    #         ".pytest_cache",
    #     ),
    # )
    #
    # worker_submission.mkdir(exist_ok=True)
    # worker_results.mkdir(exist_ok=True)

    # TODO: better version of extracting worker src files
    config_proj_loc = (
        config["project_location"]
        .strip("/\\")
        .replace("/", os.sep)
    )

    if lang == Language.JAVA:
        project_location = config["project_location"]

        prefix = "/autograder/source/"

        if project_location.startswith(prefix):
            project_location = project_location[len(prefix):]

        project_location = project_location.strip("/\\")
        project_location = project_location.replace("/", os.sep)

        worker_src = os.path.join(
            worker_root,
            project_location,
        )
    else:
        worker_src = os.path.join(
            worker_root,
            "submission",
        )

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
        _remove_worker(worker_root)
        return f"{filename}: already exists"

    try:
        if lang == Language.JAVA:
            log.info(f"worker_src = {worker_src}")

            for req in required_files:
                path = os.path.join(worker_src, req)

                log.info(
                    f"{req}: exists={os.path.exists(path)} "
                    f"path={path}"
                )
            result = subprocess.run(
                ["mvn", "-q", "compile", "exec:java"],
                cwd=worker_root,
                capture_output=True,
                text=True,
                shell=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                raise AutograderRunFailed(
                    (
                        f"mvn exited with status {result.returncode}\n\n"
                        f"STDOUT:\n{result.stdout}\n\n"
                        f"STDERR:\n{result.stderr}"
                    ),
                    result.returncode,
                    result.stdout,
                    result.stderr,
                )

            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise AutograderRunFailed(
                    "no results JSON on stdout", result.returncode, result.stdout, result.stderr
                ) from exc
            with open(output_path, "w", encoding="utf-8") as out:
                json.dump(parsed, out, indent=4)


        else:  # C autograder


            log_path = os.path.splitext(output_path)[0] + "_stdout.txt"


            results_path = os.path.join(

                worker_root,

                "results",

                "results.json",

            )


            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--mount",
                f"type=bind,source={Path(worker_root).resolve()},target=/work",
                "-w",
                "/work/autograder",
                "gavel-c-runtime",
                "python3",
                "main.py",
            ]

            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )


            with open(log_path, "w", encoding="utf-8") as out:

                out.write(result.stdout)

                out.write("\n=== STDERR ===\n")

                out.write(result.stderr)


            if result.returncode != 0:
                raise AutograderRunFailed(
                    (
                        f"Docker exited with status {result.returncode}\n\n"
                        f"STDOUT:\n{result.stdout}\n\n"
                        f"STDERR:\n{result.stderr}"
                    ),
                    result.returncode,
                    result.stdout,
                    result.stderr,
                )


            if not os.path.exists(results_path):

                raise AutograderRunFailed(

                    "Autograder produced no results.json",

                    result.returncode,

                    result.stdout,

                    result.stderr,

                )


            shutil.copy(results_path, output_path)

    finally:
        # clean up directory
        _remove_worker(worker_root)
    time_elapsed = time.perf_counter() - start
    return f"{filename}: done (elapsed time: {time_elapsed} seconds)"


def _remove_worker(worker_root):
    """
    Deletes a worker copy. Folders synced by OneDrive carry a read-only attribute
    that copytree preserves, and Windows refuses to delete a read-only folder.
    """
    for root, dirs, files in os.walk(worker_root):
        for name in dirs + files:
            path = os.path.join(root, name)
            try:
                os.chmod(path, os.stat(path).st_mode | stat.S_IWRITE)
            except OSError:
                pass
    try:
        os.chmod(worker_root, os.stat(worker_root).st_mode | stat.S_IWRITE)
    except OSError:
        pass
    shutil.rmtree(worker_root, ignore_errors=True)


def _detect_language(input_folder) -> Language | None:
    for file in input_folder.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix.lower() == ".java":
            return Language.JAVA
        elif file.suffix.lower() == ".c":
            return Language.C
    return None


def autograde_submissions_folder(
    input_folder, output_folder, autograder_folder_arg, timeout=None
) -> float | type[Exception]:
    """
    :param input_folder: submissions input folder
    :param output_folder: desired output folder
    :param autograder_folder_arg: autograder folder
    :param timeout: seconds allowed per submission, None for no limit
    :return: time elapsed
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("autograder_client")
    log.info(
        f"Autograding started on {Path(input_folder).name} using {Path(autograder_folder_arg).name}..."
    )

    start = time.perf_counter()
    lang = _detect_language(input_folder)

    config_file_location = os.path.join(autograder_folder_arg, "config.json")
    with open(config_file_location, encoding="utf-8") as file:
        config = json.load(file)

    if "files_required" not in config and "required_files" in config:
        config["files_required"] = config["required_files"]

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
                    timeout,
                )
                for filename in submissions
            ]

            for fut in as_completed(futures):
                completed_tasks += 1
                log.info(f"{fut.result()} ({completed_tasks}/{len(futures)})")

        log.info(
            f"Autograding complete! ({Path(input_folder).name} using autograder {Path(autograder_folder_arg).name}.)"
        )
        return time.perf_counter() - start
    except Exception as exc:
        log.exception(
            f"Autograding failed!! "
            f"({Path(input_folder).name} using "
            f"autograder {Path(autograder_folder_arg).name}.)"
        )
        raise
