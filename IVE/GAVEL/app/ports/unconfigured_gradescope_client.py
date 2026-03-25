from app.dtos.gradescope_assignment import GradescopeAssignment
from app.ports.gradescope_client import GradescopeClient


class UnconfiguredGradescopeClient(GradescopeClient):
    """
    Fallback implementation used when Gradescope is not configured.
    """

    def _error(self):
        raise RuntimeError("ERROR: Gradescope is not configured.")

    def list_assignments(self, course_id: str) -> list[GradescopeAssignment]:
        self._error()

    def fetch_assignment_submissions(self, course_id: str, assignment_id: str) -> bytes:
        self._error()
