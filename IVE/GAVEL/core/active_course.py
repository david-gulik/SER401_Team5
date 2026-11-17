"""The workspace course the Verification and Analysis pages work on, picked once for all."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QSettings, pyqtSignal

from GAVEL.app.workspace.layout import CourseFolder, Workspace

# Folder name of the last pick, so it survives a restart.
_SETTINGS_KEY = "active_course/folder_name"


class ActiveCourse(QObject):
    """One course folder shared by every page whose PageSpec says ``uses_active_course``.

    A page reads ``course`` when it is built (pages are built the first time
    they are opened, which may be long after the pick) and connects to
    ``changed`` for later picks. The pick is remembered between launches by
    folder name; a remembered folder that is no longer in the workspace
    restores as None.
    """

    changed = pyqtSignal(object)  # CourseFolder | None

    def __init__(self, workspace: Workspace, settings: QSettings) -> None:
        super().__init__()
        self._workspace = workspace
        self._settings = settings
        self._course = self._restore()

    @property
    def workspace(self) -> Workspace:
        return self._workspace

    @property
    def course(self) -> CourseFolder | None:
        return self._course

    def select(self, course: CourseFolder | None) -> None:
        if course == self._course:
            return
        self._course = course
        self._settings.setValue(_SETTINGS_KEY, course.key.folder_name if course else "")
        self._settings.sync()
        self.changed.emit(course)

    def revalidate(self) -> None:
        """Clear the pick if its folder was deleted or renamed while the app was running."""
        if self._course is not None and not self._course.path.is_dir():
            self.select(None)

    def _restore(self) -> CourseFolder | None:
        name = self._settings.value(_SETTINGS_KEY, "", type=str)
        if not name:
            return None
        return next((c for c in self._workspace.list_courses() if c.key.folder_name == name), None)
