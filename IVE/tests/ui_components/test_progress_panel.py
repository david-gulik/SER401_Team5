from __future__ import annotations

import pytest

from GAVEL.app.progress import DownloadProgress
from GAVEL.ui_components.progress_panel import ProgressPanel, format_duration, format_remaining


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def panel(qapp, theme, clock) -> ProgressPanel:
    return ProgressPanel(theme, clock=clock)


@pytest.mark.parametrize(
    ("seconds", "text"), [(0, "0:00"), (102, "1:42"), (3725, "1:02:05"), (-3, "0:00")]
)
def test_format_duration(seconds: float, text: str):
    assert format_duration(seconds) == text


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(20, "under a minute left"), (90, "about 2 min left"), (600, "about 10 min left")],
)
def test_format_remaining(seconds: float, text: str):
    assert format_remaining(seconds) == text


def test_hidden_until_progress_arrives(panel):
    assert panel.isHidden()


def test_shows_label_count_percent_and_last_item(panel):
    panel.show_progress(DownloadProgress("Downloading quizzes", 10, 22, "Module 4 Quiz"))

    assert not panel.isHidden()
    assert panel.title_text == "Downloading quizzes"
    assert panel.count_text == "10 of 22"
    assert panel.percent_text == "45%"
    assert panel.detail_text == "Last finished: Module 4 Quiz"
    assert (panel.bar.minimum(), panel.bar.maximum(), panel.bar.value()) == (0, 22, 10)


def test_unknown_total_spins_with_no_count(panel):
    panel.show_progress(DownloadProgress("Signing in to Gradescope", 0, 0))

    assert panel.count_text == ""
    assert panel.detail_text == ""
    assert (panel.bar.minimum(), panel.bar.maximum()) == (0, 0)


def test_time_left_follows_the_pace_of_the_current_batch(panel, clock):
    panel.show_progress(DownloadProgress("Downloading quizzes", 0, 10))
    clock.now += 60
    panel.show_progress(DownloadProgress("Downloading quizzes", 2, 10, "Quiz 2"))

    # 30 s per quiz, 8 quizzes to go.
    assert panel.timing_text == "1:00 elapsed · about 4 min left"


def test_new_batch_restarts_the_estimate_but_not_the_elapsed_time(panel, clock):
    panel.show_progress(DownloadProgress("Step 5 of 6: Downloading quizzes", 4, 4))
    clock.now += 120
    panel.show_progress(DownloadProgress("Step 6 of 6: Downloading rubric assessments", 0, 3))

    assert panel.timing_text == "2:00 elapsed"
    clock.now += 10
    panel.show_progress(DownloadProgress("Step 6 of 6: Downloading rubric assessments", 1, 3))
    assert panel.timing_text == "2:10 elapsed · under a minute left"


def test_clear_hides_and_resets_the_clock(panel, clock):
    panel.show_progress(DownloadProgress("Downloading quizzes", 1, 2))
    clock.now += 300
    panel.clear()
    assert panel.isHidden()

    panel.show_progress(DownloadProgress("Downloading quizzes", 0, 2))
    assert panel.timing_text == "0:00 elapsed"
