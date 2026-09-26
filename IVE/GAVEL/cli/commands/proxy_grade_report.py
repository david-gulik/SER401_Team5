from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from GAVEL.app.usecases.proxy_grade.generate_signed_error_report import (
    GenerateSignedErrorReportRequest,
    GenerateSignedErrorReportUseCase,
)
from GAVEL.app.usecases.proxy_grade.mappings.registry import MAPPINGS
from GAVEL.app_context import AppContext
from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader
from GAVEL.infra.yaml.yaml_gradescope_reader import YamlGradescopeReader


def handle_proxy_grade_report(ctx: AppContext, args: Namespace) -> int:
    use_case = GenerateSignedErrorReportUseCase(
        gradescope_reader=YamlGradescopeReader(),
        gradebook_reader=LegacyGradebookCSVReader(),
    )

    try:
        result = use_case.execute(
            GenerateSignedErrorReportRequest(
                submissions_dir=Path(args.submissions_dir),
                mapping=MAPPINGS[args.mapping],
                gradebook_path=Path(args.gradebook),
                gradebook_column=args.gradebook_column,
                output_path=Path(args.output),
            )
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"[PROXY-GRADE] {len(result.rows)} submissions scored, "
        f"{len(result.unmatched_submissions)} unmatched, "
        f"{len(result.failed_submissions)} failed"
    )
    if result.unmatched_submissions:
        print(
            f"[PROXY-GRADE] Unmatched: {', '.join(result.unmatched_submissions)}",
            file=sys.stderr,
        )
    return 0
