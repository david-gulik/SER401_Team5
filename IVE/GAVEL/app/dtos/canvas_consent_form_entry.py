from dataclasses import dataclass


@dataclass(frozen=True)
class ConsentFormEntry:
    """Immutable record of one consent form submission attempt."""
    sis_id: int
    # student display name as it appears in Canvas
    lms_name: str
    attempt: int
    # student's typed name (from the "leave blank if" question)
    name_response: str
    # parsed boolean from the "Do you consent" question
    consented: bool
