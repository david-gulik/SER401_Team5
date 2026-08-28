"""
shoggoth-validation - analysis_proxy_grade_ser222.py

This file includes methods that compute proxy grades based on autograder data.

It is used by analysis_proxy_comparison.

Each function takes a standard Gradescope result dictionary and returns a list of the scores for each criterion and
their sum total.
"""

__author__ = "Ruben Acuna, Mitchell Buckner"
__copyright__ = "Copyright 2024, Ruben Acuna"

from analysis_proxy_grade_util import get_test_case_by_name, was_test_passed_by_name


def compute_proxy_grades_m1_21sc(data):
    proxies = []

    # constructor (4 pts)
    t1_1 = was_test_passed_by_name(data, "Constructor 1")  # square
    t1_2 = get_test_case_by_name(data, "Constructor 2")  # rect
    t1_3 = was_test_passed_by_name(data, "Constructor 3")  # imm
    t1_4 = get_test_case_by_name(data, "Constructor 4")  # 0x0
    t1_5 = get_test_case_by_name(
        data, "Constructor 5"
    )  # null case. not suggested anywhere

    if t1_1 and t1_2 and t1_3 and t1_4:
        proxies += [4.0]
    elif t1_1 and t1_2 and t1_3:  # is this too picky?
        proxies += [2.0]
    else:
        proxies += [0.0]

    # getElement (2 pts)
    t2_1 = was_test_passed_by_name(data, "getElement() 1")
    t2_2 = was_test_passed_by_name(data, "getElement() 2")

    if t2_1 and t2_2:
        proxies += [2.0]
    elif not t2_1 and not t2_2:
        proxies += [0.0]
    else:
        proxies += [1.0]

    # getRows (1 pts)
    t3_1 = was_test_passed_by_name(data, "getRows() 1")
    t3_2 = was_test_passed_by_name(data, "getRows() 2")

    if t3_1 and t3_2:
        proxies += [1.0]
    elif not t3_1 and not t3_2:
        proxies += [0.0]
    else:
        proxies += [0.5]

    # getColumns (1 pts)
    t4_1 = was_test_passed_by_name(data, "getColumns() 1")
    t4_2 = was_test_passed_by_name(data, "getColumns() 2")

    if t4_1 and t4_2:
        proxies += [1.0]
    elif not t4_1 and not t4_2:
        proxies += [0.0]
    else:
        proxies += [0.5]

    # scale (3 pts)
    t5_1 = was_test_passed_by_name(data, "scale() 1")
    t5_2 = was_test_passed_by_name(data, "scale() 2")
    t5_3 = was_test_passed_by_name(data, "scale() 3")
    t5_4 = was_test_passed_by_name(data, "scale() 4")

    if t5_1 and t5_2 and t5_3 and t5_4:
        proxies += [3.0]
    # elif (t5_1 and t5_3 and t5_4) or t5_2:
    elif (t5_1 and t5_3 and t5_4) or t5_1 or t5_2:
        proxies += [1.5]
    else:
        proxies += [0.0]

    # plus (3 pts)
    t6_1 = was_test_passed_by_name(data, "plus() 1")
    t6_2 = was_test_passed_by_name(data, "plus() 2")
    t6_3 = was_test_passed_by_name(data, "plus() 3")
    t6_4 = was_test_passed_by_name(data, "plus() 4")
    # t6_5 is skipped wasn't part of original requirements
    if t6_1 and t6_2 and t6_3 and t6_4:
        proxies += [3.0]
    # elif (t6_1 and t6_3) or t6_2 or t6_4:
    elif (t6_1 and t6_3) or (t6_1 or t6_2) or t6_4:
        proxies += [1.5]
    else:
        proxies += [0.0]

    # minus (3 pts)
    t7_1 = was_test_passed_by_name(data, "minus() 1")
    t7_2 = was_test_passed_by_name(data, "minus() 2")
    t7_3 = was_test_passed_by_name(data, "minus() 3")
    t7_4 = was_test_passed_by_name(data, "minus() 4")
    # t6_5 is skipped wasn't part of original requirements
    if t7_1 and t7_2 and t7_3 and t7_4:
        proxies += [3.0]
    # elif (t7_1 and t7_3) or t7_2 or t7_4:
    elif (t7_1 and t7_3) or (t7_1 or t7_2) or t7_4:
        proxies += [1.5]
    else:
        proxies += [0.0]

    # multiply (5 pts)
    t8_1 = was_test_passed_by_name(
        data, "multiply() 1"
    )  # [Hint: Basic Behavior (square matrices)]
    t8_2 = was_test_passed_by_name(
        data, "multiply() 2"
    )  # [Hint: Basic Behavior + Immutability Check]
    t8_3 = was_test_passed_by_name(
        data, "multiply() 3"
    )  # [Hint: Basic Behavior (rectangular matrices)]
    t8_4 = was_test_passed_by_name(
        data, "multiply() 4"
    )  # [Hint: Exceptions (incorrect shapes)]
    t8_5 = was_test_passed_by_name(
        data, "multiply() 5"
    )  # [Hint: Exceptions (null matrix)] not in original HW.

    # "Computed the result correctly, checked the dimensions match, built and returned the new matrix."
    if t8_1 and t8_2 and t8_3 and t8_4:
        proxies += [5.0]
    # "Computed the result correctly, or, built and returned the new matrix, or checked the dimensions match (using exceptions), but not all are not correct."
    # elif (t8_1 and t8_3) or t8_2 or t8_4:
    elif (t8_1 and t8_3) or (t8_1 or t8_2) or t8_4:
        proxies += [2.5]

    # "Did not attempt, or attempt is only signature from interface."
    else:
        proxies += [0.0]

    # equals (5 pts)
    t9_1 = was_test_passed_by_name(data, "equals() 1")  # null
    t9_2 = was_test_passed_by_name(data, "equals() 2")
    t9_3 = was_test_passed_by_name(data, "equals() 3")
    t9_4 = was_test_passed_by_name(data, "equals() 4")
    t9_5 = was_test_passed_by_name(data, "equals() 5")
    t9_6 = was_test_passed_by_name(data, "equals() 6")

    # double-checked on 11/20
    if t9_2 and t9_3 and t9_4 and t9_5 and t9_6:
        proxies += [5.0]
    elif (t9_3 and t9_4 and t9_5 and t9_6) or t9_2:
        proxies += [2.5]
    else:
        proxies += [0.0]

    # toString (5 pts)
    t10_1 = was_test_passed_by_name(
        data, "toString() 1"
    )  # this checks for a crash... so technically we are aligned with rubric.
    t10_2 = was_test_passed_by_name(data, "toString() 2")
    t10_3 = was_test_passed_by_name(data, "toString() 3")
    t10_4 = was_test_passed_by_name(data, "toString() 4")
    if t10_1 and t10_2 and t10_3 and t10_4:
        proxies += [5.0]
    elif (
        t10_1 or t10_2 or t10_3 or t10_4
    ):  # this allows even a blank string, but that's okay. be lenient like human.
        proxies += [2.5]
    else:
        proxies += [0.0]

    total_score_proxy = sum([ps for ps in proxies if ps])

    return proxies, total_score_proxy


