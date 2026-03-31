from GAVEL.infra.canvas.http_canvas_client import (
    CanvasApiConfig,
    HttpCanvasClient,
)

config = CanvasApiConfig(
    base_url="https://canvas.asu.edu",
    token="7236~2HGkhWPPTu7Jy4raxXEWV3VP7Yr244NZ4WZVwWG6v6NDAmV6XJBMxFvuXrNeE78K",
    account_id=319,
)

client = HttpCanvasClient(config)

# Inputs
COURSE_ID = 253450
ASSIGNMENT_ID = 7216983
USER_ID = 309780


# TEST 1 — Rubric level grades per submission
print("\n--- TEST 1: Rubric level grades per submission ---")

submissions = client._get_json(
    f"/api/v1/courses/{COURSE_ID}/assignments/{ASSIGNMENT_ID}/submissions"
    f"?include[]=rubric_assessment&include[]=user&per_page=5"
)

print(f"Submissions returned: {len(submissions)}")

for sub in submissions:
    rubric = sub.get("rubric_assessment")
    sis_id = sub.get("user", {}).get("sis_user_id")
    print(f"\n  user_id={sub.get('user_id')}  sis_user_id={sis_id}  score={sub.get('score')}")
    if rubric:
        print(f"  rubric_assessment: {rubric}")
    else:
        print("  rubric_assessment: not present (submission may not be graded yet)")


# TEST 2 — Grader comments on student submission
print("\n--- TEST 2: Grader comments on student submission ---")

user_sub = client._get_json(
    f"/api/v1/courses/{COURSE_ID}/assignments/{ASSIGNMENT_ID}/submissions/{USER_ID}"
    f"?include[]=rubric_assessment"
)

rubric = user_sub.get("rubric_assessment", {})

if not rubric:
    print("No rubric assessment found — make sure student submission has been graded.")
else:
    print(f"Score: {user_sub.get('score')}")
    print("Per-criterion breakdown:")
    for criterion_id, data in rubric.items():
        points = data.get("points", "—")
        comments = data.get("comments") or "(no comment left)"
        print(f"  [{criterion_id}]  points={points}  comment: {comments}")
