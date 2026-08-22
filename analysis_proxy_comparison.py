"""
shoggoth-validation - analysis_proxy_comparison.py
"""

__author__ = "Ruben Acuna"
__copyright__ = "Copyright 2024-25, Ruben Acuna"

import csv
import math
import os

import matplotlib.pyplot as plt

import constants


def compare_autograder_accuracy(course, canvas_gradebook, class_data, config, semester):

    # populate class_data with original scores
    columns, gradebook_rows = load_canvas_gradebook(canvas_gradebook)
    for entry in gradebook_rows:
        entry["Student"] = entry["Student"].split(",")[0].split(" ")[0]

    # find assignment score key.
    key_candidates = [
        x
        for x in gradebook_rows[0].keys()
        if (
            "Module " + config["module"][1:] in x
            or "Module CP" + config["module"][1:] in x
        )
        and ": Programming" in x
    ]
    key_candidates = [x for x in key_candidates if "EC" not in x]

    if len(key_candidates) != 1:
        raise Exception(f"Issue finding column with grade information.")
    key = key_candidates[0]

    # extract grade for each student and update class data
    for student in class_data:
        uid = student["last_name"].lower()
        gradebook_entry = None
        for entry in gradebook_rows:
            if entry["Student"].lower() == uid.lower():
                if gradebook_entry:
                    raise Exception("Already found student.")
                gradebook_entry = entry

        if not gradebook_entry:
            raise Exception(f"Could not find student ({uid}) in gradebook.")

        student["original_score"] = float(gradebook_entry[key])

    # compute error
    for student in class_data:
        student["error"] = student["original_score"] - student["total_score_proxy"]
        student["abs_error"] = abs(student["error"])
        student["sq_error"] = student["error"] * student["error"]

    generate_grade_table(class_data)
    generate_visuals(class_data, course + "_" + semester + "_" + config["module"])


def load_canvas_gradebook(path_gradebook):
    gradebook_rows = []
    useful_columns = ["Student"]

    with open(path_gradebook) as csvfile:
        reader = csv.DictReader(csvfile)

        # skip header lines (removing two lines due to Canvas export format).
        header = list(next(reader).keys())
        next(reader)  # dummy line

        # add all columns for all programming assignments
        for column in header:
            if ": Programming" in column:
                useful_columns += [column]

        for row in reader:
            # skip the entry for the test student
            if row["Student"] == "Student, Test":
                continue

            # filter the row to only the useful columns
            row_useful = {key: row[key] for key in useful_columns}
            gradebook_rows.append(row_useful)
    return useful_columns, gradebook_rows


def generate_grade_table(cd):

    # display table of data
    print(f"Last Name\tOriginal Score\tProxy Score\tabs_error\tAutograder\tProxies")
    for student in cd:
        name_printable = student["last_name"][:5]

        print(
            f"{name_printable}\t{student['original_score']}\t{student['total_score_proxy']}\t{student['abs_error']}\t{student['total_score_autograder']}\t{student['proxies']}"
        )
        # print(f"{last_name}\t{total_score_autograder}\t{total_score_proxy}\t{proxies}")

    print(f"n={len(cd)}")
    print(f"total abs error: {sum([s['abs_error'] for s in cd])}")

    def display_summary_stats(key):
        # print(f"==display_summary_stats for {key}==")
        key_data = [x[key] for x in cd]
        data_min = min(key_data)

        data_mean = sum(key_data) / len(key_data)

        data_max = max(key_data)

        # SD
        data_sd = [(x - data_mean) ** 2 for x in key_data]
        data_sd = math.sqrt(sum(data_sd) / len(data_sd))

        # max count
        maxes = len([x for x in key_data if math.isclose(x, data_max)])
        print(
            f"{key[:14]}\tmin: {data_min}\tmean: {round(data_mean, 2)}\tmax: {data_max}\tsd: {round(data_sd, 2)}\tmaxes: {maxes}"
        )

    display_summary_stats("original_score")
    display_summary_stats("total_score_proxy")


def generate_visuals(cd, prefix):
    # generate histogram of errors

    error_data = [x["error"] for x in cd]
    error_min_value = min(error_data + [0])
    fig, ax = plt.subplots()
    ax.set(
        title=r"Error Distribution for Manual Assessment",
        ylabel="Count",
        xlabel="Error (points)",
    )
    ax.hist(error_data, bins=32, density=False, range=(error_min_value, 32))
    fig.show()
    fig.savefig(
        constants.FOLDER_VISUALS
        + os.sep
        + prefix
        + "_"
        + "visual_error_distribution.png"
    )

    # generate boxplots for scores

    # arrange data
    data_ori_scores = [x["original_score"] for x in cd]
    data_proxy_scores = [x["total_score_proxy"] for x in cd]
    # data_autograder_scores = [x["total_score_autograder"] for x in cd]
    boxplot_data_scores = [data_ori_scores, data_proxy_scores]

    # create boxplot for number of
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_ylabel("Score")
    ax.boxplot(boxplot_data_scores)
    plt.xticks(
        [1, 2], ["Manual Grade", "Automated Proxy Grade"]
    )  # this is weird b/c of new test.
    fig.show()
    fig.savefig(
        constants.FOLDER_VISUALS + os.sep + prefix + "_" + "visual_boxplot_scores.png"
    )