def compute_proxy_grades_m12_21sc(data):
    # Rubric for SC21  [50 + 8]:
    #   BetterDiGraph is 26pts
    #   IntuitiveTopological is 24pts
    #   EC: Visualization 8pts (skipped)

    proxy_criteria_grades = []

    # there is also an autograder criteria for constructor, but we don't use that here.

    ####################################################################################################################
    # BetterDiGraph: addEdge(int v, int w) [5pts]
    #   5 pts	Proficient	Adds an edge between two vertices, v and w. If vertices do not exist, adds them first.
    #   2.5 pts	Competent	Does not add edge or does not add vertices if they don't exist.
    #   0 pts	Novice	    Did not attempt.

    # 2.1) BetterDigraph addEdge() 1 [Hint: Basic Behavior.] (1)
    # 2.2) BetterDigraph addEdge() 2 [Hint: New Vertices.] (1)
    # 2.4) BetterDigraph addEdge() 4 [Hint: Keeps Accurate Edge Count.] (1)
    # (NOT IN HOMEWORK BEFORE):
    # 2.3) BetterDigraph addEdge() 3 [Hint: Duplicate Edges.] (1)

    c1_1 = was_test_passed_by_name(data, "addEdge() 1 [Hint: Basic Behavior.]")
    c1_2 = was_test_passed_by_name(
        data, "addEdge() 2 [Hint: New Vertices.]"
    )  # RA: does t1_2 only pass if t1_1 passes? # MB: this is correct, 1_2 cannot pass without 1_1
    c1_3 = was_test_passed_by_name(
        data, "addEdge() 3 [Hint: Duplicate Edges.]"
    )  # RA: parallel edges, not used in SC21.
    # c1_4 = was_test_cased_passed_by_name(data, "addEdge() 4 [Hint: Keeps Accurate Edge Count.]") #RA: this appears to give the same result as c1_3.
    c1_weight = 5.0

    # compute the rubric level from the test case results.
    if (
        c1_1 and c1_2
    ):  # Proficient. skipping c1_3 since duplicate edges not mentioned in original rubric.
        proxy_criteria_grades += [c1_weight]
    elif c1_1 or c1_2:  # Competent
        proxy_criteria_grades += [c1_weight * 0.5]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: addVertex(int v) [5pts]
    #   5 pts	Proficient	Adds a vertex to the graph. Does not allow duplicate vertices.
    #   2.5 pts	Competent	Does not add vertex, or allows duplicates.
    #   0 pts	Novice	    Did not attempt

    # 3.1) BetterDigraph addVertex() 1 [Hint: Basic behavior.] (2)
    # 3.2) BetterDigraph addVertex() 2 [Hint: Duplicates.] (1)
    # 3.3) BetterDigraph addVertex() 3 [Hint: Keeps Accurate Vertex Count.] (1)
    c2_1 = was_test_passed_by_name(
        data, "addVertex() 1 [Hint: Basic behavior.]"
    )  # RA: does c2_2 only pass if c2_1 passes? # MB: this is correct
    c2_2 = was_test_passed_by_name(data, "addVertex() 2 [Hint: Duplicates.]")
    c2_3 = was_test_passed_by_name(
        data, "addVertex() 3 [Hint: Keeps Accurate Vertex Count.]"
    )
    c2_weight = 5.0

    if c2_1 and c2_2 and c2_3:  # Proficient
        proxy_criteria_grades += [c2_weight]
    elif c2_1 or (c2_2 and c2_3):  # Competent
        proxy_criteria_grades += [c2_weight * 0.5]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: getAdj(int v) [2pts]
    #   2 pts	Proficient	Returns the direct successors of a vertex v
    #   1 pts	Competent	Does not properly return direct successors.
    #   0 pts	Novice	    Did not attempt

    # 4.1) BetterDigraph getAdj() [Hint: New Vertices.] (1/1)
    c3_1 = was_test_passed_by_name(data, "getAdj() [Hint: New Vertices.]")
    c3_weight = 2.0

    if c3_1:  # Proficient
        proxy_criteria_grades += [c3_weight]
    # TODO: how to assess Competent?
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: getEdgeCount() [1pts]
    #   1 pts	Proficient	Number of edges.
    #   0 pts	Novice	    Did not attempt

    # 5.1) getEdgeCount() 1 [Hint: Basic Behavior with adding and removing edges] (0.5/0.5)
    # 5.2) getEdgeCount() 2 [Hint: Missing/Duplicate Edges] (0/0.5)
    c4_1 = was_test_passed_by_name(
        data, "getEdgeCount() [Hint: Basic Behavior with adding edges.]"
    )
    c4_weight = 1.0

    if c4_1:  # Proficient
        proxy_criteria_grades += [c4_weight]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: getIndegree(int v) [2pts]
    #   2 pts	Proficient	Returns the in-degree of a vertex.
    #   1 pts	Competent	Does not properly return direct successors.
    #   0 pts	Novice	    Did not attempt

    # 6.1) BetterDigraph getInDegree() 1 [Hint: Basic Behavior.] (1/1)
    # 6.2) BetterDigraph getInDegree() 2 [Hint: Missing Element.] (1/1)
    c5_1 = was_test_passed_by_name(data, "getInDegree() 1 [Hint: Basic Behavior.]")
    c5_2 = was_test_passed_by_name(data, "getInDegree() 2 [Hint: Missing Element.]")
    c5_weight = 2.0

    if c5_1 and c5_2:  # Proficient
        proxy_criteria_grades += [c5_weight]
    # MB: I would assess competent based on first test only, the second one is very easy
    elif c5_1:
        proxy_criteria_grades += [c5_weight * 0.5]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: getVertexCount() [1pts]
    #   1 pts	Proficient	Returns number of vertices.
    #   0 pts	Novice	    Did not attempt

    # 7.1) getVertexCount() 1 [Hint: Basic Behavior with adding and removing vertices] (0.5/0.5)
    c6_1 = was_test_passed_by_name(
        data, "getVertexCount() [Hint: Basic Behavior with adding vertices]"
    )
    c6_weight = 1.0

    if c6_1:  # Proficient
        proxy_criteria_grades += [c6_weight]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: removeEdge(int v, int w) [2pts]
    #   2 pts	Proficient	Removes edge from graph. If vertices do not exist, does not remove edge.
    #   1 pts	Competent	Does not remove edge, or does not check that vertices exist.
    #   0 pts	Novice	    Did not attempt

    # 8.1) BetterDigraph removeEdge() 1 [Hint: Basic Behavior.] (1)
    # 8.2) BetterDigraph removeEdge() 2 [Hint: Nonexistent Edge/Vertex.] (.5)
    # 8.3) BetterDigraph removeEdge() 3 [Hint: Keeps Accurate Edge Count.] (.5)

    c7_1 = was_test_passed_by_name(data, "removeEdge() 1 [Hint: Basic Behavior.]")
    c7_2 = was_test_passed_by_name(
        data, "removeEdge() 2 [Hint: Nonexistent Edge/Vertex.]"
    )
    c7_3 = was_test_passed_by_name(
        data, "removeEdge() 3 [Hint: Keeps Accurate Edge Count.]"
    )
    c7_weight = 2.0

    if c7_1 and c7_2 and c7_3:  # Proficient
        proxy_criteria_grades += [c7_weight]
    elif (
        c7_1 or c7_2
    ):  # Competent. RA: it seems like c7_3 isn't really in the rubric here.
        proxy_criteria_grades += [c7_weight * 0.5]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: removeVertex(int v) [4pts]
    #   2 pts	Proficient	Removes vertex from graph. If vertex does not exist, does not try to remove it.
    #   1 pts	Competent	Does not remove vertex.
    #   0 pts	Novice	    Did not attempt

    # 9.1) BetterDigraph removeVertex() 1 [Hint: Basic Behavior.] (1)
    # 9.2) BetterDigraph removeVertex() 2 [Hint: Nonexistent Vertex] (.5)
    # 9.3) BetterDigraph removeVertex() 3 [Hint: Removes Edges] (1)
    # 9.4) BetterDigraph removeVertex() 4 [Hint: Maintains Count.] (.5)
    c8_1 = was_test_passed_by_name(data, "removeVertex() 1 [Hint: Basic Behavior.]")
    c8_2 = was_test_passed_by_name(data, "removeVertex() 2 [Hint: Nonexistent Vertex.]")
    c8_3 = was_test_passed_by_name(data, "removeVertex() 3 [Hint: Removes Edges.]")
    c8_4 = was_test_passed_by_name(data, "removeVertex() 4 [Hint: Maintains Count.]")
    c8_weight = 4.0

    if c8_1 and c8_2 and c8_3 and c8_4:  # Proficient
        proxy_criteria_grades += [c8_weight]
    elif (
        (c8_1 and c8_2)
        or (c8_3 and c8_4)
        or (c8_1 and c8_4)
        or (c8_2 and c8_3)
        or (c8_1 and c8_3)
    ):
        # all 2x or 3x combos that give at least 1.5 pts
        # all relevant 3x combos should be implicit here I think - MB
        proxy_criteria_grades += [c8_weight * 0.5]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: vertices() [2pts]
    #   2 pts	Proficient	Returns iterable object containing all vertices in graph.
    #   1 pts	Competent	Does not return iterable object or object does not contain all vertices.
    #   0 pts	Novice	    Did not attempt

    # 10.1) BetterDigraph vertices() [Hint: Basic Behavior.] (2/2)
    c9_1 = was_test_passed_by_name(data, "vertices() [Hint: Basic Behavior.]")
    c9_weight = 2.0

    if c9_1:  # Proficient
        proxy_criteria_grades += [c9_weight]
    # TODO: how to assess Competent? could add a new test case that only checks if non-null is returned.
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # IntuitiveTopological: Intuitive Topological Algorithm [8 pts]
    #  8 pts Proficient	Implemented the IntuitiveTopological as stated in the assignment.
    #  4 pts Competent	Did not correctly implement the stated algorithm.
    #  0 pts Novice		Did not attempt or used DFS algorithm.

    # 15.1) TopologicalSort intuitiveTopological() [Hint: Uses intuitive topological algorithm to generate order.] (8)
    c12_1 = was_test_passed_by_name(
        data,
        "intuitiveTopological() 1 [Hint: Uses intuitive topological algorithm to generate order on a simple graph.]",
    )
    c12_2 = was_test_passed_by_name(
        data,
        "intuitiveTopological() 2 [Hint: Uses intuitive topological algorithm to generate order on a complex graph.]",
    )
    c12_weight = 8.0

    if c12_1 and c12_2:
        proxy_criteria_grades += [c12_weight]
    elif c12_1 or c12_2:
        proxy_criteria_grades += [c12_weight * 0.5]
    else:
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # IntuitiveTopological: Intuitive Topological Cycles [8 pts]
    #  8 pts Proficient	Checks for cycles before trying to generate topological sort.
    #  4 pts Competent 	Does not correctly check for cycles before computing sort.
    #  0 pts Novice		Did not attempt.

    # 13.2) order() [Hint: Cycles are correctly checked for] (8)
    c13_3 = was_test_passed_by_name(
        data, "order() 3 [Hint: Cycles in small graphs are correctly identified.]"
    )
    c13_4 = was_test_passed_by_name(
        data, "order() 4 [Hint: Cycles in small graphs are correctly identified.]"
    )
    c13_5 = was_test_passed_by_name(
        data, "order() 5 [Hint: Cycles in very small graph are correctly identified.]"
    )
    c13_6 = was_test_passed_by_name(
        data, "order() 6 [Hint: Cycles in graphs are correctly identified.]"
    )  # requires c13_3 and c13_4.
    c13_7 = was_test_passed_by_name(
        data, "order() 7 [Hint: Cycles in complex graphs are correctly identified.]"
    )
    # 4-8
    c13_weight = 8.0

    if c13_3 and c13_4 and c13_5 and c13_6 and c13_7:  # Proficient
        proxy_criteria_grades += [c13_weight]
    elif (c13_3 and c13_4) or c13_6 or c13_7:
        proxy_criteria_grades += [c13_weight * 0.5]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    """
    elif (c13_1 and c13_2) or (c13_2 and c13_3) or(c13_1 and c13_3):  # Proficient
        proxy_criteria_grades += [c13_weight * .5]

    """

    ####################################################################################################################
    # IntuitiveTopological: order() [4 pts]
    #  4 pts Proficient	Returns an iterable object containing a topological sort.
    #  2 pts Competent	Does not return iterable object, or does not contain topological sort.
    #  0 pts Novice 		Did not attempt.

    # 13.1) TopologicalSort order() 1 [Hint: Generating a result.] (.5)
    # 13.2) TopologicalSort order() 2 [Hint: Generating valid topological sort.] (1.5)
    c14_1 = was_test_passed_by_name(data, "order() 1 [Hint: Generating a result.]")
    c14_2 = was_test_passed_by_name(
        data, "order() 2 [Hint: Generating valid topological sort.]"
    )
    c14_weight = 4.0

    if c14_1 and c14_2:  # Proficient
        proxy_criteria_grades += [c14_weight]
    elif c14_1:
        proxy_criteria_grades += [c14_weight * 0.5]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # IntuitiveTopological: isDAG() [4 pts]
    #  2 pts Proficient	Returns true if the graph being sorted is a DAG, false otherwise.
    #  1 pts Competent	Does not true if the graph being sorted is a DAG, false otherwise.
    #  0 pts Novice 		Did not attempt.

    # 14.1) TopologicalSort isDag() 1 [Hint: Simple graph.] (.5)
    # 14.2) TopologicalSort isDag() 2 [Hint: Branching graph.] (1.5)
    c15_1 = was_test_passed_by_name(data, "isDag() 1 [Hint: Simple graph.]")
    c15_2 = was_test_passed_by_name(data, "isDag() 2 [Hint: Branching graph.]")
    c15_weight = 4.0

    if c15_1 and c15_2:  # Proficient
        proxy_criteria_grades += [c15_weight]
    elif c15_1 or c15_2:  # Competent. Interpreting the level as working inconsistently.
        proxy_criteria_grades += [c15_weight * 0.5]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: isEmpty() [1pts]
    #   1 pts Full Marks	Returns true if and only if there are no vertices in the graph.
    #   0 pts No Marks	Did not attempt or skeletal answer.

    # 11.1) BetterDigraph isEmpty()[Hint: Basic Behavior] (1)
    c10_1 = was_test_passed_by_name(data, "isEmpty() [Hint: Basic Behavior]")
    c10_weight = 1.0

    if c10_1:  # Proficient
        proxy_criteria_grades += [c10_weight]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    ####################################################################################################################
    # BetterDiGraph: containsVertex() [1pts]
    #   1 pts Full Marks	Trues true if indicated vertex is contained by the graph.
    #   0 pts No Marks	Did not attempt or skeletal answer.

    # 12.1) BetterDigraph containsVertex() [Hint: Basic Behavior] (1)
    c11_1 = was_test_passed_by_name(data, "containsVertex() [Hint: Basic Behavior]")
    c11_weight = 1.0

    if c11_1:  # Proficient
        proxy_criteria_grades += [c11_weight]
    else:  # Novice
        proxy_criteria_grades += [0.0]

    total_score_proxy = sum([ps for ps in proxy_criteria_grades if ps])

    return proxy_criteria_grades, total_score_proxy
