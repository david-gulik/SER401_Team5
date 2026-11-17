from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricRating,
)
from GAVEL.pages.inspect_grades.rubric_correction_panel import (
    RubricCorrectionPanel,
)


def test_displays_selected_criterion(qapp, theme):
    panel = RubricCorrectionPanel(theme)

    criterion = RubricCriterionDefinition(
        id="criterion_1",
        description="Code Correctness",
        long_description="Code produces the expected output.",
        points=4.0,
        ratings=(
            RubricRating(
                id="full",
                description="Full Credit",
                long_description="",
                points=4.0,
            ),
            RubricRating(
                id="partial",
                description="Partial Credit",
                long_description="",
                points=2.0,
            ),
            RubricRating(
                id="none",
                description="No Credit",
                long_description="",
                points=0.0,
            ),
        ),
    )

    panel.set_criterion(
        student_id=100002,
        criterion=criterion,
        original_score=2.0,
    )

    assert panel.student_label.text() == "Student: 100002"
    assert panel.criterion_label.text() == "Criterion: Code Correctness"
    assert panel.original_grade_label.text() == ("Original Grade (Canvas): 2 / 4")

    assert panel.description_text.text() == ("Code produces the expected output.")

    buttons = panel.grade_buttons.buttons()

    assert len(buttons) == 3
    assert any("Full Credit: 4 / 4" in button.text() for button in buttons)
    assert any("Partial Credit: 2 / 4" in button.text() for button in buttons)
    assert any("No Credit: 0 / 4" in button.text() for button in buttons)

    assert panel.notes_input.isEnabled()

    panel.deleteLater()


def test_selecting_corrected_grade_emits_score(qapp, theme):
    panel = RubricCorrectionPanel(theme)

    criterion = RubricCriterionDefinition(
        id="criterion_1",
        description="Code Correctness",
        long_description="",
        points=4.0,
        ratings=(
            RubricRating("full", "Full Credit", "", 4.0),
            RubricRating("partial", "Partial Credit", "", 2.0),
            RubricRating("none", "No Credit", "", 0.0),
        ),
    )

    selected_scores = []
    panel.correction_changed.connect(selected_scores.append)

    panel.set_criterion(100002, criterion, 2.0)

    buttons = panel.grade_buttons.buttons()

    buttons[0].click()
    buttons[1].click()

    assert selected_scores == [4.0, 2.0]
    assert buttons[1].isChecked()
    assert not buttons[0].isChecked()

    panel.deleteLater()


def test_editing_notes_emits_text(qapp, theme):
    panel = RubricCorrectionPanel(theme)

    criterion = RubricCriterionDefinition(
        id="criterion_1",
        description="Code Correctness",
        long_description="",
        points=4.0,
        ratings=(RubricRating("full", "Full Credit", "", 4.0),),
    )

    notes = []
    panel.notes_changed.connect(notes.append)

    panel.set_criterion(100002, criterion, 2.0)
    panel.notes_input.setPlainText("Student deserves full credit.")

    assert panel.notes_input.toPlainText() == ("Student deserves full credit.")
    assert notes[-1] == "Student deserves full credit."

    panel.deleteLater()


def test_clearing_panel_resets_selection(qapp, theme):
    panel = RubricCorrectionPanel(theme)

    criterion = RubricCriterionDefinition(
        id="criterion_1",
        description="Code Correctness",
        long_description="",
        points=4.0,
        ratings=(RubricRating("full", "Full Credit", "", 4.0),),
    )

    panel.set_criterion(100002, criterion, 2.0)

    panel.grade_buttons.buttons()[0].click()
    panel.notes_input.setPlainText("Correction note")

    panel.clear()

    assert panel.student_label.text() == "Student: —"
    assert panel.criterion_label.text() == "Criterion: —"
    assert panel.original_grade_label.text() == "Original Grade (Canvas): —"
    assert panel.grade_buttons.buttons() == []
    assert panel.notes_input.toPlainText() == ""
    assert not panel.notes_input.isEnabled()

    panel.deleteLater()


def test_handles_missing_numeric_ratings(qapp, theme):
    panel = RubricCorrectionPanel(theme)

    criterion = RubricCriterionDefinition(
        id="criterion_1",
        description="Code Correctness",
        long_description="",
        points=None,
        ratings=(RubricRating("ungraded", "Not Graded", "", None),),
    )

    panel.set_criterion(100002, criterion, None)

    assert panel.grade_buttons.buttons() == []
    assert panel.original_grade_label.text() == ("Original Grade (Canvas): — / —")

    assert (
        panel.grade_options_layout.itemAt(1).widget().text()
        == "No predefined rubric ratings available."
    )

    panel.deleteLater()


def test_switching_criterion_resets_previous_values(qapp, theme):
    panel = RubricCorrectionPanel(theme)

    first_criterion = RubricCriterionDefinition(
        id="criterion_1",
        description="Code Correctness",
        long_description="First criterion description.",
        points=4.0,
        ratings=(
            RubricRating("full", "Full Credit", "", 4.0),
            RubricRating("none", "No Credit", "", 0.0),
        ),
    )

    second_criterion = RubricCriterionDefinition(
        id="criterion_2",
        description="Documentation",
        long_description="Second criterion description.",
        points=2.0,
        ratings=(RubricRating("partial", "Partial Credit", "", 1.0),),
    )

    panel.set_criterion(100001, first_criterion, 4.0)
    panel.grade_buttons.buttons()[0].click()
    panel.notes_input.setPlainText("Previous correction note")

    panel.set_criterion(100002, second_criterion, 1.0)

    assert panel.student_label.text() == "Student: 100002"
    assert panel.criterion_label.text() == "Criterion: Documentation"
    assert panel.original_grade_label.text() == ("Original Grade (Canvas): 1 / 2")
    assert panel.description_text.text() == ("Second criterion description.")

    buttons = panel.grade_buttons.buttons()
    assert len(buttons) == 1
    assert buttons[0].text() == "Partial Credit: 1 / 2"
    assert buttons[0].isChecked()
    assert panel.notes_input.toPlainText() == ""

    panel.deleteLater()


def test_original_grade_selected_without_emitting_correction(qapp, theme):
    panel = RubricCorrectionPanel(theme)

    criterion = RubricCriterionDefinition(
        id="criterion_1",
        description="Code Correctness",
        long_description="",
        points=4.0,
        ratings=(
            RubricRating("full", "Full Credit", "", 4.0),
            RubricRating("partial", "Partial Credit", "", 2.0),
            RubricRating("none", "No Credit", "", 0.0),
        ),
    )

    corrections = []
    panel.correction_changed.connect(corrections.append)

    panel.set_criterion(100002, criterion, 2.0)

    buttons = panel.grade_buttons.buttons()

    assert buttons[1].isChecked()
    assert not buttons[0].isChecked()
    assert not buttons[2].isChecked()
    assert corrections == []

    buttons[0].click()

    assert corrections == [4.0]

    panel.deleteLater()
