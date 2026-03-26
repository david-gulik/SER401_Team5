from GAVEL.infra.canvas.http_canvas_client import CanvasApiConfig, HttpCanvasClient
import os

BASE_URL = "https://canvas.asu.edu"
COURSE_ID = 253450

TOKEN = os.getenv("CANVAS_TOKEN")

if not TOKEN:
    raise ValueError("Set CANVAS_TOKEN first")

config = CanvasApiConfig(
    base_url=BASE_URL,
    token=TOKEN,
    account_id=1,
)

client = HttpCanvasClient(config)

print("Fetching gradebook CSV...")

csv_bytes = client.fetch_gradebook_csv(course_id=COURSE_ID)

with open("gradebook.csv", "wb") as f:
    f.write(csv_bytes)

print("gradebook.csv complete")