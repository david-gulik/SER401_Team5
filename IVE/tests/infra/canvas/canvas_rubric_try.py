from GAVEL.infra.canvas.http_canvas_client import (
    CanvasApiConfig,
    HttpCanvasClient,
)

config = CanvasApiConfig(base_url="https://canvas.asu.edu", token="TOKEN_GOES_HERE", account_id=319)
client = HttpCanvasClient(config)

course_id = 253450
assignment_id = 7216983  # Mod 4: ADJ Problem Set (from SCRUM-146)

submissions = client._get_json(
    f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
    "?include[]=rubric_assessment&include[]=user&per_page=10"
)

for sub in submissions:
    user = sub.get("user", {})
    sis_id = user.get("sis_user_id", "KEY_MISSING")
    print(f"\nuser_id={sub['user_id']}  sis_user_id={sis_id}  score={sub.get('score')}")

    # Unknown 3: is rubric_assessment missing entirely, or explicitly null?
    if "rubric_assessment" not in sub:
        print("  rubric_assessment: KEY ABSENT")
    elif sub["rubric_assessment"] is None:
        print("  rubric_assessment: null")
    else:
        ra = sub["rubric_assessment"]
        print(f"  rubric_assessment: {len(ra)} criteria")
        for crit_id, entry in list(ra.items())[:2]:  # inspect first 2
            print(f"  [{crit_id}] keys={list(entry.keys())}")
            print(f"    rating_id present: {'rating_id' in entry}")
            print(f"    comments type={type(entry.get('comments')).__name__}  value={repr(entry.get('comments'))}")