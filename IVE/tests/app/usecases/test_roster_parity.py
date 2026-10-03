from pathlib import Path

import pandas as pd
from GAVEL.app.usecases.anonymize_roster import (
    AnonymizeRosterRequest,
    AnonymizeRosterUseCase,
)
from GAVEL.infra.csv.canvas_roster_csv_reader import CanvasRosterCSVReader


FIXTURE_DIR = Path(__file__).parents[2] / "data" / "parity" / "roster"


def test_roster_matches_palantir_except_status_and_residency_divergence():
    reader = CanvasRosterCSVReader()

    original = reader.read(FIXTURE_DIR / "roster.csv")
    expected = reader.read(FIXTURE_DIR / "roster_golden.csv")

    use_case = AnonymizeRosterUseCase()

    request = AnonymizeRosterRequest(
        students=original,
        consented_ids=(9000000001,),
        id_map=((9000000001, 4242),),
    )

    result = use_case.execute(request)

    actual_student = result.students[0]
    expected_student = expected[0]

    assert actual_student.id == expected_student.id
    assert actual_student.posting_id == expected_student.posting_id
    assert actual_student.first_name == expected_student.first_name
    assert actual_student.last_name == expected_student.last_name
    assert actual_student.units == expected_student.units
    assert actual_student.grade_basis == expected_student.grade_basis
    assert actual_student.program_and_plan == expected_student.program_and_plan
    assert actual_student.academic_level == expected_student.academic_level
    assert actual_student.asurite == expected_student.asurite
    assert actual_student.zoom_email == expected_student.zoom_email

    # Palantir blanks Status and Residency.
    # GAVEL preserves both values.
    assert pd.isna(expected_student.status)
    assert pd.isna(expected_student.residency)
    assert actual_student.status == original[0].status
    assert actual_student.residency == original[0].residency