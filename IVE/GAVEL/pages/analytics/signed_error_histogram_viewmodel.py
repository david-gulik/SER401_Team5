from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.usecases.bin_signed_errors import SignedErrorBin, bin_signed_errors
from GAVEL.infra.json.signed_error_report_reader import read_signed_errors


@dataclass(frozen=True)
class SignedErrorHistogramData:
    module_label: str
    bins: tuple[SignedErrorBin, ...]


class SignedErrorHistogramViewModel:
    """Loads a signed-error report and prepares its values for the histogram chart."""

    def load(self, report_path: Path, bin_width: float = 1.0) -> SignedErrorHistogramData:
        values = read_signed_errors(report_path)
        bins = bin_signed_errors(values, bin_width=bin_width)
        return SignedErrorHistogramData(module_label=report_path.stem, bins=bins)
