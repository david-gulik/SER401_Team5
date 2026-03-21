from abc import ABC, abstractmethod
from typing import List
from app.dtos.gradescope_assignment import GradescopeAssignment


class GradescopeClient(ABC):
    """
    Interface for interacting with Gradescope.
    """

    @abstractmethod
    def list_assignments(self, course_id: str) -> List[GradescopeAssignment]:
        """
        Return a list of assignments for the given course.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_assignment_submissions(self, course_id: str, assignment_id: str) -> bytes:
        """
        Return the ZIP export of submissions for the given assignment.
        """
        raise NotImplementedError