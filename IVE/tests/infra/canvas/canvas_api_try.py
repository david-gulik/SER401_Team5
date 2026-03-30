from GAVEL.infra.canvas.http_canvas_client import (
    CanvasApiConfig,
    HttpCanvasClient,
)

config = CanvasApiConfig(
    base_url="https://canvas.asu.edu",
    token="TOKEN_GOES_HERE",
    account_id=319
)

client = HttpCanvasClient(config)

result = client.fetch_quiz_student_analysis(
    course_id=253450,
    quiz_id=1960789,
)

print(f"Success! Got {len(result)} bytes")
print(result[:500])
