from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnvVarSpec:
    name: str
    group: str
    label: str
    kind: str = "text"  # text | secret | int | dropdown | path
    options: tuple[str, ...] = ()
    path_kind: str = "file"  # file | folder (used when kind == "path")
    default: str = ""
    placeholder: str = ""
    help: str = ""


# Single source of truth for variables exposed in the settings UI.
# Order here drives display order within each group.
ENV_SCHEMA: tuple[EnvVarSpec, ...] = (
    # -- General -------------------------------------------------------------
    EnvVarSpec(
        name="DEFAULT_OUTPUT_DIR",
        group="General",
        label="Default output folder",
        kind="path",
        path_kind="folder",
        placeholder="~/Downloads/GAVEL",
        help=(
            "Default folder for all GAVEL downloads. Used as the starting value "
            "on the Download page; can be overridden there per-session."
        ),
    ),
    # -- Canvas --------------------------------------------------------------
    EnvVarSpec(
        name="CANVAS_BASE_URL",
        group="Canvas",
        label="Base URL",
        kind="text",
        default="https://canvas.asu.edu",
        placeholder="https://canvas.asu.edu",
        help="Canvas LMS root URL.",
    ),
    EnvVarSpec(
        name="CANVAS_TOKEN",
        group="Canvas",
        label="API token",
        kind="secret",
        help="Personal Canvas API token (Account -> Settings -> New Access Token).",
    ),
    EnvVarSpec(
        name="CANVAS_USERNAME",
        group="Canvas",
        label="Username",
        kind="text",
        help="Canvas login email; only required by flows that use password auth.",
    ),
    EnvVarSpec(
        name="CANVAS_PASSWORD",
        group="Canvas",
        label="Password",
        kind="secret",
        help="Canvas password; only required by flows that use password auth.",
    ),
    # -- ASU Roster ----------------------------------------------------------
    EnvVarSpec(
        name="ROSTER_AUTH_METHOD",
        group="ASU Roster",
        label="Auth method",
        kind="dropdown",
        options=("selenium", "cookies"),
        default="selenium",
        help="selenium opens a browser for CAS + Duo MFA. cookies uses an exported cookie file.",
    ),
    EnvVarSpec(
        name="ROSTER_COOKIE_FILE",
        group="ASU Roster",
        label="Cookie file",
        kind="path",
        path_kind="file",
        placeholder="cookies.txt",
        help="Netscape-format cookie file. Required when auth method is 'cookies'.",
    ),
    EnvVarSpec(
        name="ROSTER_TOKEN",
        group="ASU Roster",
        label="Catalog API token",
        kind="secret",
        help="Pre-existing catalog API Bearer token. Optional; skips Selenium for class lookup.",
    ),
    EnvVarSpec(
        name="ROSTER_MFA_TIMEOUT",
        group="ASU Roster",
        label="MFA timeout (s)",
        kind="int",
        default="120",
        help="Time the user has to complete CAS + Duo MFA in the browser.",
    ),
    EnvVarSpec(
        name="ROSTER_SESSION_TTL",
        group="ASU Roster",
        label="Session TTL (s)",
        kind="int",
        default="600",
        help="How long a cached session stays valid before re-authentication.",
    ),
    EnvVarSpec(
        name="ROSTER_HTTP_TIMEOUT",
        group="ASU Roster",
        label="HTTP timeout (s)",
        kind="int",
        default="30",
        help="Timeout for individual HTTP requests (API calls, roster downloads).",
    ),
    EnvVarSpec(
        name="ROSTER_PAGE_LOAD_TIMEOUT",
        group="ASU Roster",
        label="Page load timeout (s)",
        kind="int",
        default="30",
        help="Time to wait for the catalog domain to load before seeding PKCE params.",
    ),
    EnvVarSpec(
        name="ROSTER_TOKEN_EXCHANGE_TIMEOUT",
        group="ASU Roster",
        label="Token exchange timeout (s)",
        kind="int",
        default="30",
        help="Time for the catalog SPA to exchange an OAuth code for a JWT.",
    ),
    # -- Gradescope ----------------------------------------------------------
    EnvVarSpec(
        name="SUBMISSIONS_FOLDER",
        group="Gradescope",
        label="Submissions folder",
        kind="path",
        path_kind="folder",
        help="Local folder where Gradescope bulk-downloaded submissions are saved.",
    ),
    EnvVarSpec(
        name="GRADESCOPE_BASE_URL",
        group="Gradescope",
        label="Base URL",
        kind="text",
        default="https://www.gradescope.com",
        placeholder="https://www.gradescope.com",
    ),
    EnvVarSpec(
        name="GRADESCOPE_COURSES_SUFFIX",
        group="Gradescope",
        label="Courses URL suffix",
        kind="text",
        default="/courses",
    ),
    EnvVarSpec(
        name="GRADESCOPE_ASSIGNMENTS_SUFFIX",
        group="Gradescope",
        label="Assignments URL suffix",
        kind="text",
        default="/assignments",
    ),
    EnvVarSpec(
        name="GRADESCOPE_REVIEW_GRADES_SUFFIX",
        group="Gradescope",
        label="Review grades URL suffix",
        kind="text",
        default="/review_grades",
    ),
    EnvVarSpec(
        name="GRADESCOPE_GENERATED_FILES_SUFFIX",
        group="Gradescope",
        label="Generated files URL suffix",
        kind="text",
        default="/generated_files",
    ),
)


