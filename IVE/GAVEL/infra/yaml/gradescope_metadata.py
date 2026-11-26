from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# A "..." alone at the start of a line ends a YAML document. Inside a value it
# is always indented, so a line matching this is never student data.
_DOCUMENT_END = re.compile(r"^\.\.\.[ \t]*$\n?", re.MULTILINE)


def load_gradescope_metadata(path: Path) -> dict[str, Any]:
    """The submissions in a Gradescope ``submission_metadata.yml``, keyed by folder name.

    Some exports put "..." lines between submissions, and PyYAML rejects
    anything that follows one without a "---". Those lines are dropped, and a
    file split into several documents is read as one mapping.
    """
    text = _DOCUMENT_END.sub("", path.read_text(encoding="utf-8"))

    submissions: dict[str, Any] = {}
    for document in yaml.safe_load_all(text):
        if document is None:
            continue
        if not isinstance(document, dict):
            raise yaml.YAMLError(
                f"expected a mapping of submissions, found {type(document).__name__}"
            )
        submissions.update(document)
    return submissions
