"""Proxy-grade mapping for SER334 Module 2, ported from
analysis_proxy_grade_ser334.py::compute_proxies_m2_24sc.
"""

from __future__ import annotations

from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier

SER334_M2 = ProxyGradeMapping(
    name="ser334_m2",
    criteria=(
        Criterion(
            "main menu",
            (
                Tier(2.0, all_of=("Main Menu 1", "Main Menu 2")),
                Tier(1.0, all_of=("Main Menu 1",)),
            ),
        ),
        Criterion(
            "memory leaks",
            (
                Tier(2.0, all_of=("Memory Allocation 3", "Memory Allocation 4")),
                Tier(1.0, all_of=("Memory Allocation 3",)),
            ),
        ),
        Criterion(
            "course_insert",
            (
                Tier(7.0, all_of=tuple(f"Insert Course {n}" for n in range(1, 8))),
                Tier(3.5, all_of=("Insert Course 1", "Insert Course 2", "Insert Course 4")),
                Tier(1.75, all_of=("Insert Course 1",)),
            ),
        ),
        Criterion(
            "course_insert::memory",
            (
                Tier(2.0, all_of=("Memory Allocation 1", "Memory Allocation 2")),
                Tier(1.0, all_of=("Memory Allocation 1",)),
            ),
        ),
        Criterion("schedule_print", (Tier(2.0, all_of=("Schedule Print",)),)),
        Criterion(
            "course_drop",
            (
                Tier(5.0, all_of=tuple(f"Remove Course {n}" for n in range(1, 5))),
                Tier(2.5, all_of=("Remove Course 1", "Remove Course 2", "Remove Course 3")),
                Tier(1.25, all_of=("Remove Course 1",)),
            ),
        ),
        Criterion(
            "course_drop::memory",
            (
                Tier(
                    2.0,
                    all_of=(
                        "Memory Allocation 5",
                        # "Memory Allocation 6",  # disabled for now
                    ),
                ),
                Tier(1.0, all_of=("Memory Allocation 5",)),
            ),
        ),
        Criterion(
            "schedule_load",
            (
                Tier(4.0, all_of=("Load File 1", "Load File 2", "Load File 3")),
                Tier(2.0, all_of=("Load File 1",)),
            ),
        ),
        Criterion(
            "schedule_save",
            (
                Tier(4.0, all_of=("Save File 1", "Save File 2")),
                Tier(2.0, all_of=("Save File 1",)),
            ),
        ),
    ),
)
