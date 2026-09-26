"""Proxy-grade mapping for SER334 Module 9, ported from
analysis_proxy_grade_ser334.py::compute_proxies_m9_25fc.
"""

from __future__ import annotations

from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier

SER334_M9 = ProxyGradeMapping(
    name="ser334_m9",
    criteria=(
        Criterion("read data: basic", (Tier(2.0, all_of=("Read Data From File",)),)),
        Criterion("read data: processes", (Tier(2.0, all_of=("Read Data From File",)),)),
        Criterion("read data: dynamic", (Tier(7.0, all_of=("Dynamic Memory Allocation",)),)),
        Criterion(
            "sjf: simulation",
            (
                Tier(3.0, all_of=("SJF Test Display Ticks", "SJF Test Simulate Ticks")),
                Tier(1.5, all_of=("SJF Test Display Ticks",)),
            ),
        ),
        Criterion(
            "sjf: algorithms",
            (
                Tier(
                    4.0,
                    all_of=(
                        "SJF Test Algorithm with 2 Processes",
                        "SJF Test Algorithm with a variable number of Processes",
                    ),
                ),
                Tier(2.0, all_of=("SJF Test Algorithm with 2 Processes",)),
            ),
        ),
        Criterion(
            "sjf: output",
            (
                Tier(3.0, all_of=("SJF Calculate Turnaround Time", "SJF Calculate Waiting Time")),
                Tier(1.5, any_of=("SJF Calculate Turnaround Time", "SJF Calculate Waiting Time")),
            ),
        ),
        Criterion(
            "sjfl: simulation",
            (
                Tier(3.0, all_of=("SJFL Test Display Ticks", "SJFL Test Simulate Ticks")),
                Tier(1.5, all_of=("SJFL Test Display Ticks",)),
            ),
        ),
        Criterion(
            "sjfl: algorithms",
            (
                Tier(
                    4.0,
                    all_of=(
                        "SJFL Test Algorithm with 2 Processes",
                        "SJFL Test Algorithm with a variable number of Processes",
                    ),
                ),
                Tier(2.0, all_of=("SJFL Test Algorithm with 2 Processes",)),
            ),
        ),
        Criterion(
            "sjfl: output",
            (
                Tier(
                    4.0,
                    all_of=(
                        "SJFL Calculate Turnaround Time",
                        "SJFL Calculate Waiting Time",
                        "SJFL Calculate Estimation Error",
                    ),
                ),
                Tier(
                    2.0,
                    any_of=(
                        "SJFL Calculate Turnaround Time",
                        "SJFL Calculate Waiting Time",
                        "SJFL Calculate Estimation Error",
                    ),
                ),
            ),
        ),
    ),
)
