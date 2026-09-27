"""On-disk layout of a GAVEL workspace and the tools to read it back.

- ``layout``: where every file lives (``CourseKey``, ``Workspace``, ``DataTree``).
- ``manifest``: the ``manifest.json`` written at each course root.
- ``recording``: helpers a download use case calls after writing a file.
- ``dataset``: ``CourseDataset``, which loads a course folder into the existing DTOs.

See ``docs/workspace_layout.md`` for the agreed structure and naming rules.
"""

from GAVEL.app.workspace.dataset import CourseDataset, DatasetReaders, MissingArtifactError
from GAVEL.app.workspace.layout import (
    AssignmentFolder,
    CourseFolder,
    CourseKey,
    DataTree,
    Workspace,
    module_number_from_name,
)
from GAVEL.app.workspace.manifest import (
    ArtifactEntry,
    AssignmentEntry,
    CourseManifest,
    ManifestError,
    load_manifest,
    save_manifest,
)
from GAVEL.app.workspace.recording import ArtifactExistsError, guard_not_downloaded, record

__all__ = [
    "ArtifactEntry",
    "ArtifactExistsError",
    "AssignmentEntry",
    "AssignmentFolder",
    "CourseDataset",
    "CourseFolder",
    "CourseKey",
    "CourseManifest",
    "DataTree",
    "DatasetReaders",
    "ManifestError",
    "MissingArtifactError",
    "Workspace",
    "guard_not_downloaded",
    "load_manifest",
    "module_number_from_name",
    "record",
    "save_manifest",
]
