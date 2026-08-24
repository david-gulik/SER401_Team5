"""
shoggoth-validation - study_replication.py

This file can be used to replicate the results from various papers.

"""

__author__ = "Ruben Acuna"
__copyright__ = "Copyright 2025, Ruben Acuna"

import os
import constants

from analysis import analyze_assignment
from analysis_proxy_grade_ser334 import compute_proxies_m2_24sc
from stats import perform_two_tailed_test, prepare_gradebook


def fie_2025_enhancing():
    # rename_canvas_submission_files(constants.FOLDER_SUBMISSIONS + os.sep + "ser334_24sc_m2_0raw", constants.FOLDER_SUBMISSIONS + os.sep + "ser334_24sc_m2_1renamed")
    # run_shoggoth_bulk("ser334", Language.C, constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_config_m2.json", "24sc")

    # accuracy evaluation
    analyze_assignment(
        "ser334",
        constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_config_m2.json",
        constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_24sc_gradebook.csv",
        "24sc",
        compute_proxies_m2_24sc,
    )

    # t-tests (M1, M3 two-tailed comparison between sections)
    path_gradebook_ser334_24sc = (
        constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_24sc_gradebook.csv"
    )  # old
    path_gradebook_ser334_24sc_output = (
        path_gradebook_ser334_24sc[:-4] + "_stats_cleaned.csv"
    )
    path_gradebook_ser334_24fc = (
        constants.FOLDER_DATA_ORIGINAL + os.sep + "ser334_24fc_gradebook.csv"
    )  # new
    path_gradebook_ser334_24fc_output = (
        path_gradebook_ser334_24fc[:-4] + "_stats_cleaned.csv"
    )

    df_grades_ser334_24sc = prepare_gradebook(
        path_gradebook_ser334_24sc, path_gradebook_ser334_24sc_output
    )
    df_grades_ser334_24fc = prepare_gradebook(
        path_gradebook_ser334_24fc, path_gradebook_ser334_24fc_output
    )

    a = 0.05
    print(f"Assessment\t\t\t\tSection\tn\tMean\tSD\tMin")
    perform_two_tailed_test(
        "Module 1: Programming", None, a, df_grades_ser334_24sc, df_grades_ser334_24fc
    )
    # perform_two_tailed_test("Module 2: Programming", "Module 2: Programming (Gradescope)", alpha, df_grades_ser334_24sc, df_grades_ser334_24fc)
    perform_two_tailed_test(
        "Module CP3: Programming", None, a, df_grades_ser334_24sc, df_grades_ser334_24fc
    )


if __name__ == "__main__":
    fie_2025_enhancing()
