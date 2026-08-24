"""
shoggoth-validation - analysis.py

Computes proxy grades for assignments.

A proxy grade is an assignment grade that follows the manual assessment rubrics but which uses autograder information.
They are computed as if we are a human grading the normal rubric but going off of the information extracted by the
autograder as a boolean feature vector.

Requires JSON evaluations to exist in a folder like: shoggoth-validation/data_processed/evaluations/ser334_24sc_m2/

Produces:
  1) A table of autograder grades, proxy criteria grades, computed total proxy grades, and individual test results.
  2) A table of correlations (r^2) for each test case.
  3) If ground truth grades are available, calculates the delta between them and the proxy grades to produce a table,
    box plot comparison, and a error histogram.

These outputs are typically used to analyze the grades produced by the autograder to improve. For example, the
correlations can be used to find redundant tests. If grades are available, it can be used to compare grade accuracy with
human grades.
"""

__author__ = "Ruben Acuna"
__copyright__ = "Copyright 2024-25, Ruben Acuna"

import os
import json

import pandas as pd

from analysis_proxy_grade_ser222 import *
import constants
import analysis_proxy_grade_ser334 as proxy_ser334
import analysis_proxy_comparison as apc


# pandas settings
pd.options.display.width = 0
pd.options.display.precision = 3


def analyze_assignment(course, config_file, canvas_gradebook, semester, proxy_func):

    print(f"analyze_assignment({config_file}, {semester}):")

    with open(config_file) as file:
        config = json.load(file)

    module = config["module"]
    input_folder = (
        constants.FOLDER_EVALUATIONS + os.sep + f"{course}_{semester}_{module}"
    )
    class_data = []

    if not os.path.exists(input_folder):
        print(f"Cannot find completed Shoggoth evaluations in {input_folder}.")
        exit()

    # automatically detect common suffix so that UID can be found
    all_filenames = [f for f in os.listdir(input_folder) if ".json" in f]
    all_filenames = [f[::-1] for f in all_filenames]  # ugh
    fakey_suffix = os.path.commonprefix(all_filenames)
    suffix = fakey_suffix[::-1]

    row_dict = {
        "last_name": [],
        "total_score_autograder": [],
        "proxies": [],
        "total_score_proxy": [],
    }
    number_of_tests = 0

    for filename in sorted([f for f in os.listdir(input_folder) if ".json" in f]):
        with open(input_folder + os.sep + filename) as f:
            uid = filename[: -len(suffix)]
            print(f"  Processing {uid}")

            try:
                student_data = json.load(f)
            except json.JSONDecodeError:
                print("    Failed to parse JSON, skipping student.")
                continue

            # TODO: technically we should validate the entire schema first but whatever
            test_numbers = [n["number"] for n in student_data["tests"]]
            if len(test_numbers) != len(set(test_numbers)):
                print("Testcase numbering is not unique.")
                exit()
            number_of_tests = len(test_numbers)

            # compute the autograder's total and proxy scores
            score_autograder_total = sum([s["score"] for s in student_data["tests"]])
            proxy_criteria_grades, total_score_proxy = proxy_func(student_data)

            # old: populate dictionary
            student_data["last_name"] = uid
            student_data["total_score_autograder"] = score_autograder_total
            student_data["proxies"] = proxy_criteria_grades
            student_data["total_score_proxy"] = total_score_proxy

            # new: populate dictionary for use with a DF
            row_dict["last_name"] += [uid]
            row_dict["total_score_autograder"] += [score_autograder_total]
            row_dict["total_score_proxy"] += [total_score_proxy]
            row_dict["proxies"] += [proxy_criteria_grades]

            # extract and sort the raw test results
            test_results = sorted(
                student_data["tests"], key=lambda x: float(x["number"])
            )

            for test in test_results:
                key_name = "T " + str(test["number"])

                if key_name not in row_dict:
                    row_dict[key_name] = []

                row_dict[key_name].append(test["score"])

            print(
                f"    autograder: {score_autograder_total}, proxy: {total_score_proxy}, {proxy_criteria_grades}"
            )

            class_data += [student_data]

    df_class = pd.DataFrame.from_dict(row_dict)

    # compute statistics for assignment
    print("== CLASS DATA==")
    print(df_class)

    # compute and display correlation matrix
    selected_columns = df_class.iloc[:, 4 : 4 + number_of_tests]
    print(selected_columns.corr())

    # TODO: do PCA analysis.

    if os.path.exists(canvas_gradebook):
        apc.compare_autograder_accuracy(
            course, canvas_gradebook, class_data, config, semester
        )
    else:
        print("Could not find canvas gradebook, skipping grade comparison.")


# testing area
if __name__ == "__main__":
    # analyze_assignment("ser222", "ser222_config_m1.json", "ser222_21sc_gradebook.csv", "21sc", compute_proxy_grades_m1_21sc)
    # analyze_assignment("ser222", "ser222_config_m12.json", "ser222_21sc_gradebook.csv", "21sc", compute_proxy_grades_m12_21sc)
    # analyze_assignment("ser222", "ser222_config_m12.json", "ser222_21sa_gradebook.csv", "24sa", compute_proxy_grades_m12_21sc)

    # analyze_assignment("ser334", constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_config_m2.json", constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_24sc_gradebook.csv", "24sc", proxy_ser334.compute_proxies_m2_24sc)

    # SER334 M3 (developmental test set)
    analyze_assignment(
        "ser334",
        constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_config_m3.json",
        constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_00dv_gradebook.csv",
        "00dv",
        proxy_ser334.compute_proxies_m3_24fc,
    )
