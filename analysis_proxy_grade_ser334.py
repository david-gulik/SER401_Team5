"""
shoggoth-validation - analysis_proxy_grade_ser334.py

See analysis_proxy_grade_ser222.py for details.
"""

__author__ = "Ruben Acuna"
__author__ = "Kyle Burnett"
__author__ = "Michael Deitch"
__author__ = "Sarath Kumar Dunga"

from analysis_proxy_grade_util import was_test_passed_by_name


def compute_proxies_m2_24sc(data):
    proxies = []

    # total: 30pts

    # 1) main menu [2pts]
    t1_1 = was_test_passed_by_name(
        data, "Main Menu 1"
    )  # Main Menu 1 [Hint: Displays Credits.]
    t1_2 = was_test_passed_by_name(
        data, "Main Menu 2"
    )  # Main Menu 2 [Hint: Displays Correct Credit Count.]

    if t1_1 and t1_2:
        proxies += [2.0]
    elif t1_1:
        proxies += [1.0]
    else:
        proxies += [0.0]

    # 2) memory leaks [2pts]
    t2_1 = was_test_passed_by_name(
        data, "Memory Allocation 3"
    )  # 7.3) Memory Allocation 3 [Hint: Frees all Memory on close.]
    t2_2 = was_test_passed_by_name(
        data, "Memory Allocation 4"
    )  # 7.4) Memory Allocation 4 [Hint: Frees Correct Memory addresses on close.]

    if t2_1 and t2_2:
        proxies += [2.0]
    elif t2_1:
        proxies += [1.0]
    else:
        proxies += [0.0]

    # 3) course_insert [7pts]
    t3_1 = was_test_passed_by_name(
        data, "Insert Course 1"
    )  # 2.1) Insert Course 1 [Hint: Basic Behavior.]
    t3_2 = was_test_passed_by_name(
        data, "Insert Course 2"
    )  # 2.2) Insert Course 2 [Hint: Inserts 2 Courses.]
    t3_3 = was_test_passed_by_name(
        data, "Insert Course 3"
    )  # 2.3) Insert Course 3 [Hint: Correct Ordering.]
    t3_4 = was_test_passed_by_name(
        data, "Insert Course 4"
    )  # 2.4) Insert Course 4 [Hint: Inserts 3 Courses.]
    t3_5 = was_test_passed_by_name(
        data, "Insert Course 5"
    )  # 2.5) Insert Course 5 [Hint: Correct Ordering.]
    t3_6 = was_test_passed_by_name(
        data, "Insert Course 6"
    )  # 2.6) Insert Course 6 [Hint: Inserting a Duplicate Course.]
    t3_7 = was_test_passed_by_name(
        data, "Insert Course 7"
    )  # 2.7) Insert Course 7 [Hint: Prints Error Message on Duplicate.]

    if t3_1 and t3_2 and t3_3 and t3_4 and t3_5 and t3_6 and t3_7:
        proxies += [7.0]
    elif (
        t3_1 and t3_2 and t3_4
    ):  # NOTE: the rubric has a memory requirement here... probably can skip since not in full points level.
        proxies += [3.5]
    elif t3_1:
        proxies += [1.75]
    else:
        proxies += [0.0]

    # 4) course_insert::memory [2pts]
    t4_1 = was_test_passed_by_name(
        data, "Memory Allocation 1"
    )  # 7.1) Memory Allocation 1 [Hint: Uses Malloc when creating courses.]
    t4_2 = was_test_passed_by_name(
        data, "Memory Allocation 2"
    )  # 7.2) Memory Allocation 2 [Hint: Frees memory from creating a course.]
    if t4_1 and t4_2:
        proxies += [2.0]
    elif t4_1:
        proxies += [1.0]
    else:
        proxies += [0.0]

    # 5) schedule_print [2pts]
    t5_1 = was_test_passed_by_name(
        data, "Schedule Print"
    )  # 3.1) Schedule Print [Hint: Basic Behavior.]

    if t5_1:
        proxies += [2.0]
    # NOTE: original had partial credit if printed all courses but incomplete data.
    else:
        proxies += [0.0]

    # 6) course_drop [5pts]
    t6_1 = was_test_passed_by_name(
        data, "Remove Course 1"
    )  # 4.1) Remove Course 1 [Hint: Basic Behavior.] (1/1)
    t6_2 = was_test_passed_by_name(
        data, "Remove Course 2"
    )  # 4.2) Remove Course 2 [Hint: Removing first course in a list of 2.] (1/1)
    t6_3 = was_test_passed_by_name(
        data, "Remove Course 3"
    )  # 4.3) Remove Course 3 [Hint: Removing course from list of 3.] (1/1)
    t6_4 = was_test_passed_by_name(
        data, "Remove Course 4"
    )  # 4.4) Remove Course 4 [Hint: Maintaining list after removing course.] (1/1)
    # 4.5) Remove Course 5 [Hint: Removing a course not in the list.] #NOTE: rubric doesn't use.
    if t6_1 and t6_2 and t6_3 and t6_4:
        proxies += [5.0]
    elif t6_1 and t6_2 and t6_3:
        proxies += [2.5]
    elif t6_1:
        proxies += [1.25]
    else:
        proxies += [0.0]

    # 7) course_drop::memory [2pts]
    t7_1 = was_test_passed_by_name(
        data, "Memory Allocation 5"
    )  # 7.4) Memory Allocation 5 [Hint: Frees Memory when removing courses.]
    t7_2 = was_test_passed_by_name(
        data, "Memory Allocation 6"
    )  # 7.5) Memory Allocation 6 [Hint: Frees Correct Memory addresses when removing courses.]

    if t7_1 and t7_2:
        proxies += [2.0]
    elif t7_1:
        proxies += [1.0]
    else:
        proxies += [0.0]

    # 8) schedule_load [4pts]
    t8_1 = was_test_passed_by_name(
        data, "Load File 1"
    )  # 5.1) Load File 1 [Hint: Basic Behavior.]
    t8_2 = was_test_passed_by_name(
        data, "Load File 2"
    )  # 5.2) Load File 2 [Hint: Loads all courses in file.]
    t8_3 = was_test_passed_by_name(
        data, "Load File 3"
    )  # 5.3) Load File 3 [Hint: No file exists.]

    if t8_1 and t8_2 and t8_3:
        proxies += [4.0]
    elif t8_1:
        proxies += [2.0]
    else:
        proxies += [0.0]

    # 9) schedule_save [4pts]
    t9_1 = was_test_passed_by_name(
        data, "Save File 1"
    )  # 6.1) Save File 1 [Hint: Saves a Course.]
    t9_2 = was_test_passed_by_name(
        data, "Save File 2"
    )  # 6.2) Save File 2 [Hint: Correctly Saves all Courses.]

    if t9_1 and t9_2:
        proxies += [4.0]
    elif t9_1:
        proxies += [2.0]
    else:
        proxies += [0.0]

    total_score_proxy = sum([ps for ps in proxies if ps])

    return proxies, total_score_proxy


