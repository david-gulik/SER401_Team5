import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.workspace import CourseFolder
from GAVEL.app_context import AppContext
from GAVEL.core.background import run_in_background
from GAVEL.core.base_tab import ScrollableTab
from GAVEL.infra.autograders.autograder_evaluation_comparions import (
    MatplotlibWidget,
    compare_evaluations,
    plot_bland_altman,
    plot_criterion_heatmap,
    plot_difference_histogram,
    plot_scatter_comparison,
    plot_score_distribution,
)
from GAVEL.infra.autograders.autograder_metadata import (
    AutograderInfo,
    AutograderRow,
    load_autograder,
    save_autograder_metadata,
)
from GAVEL.infra.autograders.parallel_autograder_client import (
    autograde_submissions_folder,
)
from GAVEL.ui_components.log_handler import QtLogHandler
from GAVEL.ui_components.section_card import SectionCard


def get_assignment_subfolders(folder: Path) -> list[str]:
    if not folder.exists():
        return []

    if not folder.is_dir():
        return []

    return [p.name for p in folder.iterdir() if p.is_dir() and p.name != "_unmatched"]


class RunAutogradersTab(ScrollableTab):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__(ctx.theme)
        self._ctx = ctx
        self._theme = self._ctx.theme
        self._active_course = ctx.active_course

        course = self._ctx.active_course.course
        self.assignment_folder = course.path / "anonymized" / "gradescope_submissions"
        load_dotenv()
        env_dir = (os.getenv("DEFAULT_OUTPUT_DIR") or "").strip()
        self.root_path = (
            Path(env_dir).expanduser() if env_dir else Path.home() / "Downloads" / "GAVEL"
        )
        self.courses_path = self.root_path / "courses"
        self.autograders_path = self.root_path / "autograders"

        # self.course_combo: QComboBox | None = None
        self.assignment_combo: QComboBox | None = None

        self.autograders_card: SectionCard | None = None
        self.autograder_rows: list[AutograderRow] = []

        # self.add_section(self._build_course_select_dropdown(self.courses_path))
        self.add_section(self._build_course_label_card())
        self.add_section(self._build_assignments_dropdown())
        self.add_section(self._build_available_autograders_dropdown())

        self.run_btn = QPushButton("Run")

        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)

        self.run_btn.setIcon(icon)
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run_autograders)
        self.add_section(self.run_btn)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        self.log_handler = QtLogHandler()

        self.log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

        self.log_handler.message_emitted.connect(self.log_output.appendPlainText)
        autograder_logger = logging.getLogger("autograder_client")

        autograder_logger.addHandler(self.log_handler)
        self._log_card = SectionCard(self._theme, "Execution Log")
        self._log_card.add_row(self.log_output)

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self._clear_text_log)
        self._log_card.add_title_suffix(clear_log_btn)

        self.add_section(self._log_card)

        self.add_stretch()
        self._active_course.changed.connect(self._on_active_course_changed)

        self._on_active_course_changed(self._active_course.course)

    def _clear_text_log(self):
        self.log_output.clear()

    # building a stub description card

    def _build_description_card(self) -> QWidget:
        card = SectionCard(self._theme, "Run Autograder(s)")
        badge = QLabel("(early alpha)")
        badge.setProperty("role", "text_muted")
        card.add_title_suffix(badge)
        description = QLabel("What a mess this page is!..")
        description.setWordWrap(True)
        card.add_row(description)
        return card

    def _build_course_label_card(self) -> QWidget:
        card = SectionCard(self._theme, "Selected Course:")
        self._course_label = QLabel(
            self._active_course.course.key.folder_name if self._active_course else ""
        )
        card.add_title_suffix(self._course_label)

        assignments = len(get_assignment_subfolders(self.assignment_folder))

        self._course_assignment_count_label = QLabel(
            f"{assignments} assignment(s) available for autograding."
        )
        self._active_course.changed.connect(self._update_course_label)

        self._update_course_label(self._active_course.course)

        card.add_row(self._course_assignment_count_label)
        return card

    # this is the assignments dropdown which will populate upon selection of a course

    def _build_assignments_dropdown(self) -> QWidget:
        card = SectionCard(self._theme, "Select Assignment:")

        self.assignment_combo = QComboBox()
        self.assignment_combo.setProperty("role", "dropdown")

        self.assignment_combo.setCurrentIndex(-1)

        self.assignment_combo.currentTextChanged.connect(self._on_assignment_selected)

        card.add_row(self.assignment_combo)
        return card

    # this checkbox field populates upon selection of an assignment

    def _build_available_autograders_dropdown(self) -> QWidget:
        self.autograders_card = SectionCard(self._theme, "Select Autograder(s):")

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        self.select_all_btn = QPushButton("Select All")
        self.select_unrun_btn = QPushButton("Select Not Yet Run")
        self.deselect_all_btn = QPushButton("Clear Selections")

        self.select_all_btn.clicked.connect(self._select_all_autograders)

        self.select_unrun_btn.clicked.connect(self._select_unrun_autograders)

        self.deselect_all_btn.clicked.connect(self._deselect_autograders)
        controls_layout.addStretch()
        controls_layout.addWidget(self.select_all_btn)
        controls_layout.addWidget(self.select_unrun_btn)
        controls_layout.addWidget(self.deselect_all_btn)

        self.autograders_card.add_title_suffix(controls)

        return self.autograders_card

    def _select_all_autograders(self) -> None:
        for row in self.autograder_rows:
            row.checkbox.setChecked(True)

        self._update_run_button_state()

    def _select_unrun_autograders(self) -> None:
        for row in self.autograder_rows:
            row.checkbox.setChecked(not row.autograder.has_run)

        self._update_run_button_state()

    def _deselect_autograders(self) -> None:
        for row in self.autograder_rows:
            row.checkbox.setChecked(False)
        self._update_run_button_state()

    # this method updates the available assignments and clears the autograders

    def _on_active_course_changed(
        self,
        course: CourseFolder | None,
    ) -> None:
        if course is None:
            self.assignment_combo.clear()
            self._clear_autograders()
            return

        self.assignment_folder = course.path / "anonymized" / "gradescope_submissions"

        self.evaluations_folder = course.path / "anonymized" / "evaluations"

        self.saved_evaluations_folder = self.evaluations_folder

        assignments = get_assignment_subfolders(self.assignment_folder)

        self.assignment_combo.clear()
        self.assignment_combo.addItems(assignments)
        self.assignment_combo.setCurrentIndex(-1)

        self._clear_autograders()

    def _on_assignment_selected(self, assignment: str) -> None:
        active_course = self._active_course.course

        if active_course is None or not assignment:
            return

        course_name = active_course.key.course_label

        def normalize(s: str) -> str:
            return "".join(s.lower().split())

        course_name = normalize(course_name)
        autograder_folder = self.autograders_path / course_name / assignment

        self.evaluations_folder = self.saved_evaluations_folder / assignment

        self.submissions_folder = (
            active_course.path / "anonymized" / "gradescope_submissions" / assignment
        )
        self._update_run_button_state()

        self._populate_autograders(autograder_folder)

    def _populate_autograders(self, autograders_folder: Path) -> None:

        self._clear_autograders()

        self.autograder_rows = []

        for folder_name in get_assignment_subfolders(autograders_folder):
            folder = autograders_folder / folder_name

            info = load_autograder(folder)

            row = AutograderRow(self._theme, info)

            row.checkbox.stateChanged.connect(self._update_run_button_state)

            self.autograder_rows.append(row)

            self.autograders_card.add_row(row)

    def _clear_autograders(self) -> None:
        while self.autograder_rows:
            row = self.autograder_rows.pop()

            self.autograders_card._body_layout.removeWidget(row)

            row.deleteLater()

    def _run_autograders(self):
        for row in self.autograder_rows:
            if not row.checkbox.isChecked():
                continue

            def work(row=row):
                return autograde_submissions_folder(
                    input_folder=self.submissions_folder,
                    output_folder=self.evaluations_folder,
                    autograder_folder_arg=row.autograder.path.resolve(),
                )

            def on_result(elapsed, row=row):
                row.autograder.has_run = True
                row.autograder.duration_seconds = elapsed
                row.autograder.last_run = datetime.now()
                row.autograder.last_status = "success"

                save_autograder_metadata(row.autograder)
                row.refresh()

            def on_error(exc, row=row):
                row.autograder.has_run = True
                row.autograder.duration_seconds = None
                row.autograder.last_run = None
                row.autograder.last_status = "failure"

                save_autograder_metadata(row.autograder)
                row.refresh()

            run_in_background(
                work,
                on_result,
                on_error,
            )

    def _update_run_button_state(self) -> None:
        self.run_btn.setEnabled(self._can_run())

    def _can_run(self) -> bool:
        # course_selected = bool(self.course_combo.currentText())
        course_selected = self._active_course.course is not None
        assignment_selected = bool(self.assignment_combo.currentText())

        autograder_selected = any(row.checkbox.isChecked() for row in self.autograder_rows)

        if not course_selected:
            self.run_btn.setToolTip("Select a course")

        elif not assignment_selected:
            self.run_btn.setToolTip("Select an assignment")

        elif not autograder_selected:
            self.run_btn.setToolTip("Select at least one autograder")

        else:
            self.run_btn.setToolTip("")

        return course_selected and assignment_selected and autograder_selected

    def selected_autograders(self) -> list[AutograderInfo]:
        return [row.autograder for row in self.autograder_rows if row.checkbox.isChecked()]

    def _update_course_label(
        self,
        course: CourseFolder | None,
    ) -> None:
        if course is None:
            self._course_label.setText("No course selected")
            self._course_assignment_count_label.setText(
                "0 assignment(s) available for autograding."
            )
            return

        self._course_label.setText(course.key.folder_name)

        assignment_folder = course.path / "anonymized" / "gradescope_submissions"

        assignments = len(get_assignment_subfolders(assignment_folder))

        self._course_assignment_count_label.setText(
            f"{assignments} assignment(s) available for autograding."
        )


