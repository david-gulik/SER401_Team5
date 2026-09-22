"""Ported from the sponsor's analysis_proxy_grade_ser334.py::compute_proxies_m2_24sc.

Reimplements the same boolean-expression rules and point tiers against
GAVEL's own GradescopeSubmission DTO, rather than the original's raw dict
access, so it fits GAVEL's own architecture.

Specific to SER334 Module 2 only: the test-name lookups and point tiers
below are hardcoded to that one assignment's rubric and will not produce
correct results for any other module or course. A different module needs
its own file in this same proxy_grade package, not a reuse of this one.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeTestScore
from GAVEL.app.dtos.proxy_grade_result import ProxyGradeResult


def _test_passed(tests: Sequence[GradescopeTestScore], name_substring: str) -> bool:
    for test in tests:
        if name_substring in test.name:
            if test.max_score is None:
                return False
            return math.isclose(test.max_score, test.score, abs_tol=0.0001)
    raise ValueError(f"No test result found matching {name_substring!r}.")


def compute_proxy_grade(submission: GradescopeSubmission) -> ProxyGradeResult:
    """Maps SER334 Module 2's granular autograder tests onto the human rubric's nine criteria (30 points total)."""
    tests = submission.tests
    criterion_scores: list[float] = []

    # 1) main menu [2pts]
    t1_1 = _test_passed(tests, "Main Menu 1")
    t1_2 = _test_passed(tests, "Main Menu 2")
    if t1_1 and t1_2:
        criterion_scores.append(2.0)
    elif t1_1:
        criterion_scores.append(1.0)
    else:
        criterion_scores.append(0.0)

    # 2) memory leaks [2pts]
    t2_1 = _test_passed(tests, "Memory Allocation 3")
    t2_2 = _test_passed(tests, "Memory Allocation 4")
    if t2_1 and t2_2:
        criterion_scores.append(2.0)
    elif t2_1:
        criterion_scores.append(1.0)
    else:
        criterion_scores.append(0.0)

    # 3) course_insert [7pts]
    t3_1 = _test_passed(tests, "Insert Course 1")
    t3_2 = _test_passed(tests, "Insert Course 2")
    t3_3 = _test_passed(tests, "Insert Course 3")
    t3_4 = _test_passed(tests, "Insert Course 4")
    t3_5 = _test_passed(tests, "Insert Course 5")
    t3_6 = _test_passed(tests, "Insert Course 6")
    t3_7 = _test_passed(tests, "Insert Course 7")
    if t3_1 and t3_2 and t3_3 and t3_4 and t3_5 and t3_6 and t3_7:
        criterion_scores.append(7.0)
    elif t3_1 and t3_2 and t3_4:
        criterion_scores.append(3.5)
    elif t3_1:
        criterion_scores.append(1.75)
    else:
        criterion_scores.append(0.0)

    # 4) course_insert::memory [2pts]
    t4_1 = _test_passed(tests, "Memory Allocation 1")
    t4_2 = _test_passed(tests, "Memory Allocation 2")
    if t4_1 and t4_2:
        criterion_scores.append(2.0)
    elif t4_1:
        criterion_scores.append(1.0)
    else:
        criterion_scores.append(0.0)

    # 5) schedule_print [2pts]
    t5_1 = _test_passed(tests, "Schedule Print")
    criterion_scores.append(2.0 if t5_1 else 0.0)

    # 6) course_drop [5pts]
    t6_1 = _test_passed(tests, "Remove Course 1")
    t6_2 = _test_passed(tests, "Remove Course 2")
    t6_3 = _test_passed(tests, "Remove Course 3")
    t6_4 = _test_passed(tests, "Remove Course 4")
    if t6_1 and t6_2 and t6_3 and t6_4:
        criterion_scores.append(5.0)
    elif t6_1 and t6_2 and t6_3:
        criterion_scores.append(2.5)
    elif t6_1:
        criterion_scores.append(1.25)
    else:
        criterion_scores.append(0.0)

    # 7) course_drop::memory [2pts]
    t7_1 = _test_passed(tests, "Memory Allocation 5")
    t7_2 = _test_passed(tests, "Memory Allocation 6")
    if t7_1 and t7_2:
        criterion_scores.append(2.0)
    elif t7_1:
        criterion_scores.append(1.0)
    else:
        criterion_scores.append(0.0)

    # 8) schedule_load [4pts]
    t8_1 = _test_passed(tests, "Load File 1")
    t8_2 = _test_passed(tests, "Load File 2")
    t8_3 = _test_passed(tests, "Load File 3")
    if t8_1 and t8_2 and t8_3:
        criterion_scores.append(4.0)
    elif t8_1:
        criterion_scores.append(2.0)
    else:
        criterion_scores.append(0.0)

    # 9) schedule_save [4pts]
    t9_1 = _test_passed(tests, "Save File 1")
    t9_2 = _test_passed(tests, "Save File 2")
    if t9_1 and t9_2:
        criterion_scores.append(4.0)
    elif t9_1:
        criterion_scores.append(2.0)
    else:
        criterion_scores.append(0.0)

    total_score = sum(criterion_scores)
    return ProxyGradeResult(criterion_scores=tuple(criterion_scores), total_score=total_score)