SCHEMA_NAMES: frozenset[str] = frozenset(spec.name for spec in ENV_SCHEMA)

# Map of env var name -> default value, for specs that declare one. Consumers
# read this when an env var is unset so the schema stays the single source of
# truth for default URLs/paths/etc.
SCHEMA_DEFAULTS: dict[str, str] = {spec.name: spec.default for spec in ENV_SCHEMA if spec.default}


def grouped_schema() -> tuple[tuple[str, tuple[EnvVarSpec, ...]], ...]:
    """Return ENV_SCHEMA bucketed by group, preserving first-seen order."""
    order: list[str] = []
    buckets: dict[str, list[EnvVarSpec]] = {}
    for spec in ENV_SCHEMA:
        if spec.group not in buckets:
            buckets[spec.group] = []
            order.append(spec.group)
        buckets[spec.group].append(spec)
    return tuple((g, tuple(buckets[g])) for g in order)


_ASSIGN_RE = re.compile(r"^(\s*)(#\s*)?([A-Z_][A-Z0-9_]*)\s*=(.*)$")


class EnvService:
    """Reads and writes the project .env file while preserving comments and ordering."""

    def __init__(self, env_path: Path) -> None:
        self._path = env_path

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> dict[str, str]:
        """Return active (non-commented) KEY=VALUE pairs from the file."""
        if not self._path.exists():
            return {}
        result: dict[str, str] = {}
        for raw in self._path.read_text(encoding="utf-8").splitlines():
            m = _ASSIGN_RE.match(raw)
            if not m or m.group(2):
                continue
            key, value = m.group(3), m.group(4)
            result[key] = _unquote(value.strip())
        return result

    def write(self, values: Mapping[str, str]) -> None:
        """Rewrite .env with `values`, preserving existing comments and order.

        For each key in `values`:
          - non-empty: ensure an active assignment line exists. Replaces the first
            line that mentions the key (commented or not), or appends if absent.
          - empty: comments out any active assignment for that key. Existing
            commented lines are left as-is.

        Lines that don't reference a schema key are passed through untouched.
        """
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("", encoding="utf-8")

        existing = self._path.read_text(encoding="utf-8").splitlines()
        seen: set[str] = set()
        out_lines: list[str] = []

        for raw in existing:
            m = _ASSIGN_RE.match(raw)
            if not m:
                out_lines.append(raw)
                continue
            key = m.group(3)
            if key not in values:
                out_lines.append(raw)
                continue

            new_value = values[key]
            if key in seen:
                # Already wrote the canonical line; drop subsequent matches to avoid duplicates.
                if new_value == "" and m.group(2):
                    out_lines.append(raw)
                continue

            seen.add(key)
            if new_value == "":
                out_lines.append(f"# {key}=")
            else:
                out_lines.append(f"{key}={_quote_if_needed(new_value)}")

        appended_header = False
        for key, value in values.items():
            if key in seen or value == "":
                continue
            if not appended_header:
                if out_lines and out_lines[-1].strip() != "":
                    out_lines.append("")
                appended_header = True
            out_lines.append(f"{key}={_quote_if_needed(value)}")

        text = "\n".join(out_lines)
        if not text.endswith("\n"):
            text += "\n"
        self._path.write_text(text, encoding="utf-8")


def _unquote(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        inner = v[1:-1]
        if v[0] == '"':
            return _unescape_double_quoted(inner)
        return inner
    return v


def _unescape_double_quoted(s: str) -> str:
    # Reverses _quote_if_needed's escaping (\\ -> \ and \" -> ") in one pass
    # so repeated read/write cycles don't keep doubling backslashes.
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "\\" and i + 1 < n and s[i + 1] in ('\\', '"'):
            out.append(s[i + 1])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _quote_if_needed(value: str) -> str:
    if value == "":
        return ""
    if any(ch in value for ch in (" ", "\t", "#")):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
