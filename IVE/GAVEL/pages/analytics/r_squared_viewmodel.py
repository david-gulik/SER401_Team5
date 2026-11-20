from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.usecases.compute_test_redundancy import PairRedundancy
from GAVEL.app.usecases.proxy_grade.generate_r_squared_report import CrossAssessmentResult
from GAVEL.infra.json.r_squared_report_reader import read_r_squared_report


@dataclass(frozen=True)
class RSquaredData:
    report_label: str
    test_pairs: tuple[PairRedundancy, ...]
    cross_assessment: CrossAssessmentResult


class RSquaredViewModel:
    def load(self, report_path: Path) -> RSquaredData:
        result = read_r_squared_report(report_path)
        return RSquaredData(
            report_label=report_path.stem,
            test_pairs=result.test_pairs,
            cross_assessment=result.cross_assessment,
        )
