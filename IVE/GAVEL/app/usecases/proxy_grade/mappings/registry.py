"""The proxy-grade mappings available by name."""

from __future__ import annotations

from GAVEL.app.dtos.proxy_grade_mapping import ProxyGradeMapping
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m2 import SER334_M2

MAPPINGS: dict[str, ProxyGradeMapping] = {mapping.name: mapping for mapping in (SER334_M2,)}