def compute_proxies_m3_24fc(data):
    proxies = []

    # 1) BMP Headers IO (4pts)
    # Competent: Creates structures for the headers of a BMP file and functions which read and write them.
    # Novice: Some mistakes in creating structures for the headers of a BMP file or creating functions which read and write them.
    # No Marks: Most or all functionality is not attempted or is mostly incorrect.

    t1_1 = was_test_passed_by_name(
        data, "1.1)"
    )  # "1.1) BMP Headers IO [Hint: incorrectly reading and/or writing of BMP header]"
    t1_2 = was_test_passed_by_name(
        data, "1.2)"
    )  # 1.2) DIB Headers IO [Hint: incorrectly reading and/or writing of DIB header]

    if t1_1 and t1_2:
        proxies += [4.0]
    elif t1_1 or t1_2:
        proxies += [2.0]
    else:
        proxies += [0.0]

    # 2) Pixels IO (4pts)
    numPassed = 0
    t2_1 = was_test_passed_by_name(
        data, "2.1)"
    )  # 2.1) DIB Headers IO [Hint: incorrectly sized DIB header struct (change this to pixel struct size check)]

    t2_2 = was_test_passed_by_name(
        data, "2.2)"
    )  # "2.2) Reading pixels single row [Hint: Case when padding is needed]"

    t2_3 = was_test_passed_by_name(
        data, "2.3)"
    )  # "2.3) Reading pixels single rows [Hint: Case when padding is not needed"

    t2_4 = was_test_passed_by_name(
        data, "2.4)"
    )  # "2.4) Reading pixels many rows  [Hint: Case when padding is needed]"

    t2_5 = was_test_passed_by_name(
        data, "2.5)"
    )  # "2.5) Reading pixels many rows [Hint: Case when padding is not needed]"

    t3_1 = was_test_passed_by_name(
        data, "3.1)"
    )  # "3.1) Write pixels single row [Hint: Case when padding is needed]"

    t3_2 = was_test_passed_by_name(
        data, "3.2)"
    )  # "3.2) Write pixels single row [Hint: Case when padding is not needed]"

    t3_3 = was_test_passed_by_name(
        data, "3.3)"
    )  # "3.3) Write pixels many rows [Hint: Case when paddings is needed]"

    t3_4 = was_test_passed_by_name(
        data, "3.4)"
    )  # "3.4) Write pixels many rows [Hint: Case when paddings is not needed]"

    # Sorry for ugly code ._.
    if t2_1:
        numPassed += 1
    if t2_2:
        numPassed += 1
    if t2_3:
        numPassed += 1
    if t2_4:
        numPassed += 1
    if t2_5:
        numPassed += 1
    if t3_1:
        numPassed += 1
    if t3_2:
        numPassed += 1
    if t3_3:
        numPassed += 1
    if t3_4:
        numPassed += 1

    if t2_1 and t2_2 and t2_3 and t2_4 and t2_5 and t3_1 and t3_2 and t3_3 and t3_4:
        proxies += [4.0]
    elif numPassed >= 5:
        proxies += [2.0]
    else:
        proxies += [0.0]

    # 3) Input and output file names (4pts)
    t9_1 = was_test_passed_by_name(
        data, "9.1)"
    )  # "9.1) Program Input 1 [Hint: Default output file name is correct.]"

    t9_2 = was_test_passed_by_name(
        data, "9.2)"
    )  # "9.2) Program Input 2 [Hint: Output file matches argument.]"

    t9_3 = was_test_passed_by_name(
        data, "9.3)"
    )  # "9.3) Program Input 3 [Hint: Input File Does not Exist.]"

    if t9_1 and t9_2 and t9_3:
        proxies += [4.0]
    elif (t9_1 and t9_2) or (t9_1 and t9_3) or (t9_2 and t9_3):
        proxies += [2.0]
    else:
        proxies += [0.0]

    # 4) Input Validation
    t10_1 = was_test_passed_by_name(
        data, "10.1)"
    )  # "10.1) Program Input 4 [Hint: Color Arguments.]"

    if t10_1:
        proxies += [4.0]
    else:
        proxies += [0.0]

    # 5) Filter: Color Shift (5pts)
    t5_1 = was_test_passed_by_name(
        data, "5.1)"
    )  # "5.1) Color shift - Divisible by 4, shfiting 0. [Hint no changes to pixels]"

    t5_2 = was_test_passed_by_name(
        data, "5.2)"
    )  # "5.2) Color shift - Divisible by 4, shfiting positive. [Hint: Clamping and positive shifts]"

    t5_3 = was_test_passed_by_name(
        data, "5.3)"
    )  # "5.3) Color shift - Divisible by 4, shfiting negative. [Hint: Clamping and negative shifts]"

    t5_4 = was_test_passed_by_name(
        data, "5.4)"
    )  # "5.4) Color shift - Non-Divisible by 4, shfiting 0. [Hint no changes to pixels]"

    t5_5 = was_test_passed_by_name(
        data, "5.5)"
    )  # "5.5) Color shift - Non-Divisible by 4, shfiting positive. [Hint: Clamping and positive shifts]"

    t5_6 = was_test_passed_by_name(
        data, "5.6)"
    )  # "5.6) Color shift - Non-Divisible by 4, shfiting negative. [Hint: Clamping and negative shifts]"

    t10_1 = was_test_passed_by_name(
        data, "10.1)"
    )  # "10.1) Program Input 4 [Hint: Color Arguments.]"

    t10_2 = was_test_passed_by_name(
        data, "10.2)"
    )  # "10.2) Color Shift 1 [Hint: Basic Behavior Shifting Up.]"

    t10_3 = was_test_passed_by_name(
        data, "10.3)"
    )  # "10.3) Color Shift 2 [Hint: Basic Behavior Shifting Down.]"

    t10_4 = was_test_passed_by_name(
        data, "10.4)"
    )  # "10.4) Color Shift 3 [Hint: Shifting Multiple Colors Up.]"

    t10_5 = was_test_passed_by_name(
        data, "10.5)"
    )  # "10.5) Color Shift 4 [Hint: Shifting Multiple Colors Down.]"

    colorOption1 = (
        t5_2 and t5_5 and t10_2 and t10_4 and t5_1 and t5_4
    )  # only able to shift up correctly

    colorOption2 = (
        t5_3 and t5_6 and t10_3 and t10_5 and t5_1 and t5_4
    )  # only able to shift down correctly

    colorOption3 = t5_1 and t5_2 and t5_3  # only able to shift divisible by 4 images

    colorOption4 = (
        t5_4 and t5_5 and t5_6
    )  # only able to shift non divisible by 4 images

    if (
        t5_1
        and t5_2
        and t5_3
        and t5_4
        and t5_5
        and t5_6
        and t10_2
        and t10_3
        and t10_4
        and t10_5
    ):
        proxies += [5.0]
    elif colorOption1 or colorOption2 or colorOption3 or colorOption4:
        proxies += [2.5]
    else:
        proxies += [0.0]

    # 6) Test: Copy Image (5pts)
    t11_1 = was_test_passed_by_name(
        data, "11.1)"
    )  # "11.1) Copy Image 1 [Hint: Copied Image matches size of original image.]"

    t11_2 = was_test_passed_by_name(
        data, "11.2)"
    )  # "11.2) Copy Image 2 [Hint: Copied Image has matching pixel array.]"

    t12_1 = was_test_passed_by_name(
        data, "12.1)"
    )  # "12.1) Copy Image 3 [Hint: Copied Image matches size of original image on image with padding.]"

    t12_2 = was_test_passed_by_name(
        data, "12.2)"
    )  # "12.2) Copy Image 4 [Hint: Copied Image has matching pixel array on image with padding.]"

    if t11_1 and t11_2 and t12_1 and t12_2:
        proxies += [5.0]
    elif (t11_1 and t11_2) or (t12_1 and t12_2) or (t11_1 and t12_1):
        proxies += [2.5]
    else:
        proxies += [0.0]

    # 7) Image OOP (5pts)

    t8_1 = was_test_passed_by_name(
        data, "8.1)"
    )  # "8.1) Image create [Hint: all fields set correctly]"

    t8_2 = was_test_passed_by_name(
        data, "8.2)"
    )  # "8.2) Image destroy [Hint: 'Object' should be no longer usable]"

    t8_3 = was_test_passed_by_name(
        data, "8.3)"
    )  # "8.3) Image destroy [Hint: Underlying pixel array should not be deallocated...]"

    t4_1 = was_test_passed_by_name(
        data, "4.1)"
    )  # "4.1) Image -- getWidth [Hint: Case when padding is not needed]"

    t4_2 = was_test_passed_by_name(
        data, "4.2)"
    )  # "4.2) Image -- getWidth [Hint: Case when there is padding present"

    t4_3 = was_test_passed_by_name(
        data, "4.3)"
    )  # "4.3) Image -- getHeight [Hint: Case when there is no padding present]"

    t4_4 = was_test_passed_by_name(
        data, "4.4)"
    )  # "4.4) Image -- getHeight [Hint: case when there is padding present]"

    t4_5 = was_test_passed_by_name(
        data, "4.5)"
    )  # "4.5) Image -- getPixels [Hint: padding necessary]"

    t4_6 = was_test_passed_by_name(
        data, "4.6)"
    )  # "4.6) Image -- getPixels [Hint: No padding needed]"

    t4_7 = was_test_passed_by_name(
        data, "4.7)"
    )  # "4.7) Image -- getPixels [Hint: No padding needed]"

    t4_8 = was_test_passed_by_name(
        data, "4.8)"
    )  #  "4.8) Image -- getPixels [Hint: No padding needed]"

    numPassed = 0

    if t4_1:
        numPassed += 1
    if t4_2:
        numPassed += 1
    if t4_3:
        numPassed += 1
    if t4_4:
        numPassed += 1
    if t4_5:
        numPassed += 1
    if t4_6:
        numPassed += 1
    if t4_7:
        numPassed += 1
    if t4_8:
        numPassed += 1

    if (
        t8_1
        and t8_2
        and t8_3
        and t4_1
        and t4_2
        and t4_3
        and t4_4
        and t4_5
        and t4_6
        and t4_7
        and t4_8
    ):
        proxies += [5.0]
    elif (
        (numPassed >= 4)
        or (t8_1 and t8_2 and t8_3)
        or (t4_1 and t4_2 and t4_3 and t4_4 and t4_5 and t4_6 and t4_7)
    ):
        proxies += [2.5]
    else:
        proxies += [0.0]

    # 8) Filter: Grayscale (5pts)
    t6_1 = was_test_passed_by_name(
        data, "6.1)"
    )  # "6.1) Image_BW divisble by 4 [Hint: basic functionality]"

    t6_2 = was_test_passed_by_name(
        data, "6.2)"
    )  # "6.2) Image_BW -- non divisble by 4 [Hint: basic functionality]"

    t6_3 = was_test_passed_by_name(
        data, "6.3)"
    )  # "6.3) Image_BW -- Setting channels [Hint: Properties of grayscale ]"

    t13_1 = was_test_passed_by_name(
        data, "13.1)"
    )  # "13.1) Grayscale 1 [Hint: Basic Behavior.]"

    t13_2 = was_test_passed_by_name(
        data, "13.2)"
    )  # "13.2) Grayscale 2 [Hint: Grayscale applied before color shift.]"

    if t6_1 and t6_2 and t6_3 and t13_1 and t13_2:
        proxies += [5.0]
    elif (
        (t6_1 and t6_2 and t6_3)
        or (t6_1 and t6_3 and t13_1)
        or (t6_2 and t6_3 and t13_1)
    ):
        proxies += [2.5]
    else:
        proxies += [0.0]

    # 9) Filter: Scaling
    t7_1 = was_test_passed_by_name(
        data, "7.1)"
    )  # "7.1) Image -- Resize, number of pixels [Hint: scaling up]"

    t7_2 = was_test_passed_by_name(
        data, "7.2)"
    )  # "7.2) Image -- Resize, pixel data [Hint: scaling up]"

    t7_3 = was_test_passed_by_name(
        data, "7.3)"
    )  # "7.3) Image -- Resize, number of pixels [Hint: scaling down]"

    t7_4 = was_test_passed_by_name(
        data, "7.4)"
    )  # "7.4) Image -- Resize, pixel data [Hint: scaling down]"

    t14_1 = was_test_passed_by_name(
        data, "14.1)"
    )  # "14.1) Image Scaling 1 [Hint: Scaled up image has correct image size.]"

    t14_2 = was_test_passed_by_name(
        data, "14.2)"
    )  # "14.2) Image Scaling 2 [Hint: Scaled up image has correct pixel array.]"

    t14_3 = was_test_passed_by_name(
        data, "14.3)"
    )  # "14.3) Image Scaling 3 [Hint: Scaled down image has correct image size.]"

    t14_4 = was_test_passed_by_name(
        data, "14.4)"
    )  # "14.4) Image Scaling 4 [Hint: Scaled down image has correct pixel array.]"

    if t7_1 and t7_2 and t7_3 and t7_4 and t14_1 and t14_2 and t14_3 and t14_4:
        proxies += [5.0]
    elif (t7_1 and t7_2 and t14_1 and t14_2) or (t7_3 and t7_4 and t14_3 and t14_4):
        proxies += [2.5]
    else:
        proxies += [0.0]

    total_score_proxy = sum([ps for ps in proxies if ps])

    return proxies, total_score_proxy


