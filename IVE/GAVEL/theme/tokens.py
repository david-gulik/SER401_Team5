from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class ThemeTokens:
    color: Dict[str, str]
    spacing: Dict[str, int]
    shape: Dict[str, int]
    typography: Dict[str, Any]

    def sp(self, n: int) -> int:
        key = str(n)
        if key not in self.spacing:
            raise KeyError(f"Missing spacing token: {key}")
        return int(self.spacing[key])


_REQUIRED_COLOR_KEYS = [
    "bg",
    "surface",
    "surface_alt",
    "border",
    "text",
    "text_muted",
    "focus",
    "selection",
    "status_nominal",
    "status_caution",
    "status_warning",
    "status_critical",
    "status_unknown",
]

_REQUIRED_SPACING_KEYS = ["0", "4", "8", "12", "16", "24", "32"]
_REQUIRED_SHAPE_KEYS = ["radius_sm", "radius_md", "radius_lg", "border_width"]
_REQUIRED_TYPE_KEYS = ["font_family", "font_size_base", "font_size_h1", "font_size_h2", "font_size_h3"]


def load_tokens(path: Path) -> ThemeTokens:
    data = json.loads(path.read_text(encoding="utf-8"))

    for block in ["color", "spacing", "shape", "typography"]:
        if block not in data:
            raise KeyError(f"Missing token block: {block}")

    for k in _REQUIRED_COLOR_KEYS:
        if k not in data["color"]:
            raise KeyError(f"Missing color token: {k}")

    for k in _REQUIRED_SPACING_KEYS:
        if k not in data["spacing"]:
            raise KeyError(f"Missing spacing token: {k}")

    for k in _REQUIRED_SHAPE_KEYS:
        if k not in data["shape"]:
            raise KeyError(f"Missing shape token: {k}")

    for k in _REQUIRED_TYPE_KEYS:
        if k not in data["typography"]:
            raise KeyError(f"Missing typography token: {k}")

    return ThemeTokens(
        color=data["color"],
        spacing={k: int(v) for k, v in data["spacing"].items()},
        shape={k: int(v) for k, v in data["shape"].items()},
        typography=data["typography"],
    )
