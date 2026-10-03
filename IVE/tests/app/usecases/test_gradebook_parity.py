from pathlib import Path

from GAVEL.app.usecases.anonymize_gradebook import (
    AnonymizeGradebookRequest,
    AnonymizeGradebookUseCase,
)
from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader


FIXTURE_DIR = Path(__file__).parents[2] / "data" / "parity" / "gradebook"


def test_gradebook_matches_palantir_except_canvas_id_divergence():
    reader = LegacyGradebookCSVReader()

    original = reader.parse(FIXTURE_DIR / "gradebook.csv")
    expected = reader.parse(FIXTURE_DIR / "gradebook_golden.csv")

    use_case = AnonymizeGradebookUseCase()

    request = AnonymizeGradebookRequest(
        gradebook=original,
        consented_ids=(309780,),
        id_map=((309780, 4242),),
    )

    result = use_case.execute(request)

    actual_row = result.gradebook.rows[0]
    expected_row = expected.rows[0]

    assert result.gradebook.columns == expected.columns
    assert actual_row.student_name == expected_row.student_name
    assert actual_row.sis_login_id == expected_row.sis_login_id
    assert actual_row.section == expected_row.section
    assert actual_row.assignment_scores == expected_row.assignment_scores

    # Palantir uses the constant 123456 for the Canvas ID.
    # GAVEL preserves a unique anonymous ID.
    assert expected_row.canvas_id == 123456
    assert actual_row.canvas_id == 4242