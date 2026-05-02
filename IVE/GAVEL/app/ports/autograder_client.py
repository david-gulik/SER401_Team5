from __future__ import annotations

from abc import ABC, abstractmethod


class AutograderClient(ABC):
    @abstractmethod
    def run_autograder(self, directory_path: str, autograder_cycles: int) -> None:
        """Using a given directory, runs an autograder (included in the directory) on all included submissions
        a given number of times and creates results JSONs for each cycle of each submission."""
        raise NotImplementedError

    @abstractmethod
    def import_autograder_file(self, directory_path: str, autograder_folder_path: str) -> None:
        """Puts the autograder file from autograder_folder_path into the directory specified by directory_path"""
        raise NotImplementedError

    @abstractmethod
    def import_submissions(self, directory_path: str, submissions_folder_path: str) -> None:
        """Puts the submissions file from submissions_folder_path into directory specified by directory_path"""
        raise NotImplementedError
