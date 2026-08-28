"""
shoggoth-validation - stats.py

Loads Canvas exported gradebooks and executes t-tests between assignment grades.

"""

__author__ = "Ruben Acuna"
__copyright__ = "Copyright 2024-25, Ruben Acuna"

import csv
import numpy as np
import os
import pandas as pd
from scipy.stats import ttest_ind

import constants

pd.options.display.width = 0


def prepare_gradebook(path_gradebook, path_output):
    gradebook_rows = []
    useful_columns = ["Student", "SIS User ID"]  # TODO: redundant

    with open(path_gradebook) as csvfile:
        reader = csv.DictReader(csvfile)

        # skip header lines (removing two lines due to Canvas export format).
        header = list(next(reader).keys())
        next(reader)

        # add all columns from space module.
        for column in header:
            if "EC" in column:
                continue

            if "(" and ")" in column:  # only get columns that come from assignments.
                if "Programming" in column:  # or "Exercise" in column:
                    useful_columns += [column]

        for row in reader:
            # skip the entry for the testing student
            if row["Student"] == "Student, Test":
                continue

            # filter the row to only the useful columns
            row_useful = {key: row[key] for key in useful_columns}
            gradebook_rows.append(row_useful)

    better_column_names = {}
    for original_column in useful_columns:
        better_name = original_column.replace(
            " - Requires Respondus LockDown Browser + Webcam", ""
        )
        if "(" in better_name:
            better_name = better_name[: better_name.rindex("(")].strip()
        better_column_names[original_column] = better_name

    # construct DataFrame for gradebook
    df_gradebook = pd.DataFrame(gradebook_rows)
    df_gradebook = df_gradebook.rename(columns=better_column_names)

    # type columns
    df_gradebook["SIS User ID"] = df_gradebook["SIS User ID"].astype(np.int64)

    for column_name in df_gradebook:
        if "Programming" in column_name:
            df_gradebook[column_name] = df_gradebook[column_name].astype(float)

    # display and save data
    df_gradebook.to_csv(path_output)

    return df_gradebook


def perform_two_tailed_test(col_1st, col_2nd, alpha, df_1stf, df_second):

    if not col_2nd:
        col_2nd = col_1st

    # FILTERING (only use assessments scores for students who submitted)
    df_1stf = df_1stf[col_1st].loc[df_1stf[col_1st] != 0]
    df_2ndf = df_second[col_2nd].loc[df_second[col_2nd] != 0]

    df = len(df_1stf) + len(df_2ndf) - 2

    print(
        f"{col_1st}\t1st\t{len(df_1stf)}\t{round(df_1stf.mean(), 3)}\t{round(df_1stf.std(), 3)}\t{round(df_1stf.min(), 3)}\t{round(df_1stf.max(), 3)}"
    )
    print(
        f"{col_2nd}\t2nd\t{len(df_2ndf)}\t{round(df_2ndf.mean(), 3)}\t{round(df_2ndf.std(), 3)}\t{round(df_2ndf.min(), 3)}\t{round(df_2ndf.max(), 3)}"
    )

    # RA note: pandas std is supposed to take ddof=1 by default (to produce sample std)

    # hypo test
    result = ttest_ind(df_1stf, df_2ndf)

    if result.pvalue > alpha:
        ans = "Failed to reject H0."
    else:
        ans = "Reject H0."

    print(
        f"\t\tt({df}) = {round(result.statistic, 3)}, p = {round(result.pvalue, 3)}. {ans}"
    )


# testing area
if __name__ == "__main__":
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

    # ANALYSIS
    a = 0.05
    # print(df_grades_ser334_24sc)
    # print(df_grades_ser334_24fc)

    print(f"Assessment\t\t\t\tSection\tn\tMean\tSD\tMin")
    perform_two_tailed_test(
        "Module 1: Programming", None, a, df_grades_ser334_24sc, df_grades_ser334_24fc
    )
    # perform_two_tailed_test("Module 2: Programming", "Module 2: Programming (Gradescope)", alpha, df_grades_ser334_24sc, df_grades_ser334_24fc)
    perform_two_tailed_test(
        "Module CP3: Programming", None, a, df_grades_ser334_24sc, df_grades_ser334_24fc
    )
