"""The status-bar course picker, and the stand-in a page shows until a course is picked."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.course_summary import AnonymizationStatus, CourseSummary
from GAVEL.app.usecases.list_workspace_courses import (
    ListWorkspaceCoursesRequest,
    ListWorkspaceCoursesResult,
    ListWorkspaceCoursesUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.core.active_course import ActiveCourse
from GAVEL.core.background import BackgroundRunner, run_in_background
from GAVEL.core.status import ANONYMIZATION_STATUS_COLOR_TOKEN, ANONYMIZATION_STATUS_TEXT
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_margins, set_spacing
from GAVEL.ui_components.section_card import SectionCard

NO_COURSE_TEXT = "No course selected"
CHOOSE_COURSE_TEXT = "Choose a course…"
# Course folder name, on every row of the picker.
_FOLDER_ROLE = Qt.ItemDataRole.UserRole
# The Verification and Analysis pages read anonymized/, so a course without one cannot be
# picked. It is still listed, dimmed, with this hint, so the user sees what to do about it.
_NOT_SELECTABLE_HINT = {
    AnonymizationStatus.NOT_ANONYMIZED: (
        "Not anonymized yet. Anonymize it on the Sanitize page to work on it here."
    ),
    AnonymizationStatus.NO_CONSENT_FORM: (
        "No consent form, so it cannot be anonymized. Download the consent form, then "
        "anonymize it on the Sanitize page."
    ),
}


def is_selectable(course: CourseSummary) -> bool:
    """Whether the active course may be set to this course: it has an anonymized copy."""
    return course.status not in _NOT_SELECTABLE_HINT


# The picker's list grows with its rows between these heights, then scrolls.
_LIST_MIN_HEIGHT = 80
_LIST_MAX_HEIGHT = 320


def _course_text(course: CourseFolder | None) -> str:
    return course.key.folder_name if course is not None else NO_COURSE_TEXT


class ActiveCourseChip(QFrame):
    """Status-bar readout of the active course; clicking it opens the picker above."""

    def __init__(
        self,
        theme: ThemeContext,
        active_course: ActiveCourse,
        popup: CoursePickerPopup | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._active = active_course
        self._popup = popup or CoursePickerPopup(theme, active_course)

        self.setProperty("role", "course_chip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(
            "The course the Verification and Analysis pages work on. Click to change it."
        )

        key = QLabel("COURSE")
        key.setProperty("role", "readout_key")
        self._name = QLabel()
        caret = QLabel("▴")
        caret.setProperty("role", "course_chip_caret")

        root = QHBoxLayout(self)
        root.setContentsMargins(theme.tokens.sp(8), 0, theme.tokens.sp(8), 0)
        set_spacing(root, theme, 8)
        root.addWidget(key)
        root.addWidget(self._name)
        root.addWidget(caret)

        self._active.changed.connect(self._render)
        self._render(self._active.course)

    @property
    def popup(self) -> CoursePickerPopup:
        return self._popup

    @property
    def name_label(self) -> QLabel:
        return self._name

    def _render(self, course: CourseFolder | None) -> None:
        self._name.setText(_course_text(course))

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._popup.open_above(self)
        super().mousePressEvent(event)


class CourseRow(QWidget):
    """One picker row: folder name, Canvas course name, and anonymization status.

    A row that cannot be picked (see is_selectable) is drawn muted; its status
    label keeps its color so the reason stands out.
    """

    def __init__(
        self,
        theme: ThemeContext,
        course: CourseSummary,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "course_row")
        # Clicks fall through to the list, so the row behaves like a plain item.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.name_label = QLabel(course.folder_name, self)
        if not is_selectable(course):
            self.name_label.setProperty("role", "text_muted")
        self.canvas_label = QLabel(course.canvas_course_name or "", self)
        self.canvas_label.setProperty("role", "text_muted")

        self.status_label = QLabel(f"●  {ANONYMIZATION_STATUS_TEXT[course.status]}", self)
        color = theme.tokens.color[ANONYMIZATION_STATUS_COLOR_TOKEN[course.status]]
        self.status_label.setStyleSheet(f"color: {color}; background: transparent;")

        names = QVBoxLayout()
        names.setContentsMargins(0, 0, 0, 0)
        names.setSpacing(0)
        names.addWidget(self.name_label)
        names.addWidget(self.canvas_label)
        # Only once it has a parent: setVisible(True) on a parentless widget opens it as
        # a window, and showing a window closes the popup this row is about to sit in.
        self.canvas_label.setVisible(bool(course.canvas_course_name))

        root = QHBoxLayout(self)
        root.setContentsMargins(
            theme.tokens.sp(8), theme.tokens.sp(4), theme.tokens.sp(8), theme.tokens.sp(4)
        )
        set_spacing(root, theme, 12)
        root.addLayout(names, 1)
        root.addWidget(self.status_label)


class CoursePickerPopup(QFrame):
    """Every course folder in the workspace with its anonymization status; one click picks.

    Listing hashes each course's inputs (see ListWorkspaceCoursesUseCase), so
    it runs off the GUI thread and the rows fill in when it finishes. Only a
    course with an anonymized copy can be picked (see is_selectable); the rest
    are listed dimmed, with a tooltip saying what to do.
    """

    courses_loaded = pyqtSignal(object)  # tuple[CourseSummary, ...]

    def __init__(
        self,
        theme: ThemeContext,
        active_course: ActiveCourse,
        list_courses: ListWorkspaceCoursesUseCase | None = None,
        runner: BackgroundRunner = run_in_background,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self._theme = theme
        self._active = active_course
        self._list_courses = list_courses or ListWorkspaceCoursesUseCase()
        self._runner = runner
        self._courses: tuple[CourseSummary, ...] = ()
        self._loading = False
        # The widget the popup sits on, so it stays put when the list changes height.
        self._anchor: QWidget | None = None

        self.setProperty("role", "course_picker")
        self.setFixedWidth(440)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by folder or Canvas course name")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._pick)
        self._list.itemActivated.connect(self._pick)

        self._footer = QLabel()
        self._footer.setProperty("role", "text_muted")
        self._footer.setWordWrap(True)
        # Wraps in the width the Refresh button leaves instead of squeezing it out.
        self._footer.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._refresh = QPushButton("Refresh")
        self._refresh.setProperty("role", "borderless")
        self._refresh.clicked.connect(self.reload)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(self._footer, 1)
        footer.addWidget(self._refresh)

        root = QVBoxLayout(self)
        set_margins(root, theme, 8)
        set_spacing(root, theme, 8)
        root.addWidget(self._search)
        root.addWidget(self._list)
        root.addLayout(footer)
        self._fit_list()

    @property
    def courses(self) -> tuple[CourseSummary, ...]:
        return self._courses

    @property
    def list_widget(self) -> QListWidget:
        return self._list

    @property
    def search_input(self) -> QLineEdit:
        return self._search

    @property
    def footer_label(self) -> QLabel:
        return self._footer

    def row(self, index: int) -> CourseRow:
        widget = self._list.itemWidget(self._list.item(index))
        assert isinstance(widget, CourseRow)
        return widget

    def open_above(self, anchor: QWidget) -> None:
        """Show sitting on the anchor's top-left corner, then reread the workspace."""
        self._anchor = anchor
        self._place_above(anchor)
        self.show()
        self._search.setFocus()
        self.reload()

    def _place_above(self, anchor: QWidget) -> None:
        self.adjustSize()
        top_left = anchor.mapToGlobal(QPoint(0, 0))
        self.move(top_left.x(), top_left.y() - self.height())

    def _fit_list(self) -> None:
        """Size the list to its rows, up to a scrolling maximum, and keep the popup anchored."""
        rows = sum(self._list.sizeHintForRow(i) for i in range(self._list.count()))
        frame = 2 * self._list.frameWidth()
        self._list.setFixedHeight(min(max(rows, _LIST_MIN_HEIGHT), _LIST_MAX_HEIGHT) + frame)
        if self._anchor is not None:
            self._place_above(self._anchor)
        else:
            self.adjustSize()

    def reload(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._footer.setText("Reading the workspace…")
        request = ListWorkspaceCoursesRequest(workspace_root=self._active.workspace.root)
        self._runner(
            lambda: self._list_courses.execute(request), self._on_loaded, self._on_load_failed
        )

    def _on_loaded(self, result: object) -> None:
        self._loading = False
        assert isinstance(result, ListWorkspaceCoursesResult)
        self._courses = result.courses
        self._rebuild()
        self.courses_loaded.emit(self._courses)

    def _on_load_failed(self, exc: Exception) -> None:
        self._loading = False
        self._courses = ()
        self._list.clear()
        self._fit_list()
        self._footer.setText(f"Could not read the workspace: {exc}")

    def _rebuild(self) -> None:
        self._list.clear()
        current = self._active.course
        for course in self._courses:
            item = QListWidgetItem()
            item.setData(_FOLDER_ROLE, course.folder_name)
            if not is_selectable(course):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(_NOT_SELECTABLE_HINT[course.status])
            row = CourseRow(self._theme, course)
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
            if current is not None and course.key == current.key:
                self._list.setCurrentItem(item)
        self._apply_filter()
        self._fit_list()

        count = len(self._courses)
        anonymized = sum(1 for course in self._courses if is_selectable(course))
        self._footer.setToolTip(str(self._active.workspace.courses_dir))
        if count == 0:
            self._footer.setText("No courses in the workspace. Download one first.")
        else:
            self._footer.setText(
                f"{count} course{'s' if count != 1 else ''} in the workspace, "
                f"{anonymized} anonymized"
            )

    def _apply_filter(self) -> None:
        needle = self._search.text().strip().lower()
        for index, course in enumerate(self._courses):
            haystack = f"{course.folder_name} {course.canvas_course_name or ''}".lower()
            self._list.item(index).setHidden(bool(needle) and needle not in haystack)

    def _pick(self, item: QListWidgetItem) -> None:
        if not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        folder_name = item.data(_FOLDER_ROLE)
        course = next((c for c in self._courses if c.folder_name == folder_name), None)
        if course is not None and is_selectable(course):
            self._active.select(CourseFolder(course.path, course.key))
        self.hide()


class ChooseCourseCard(QWidget):
    """What a page shows in place of its content while no course is active.

    Its button opens the same picker as the status-bar chip, so which courses
    can be picked is decided in one place.
    """

    def __init__(
        self,
        theme: ThemeContext,
        page_title: str,
        popup: CoursePickerPopup,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._popup = popup

        card = SectionCard(theme, "Choose a course")
        card.setMaximumWidth(480)

        text = QLabel(
            f"{page_title} works on one anonymized course from your workspace. The same "
            "choice applies to every Verification and Analysis page; change it any time "
            "from the bar at the bottom of the window. A course that has not been "
            "anonymized yet is listed but cannot be chosen: run it through Sanitize first."
        )
        text.setWordWrap(True)
        text.setProperty("role", "text_muted")

        self._choose = QPushButton(CHOOSE_COURSE_TEXT)
        self._choose.setProperty("role", "primary")
        self._choose.clicked.connect(self._open_picker)

        card.add_row(text)
        card.add_row(self._choose)

        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(card)
        centered.addStretch(1)

        root = QVBoxLayout(self)
        set_margins(root, theme, 16)
        root.addStretch(1)
        root.addLayout(centered)
        root.addStretch(2)

    @property
    def choose_button(self) -> QPushButton:
        return self._choose

    def _open_picker(self) -> None:
        self._popup.open_above(self._choose)


class ActiveCourseGate(QStackedWidget):
    """Shows a page only while a course is active, and a ChooseCourseCard otherwise."""

    def __init__(
        self,
        theme: ThemeContext,
        active_course: ActiveCourse,
        page_title: str,
        page: QWidget,
        popup: CoursePickerPopup,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._card = ChooseCourseCard(theme, page_title, popup)
        self._page = page
        self.addWidget(self._card)
        self.addWidget(self._page)

        active_course.changed.connect(self._render)
        self._render(active_course.course)

    @property
    def card(self) -> ChooseCourseCard:
        return self._card

    @property
    def page(self) -> QWidget:
        return self._page

    def _render(self, course: CourseFolder | None) -> None:
        self.setCurrentWidget(self._page if course is not None else self._card)
