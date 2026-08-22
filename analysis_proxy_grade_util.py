"""
shoggoth-validation - analysis_proxy_grade_util.py

Contains various helpers for computing proxy grades.
"""

__author__ = "Ruben Acuna"
__copyright__ = "Copyright 2024-25, Ruben Acuna"

import math


def get_test_case_by_name(data, target):
    for test in data["tests"]:
        if target in test["name"]:
            return test

    raise Exception("Unable to find test case.")


def was_test_passed_by_name(data, target):
    test = get_test_case_by_name(data, target)

    return math.isclose(test["max_score"], test["score"], abs_tol=0.0001)
