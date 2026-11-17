from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QByteArray, QPointF, QRectF, QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPen, QPixmap, QShowEvent
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.workspace.dataset import DatasetReaders
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.manifest import AssignmentEntry
from GAVEL.pages.analytics.generate_report_viewmodel import GenerateReportViewModel
from GAVEL.pages.analytics.heat_map_card import HeatMapCard
from GAVEL.pages.analytics.score_distribution_card import ScoreDistributionCard
from GAVEL.pages.analytics.signed_error_histogram_card import SignedErrorHistogramCard
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.hint_icon import hint_icon
from GAVEL.ui_components.section_card import SectionCard

_PLACEHOLDER_VISUALIZATIONS = (
    "Swiss Cheese Comparison Table",
    "Multi-Autograder Heat Map",
    "R² Chart",
)

# Dock position, size, and visibility, saved under the same per-app settings
# as the last course pick.
_DOCK_LAYOUT_SETTINGS_KEY = "analytics/dock_layout"


class _PersistentCheckMenu(QMenu):
    """A QMenu that stays open after toggling a checkable action.

    Qt closes a menu on any item click by default.
    Clicking elsewhere still closes it as usual.
    """

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        action = self.activeAction()
        if action is not None and action.isCheckable():
            action.trigger()
            return
        super().mouseReleaseEvent(event)


