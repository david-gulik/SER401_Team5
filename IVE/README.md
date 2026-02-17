## Design Description

### 1. Overall Architecture and Purpose

This system is an Integrated Validation Environment (IVE) for Automated Assessment Tools (AATs). Its purpose is to execute an autograder against a historical dataset of student submissions and compare the autograder's rubric-level results to a ground truth set derived from human grading. The IVE supports iterative autograder development by rerunning evaluations after code changes to detect regressions, quantify accuracy improvements, and identify instability (non-deterministic scoring) across repeated runs. The system captures validation activity, including accuracy metrics across autograder versions and progress visualizations. This IVE supports both a GUI for interactive analysis and a CLI for repeatable and scalable runs.  

To meet these requirements, this design uses a component-based architecture with clear boundaries between presentation, application workflow logic, and external integrations. The GUI uses MVVM so that views remain focused on rendering and user interaction, while view-models coordinate actions through use cases. The application layer implements core workflows as use cases so the same logic can be invoked by both GUI and CLI without duplication.

### 2. Major Components and Responsibilities

#### 2.1 Core Shell and Extensibility Framework (GUI Shell)

**Purpose:** Provide a modular, replaceable framework for adding new IVE capabilities as pages and tabs.
**Key functionality:**

* **MainWindow (Shell):** Owns the navigation drawer and the page container. Creates pages lazily on first navigation to keep startup fast as the tool grows.
* **NavigationDrawer:** Provides left-side navigation across capability groups (pages), with stable ordering and selection state.
* **PageRegistry / PageSpec:** Central capability registration. Each page is declared via metadata and a factory method, enabling future developers to add new modules without modifying the shell.

This framework exists to support the IVE workflows, not as an end in itself. Each page corresponds to a cohesive validation capability.

#### 2.2 Presentation Layer (GUI, MVVM)

**Purpose:** Provide interactive workflows for AAT developers, instructors, and TAs to explore disagreements, validate rubric scoring, and manage regression results.
**Key functionality:**

* **Pages:** Capability groups aligned to IVE needs, for example:

  * Dataset and Course Data Download
  * Autograder Execution and Run History
  * Rubric-level Delta Review (human vs autograder)
  * Regression Comparison (baseline vs candidate run)
  * Stability Evaluation (repeat-run variance)
  * Ground Truth Correction and Annotation
  * Metrics and Reporting (accuracy trends, charts)
* **Tabs (Views):** Responsible for layout and rendering only. Tabs do not perform grading logic or call external APIs directly.
* **ViewModels:** Own UI state and expose commands. View-models invoke application use cases, translate results into UI-ready state (including status semantics), and emit events for one-time UI actions (errors, notifications).

#### 2.3 Presentation Layer (CLI)

**Purpose:** Provide traceable, repeatable execution of the same validation workflows without the GUI, enabling scripting, batch runs, and integration into local automation. 
**Key functionality:**

* Commands map directly to application use cases (example: download course data, run autograder on dataset, compute deltas, compare runs).
* CLI produces deterministic outputs (files and structured summaries) and exit codes suitable for automation.

#### 2.4 Application Layer (Use Cases)

**Purpose:** Centralize IVE workflows in a UI-agnostic form that can be invoked consistently by both GUI and CLI. 
**Key functionality (core IVE workflows):**

* **Dataset ingestion and normalization:** Load submissions and ground truth grades into a consistent internal representation.
* **Autograder execution orchestration:** Run an autograder against a dataset, capture rubric-level outputs, and store run artifacts.
* **Rubric delta computation:** Compute per-submission and per-rubric criterion differences between autograder results and ground truth, prioritizing review of disagreements. 
* **Regression testing:** Compare a new run to a baseline run, detect score drift, and identify regressions where previously-correct cases become incorrect.  
* **Stability checking:** Execute repeated runs to detect non-determinism (example: 1 out of 10 runs produces a different result), quantify variance, and flag unstable rubric elements. 
* **Ground truth correction:** Support curation when human grading is incorrect by allowing annotations and corrections to the truth set while preserving provenance (who changed what, when, and why). 
* **Metrics logging and reporting:** Track accuracy improvements across autograder versions and validation sessions, including trend charts akin to burndown. 

Use cases depend on interfaces (ports) rather than concrete integrations. This keeps the validation logic stable even if external APIs or grading platforms change.

#### 2.5 Integration Layer (External Systems via Ports and Adapters)

**Purpose:** Represent external systems explicitly and isolate them behind replaceable adapters.  
**External systems represented:**

* **Canvas:** Source of course structure, gradebook matrices, assignment metadata, and submission artifacts as permitted.
* **Gradescope:** Source and execution environment for autograders and associated rubric data when applicable.
* **Autograder runtime:** The shoggoth-based autograder codebase and execution harness (building upon the existing repository). 

