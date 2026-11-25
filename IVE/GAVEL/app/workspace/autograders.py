"""The autograders a course can run, and getting one out of its zip.

Downloads keep each autograder as the zip Gradescope served, in the course's
folder under ``autograders/``. Running one needs a folder, so the first run
extracts the zip to ``autograders/<course>/m<module>/<zip name>/`` and later
runs reuse that folder. Autograders that were placed there by hand are listed
the same way.
"""

from __future__ import annotations

import os
import shutil
import stat
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.workspace.layout import CourseKey, Workspace


@dataclass(frozen=True)
class AutograderOption:
    name: str
    path: Path

    @property
    def is_zip(self) -> bool:
        return self.path.suffix.lower() == ".zip"


def list_autograders(
    workspace: Workspace, key: CourseKey, module_number: int
) -> tuple[AutograderOption, ...]:
    """Folders extracted for the module, then zips not yet extracted; newest first in each.

    A course keeps every autograder version it downloaded, so the one wanted is
    usually the latest and goes on top.
    """
    root = workspace.course_autograders_dir(key)
    options: dict[str, AutograderOption] = {}
    module_dir = root / f"m{module_number}"
    if module_dir.is_dir():
        for path in _newest_first(p for p in module_dir.iterdir() if p.is_dir()):
            options[path.name] = AutograderOption(path.name, path)
    if root.is_dir():
        for path in _newest_first(root.glob("*.zip")):
            options.setdefault(path.stem, AutograderOption(path.stem, path))
    return tuple(options.values())


def _newest_first(paths: Iterable[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: (-p.stat().st_mtime, p.name))


def ensure_extracted(
    option: AutograderOption, workspace: Workspace, key: CourseKey, module_number: int
) -> Path:
    """The folder to run; a zip is extracted on first use and reused after that."""
    if not option.is_zip:
        return option.path
    target = workspace.course_autograders_dir(key) / f"m{module_number}" / option.name
    if target.is_dir() and target.stat().st_mtime >= option.path.stat().st_mtime:
        return target
    if target.exists():
        _remove_tree(target)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(option.path) as archive:
        members = [m for m in archive.infolist() if _is_safe(m.filename)]
        prefix = _common_folder(members)
        for member in members:
            relative = member.filename[len(prefix) :]
            if not relative or relative.endswith("/"):
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)
    os.utime(target)
    return target


def _common_folder(members: list[zipfile.ZipInfo]) -> str:
    """``"grader/"`` when every file sits under one top-level folder, else ``""``."""
    tops = {m.filename.split("/", 1)[0] for m in members if not m.filename.endswith("/")}
    if len(tops) != 1:
        return ""
    [top] = tops
    if any("/" not in m.filename for m in members if not m.filename.endswith("/")):
        return ""
    return top + "/"


def _is_safe(name: str) -> bool:
    parts = Path(name).parts
    return not Path(name).is_absolute() and ".." not in parts


def _remove_tree(root: Path) -> None:
    for path in (root, *root.rglob("*")):
        try:
            os.chmod(path, path.stat().st_mode | stat.S_IWRITE)
        except OSError:
            pass
    shutil.rmtree(root, ignore_errors=True)