def _checkbox_icon(theme: ThemeContext) -> QIcon:
    """A small checkbox: an empty outline when off and a filled check when on.

    Drawn at runtime with the theme.
    Replaces Qt's native checkmark indicator.
    """
    size = 14
    border = QColor(theme.tokens.color["border"])
    accent = QColor(theme.tokens.color["interactive"])
    rect = QRectF(1, 1, size - 2, size - 2)

    off = QPixmap(size, size)
    off.fill(Qt.GlobalColor.transparent)
    painter = QPainter(off)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(border, 1))
    painter.drawRoundedRect(rect, 2, 2)
    painter.end()

    on = QPixmap(size, size)
    on.fill(Qt.GlobalColor.transparent)
    painter = QPainter(on)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(accent, 1))
    painter.drawRoundedRect(rect, 2, 2)
    check_pen = QPen(accent, 2)
    check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(check_pen)
    painter.drawLine(QPointF(3, 7), QPointF(6, 10))
    painter.drawLine(QPointF(6, 10), QPointF(11, 4))
    painter.end()

    icon = QIcon()
    icon.addPixmap(off, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(on, QIcon.Mode.Normal, QIcon.State.On)
    return icon


class OverviewTab(QWidget):
    def __init__(
        self,
        theme: ThemeContext,
        dataset_readers: DatasetReaders,
        settings: QSettings,
    ) -> None:
        super().__init__()
        self._theme = theme
        self._settings = settings

        self._generate_card = GenerateReportCard(theme, dataset_readers)
        histogram_card = SignedErrorHistogramCard(theme)
        heat_map_card = HeatMapCard(theme)
        score_distribution_card = ScoreDistributionCard(theme)
        self._generate_card.signed_error_report_generated.connect(histogram_card.load_report)
        self._generate_card.heat_map_report_generated.connect(heat_map_card.load_report)
        self._generate_card.heat_map_report_generated.connect(score_distribution_card.load_report)
        # Each chart shows one course's report, so a change of course empties them.
        self._report_cards = (histogram_card, heat_map_card, score_distribution_card)

        self._dock_host = QMainWindow()
        self._dock_host.setDockNestingEnabled(True)
        # A plain child QMainWindow (not shown as its own window) hosts the
        # docks, giving every card drag-to-rearrange and resize for free.
        self._dock_host.setWindowFlags(Qt.WindowType.Widget)

        # Default layout is three full-width rows: Generate Report alone on
        # top, the three real charts side by side below it, and the three
        # not-yet-built visualizations side by side at the bottom. Dragging
        # afterward is unrestricted; this only sets the first look.
        generate_dock = self._make_dock("Generate Report", self._generate_card)
        histogram_dock = self._make_dock("Signed Error Histogram", histogram_card)
        heat_map_dock = self._make_dock("Heat Map", heat_map_card)
        score_dock = self._make_dock("Score Distribution Boxplot", score_distribution_card)
        placeholder_docks = [
            self._make_dock(title, _PlaceholderCard(theme, title))
            for title in _PLACEHOLDER_VISUALIZATIONS
        ]

        # The three rows are split first, each spanning the full width, so
        # every row boundary is a real splitter all the way across. Splitting
        # a row into its columns afterward only divides within that row,
        # instead of a column split accidentally confining a later row's
        # split (and its resize handle) to one side of the window.
        self._dock_host.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, generate_dock)
        self._dock_host.splitDockWidget(generate_dock, histogram_dock, Qt.Orientation.Vertical)
        self._dock_host.splitDockWidget(
            histogram_dock, placeholder_docks[0], Qt.Orientation.Vertical
        )

        self._dock_host.splitDockWidget(histogram_dock, heat_map_dock, Qt.Orientation.Horizontal)
        self._dock_host.splitDockWidget(heat_map_dock, score_dock, Qt.Orientation.Horizontal)
        for left, right in zip(placeholder_docks, placeholder_docks[1:], strict=False):
            self._dock_host.splitDockWidget(left, right, Qt.Orientation.Horizontal)

        # Builds a Manage Analytics dropdown so that analytics visuals can be displayed or hidden.
        # It is a QPushButton with a menu.
        # _PersistentCheckMenu keeps the menu open across several toggles.
        # A plain QMenu closes after every single one.
        checkbox_icon = _checkbox_icon(theme)
        view_menu = _PersistentCheckMenu(self._dock_host)
        for dock in (generate_dock, histogram_dock, heat_map_dock, score_dock, *placeholder_docks):
            action = dock.toggleViewAction()
            action.setIcon(checkbox_icon)
            view_menu.addAction(action)
        view_button = QPushButton("Manage Analytics")
        view_button.setProperty("role", "secondary")
        view_button.setMenu(view_menu)

        view_bar = QWidget()
        view_bar_layout = QHBoxLayout(view_bar)
        view_bar_layout.setContentsMargins(8, 4, 8, 4)
        view_bar_layout.addWidget(view_button)
        view_bar_layout.addStretch(1)
        self._dock_host.setMenuWidget(view_bar)

        # Restores a layout saved from a previous run if there is one.
        saved_layout = settings.value(_DOCK_LAYOUT_SETTINGS_KEY, QByteArray(), type=QByteArray)
        if saved_layout:
            self._dock_host.restoreState(saved_layout)

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._save_dock_layout)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._dock_host)

    def _save_dock_layout(self) -> None:
        self._settings.setValue(_DOCK_LAYOUT_SETTINGS_KEY, self._dock_host.saveState())
        self._settings.sync()

    def _make_dock(self, title: str, widget: QWidget) -> QDockWidget:
        # A custom title bar (e.g. via setTitleBarWidget) breaks Qt's own
        # drag-to-redock drop indicator, so the dock keeps its native title
        # bar; the card's own duplicate title text is cleared instead.
        widget.clear_title()
        dock = QDockWidget(title, self._dock_host)
        # restoreState matches a saved dock by its object name. Every dock
        # defaults to the same empty name, so saved layouts cannot be
        # restored without setting a distinct one here.
        dock.setObjectName(title)
        dock.setWidget(widget)
        return dock

    def set_course(self, course: CourseFolder | None) -> None:
        """The active course, from the page: when the tab is built and on every change."""
        self._generate_card.set_course(course)
        for card in self._report_cards:
            card.clear()