**Key integration components:**

* **Ports (Interfaces):** Define required operations such as "download course dataset", "fetch rubric definition", "execute autograder", "retrieve run outputs".
* **Adapters (Implementations):** Concrete clients for Canvas/Gradescope and a local execution adapters.

This design supports testing with simulated or anonymized datasets and enables swapping implementations if access constraints change.

#### 2.6 Data Model and Artifact Store

**Purpose:** Ensure reproducibility and auditability of validation runs. 
**Key functionality:**

* Store immutable run artifacts (inputs, autograder version identifiers, configuration, raw outputs, computed deltas, metrics summaries).
* Maintain versioned datasets and ground truth with provenance tracking for corrections.
* Provide exportable formats (JSON/CSV) for downstream analysis and reporting.

#### 2.7 Activity Logging and Visualization

**Purpose:** Provide traceability for scientific software development workflows and show progress across iterations.  
**Key functionality:**

* Record each run, comparison, and correction event.
* Generate accuracy trend summaries and charts (burndown-like progress visualization).
* Support "compare" views modeled after code review diffs (baseline vs candidate results at rubric granularity). 

### 3. Relationship Between Requirements and Design (Traceable Mapping)

The component design supports the final project requirements:

* **Execute autograder on historical submissions and compare to human ground truth**
  Implemented by application use cases for dataset ingestion, run orchestration, and rubric delta computation, backed by a dataset model and artifact store. 

* **Rubric-level disagreement review and deltas**
  Implemented by rubric delta computation outputs and dedicated GUI pages/tabs for filtering and investigating disagreements. 

* **Regression testing across autograder versions**
  Implemented by run comparison use cases that compare baseline vs candidate runs, producing regression reports and drill-down views.  

* **Stability checking for non-deterministic grading**
  Implemented by repeated-run workflows and stability metrics that flag variance at rubric criterion granularity. 

* **Correcting and annotating the truth set when humans make mistakes**
  Implemented by ground truth curation workflows that track provenance and allow controlled updates to the truth data used for comparisons. 

* **Capture activity information and show improvement over time**
  Implemented by run logging, metrics aggregation, and visualization components for trend and burndown-like charts. 

* **Provide both GUI and CLI**
  Implemented by shared use cases invoked by both MVVM view-models (GUI) and thin CLI commands (automation). 

* **Course data downloader as additional utility suite**
  Implemented as a dedicated integration module (Canvas downloader) and corresponding use case and CLI command, plus an optional GUI page for interactive use.  

### 4. Design Patterns and Architectural Impact

* **MVVM (GUI):** Keeps views simple and collaboration-friendly by pushing workflow logic into view-models and use cases.
* **Use Case / Application Service:** Ensures the same workflow logic is shared between GUI and CLI, improving correctness and reducing duplication.
* **Ports and Adapters:** Ensures Canvas, Gradescope, and autograder runtime integrations are replaceable and testable.
* **Factory + Registry:** Enables modular extension by registering new pages, integrations, and commands without modifying the shell.
* **Observer (signals):** Standard communication from view-models to views for state updates and events.
* **Provenance-aware artifact storage:** Supports reproducibility and auditability of validation outputs consistent with scientific software expectations. 

### 5. External Systems Representation

External systems are modeled as integration adapters with well-defined ports:

* Canvas API adapter for course metadata, gradebook matrices, and assignment artifacts.
* Gradescope adapter for autograder packaging/execution and rubric results where applicable.
* Local runtime adapter for controlled execution of shoggoth-based autograders, building upon the existing evaluation repository. 

### 6. Modularity and Replaceability

Each component is designed to be replaceable within its boundary:

* UI framework components (drawer, page shell, tab containers) can change without impacting validation logic.
* Use cases can be tested without GUI and reused by CLI.
* Integration adapters can be swapped (mock Canvas, offline datasets) without changing use cases.
* Data storage format can evolve (JSON to database) if the artifact store interface remains stable.


## Configuration & Environment

| Variable | Purpose | Default |
| --- | --- | --- |
| `CANVAS_BASE_URL` | Canvas API base URL; used by `HttpCanvasClient`. | `None` (Canvas features disabled) |
| `CANVAS_TOKEN` | Canvas API token (Bearer). | `None` |

If either Canvas variable is missing, the app falls back to `UnconfiguredCanvasClient`, raising user-friendly errors while allowing the rest of the UI to function.

---

## CLI Usage

```
python -m my_app.cli.main canvas-course download --course-id 123 --output-dir ./dump
```

The CLI shares the same `AppContext`, so any new use cases/services wired in GUI land can be exposed here by adding a subcommand.

---