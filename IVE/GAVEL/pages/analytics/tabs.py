from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.workspace.dataset import DatasetReaders
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.manifest import AssignmentEntry
from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.analytics.generate_report_viewmodel import GenerateReportViewModel
from GAVEL.pages.analytics.heat_map_card import HeatMapCard
from GAVEL.pages.analytics.signed_error_histogram_card import SignedErrorHistogramCard
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.hint_icon import hint_icon
from GAVEL.ui_components.section_card import SectionCard

_PLACEHOLDER_VISUALIZATIONS = (
    "Signed Error Boxplot (Mann-Whitney U)",
    "Swiss Cheese Comparison Table",
    "Multi-Autograder Heat Map",
    "R² Chart",
)


class OverviewTab(ScrollableTab):
    def __init__(
        self,
        theme: ThemeContext,
        dataset_readers: DatasetReaders,
        workspace_root: Path,
    ) -> None:
        super().__init__(theme)
        self._theme = theme

        generate_card = GenerateReportCard(theme, dataset_readers, workspace_root)
        histogram_card = SignedErrorHistogramCard(theme)
        heat_map_card = HeatMapCard(theme)
        generate_card.signed_error_report_generated.connect(histogram_card.load_report)
        generate_card.heat_map_report_generated.connect(heat_map_card.load_report)

        self.add_section(generate_card)
        self.add_section(histogram_card)
        self.add_section(heat_map_card)
        for title in _PLACEHOLDER_VISUALIZATIONS:
            self.add_section(_PlaceholderCard(theme, title))
        self.add_stretch()


class _PlaceholderCard(QWidget):
    """A named spot for a visualization that has not been built yet."""

    def __init__(self, theme: ThemeContext, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        card = SectionCard(theme, title)

        label = QLabel("Not yet implemented.")
        label.setProperty("role", "text_muted")
        card.add_row(label)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(card)


class GenerateReportCard(QWidget):
    """Builds a report from a course already in the workspace.

    The report type picked determines which extra fields appear: a signed-
    error report needs a gradebook column, a heat map report needs a rubric
    assignment. Always reads the anonymized side of the course folder,
    through GenerateReportViewModel.
    """

    signed_error_report_generated = pyqtSignal(Path)
    heat_map_report_generated = pyqtSignal(Path)

    _CHOOSE_TYPE = "Choose a report type…"
    _SIGNED_ERROR = "Signed Error Report"
    _HEAT_MAP = "Heat Map Report"

    def __init__(
        self,
        theme: ThemeContext,
        dataset_readers: DatasetReaders,
        workspace_root: Path,
        view_model: GenerateReportViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._workspace_root = workspace_root
        self._view_model = view_model or GenerateReportViewModel(dataset_readers)
        self._courses: tuple[CourseFolder, ...] = ()
        self._rubric_assignments: tuple[AssignmentEntry, ...] = ()

        self._card = SectionCard(self._theme, "Generate Report")
        self._card.add_title_suffix(
            hint_icon(
                "Pick a report type, then fill in what it needs. Both types require a course "
                "that has been downloaded and anonymized in the workspace."
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

        self._course_box = QComboBox()
        self._course_box.currentIndexChanged.connect(self._refresh_modules)
        self._module_box = QComboBox()
        self._module_box.currentIndexChanged.connect(self._refresh_module_dependents)
        self._mapping_box = QComboBox()
        self._mapping_box.addItems(self._view_model.mapping_names())

        common_form = QFormLayout()
        common_form.addRow("Course", self._course_box)
        common_form.addRow("Module", self._module_box)
        common_form.addRow("Proxy Mapping", self._mapping_box)
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

        self._status = QLabel("No courses found in the workspace.")
        self._status.setProperty("role", "text_muted")
        self._card.add_row(self._status)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._card)

        self._common_fields.setVisible(False)
        self._signed_error_fields.setVisible(False)
        self._heat_map_fields.setVisible(False)
        self._generate_button.setVisible(False)

        self._refresh_courses()

    def showEvent(self, event: QShowEvent) -> None:
        """Rereads the workspace from disk each time this page is shown.

        Downloading and anonymizing both happen outside this widget's
        lifetime, so its cached course/module/column lists can go stale
        without this.
        """
        super().showEvent(event)
        self._refresh_courses()
        self._refresh_modules()
        self._refresh_module_dependents()

    def _on_report_type_changed(self) -> None:
        report_type = self._report_type_box.currentText()
        chosen = report_type in (self._SIGNED_ERROR, self._HEAT_MAP)
        self._common_fields.setVisible(chosen)
        self._generate_button.setVisible(chosen)
        self._signed_error_fields.setVisible(report_type == self._SIGNED_ERROR)
        self._heat_map_fields.setVisible(report_type == self._HEAT_MAP)

    def _refresh_courses(self) -> None:
        previous = self._course_box.currentText()
        try:
            self._courses = self._view_model.list_courses(self._workspace_root)
        except Exception as exc:
            self._status.setText(f"Could not read the workspace: {exc}")
            return
        self._course_box.clear()
        self._course_box.addItems([c.key.folder_name for c in self._courses])
        if self._courses:
            self._status.setText("Ready.")
        else:
            self._status.setText("No courses found in the workspace.")
        index = self._course_box.findText(previous)
        if index >= 0:
            self._course_box.setCurrentIndex(index)

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
        index = self._course_box.currentIndex()
        if index < 0 or index >= len(self._courses):
            return None
        return self._courses[index]

    def _selected_rubric_assignment(self) -> AssignmentEntry | None:
        index = self._rubric_box.currentIndex()
        if index < 0 or index >= len(self._rubric_assignments):
            return None
        return self._rubric_assignments[index]

    def _generate(self) -> None:
        report_type = self._report_type_box.currentText()
        course = self._selected_course()
        module_text = self._module_box.currentText()
        mapping_name = self._mapping_box.currentText()

        if course is None or not module_text or not mapping_name:
            self._status.setText("Choose a course, module, and proxy mapping.")
            return

        if report_type == self._SIGNED_ERROR:
            self._generate_signed_error_report(course, int(module_text), mapping_name)
        elif report_type == self._HEAT_MAP:
            self._generate_heat_map_report(course, int(module_text), mapping_name)
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
                self._workspace_root, course, module_number, mapping_name, gradebook_column
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
                self._workspace_root, course, module_number, mapping_name, rubric_assignment
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
