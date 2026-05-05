# gradescope-tool/Gradescope

## Overview

Gradescope is a Python package project designed to provide seamless interaction with the Gradescope service, offering functionalities such as login, fetching course and assignment information, and submission downloads. By encapsulating key entities like Courses, Assignments, and Members, Gradescope provides a structured approach for managing data in JSON and CSV formats. The project aims to simplify tasks for users by providing wrapper functions that handle data retrieving and API calls.

## Installation

`pip install gradescope-tool`

## Example Usage

```
from gradescope import *

# Instantiate Gradescope and log on 

gs = Gradescope('username', 'password')

# View your courses 

courses = gs.get_courses(role=Role.INSTRUCTOR)
# courses:
# [Course(
#    course_id=123456,
#    url='/courses/123456',
#    role='instructor',
#    term='Spring 2024',
#    short_name='Math 2B',
#    full_name='Math 2B: Calculus'
# ), ...]

# View all assignments from some course (selectable in array)

assignments = gs.get_assignments(courses[0])
# assignments:
# [Assignment(
#    assignment_id=654321,
#    assignment_type='assignment',
#    url='/courses/123456/assignments/654321',
#    title='Assignment 1',
#    container_id=None,
#    versioned=False,
#    version_index=None,
#    version_name=None,
#    total_points='100.0',
#    student_submission=True,
#    created_at='Apr 01',
#    release_date='2024-04-01T00:00',
#    due_date='2024-04-07T23:59',
#    hard_due_date='2024-04-10T23:59',
#    time_limit=None,
#    active_submissions=250,
#    grading_progress=100,
#    published=True,
#    regrade_requests_open=False,
#    regrade_requests_possible=True,
#    regrade_request_count=0,
#    due_or_created_at_date='2024-04-07T23:59'
# ), ...]

# View all members of any course

members = gs.get_members(courses[0])
# members:
# [Member(
#    member_id='112233',
#    full_name='Peter Anteater',
#    first_name='Peter',
#    last_name='Anteater',
#    role='0',
#    sid='1234567890',
#    email='uci.mascot@uci.edu'
# ), ...]

# View submissions to any assignment from any member_id

past_submissions = gs.get_past_submissions(courses[0], assignments[0], members[0])
# past_submissions:
# [Submission(
#    course_id=123456,
#    assignment_id=654321,
#    member_id='112233',
#    submission_id=987654321,
#    created_at='2024-04-07T12:34:56.655388-07:00',
#    score=55.55,
#    url='/courses/123456/assignments/654321/submissions/987654321'
# ), ...]

# View and download gradebook info as JSON

gradebook = gs.get_gradebook(courses[0], members[0])
save_json('./gradebook.json', gradebook, encoder=EnhancedJSONEncoder)

# View and download grades info as CSV

grades_csv = gs.get_assignment_grades(assignments[0])
save_csv('./assignment_grades.csv', grades_csv)

# Download assignment submission using url helper

gs.download_file('./submission.zip', past_submission[-1].get_file_url())
```