class AATComparisonPage(ScrollableTab):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__(ctx.theme)
        self._ctx = ctx
        self._theme = ctx.theme
        self._active_course = ctx.active_course
        self._active_course.changed.connect(self._on_active_course_changed)
        load_dotenv()
        env_dir = (os.getenv("DEFAULT_OUTPUT_DIR") or "").strip()
        self.root_path = (
            Path(env_dir).expanduser() if env_dir else Path.home() / "Downloads" / "GAVEL"
        )
        self.courses_path = self.root_path / "courses"
        self.autograders_path = self.root_path / "autograders"
        self.assignment_folder = (
            self._active_course.course.path / "anonymized" / "gradescope_submissions"
        )
        self.reference_list_widget = QListWidget()
        self.candidate_list_widget = QListWidget()
        self.reference_list_widget.itemSelectionChanged.connect(self._on_reference_changed)
        self.visualization_tabs: QTabWidget | None = None

        self.scatter_chart: MatplotlibWidget | None = None
        self.histogram_chart: MatplotlibWidget | None = None
        self.distribution_chart: MatplotlibWidget | None = None
        self.bland_altman_chart: MatplotlibWidget | None = None
        self.heatmap_chart: MatplotlibWidget | None = None

        self.add_section(self._build_assignments_dropdown())
        self._on_active_course_changed(self._active_course.course)
        self.add_section(self._build_evaluations_selection())
        self.compare_btn = QPushButton("Compare")

        self.compare_btn.clicked.connect(self._compare_selected_evaluations)

        self.add_section(self.compare_btn)
        self.add_section(self._build_visualizations_card())

        self.visualization_tabs.setMinimumHeight(700)
        self.visualization_tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.add_stretch()

    def _build_assignments_dropdown(self) -> QWidget:
        card = SectionCard(self._theme, "Select Assignment:")

        self.assignment_combo = QComboBox()
        self.assignment_combo.setProperty("role", "dropdown")

        self.assignment_combo.setCurrentIndex(-1)

        self.assignment_combo.currentTextChanged.connect(self._on_assignment_selected)

        card.add_row(self.assignment_combo)
        return card

    def _build_evaluations_selection(self) -> QWidget:
        card = SectionCard(
            self._theme,
            "Select Autograder Evaluation Sets:",
        )

        layout = QHBoxLayout()
        self.reference_list_widget.setMaximumHeight(100)
        self.candidate_list_widget.setMaximumHeight(100)
        # self.reference_list_widget.setMaximumWidth(100)
        # self.candidate_list_widget.setMaximumWidth(100)

        # Reference column
        reference_layout = QVBoxLayout()
        reference_label = QLabel("Reference:")
        reference_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            border-width: 2px;
        """)
        reference_layout.addWidget(reference_label)
        reference_layout.addWidget(self.reference_list_widget)

        # Candidate column
        candidate_layout = QVBoxLayout()
        candidate_label = QLabel("Candidate:")
        candidate_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            border-width: 2px;
        """)
        candidate_layout.addWidget(candidate_label)
        candidate_layout.addWidget(self.candidate_list_widget)

        layout.addLayout(reference_layout)
        layout.addLayout(candidate_layout)

        card.layout().addLayout(layout)

        return card

    def _build_visualizations_card(self) -> QWidget:
        card = SectionCard(
            self._theme,
            "Comparison Visualizations",
        )

        self.visualization_tabs = QTabWidget()

        self.distribution_chart = MatplotlibWidget()
        self.scatter_chart = MatplotlibWidget()
        self.histogram_chart = MatplotlibWidget()
        self.bland_altman_chart = MatplotlibWidget()
        self.heatmap_chart = MatplotlibWidget()

        self.visualization_tabs.addTab(
            self.distribution_chart,
            "Distribution",
        )

        self.visualization_tabs.addTab(
            self.scatter_chart,
            "Scatter",
        )

        self.visualization_tabs.addTab(
            self.histogram_chart,
            "Differences",
        )

        self.visualization_tabs.addTab(
            self.bland_altman_chart,
            "Bland-Altman",
        )

        self.visualization_tabs.addTab(
            self.heatmap_chart,
            "Criteria",
        )

        card.add_row(self.visualization_tabs)

        return card

    def _compare_selected_evaluations(self) -> None:
        reference_item = self.reference_list_widget.currentItem()

        candidate_item = self.candidate_list_widget.currentItem()

        if not reference_item or not candidate_item:
            return

        reference_name = reference_item.text()
        candidate_name = candidate_item.text()

        df = compare_evaluations(
            reference_folder=Path(
                r"C:\Users\dcgul\Downloads\GAVEL\courses\trn226_26sc_12345\anonymized\evaluations\m3\ser222_01_03_hw02b_autograder_2"
            ),
            candidate_folder=Path(
                r"C:\Users\dcgul\Downloads\GAVEL\courses\trn226_26sc_12345\anonymized\evaluations\m3\ser222_01_03_hw02b_autograder"
            ),
            reference_name=reference_name,
            candidate_name=candidate_name,
            simulate_changes=True,
        )

        self._populate_visualizations(
            df,
            reference_name,
            candidate_name,
        )

    def _populate_visualizations(
        self,
        df,
        reference_name: str,
        candidate_name: str,
    ) -> None:

        ax = self.distribution_chart.get_axis()

        plot_score_distribution(
            ax,
            df,
            reference_name,
            candidate_name,
        )

        self.distribution_chart.draw()

        ax = self.scatter_chart.get_axis()

        plot_scatter_comparison(
            ax,
            df,
            reference_name,
            candidate_name,
        )

        self.scatter_chart.draw()

        ax = self.histogram_chart.get_axis()

        plot_difference_histogram(
            ax,
            df,
        )

        self.histogram_chart.draw()

        ax = self.bland_altman_chart.get_axis()

        plot_bland_altman(
            ax,
            df,
            reference_name,
            candidate_name,
        )

        self.bland_altman_chart.draw()

        ax = self.heatmap_chart.get_axis()

        plot_criterion_heatmap(
            ax,
            df,
        )

        self.heatmap_chart.draw()

    def _populate_evaluation_lists(self, evaluations_folder: Path) -> None:
        evaluation_sets = get_assignment_subfolders(evaluations_folder)
        print(evaluation_sets)

        self.reference_list_widget.clear()
        self.candidate_list_widget.clear()

        for evaluation_set in evaluation_sets:
            self.reference_list_widget.addItem(evaluation_set)
            self.candidate_list_widget.addItem(evaluation_set)

        self._evaluation_sets = evaluation_sets

    def _on_assignment_selected(self, assignment: str) -> None:
        active_course = self._active_course.course

        if active_course is None or not assignment:
            return

        self.evaluations_folder = self.saved_evaluations_folder / assignment
        print(self.evaluations_folder)

        self._populate_evaluation_lists(self.evaluations_folder)

    def _on_active_course_changed(
        self,
        course: CourseFolder | None,
    ) -> None:
        if course is None:
            self.assignment_combo.clear()
            # self._clear_autograders()
            return

        self.assignment_folder = course.path / "anonymized" / "gradescope_submissions"

        self.evaluations_folder = course.path / "anonymized" / "evaluations"

        self.saved_evaluations_folder = self.evaluations_folder

        assignments = get_assignment_subfolders(self.assignment_folder)

        self.assignment_combo.clear()
        self.assignment_combo.addItems(assignments)
        self.assignment_combo.setCurrentIndex(-1)

        self.reference_list_widget.clear()
        self.candidate_list_widget.clear()

    def _on_reference_changed(self):
        selected = self.reference_list_widget.currentItem()

        self.candidate_list_widget.clear()

        if not selected:
            self.candidate_list_widget.addItems(self._evaluation_sets)
            return

        selected_name = selected.text()

        for evaluation in self._evaluation_sets:
            if evaluation != selected_name:
                self.candidate_list_widget.addItem(evaluation)
