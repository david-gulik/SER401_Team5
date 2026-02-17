# ExtendableUI Engineering Guide

This architecture demonstrates a clean layering between views, viewmodels, use cases, and infrastructural adapters. The UI strives to meet [Astro UXDS](https://www.astrouxds.com/) guidance by keeping components consistent, status-forward, and friendly for extension across mission dashboards.

This document explains how the repository is organized today and how to add new functionality (e.g., a brand-new page with tabs) in a way that respects the architecture rules.

---

## High-Level Architecture

```
┌────────────┐      ┌─────────────┐      ┌───────────┐      ┌─────────────┐
│  Views     │◄────►│ ViewModels  │◄────►│ Use Cases │◄────►│ Ports/Infra │
└────────────┘      └─────────────┘      └───────────┘      └─────────────┘
```

* **Views (widgets & tabs)** handle layout, styling, and signal wiring only.
* **ViewModels** own UI state, expose Qt signals, raise events, and orchestrate workflow by invoking use cases.
* **Use Cases (application layer)** encapsulate business logic, return DTOs/results, and are framework-agnostic (no PyQt imports).
* **Ports (interfaces)** outline external dependencies. **Infra adapters** implement those ports (e.g., HTTP clients) and are the only place third-party libraries like `requests` live.

`AppContext` + `AppServices` wire these layers together at startup so both GUI and CLI share the same dependencies.

---

## Repository Layout

| Path | Description |
| --- | --- |
| `app.py` | Minimal shim that imports `main` from `my_app.app`. Launches the GUI when you run `python app.py`. |
| `my_app/__init__.py` | Package marker; nothing fancy here but keeps `my_app` importable. |
| `my_app/app/` | **Application layer** modules that are GUI-agnostic. Loaded by both GUI (`my_app/app/main.py`) and CLI (`my_app/cli/main.py`).<br>• `main.py`: PyQt bootstrap that loads theme tokens, builds `AppContext`, and shows `MainWindow`.<br>• `dtos/`: Typed DTOs handed to/from use cases and ports. Used by use cases, infra, and viewmodels to describe data contracts.<br>• `ports/`: Abstract base classes (e.g., `CanvasClient`) consumed by use cases; concrete adapters live elsewhere.<br>• `usecases/`: Workflow logic (e.g., `canvas_download_course.py`). Imported by viewmodels and CLI command handlers.<br>• `__init__.py`: Re-exports `main` so callers can simply `from my_app.app import main`. |
| `my_app/app_context.py` | Defines `AppContext`, an immutable dependency bundle (theme/config/logger/services) passed into every page factory by `PageRegistry`. |
| `my_app/app_services.py` | Hosts `AppServices`, which is constructed once at startup. Use to register new use cases/services that pages or CLI should share. |
| `my_app/bootstrap.py` | Glue that reads config/environment and builds concrete infra clients (e.g., HTTP adapters). `main.py` and CLI use this when wiring services. |
| `my_app/cli/` | Complete CLI stack:<br>• `main.py`: Builds argparse tree, constructs the same `AppContext`, then dispatches to handlers.<br>• `commands/`: Each file exports thin handlers wrapping use cases (e.g., Canvas download). Useful for automation/testing. |
| `my_app/core/` | Reusable GUI scaffolding consumed by every page:<br>• `base_page.py` / `base_tab.py`: Contracts for page/tab implementations.<br>• `page_registry.py`: Singleton registry; pages register themselves so `MainWindow` can auto-wire nav + content.<br>• `navigation_drawer.py`: Loads registered pages and exposes callbacks.<br>• `status.py`: `Status` enum + styling helpers supporting Astro UXDS status semantics.<br>`MainWindow` loads this layer and stays unaware of individual pages. |
| `my_app/pages/` | Feature-specific MVVM modules. Each folder (e.g., `home`, `settings`, `canvas_course`) contains:<br>• `page.py`: Registers the page, instantiates viewmodels with `AppContext`, and assembles tabs.<br>• `viewmodel.py`: Qt-based VM bridging views and use cases/services.<br>• `tabs.py`: Pure view layer that binds signals to the VM and renders `UiState`. Imported only by PyQt components. |
| `my_app/services/` | Cross-cutting singleton-like utilities:<br>• `config_service.py`: Loaded at startup (GUI + CLI) to fetch env vars such as `CANVAS_BASE_URL` / `CANVAS_TOKEN`. Viewmodels read from `ctx.config` to display environment/versions.<br>• `logger.py`: Wraps Python logging with a simple interface; both VMs and CLI share it. |
| `my_app/theme/` | Styling system consumed by GUI bootstrap and UI components:<br>• `tokens.py`: Loads token JSON (fonts, colors, spacing).<br>• `context.py`: Lightweight wrapper referencing the tokens.<br>• `qss_builder.py`: Converts tokens to QSS applied globally (keeps visuals aligned with Astro UXDS). |
| `my_app/ui_components/` | Shared widgets used by tabs (e.g., `SectionCard`, `StatusPill`, layout helpers). Only views import these; viewmodels remain oblivious to Qt specifics. |
| `my_app/infra/` | Concrete implementations of ports. Loaded during bootstrap when building services (e.g., `HttpCanvasClient`). This is the only directory that imports external SDKs like `requests`. |

Generated caches (e.g., `__pycache__`) should not be committed.

---

## Extending the Application: Adding a New Page + Tab

This end-to-end checklist shows how to introduce a new feature (for example, a “Telemetry” page with an “Upload” tab). It follows the existing Canvas Course implementation as a template.

### 1. Define Data & Contracts
1. **DTOs**: In `my_app/app/dtos/`, create models that describe the data your use case will return.
2. **Port interface**: In `my_app/app/ports/`, declare an abstract class describing the operations your use case needs (e.g., `TelemetryClient.fetch_samples`). No PyQt imports; just pure Python types/DTOs.

### 2. Implement the Use Case
1. Add a file under `my_app/app/usecases/`. Export request/result dataclasses + a `UseCase` class with an `execute` method.
2. Enforce validation, call the port, and return structured data (no printing, no QWidget references).

### 3. Provide Infrastructure
1. Under `my_app/infra/<domain>/`, create a concrete adapter implementing your port (e.g., HTTP REST client).
2. Handle serialization, error reporting (`raise_for_status`), and mapping into DTOs.
3. Keep third-party imports contained here.

### 4. Wire Services
1. Update `my_app/app_services.py` to instantiate the new use case and expose it via `AppServices`.
2. Extend `my_app/bootstrap.py` (or a new helper) to build any new adapters based on config/environment.
3. Adjust `my_app/app/main.py` (and `my_app/cli/main.py` if needed) to pass these services into `AppContext`.

### 5. Build the GUI Page
1. **ViewModel** (`my_app/pages/<feature>/viewmodel.py`):<br>   * Subclass `QObject`.<br>   * Store the relevant use case + logger + config.<br>   * Define a dataclass `UiState` and PyQt signals (`state_changed`, `event_raised`).<br>   * Expose command methods (`load_data()`, `submit()`) that guard against reentry, call the use case, and emit new states/events.
2. **Tabs** (`tabs.py`):<br>   * Subclass `ScrollableTab`.<br>   * Accept only `(ThemeContext, ViewModel)` in the constructor.<br>   * Build widgets, wire signals (`textChanged`, `clicked`, etc.) to VM methods.<br>   * Listen to `state_changed` to re-render & `event_raised` for dialogs/toasts.<br>   * No direct use case or service imports.
3. **Page** (`page.py`):<br>   * Subclass `BasePage` and register it with `PageRegistry` (icon, title, group, order).<br>   * In `__init__`, grab `ctx.services`, instantiate the viewmodel, and add tabs to a `QTabWidget`. Tabs receive only theme + VM.

### 6. Update Navigation & CLI (Optional but recommended)
1. Import your new `Page` in `my_app/app/main.py` so it registers at startup.
2. If the feature benefits from CLI access, add a command handler in `my_app/cli/commands/` that reuses the same use case.

### 7. Configuration & Testing
1. Document any required environment variables or config knobs in the README.
2. Test both GUI and CLI flows with and without config to ensure friendly error states (e.g., show “Service not configured”).

Following these steps ensures new functionality remains decoupled, testable, and visually consistent with Astro UXDS principles.

---

## Current Feature Modules

* **Home (`my_app/pages/home/`)**: Demonstrates MVVM with shared viewmodels. Overview tab shows status pills; Data Entry tab submits mock data and proves event routing.
* **Settings (`my_app/pages/settings/`)**: Preferences stored within the viewmodel; tabs render environment/version metadata from config service.
* **Canvas Course (`my_app/pages/canvas_course/`)**: Full-stack example tying ports, use cases, infra, GUI, and CLI together to download Canvas course metadata into JSON.


## Quality & Style Notes

* Views never call services directly.
* Use cases do not import PyQt.
* Only infrastructure imports `requests` or external network libraries.
* Signals/events are the preferred way to communicate from VMs back to Tabs.
* Status messaging uses the shared `Status` enum + `StatusPill` to align with Astro UXDS status semantics.
* Add tests or manual steps to verify new features under both configured and unconfigured states.

## Rapid Prototyping Templates

The following snippets show the minimum code required to add a brand-new page with MVVM wiring, keeping views dumb and workflows encapsulated. Copy the templates into the indicated folders and fill in feature-specific details.

### 1. DTO + Port (application contracts)

**Why:** Define the exact data shape and external operations before writing logic so use cases remain UI-agnostic and easily testable.

`my_app/app/dtos/my_feature.py`
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class MyFeatureRecord:
    # DTOs are pure data holders shared between use cases, viewmodels, and adapters.
    # Keep them immutable (frozen=True) so they're safe to share and hash if needed.
    id: int
    name: str
```

`my_app/app/ports/my_feature_client.py`
```python
from abc import ABC, abstractmethod
from my_app.app.dtos.my_feature import MyFeatureRecord

class MyFeatureClient(ABC):
    """
    Ports describe WHAT we need from external systems.
    Use cases depend on this interface, not on HTTP or SDK-specific calls.
    """

    @abstractmethod
    def fetch_records(self, course_id: int) -> list[MyFeatureRecord]:
        """Return the domain objects required by the use case."""
        raise NotImplementedError
```

### 2. Use Case

**Why:** Centralize workflow/business rules so both GUI and CLI trigger the same behavior without duplicating logic.

`my_app/app/usecases/my_feature_sync.py`
```python
from dataclasses import dataclass
from pathlib import Path
from my_app.app.ports.my_feature_client import MyFeatureClient

@dataclass(frozen=True)
class SyncMyFeatureRequest:
    course_id: int
    output_dir: Path

@dataclass(frozen=True)
class SyncMyFeatureResult:
    saved_path: Path
    record_count: int

class SyncMyFeatureUseCase:
    def __init__(self, client: MyFeatureClient) -> None:
        # Depend only on the port so this use case is easy to test/mocks.
        self._client = client

    def execute(self, request: SyncMyFeatureRequest) -> SyncMyFeatureResult:
        # All validation lives here instead of viewmodels or CLI.
        if request.course_id <= 0:
            raise ValueError("course_id must be positive")

        records = self._client.fetch_records(request.course_id)
        # Use cases also own file/serialization logic if it's part of the workflow.
        request.output_dir.mkdir(parents=True, exist_ok=True)
        outfile = request.output_dir / f"feature_{request.course_id}.json"
        outfile.write_text("... serialize records ...", encoding="utf-8")
        return SyncMyFeatureResult(saved_path=outfile, record_count=len(records))
```

### 3. Infra Adapter

**Why:** Encapsulate network/file integrations behind the port, keeping third-party libraries isolated and replaceable.

`my_app/infra/my_feature/http_my_feature_client.py`
```python
import requests
from dataclasses import dataclass
from my_app.app.dtos.my_feature import MyFeatureRecord
from my_app.app.ports.my_feature_client import MyFeatureClient

@dataclass(frozen=True)
class MyFeatureApiConfig:
    base_url: str
    token: str

class HttpMyFeatureClient(MyFeatureClient):
    """Only place that imports requests; map JSON → DTOs."""

    def __init__(self, cfg: MyFeatureApiConfig) -> None:
        self._cfg = cfg  # Config injected so tests can pass fake URLs.

    def fetch_records(self, course_id: int) -> list[MyFeatureRecord]:
        # Networking, auth headers, pagination, etc., belong in infra.
        resp = requests.get(
            f"{self._cfg.base_url}/records/{course_id}",
            headers={"Authorization": f"Bearer {self._cfg.token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return [
            MyFeatureRecord(id=item["id"], name=item["name"])
            for item in resp.json()
        ]
```

### 4. App Services Wiring

**Why:** Register the new use case/client once so every consumer (pages, CLI, background tasks) can access the same instances.

`my_app/app_services.py`
```python
from my_app.app.ports.my_feature_client import MyFeatureClient
from my_app.app.usecases.my_feature_sync import SyncMyFeatureUseCase

@dataclass(frozen=True)
class AppServices:
    my_feature_client: MyFeatureClient
    sync_my_feature_uc: SyncMyFeatureUseCase
    # ...

    @classmethod
    def build(cls, canvas_client: CanvasClient, logger: AppLogger, *, my_feature_client: MyFeatureClient) -> "AppServices":
        """
        Central factory: create use cases once and share across GUI/CLI.
        Inject any instrumentation/loggers here rather than deep in views.
        """
        return cls(
            my_feature_client=my_feature_client,
            sync_my_feature_uc=SyncMyFeatureUseCase(my_feature_client),
            # ...
        )
```

Update `my_app/bootstrap.py` to construct `HttpMyFeatureClient` from config/env, then pass it into `AppServices.build`.

### 5. ViewModel

**Why:** Bridge UI and use cases—manage state, handle validation feedback, and expose Qt signals without letting widgets talk to services directly.

`my_app/pages/my_feature/viewmodel.py`
```python
from dataclasses import dataclass, replace
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from my_app.core.status import Status
from my_app.app.usecases.my_feature_sync import (
    SyncMyFeatureRequest,
    SyncMyFeatureUseCase,
)

@dataclass(frozen=True)
class MyFeatureUiState:
    course_id: str
    is_busy: bool
    status: Status
    message: str

class MyFeatureViewModel(QObject):
    # Views subscribe to these signals to react to state changes/events.
    state_changed = pyqtSignal(object)
    event_raised = pyqtSignal(object)  # optional events structure

    def __init__(self, use_case: SyncMyFeatureUseCase, output_dir: Path) -> None:
        super().__init__()
        # ViewModels depend on use cases/services, never on infra directly.
        self._use_case = use_case
        self._output_dir = output_dir
        self._state = MyFeatureUiState("", False, Status.UNKNOWN, "Ready.")

    def set_course_id(self, text: str) -> None:
        self._state = replace(self._state, course_id=text.strip())
        self.state_changed.emit(self._state)

    def sync(self) -> None:
        if self._state.is_busy:
            return
        self._set_busy("Syncing...")  # Update state before long IO.
        try:
            request = SyncMyFeatureRequest(course_id=int(self._state.course_id or "0"), output_dir=self._output_dir)
            result = self._use_case.execute(request)
        except Exception as exc:  # Catch exceptions to surface friendly UI messages.
            self._set_idle(Status.CRITICAL, str(exc))
            return
        self._set_idle(Status.NOMINAL, f"Saved {result.record_count} records to {result.saved_path}")

    def _set_busy(self, message: str) -> None:
        self._state = replace(self._state, is_busy=True, status=Status.WARNING, message=message)
        self.state_changed.emit(self._state)

    def _set_idle(self, status: Status, message: str) -> None:
        self._state = replace(self._state, is_busy=False, status=status, message=message)
        self.state_changed.emit(self._state)
```

### 6. Tab (View)

**Why:** Provide the minimal PyQt wiring (inputs, buttons, status pill) that renders `UiState` and forwards user actions to the ViewModel.

`my_app/pages/my_feature/tabs.py`
```python
from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton, QFormLayout, QWidget
from my_app.core.base_tab import ScrollableTab
from my_app.pages.my_feature.viewmodel import MyFeatureViewModel, MyFeatureUiState
from my_app.ui_components.section_card import SectionCard
from my_app.ui_components.status_pill import StatusPill

class MyFeatureTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: MyFeatureViewModel) -> None:
        super().__init__(theme)
        self._vm = vm
        self._course_id = QLineEdit()
        self._status = StatusPill(theme)
        self._message = QLabel()
        self._sync_btn = QPushButton("Sync")

        # Signals from widgets hook into VM commands/state setters.
        self._course_id.textChanged.connect(self._vm.set_course_id)
        self._sync_btn.clicked.connect(self._vm.sync)
        self._vm.state_changed.connect(self.render)

        # SectionCard provides consistent padding/layout per Astro guidelines.
        card = SectionCard(theme, "My Feature")
        form = QFormLayout()
        form.addRow("Course ID", self._course_id)
        form.addRow("", self._sync_btn)
        form.addRow("Status", self._status)
        form.addRow("Message", self._message)
        host = QWidget()
        host.setLayout(form)
        card.add_row(host)
        self.add_section(card)
        self.add_stretch()
        self.render(self._vm.get_state())

    def render(self, state: MyFeatureUiState) -> None:
        self._status.set_status(state.status)
        self._message.setText(state.message)
        self._sync_btn.setEnabled(not state.is_busy)
        if self._course_id.text() != state.course_id:
            self._course_id.blockSignals(True)
            self._course_id.setText(state.course_id)
            self._course_id.blockSignals(False)
```

### 7. Page Registration

**Why:** Hook your feature into the shell via `PageRegistry` so it appears in navigation and constructs VMs with the proper dependencies.

`my_app/pages/my_feature/page.py`
```python
from pathlib import Path
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout
from my_app.app_context import AppContext
from my_app.core.base_page import BasePage
from my_app.core.page_registry import PageRegistry, PageSpec
from my_app.pages.my_feature.tabs import MyFeatureTab
from my_app.pages.my_feature.viewmodel import MyFeatureViewModel

class MyFeaturePage(BasePage):
    page_id = "my_feature"
    title = "My Feature"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        # Pages own dependency injection for their viewmodels.
        vm = MyFeatureViewModel(ctx.services.sync_my_feature_uc, Path.home() / "Downloads" / "my_feature")
        tabs = QTabWidget()
        tabs.addTab(MyFeatureTab(ctx.theme, vm), "Sync")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

PageRegistry.get().register(
    PageSpec(
        page_id=MyFeaturePage.page_id,
        title=MyFeaturePage.title,
        icon_text="🧩",
        factory=lambda ctx: MyFeaturePage(ctx),
        group="Integrations",
        order=40,
    )
)
```

### 8. CLI Command

**Why:** Expose the same workflow to automation/scripting by reusing the use case and returning clear exit codes.

`my_app/cli/commands/my_feature.py`
```python
from argparse import Namespace
from pathlib import Path
from my_app.app.usecases.my_feature_sync import SyncMyFeatureRequest

def handle_my_feature_sync(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
    except ValueError:
        # Exit code 2 = argument/validation issue.
        print("course_id must be numeric")
        return 2
    output_dir = Path(args.output_dir).expanduser()
    try:
        result = ctx.services.sync_my_feature_uc.execute(
            SyncMyFeatureRequest(course_id=course_id, output_dir=output_dir)
        )
    except Exception as exc:
        # Log + print so both console and logger capture the failure reason.
        ctx.logger.error(f"Sync failed: {exc}")
        print(f"Sync failed: {exc}")
        return 1
    print(f"Saved {result.record_count} records to {result.saved_path}")
    return 0
```

Wire this handler into `my_app/cli/main.py` via argparse routing similar to the existing Canvas command.