class _PlaceholderCard(QWidget):
    """A named spot for a visualization that has not been built yet."""

    def __init__(self, theme: ThemeContext, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._card = SectionCard(theme, title)

        label = QLabel("Not yet implemented.")
        label.setProperty("role", "text_muted")
        self._card.add_row(label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._card)

    def clear_title(self) -> None:
        """Empties this card's own title text, for a caller that already shows it."""
        self._card.clear_title()


class GenerateReportCard(QWidget):
    """Builds a report from the active course.

    The report type picked determines which extra fields appear: a signed-
    error report needs a gradebook column, a heat map report needs a rubric
    assignment. Always reads the anonymized side of the course folder,
    through GenerateReportViewModel. The course comes in through set_course;
    the report lands in the runs/ folder of the workspace that course sits in.
    """

    signed_error_report_generated = pyqtSignal(Path)
    heat_map_report_generated = pyqtSignal(Path)

    _CHOOSE_TYPE = "Choose a report type…"
    _SIGNED_ERROR = "Signed Error Report"
    _HEAT_MAP = "Heat Map Report"
    _NO_COURSE = "No course selected."

    def __init__(
        self,
        theme: ThemeContext,
        dataset_readers: DatasetReaders,
        view_model: GenerateReportViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._view_model = view_model or GenerateReportViewModel(dataset_readers)
        self._course: CourseFolder | None = None
        self._rubric_assignments: tuple[AssignmentEntry, ...] = ()

        self._card = SectionCard(self._theme, "Generate Report")
        self._card.add_title_suffix(
            hint_icon(
                "Pick a report type, then fill in what it needs. Both types read the active "
                "course, which must be downloaded and anonymized in the workspace."
            )
        )

        self._report_type_box = QComboBox()
        self._report_type_box.addItems((self._CHOOSE_TYPE, self._SIGNED_ERROR, self._HEAT_MAP))
        self._report_type_box.currentIndexChanged.connect(self._on_report_type_changed)
        type_form = QFormLayout()
        type_form.addRow("Report type", self._report_type_box)
        type_widget = QWidget()
        type_widget.setLayout(type_form)
        self._card.add_row(type_widget)

        self._module_box = QComboBox()
        self._module_box.currentIndexChanged.connect(self._refresh_module_dependents)

        common_form = QFormLayout()
        common_form.addRow("Module", self._module_box)
        self._common_fields = QWidget()
        self._common_fields.setLayout(common_form)
        self._card.add_row(self._common_fields)

        self._column_box = QComboBox()
        signed_error_form = QFormLayout()
        signed_error_form.addRow("Gradebook column", self._column_box)
        self._signed_error_fields = QWidget()
        self._signed_error_fields.setLayout(signed_error_form)
        self._card.add_row(self._signed_error_fields)

        self._rubric_box = QComboBox()
        heat_map_form = QFormLayout()
        heat_map_form.addRow("Rubric Assignment", self._rubric_box)
        self._heat_map_fields = QWidget()
        self._heat_map_fields.setLayout(heat_map_form)
        self._card.add_row(self._heat_map_fields)

        self._generate_button = QPushButton("Generate Report")
        self._generate_button.clicked.connect(self._generate)
        self._card.add_row(self._generate_button)

        self._status = QLabel(self._NO_COURSE)
        self._status.setProperty("role", "text_muted")
        self._card.add_row(self._status)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._card)

        self._common_fields.setVisible(False)
        self._signed_error_fields.setVisible(False)
        self._heat_map_fields.setVisible(False)
        self._generate_button.setVisible(False)

    def clear_title(self) -> None:
        """Empties this card's own title text, for a caller that already shows it."""
        self._card.clear_title()

    def set_course(self, course: CourseFolder | None) -> None:
        """The active course, from the page: when the card is built and on every change."""
        self._course = course
        self._status.setText("Ready." if course is not None else self._NO_COURSE)
        # Refilling the module box refreshes the columns and rubric assignments too.
        self._refresh_modules()

    def showEvent(self, event: QShowEvent) -> None:
        """Rereads the course folder from disk each time this page is shown.

        Downloading and anonymizing both happen outside this widget's
        lifetime, so its cached module/column lists can go stale without
        this.
        """
        super().showEvent(event)
        self._refresh_modules()
        self._refresh_module_dependents()

    def _on_report_type_changed(self) -> None:
        report_type = self._report_type_box.currentText()
        chosen = report_type in (self._SIGNED_ERROR, self._HEAT_MAP)
        self._common_fields.setVisible(chosen)
        self._generate_button.setVisible(chosen)
        self._signed_error_fields.setVisible(report_type == self._SIGNED_ERROR)
        self._heat_map_fields.setVisible(report_type == self._HEAT_MAP)

    def _refresh_modules(self) -> None:
        previous = self._module_box.currentText()
        self._module_box.clear()
        course = self._selected_course()
        if course is None:
            return
        try:
            modules = self._view_model.list_modules(course)
        except Exception as exc:
            self._status.setText(f"Could not read the workspace: {exc}")
            return
        self._module_box.addItems([str(m) for m in modules])
        index = self._module_box.findText(previous)
        if index >= 0:
            self._module_box.setCurrentIndex(index)

    def _refresh_module_dependents(self) -> None:
        self._refresh_columns()
        self._refresh_rubric_assignments()

    def _refresh_columns(self) -> None:
        previous = self._column_box.currentText()
        self._column_box.clear()
        course = self._selected_course()
        module_text = self._module_box.currentText()
        if course is None or not module_text:
            return
        try:
            columns = self._view_model.list_gradebook_columns(course, int(module_text))
        except Exception as exc:
            self._status.setText(f"Could not read the gradebook: {exc}")
            return
        self._column_box.addItems(columns)
        index = self._column_box.findText(previous)
        if index >= 0:
            self._column_box.setCurrentIndex(index)

    def _refresh_rubric_assignments(self) -> None:
        previous = self._rubric_box.currentText()
        self._rubric_box.clear()
        self._rubric_assignments = ()
        course = self._selected_course()
        module_text = self._module_box.currentText()
        if course is None or not module_text:
            return
        try:
            self._rubric_assignments = self._view_model.list_rubric_assignments(
                course, int(module_text)
            )
        except Exception as exc:
            self._status.setText(f"Could not read the manifest: {exc}")
            return
        self._rubric_box.addItems([a.name for a in self._rubric_assignments])
        index = self._rubric_box.findText(previous)
        if index >= 0:
            self._rubric_box.setCurrentIndex(index)

    def _selected_course(self) -> CourseFolder | None:
        return self._course

    def _selected_rubric_assignment(self) -> AssignmentEntry | None:
        index = self._rubric_box.currentIndex()
        if index < 0 or index >= len(self._rubric_assignments):
            return None
        return self._rubric_assignments[index]

    def _generate(self) -> None:
        report_type = self._report_type_box.currentText()
        course = self._selected_course()
        module_text = self._module_box.currentText()

        if course is None or not module_text:
            self._status.setText("Choose a course and module.")
            return

        module_number = int(module_text)
        mapping_name = self._view_model.resolve_mapping_name(course, module_number)
        if mapping_name is None:
            self._status.setText(
                f"No proxy mapping is defined for {course.key.folder_name} module {module_number}."
            )
            return

        if report_type == self._SIGNED_ERROR:
            self._generate_signed_error_report(course, module_number, mapping_name)
        elif report_type == self._HEAT_MAP:
            self._generate_heat_map_report(course, module_number, mapping_name)
        else:
            self._status.setText("Choose a report type.")

    def _generate_signed_error_report(
        self, course: CourseFolder, module_number: int, mapping_name: str
    ) -> None:
        gradebook_column = self._column_box.currentText()
        if not gradebook_column:
            self._status.setText("Choose a gradebook column.")
            return

        try:
            outcome = self._view_model.generate(
                course.workspace_root, course, module_number, mapping_name, gradebook_column
            )
        except Exception as exc:
            self._status.setText(f"Could not generate the report: {exc}")
            return

        self._status.setText(
            f"Scored {outcome.scored}, unmatched {outcome.unmatched}, failed {outcome.failed}. "
            f"Saved to {outcome.output_path.name}."
        )
        self.signed_error_report_generated.emit(outcome.output_path)

    def _generate_heat_map_report(
        self, course: CourseFolder, module_number: int, mapping_name: str
    ) -> None:
        rubric_assignment = self._selected_rubric_assignment()
        if rubric_assignment is None:
            self._status.setText("Choose a rubric assignment.")
            return

        try:
            outcome = self._view_model.generate_heat_map(
                course.workspace_root, course, module_number, mapping_name, rubric_assignment
            )
        except Exception as exc:
            self._status.setText(f"Could not generate the report: {exc}")
            return

        self._status.setText(
            f"Scored {outcome.scored}, unmatched {outcome.unmatched}, failed {outcome.failed}, "
            f"missing human scores {outcome.missing_human_scores}. "
            f"Saved to {outcome.output_path.name}."
        )
        self.heat_map_report_generated.emit(outcome.output_path)