def compute_proxies_m9_25fc(data):

    proxies = []

    # 1a) Read Data: Basic, Read Data: Process(es)
    # The two first checks in the rubric will be covered by 'Read Data From File", simply because
    # separating the two out is not very feasible.
    # Presently, there's not a lot of space for partial credit, so these two going to end up being all or nothing.

    t1_1 = was_test_passed_by_name(data, "Read Data From File")
    t1_2 = was_test_passed_by_name(data, "Dynamic Memory Allocation")

    if t1_1:
        proxies += [2.0]
        proxies += [2.0]
    else:
        proxies += [0.0]
        proxies += [0.0]

    # 1b) Read Data: Dynamic
    if t1_2:
        proxies += [7.0]
    else:
        proxies += [0.0]

    # 2) SJF: Simulation
    # Full credit if display and simulate, half if just simulate

    t2_1 = was_test_passed_by_name(data, "SJF Test Display Ticks")
    t2_2 = was_test_passed_by_name(data, "SJF Test Simulate Ticks")

    if t2_1 and t2_2:
        proxies += [3.0]
    elif t2_1:
        proxies += [1.5]
    else:
        proxies += [0.0]

    # 3) SJF: Algorithms
    # Full credit if the algorithm works properly for any number of processes.
    # Partial credit if it only works for two processes

    t2_3 = was_test_passed_by_name(data, "SJF Test Algorithm with 2 Processes")
    t2_4 = was_test_passed_by_name(
        data, "SJF Test Algorithm with a variable number of Processes"
    )

    if t2_3 and t2_4:
        proxies += [4.0]
    elif t2_3:  # semi-match: correctly supports 2, but does not require all.
        proxies += [2.0]
    else:
        proxies += [0.0]

    # 4) SJF: Output
    # Full credit if both turnaround and waiting time are correct
    # Partial credit if just one is correct

    t2_5 = was_test_passed_by_name(data, "SJF Calculate Turnaround Time")
    t2_6 = was_test_passed_by_name(data, "SJF Calculate Waiting Time")

    if t2_5 and t2_6:
        proxies += [3.0]
    elif t2_5 or t2_6:
        proxies += [1.5]
    else:
        proxies += [0.0]

    # 5) SJFL: Simulation
    # Full credit if display and simulate, half if just simulate

    t3_1 = was_test_passed_by_name(data, "SJFL Test Display Ticks")
    t3_2 = was_test_passed_by_name(data, "SJFL Test Simulate Ticks")

    if t3_1 and t3_2:
        proxies += [3.0]
    elif t3_1:
        proxies += [1.5]
    else:
        proxies += [0.0]

    # 6) SJFL: Algorithms
    # Full credit if the algorithm works properly for any number of processes.
    # Partial credit if it only works for two processes

    t3_3 = was_test_passed_by_name(data, "SJFL Test Algorithm with 2 Processes")
    t3_4 = was_test_passed_by_name(
        data, "SJFL Test Algorithm with a variable number of Processes"
    )

    if t3_3 and t3_4:
        proxies += [4.0]
    elif t3_3:  # semi-match: correctly supports 2, but does not require all.
        proxies += [2.0]
    else:
        proxies += [0.0]

    # 7) SJFL: Output
    # Full credit if turnaround, waiting time, and estimation error are correct
    # Partial credit if just one is correct

    t3_5 = was_test_passed_by_name(data, "SJFL Calculate Turnaround Time")
    t3_6 = was_test_passed_by_name(data, "SJFL Calculate Waiting Time")
    t3_7 = was_test_passed_by_name(data, "SJFL Calculate Estimation Error")

    if t3_5 and t3_6 and t3_7:
        proxies += [4.0]
    elif t3_5 or t3_6 or t3_7:
        proxies += [2.0]
    else:
        proxies += [0.0]


