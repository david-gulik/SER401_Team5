"""The proxy-grade mappings available by name."""

from __future__ import annotations

from GAVEL.app.dtos.proxy_grade_mapping import ProxyGradeMapping
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m2 import SER334_M2
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m3 import SER334_M3
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m9 import SER334_M9

MAPPINGS: dict[str, ProxyGradeMapping] = {
    mapping.name: mapping for mapping in (SER334_M2, SER334_M3, SER334_M9)
}
