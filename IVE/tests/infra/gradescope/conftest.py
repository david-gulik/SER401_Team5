import pytest


@pytest.fixture(autouse=True)
def _gradescope_env(monkeypatch):
    monkeypatch.setenv("GRADESCOPE_BASE_URL", "https://www.gradescope.com")
    monkeypatch.setenv("GRADESCOPE_COURSES_SUFFIX", "/courses")
    monkeypatch.setenv("GRADESCOPE_ASSIGNMENTS_SUFFIX", "/assignments")
    monkeypatch.setenv("GRADESCOPE_REVIEW_GRADES_SUFFIX", "/review_grades")
    monkeypatch.setenv("GRADESCOPE_GENERATED_FILES_SUFFIX", "/generated_files")
    monkeypatch.setenv("SUBMISSIONS_FOLDER", "submissions")
