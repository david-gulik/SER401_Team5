import json
from pathlib import Path

from GAVEL.app.usecases.downselect_consented_students import (
    DownselectConsentedStudentsRequest,
    DownselectConsentedStudentsUseCase,
)
from GAVEL.infra.csv.canvas_consent_form_csv_reader import (
    CanvasConsentFormCSVReader,
)

FIXTURE_DIR = Path(__file__).parents[2] / "data" / "parity" / "consent"


def test_consent_matches_palantir_except_revocation_divergence():
    reader = CanvasConsentFormCSVReader()
    entries = tuple(reader.read(FIXTURE_DIR / "consent_form.csv"))

    palantir_consented_sis_ids = set(
        json.loads((FIXTURE_DIR / "consent_golden.json").read_text(encoding="utf-8"))
    )

    use_case = DownselectConsentedStudentsUseCase()

    result = use_case.execute(
        DownselectConsentedStudentsRequest(
            entries=entries,
        )
    )

    # GAVEL returns Canvas IDs, Palantir returns SIS IDs.
    # Convert GAVEL's result to SIS IDs so we can compare students.
    canvas_to_sis = {entry.canvas_id: entry.sis_id for entry in entries}

    gavel_consented_sis_ids = {canvas_to_sis[canvas_id] for canvas_id in result.consented_ids}

    # Normal consent case agrees in both implementations.
    assert 9000000002 in palantir_consented_sis_ids
    assert 9000000002 in gavel_consented_sis_ids

    # Palantir retains a student who consented on an earlier attempt.
    # GAVEL uses the latest attempt, so a later revocation excludes them.
    assert 9000000001 in palantir_consented_sis_ids
    assert 9000000001 not in gavel_consented_sis_ids

    assert gavel_consented_sis_ids == {9000000002}
