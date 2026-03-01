import csv
from typing import Sequence

from GAVEL.app.dtos.consent_form_entry import ConsentFormEntry
from GAVEL.app.ports.consent_form_reader import ConsentFormReader


def _find_column(substring: str, fieldnames: Sequence[str]) -> str:
    """
    Resolves a Canvas quiz column name by substring match.
    Raises ValueError if exactly one match is not found.
    """
    matches = [f for f in fieldnames if substring in f]
    if len(matches) != 1:
        raise ValueError(
            f"Expected 1 column matching '{substring}', "
            f"found {len(matches)}: {matches}"
        )
    return matches[0]


class CanvasConsentFormReader(ConsentFormReader):
    """Reads a Canvas quiz student analysis export into
    ConsentFormEntry DTOs."""

    _COL_NAME_SUBSTR = "leave blank if"
    _COL_BOOL_SUBSTR = "Do you consent"

    def load(self, path: str) -> Sequence[ConsentFormEntry]:
        entries = []

        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            col_name = _find_column(self._COL_NAME_SUBSTR, reader.fieldnames)
            col_bool = _find_column(self._COL_BOOL_SUBSTR, reader.fieldnames)

            for row in reader:
                entries.append(ConsentFormEntry(
                    sis_id=int(row["sis_id"]),
                    lms_name=row["name"].strip(),
                    attempt=int(row["attempt"]),
                    name_response=row[col_name].strip(),
                    consented=row[col_bool] == "True",
                ))

        return entries