def compute_proxies_m6_25fc(data):

    proxies = []

    # 1) Command Args
    # If the program accepts arguments and outputs some image,
    # both input filename and output filename are assumed to pass.
    # However, it's tricky to give partial credit here without
    # splitting up some tests in the autograder.
    # Also, because these tests more directly correspond to filter selection,
    # they'll be used for those with 1 test being half credit and both being full.
    # This also doesn't really line up with the original rubric, but it's the best
    # that can be done.
    # If we care, this should be remedied by changing the actual tests and splitting up
    # some of the checks to more closely align with the rubric.

    t1_1 = was_test_passed_by_name(data, "Command Line 1")
    t1_2 = was_test_passed_by_name(data, "Command Line 2")

    # Input Filename and Output Filename
    if t1_1 and t1_2:
        proxies += [1.0]
        proxies += [1.0]
    else:
        proxies += [0.0]
        proxies += [0.0]

    # 3) Filter Selection (1 pt; full/half/0)
    if t1_1 and t1_2:
        proxies += [1.0]
    elif t1_1 or t1_2:
        proxies += [0.5]
    else:
        proxies += [0.0]

    # 2) Blur Filter
    # For the Blur Algorithm Points: Partial credit if one of the two passes, full credit if both do
    # For the rest of the memory stuff, we don't have tests for that in my autograder, so just auto fail

    t2_1 = was_test_passed_by_name(data, "Blur Interior Pixels")
    t2_2 = was_test_passed_by_name(data, "Blur Exterior Pixels")

    # Blur Algorithm
    if t2_1 and t2_2:
        proxies += [4.0]
    elif t2_1 or t2_2:
        proxies += [2.0]
    else:
        proxies += [0.0]

    # Blur: Threaded Algorithm (use FTC blur checks)
    ftc_b1 = was_test_passed_by_name(data, "FTC_Blur Check 1")
    ftc_b2 = was_test_passed_by_name(data, "FTC_Blur Check 2")
    ftc_b3 = was_test_passed_by_name(data, "FTC_Blur Check 3")
    passed_blur_ftc = sum([ftc_b1, ftc_b2, ftc_b3])
    if passed_blur_ftc == 3:
        proxies += [5.0]
    elif passed_blur_ftc > 0:
        proxies += [2.5]
    else:
        proxies += [0.0]

    # Automatic failures for:
    proxies += [0.0]  # Blur: Balanced Algorithm
    proxies += [0.0]  # Blur: Independent Memory
    proxies += [0.0]  # Blur: Padded Memory

    # 3) Cheese Filter
    # Mapping color algorithm is simple as it's a one to one for "Tint Image Yellow"
    # The hole algorithm, comprised of many tests in the autograder, will give partial credit if
    #   the "Add Holes" test passes, and full credit if they all pass
    # Like before, all of the dynamic memory related tests automatically fail

    t3_1 = was_test_passed_by_name(data, "Tint Image Yellow")
    t3_2 = was_test_passed_by_name(data, "Add Holes")

    t3_3 = was_test_passed_by_name(data, "Holes are Proper Shape")
    t3_4 = was_test_passed_by_name(data, "Holes are Proper Size")
    t3_5 = was_test_passed_by_name(data, "Correct Number of Holes")
    t3_6 = was_test_passed_by_name(data, "Holes are Uniformly Distributed")

    if t3_1:
        proxies += [4.0]
    else:
        proxies += [0.0]

    if t3_2 and t3_3 and t3_4 and t3_5 and t3_6:
        proxies += [6.0]
    elif t3_2:
        proxies += [3.0]
    else:
        proxies += [0.0]

    # Swiss Cheese: Threaded Algorithm (FTC Swiss checks)
    ftc_s1 = was_test_passed_by_name(data, "FTC_Swiss Check 1")
    ftc_s2 = was_test_passed_by_name(data, "FTC_Swiss Check 2")
    ftc_s3 = was_test_passed_by_name(data, "FTC_Swiss Check 3")
    passed_swiss_ftc = sum([ftc_s1, ftc_s2, ftc_s3])
    if passed_swiss_ftc == 3:
        proxies += [5.0]
    elif passed_swiss_ftc > 0:
        proxies += [2.5]
    else:
        proxies += [0.0]

    proxies += [0.0]  # Swiss Cheese: Data Splitting Algorithm
    proxies += [0.0]  # Swiss Cheese: Independent Memory

    total_proxy_score = sum([ps for ps in proxies if ps is not None])
    return proxies, total_proxy_score
