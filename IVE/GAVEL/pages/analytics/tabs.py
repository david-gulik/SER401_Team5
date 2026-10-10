from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.workspace.dataset import DatasetReaders, MissingArtifactError
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.analytics.generate_report_viewmodel import GenerateReportViewModel
from GAVEL.pages.analytics.signed_error_histogram_viewmodel import (
    SignedErrorHistogramData,
    SignedErrorHistogramViewModel,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.chart_canvas import ChartCanvas
from GAVEL.ui_components.section_card import SectionCard

_PLACEHOLDER_VISUALIZATIONS = (
    "Human vs Autograder Heat Map",
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
        generate_card.report_generated.connect(histogram_card.load_report)

        self.add_section(generate_card)
        self.add_section(histogram_card)
        for title in _PLACEHOLDER_VISUALIZATIONS:
            self.add_section(_PlaceholderCard(theme, title))
        self.add_stretch()


def _hint_icon(tooltip: str) -> QLabel:
    """A small circled "?" explaining a card's requirements on hover."""
    icon = QLabel("?")
    icon.setProperty("role", "hint_icon")
    icon.setFixedSize(16, 16)
    icon.setToolTip(tooltip)
    return icon


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
    """Runs the proxy-grade report against a course already in the workspace.

    Always reads the anonymized side of the course folder, through
    GenerateReportViewModel.
    """

    report_generated = pyqtSignal(Path)

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

        self._card = SectionCard(self._theme, "Generate Report")

        self._course_box = QComboBox()
        self._course_box.currentIndexChanged.connect(self._refresh_modules)
        self._module_box = QComboBox()
        self._module_box.currentIndexChanged.connect(self._refresh_columns)
        self._mapping_box = QComboBox()
        self._mapping_box.addItems(self._view_model.mapping_names())
        self._column_box = QComboBox()

        form = QFormLayout()
        form.addRow("Course", self._course_box)
        form.addRow("Module", self._module_box)
        form.addRow("Proxy Mapping", self._mapping_box)
        form.addRow("Gradebook column", self._column_box)
        form_widget = QWidget()
        form_widget.setLayout(form)
        self._card.add_row(form_widget)

        self._card.add_title_suffix(
            _hint_icon(
                "Requires a course that has been downloaded and anonymized in the workspace, "
                "including its Gradebook and Gradescope Submissions for the selected module."
            )
        )

        generate_button = QPushButton("Generate Report")
        generate_button.clicked.connect(self._generate)
        self._card.add_action(generate_button)

        self._status = QLabel("No courses found in the workspace.")
        self._status.setProperty("role", "text_muted")
        self._card.add_row(self._status)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._card)

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
        self._refresh_columns()

    def _refresh_courses(self) -> None:
        previous = self._course_box.currentText()
        self._courses = self._view_model.list_courses(self._workspace_root)
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
        modules = self._view_model.list_modules(course)
        self._module_box.addItems([str(m) for m in modules])
        index = self._module_box.findText(previous)
        if index >= 0:
            self._module_box.setCurrentIndex(index)

    def _refresh_columns(self) -> None:
        previous = self._column_box.currentText()
        self._column_box.clear()
        course = self._selected_course()
        module_text = self._module_box.currentText()
        if course is None or not module_text:
            return
        try:
            columns = self._view_model.list_gradebook_columns(course, int(module_text))
        except (MissingArtifactError, OSError, ValueError) as exc:
            self._status.setText(f"Could not read the gradebook: {exc}")
            return
        self._column_box.addItems(columns)
        index = self._column_box.findText(previous)
        if index >= 0:
            self._column_box.setCurrentIndex(index)

    def _selected_course(self) -> CourseFolder | None:
        index = self._course_box.currentIndex()
        if index < 0 or index >= len(self._courses):
            return None
        return self._courses[index]

    def _generate(self) -> None:
        course = self._selected_course()
        module_text = self._module_box.currentText()
        mapping_name = self._mapping_box.currentText()
        gradebook_column = self._column_box.currentText()

        if course is None or not module_text or not mapping_name or not gradebook_column:
            self._status.setText("Choose a course, module, mapping, and gradebook column.")
            return

        try:
            outcome = self._view_model.generate(
                self._workspace_root, course, int(module_text), mapping_name, gradebook_column
            )
        except (MissingArtifactError, OSError, ValueError) as exc:
            self._status.setText(f"Could not generate the report: {exc}")
            return

        self._status.setText(
            f"Scored {outcome.scored}, unmatched {outcome.unmatched}, failed {outcome.failed}. "
            f"Saved to {outcome.output_path.name}."
        )
        self.report_generated.emit(outcome.output_path)


class SignedErrorHistogramCard(QWidget):
    """Loads a signed-error report, chosen by the user, and charts its distribution."""

    def __init__(
        self,
        theme: ThemeContext,
        view_model: SignedErrorHistogramViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._view_model = view_model or SignedErrorHistogramViewModel()

        self._card = SectionCard(self._theme, "Signed Error Histogram")

        choose_button = QPushButton("Choose report…")
        choose_button.clicked.connect(self._choose_report)
        self._card.add_action(choose_button)

        self._status = QLabel("No report chosen yet.")
        self._status.setProperty("role", "text_muted")
        self._card.add_row(self._status)

        self._canvas = ChartCanvas(
            self._theme, placeholder_text="Choose a signed-error report to see its histogram."
        )
        self._card.add_row(self._canvas)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._card)

    def _choose_report(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a signed-error report", "", "JSON files (*.json)"
        )
        if not path:
            return
        self.load_report(Path(path))

    def load_report(self, report_path: Path) -> None:
        """Loads a report and displays its histogram, or reports why it could not."""
        try:
            data = self._view_model.load(report_path)
        except (OSError, ValueError, KeyError) as exc:
            self._status.setText(f"Could not read {report_path.name}: {exc}")
            self._canvas.clear()
            return

        self._status.setText(f"Showing {report_path.name}")
        self.display(data)

    def display(self, data: SignedErrorHistogramData) -> None:
        self._canvas.clear()
        if not data.bins:
            return

        axes = self._canvas.figure.add_subplot()
        axes.bar(
            [b.lower for b in data.bins],
            [b.count for b in data.bins],
            width=[b.upper - b.lower for b in data.bins],
            align="edge",
        )
        axes.set_xlabel("Signed error (human minus proxy)")
        axes.set_ylabel("Submissions")
        axes.set_title(data.module_label)
        self._canvas.draw()
