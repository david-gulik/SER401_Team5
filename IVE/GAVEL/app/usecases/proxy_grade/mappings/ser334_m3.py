"""Proxy-grade mapping for SER334 Module 3, ported from
analysis_proxy_grade_ser334.py::compute_proxies_m3_24fc.
"""

from __future__ import annotations

from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier

# Test names by number. The number is part of the name so that, for example,
# "1.1)" is never confused with the "1.1)" inside "11.1)".
_NAMES = {
    "1.1": "1.1) BMP Headers IO",
    "1.2": "1.2) DIB Headers IO",
    "2.1": "2.1) DIB Headers IO",
    "2.2": "2.2) Reading pixels single row",
    "2.3": "2.3) Reading pixels single rows",
    "2.4": "2.4) Reading pixels many rows",
    "2.5": "2.5) Reading pixels many rows",
    "3.1": "3.1) Write pixels single row",
    "3.2": "3.2) Write pixels single row",
    "3.3": "3.3) Write pixels many rows",
    "3.4": "3.4) Write pixels many rows",
    "4.1": "4.1) Image -- getWidth",
    "4.2": "4.2) Image -- getWidth",
    "4.3": "4.3) Image -- getHeight",
    "4.4": "4.4) Image -- getHeight",
    "4.5": "4.5) Image -- getPixels",
    "4.6": "4.6) Image -- getPixels",
    "4.7": "4.7) Image -- getPixels",
    "4.8": "4.8) Image -- getPixels",
    "5.1": "5.1) Color Shift Filter - Divisible by 4, shifting 0.",
    "5.2": "5.2) Color Shift Filter - Divisible by 4, shifting positive.",
    "5.3": "5.3) Color Shift Filter - Divisible by 4, shifting negative.",
    "5.4": "5.4) Color Shift Filter - Non-Divisible by 4, shifting 0.",
    "5.5": "5.5) Color Shift Filter - Non-Divisible by 4, shifting positive.",
    "5.6": "5.6) Color Shift Filter - Non-Divisible by 4, shifting negative.",
    "6.1": "6.1) Grayscale Filter - Divisible by 4",
    "6.2": "6.2) Grayscale Filter - Non-divisible by 4",
    "6.3": "6.3) Grayscale Filter - Setting channels",
    "7.1": "7.1) Image Resize - Number of pixels",
    "7.3": "7.3) Image Reisze - Number of pixels",
    "8.1": "8.1) Image create",
    "8.2": "8.2) Image destroy",
    "8.3": "8.3) Image destroy",
    "9.1": "9.1) Program Input 1",
    "9.2": "9.2) Program Input 2",
    "9.3": "9.3) Program Input 3",
    "10.1": "10.1) Program Input 4",
    "10.2": "10.2) Color Shift 1",
    "10.3": "10.3) Color Shift 2",
    "10.4": "10.4) Color Shift 3",
    "10.5": "10.5) Color Shift 4",
    "11.1": "11.1) Copy Image 1",
    "11.2": "11.2) Copy Image 2",
    "12.1": "12.1) Copy Image 3",
    "12.2": "12.2) Copy Image 4",
    "13.1": "13.1) Grayscale 1",
    "13.2": "13.2) Grayscale 2",
    "14.1": "14.1) Image Scaling 1",
    "14.2": "14.2) Image Scaling 2",
    "14.3": "14.3) Image Scaling 3",
    # "7.2": "7.2) Image -- Resize, pixel data",
    # "7.4": "7.4) Image -- Resize, pixel data",
    # "14.4": "14.4) Image Scaling 4",
}


def _t(*numbers: str) -> tuple[str, ...]:
    return tuple(_NAMES[number] for number in numbers)


_PIXELS_IO = _t("2.1", "2.2", "2.3", "2.4", "2.5", "3.1", "3.2", "3.3", "3.4")
_GET_PIXELS = _t("4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8")

SER334_M3 = ProxyGradeMapping(
    name="ser334_m3",
    criteria=(
        Criterion(
            "bmp headers io",
            (
                Tier(4.0, all_of=_t("1.1", "1.2")),
                Tier(2.0, any_of=_t("1.1", "1.2")),
            ),
        ),
        Criterion(
            "pixels io",
            (
                Tier(4.0, all_of=_PIXELS_IO),
                Tier(2.0, any_of=_PIXELS_IO, at_least=5),
            ),
        ),
        Criterion(
            "input and output file names",
            (
                Tier(4.0, all_of=_t("9.1", "9.2", "9.3")),
                Tier(2.0, any_of=_t("9.1", "9.2", "9.3"), at_least=2),
            ),
        ),
        Criterion("input validation", (Tier(4.0, all_of=_t("10.1")),)),
        Criterion(
            "filter: color shift",
            (
                Tier(
                    5.0,
                    all_of=_t(
                        "5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "10.2", "10.3", "10.4", "10.5"
                    ),
                ),
                Tier(2.5, all_of=_t("5.1", "5.2", "5.4", "5.5", "10.2", "10.4")),
                Tier(2.5, all_of=_t("5.1", "5.3", "5.4", "5.6", "10.3", "10.5")),
                Tier(2.5, all_of=_t("5.1", "5.2", "5.3")),
                Tier(2.5, all_of=_t("5.4", "5.5", "5.6")),
            ),
        ),
        Criterion(
            "copy image",
            (
                Tier(5.0, all_of=_t("11.1", "11.2", "12.1", "12.2")),
                Tier(2.5, all_of=_t("11.1", "11.2")),
                Tier(2.5, all_of=_t("12.1", "12.2")),
                Tier(2.5, all_of=_t("11.1", "12.1")),
            ),
        ),
        Criterion(
            "image structure",
            (
                Tier(5.0, all_of=(*_t("8.1", "8.2", "8.3"), *_GET_PIXELS)),
                Tier(2.5, any_of=_GET_PIXELS, at_least=4),
                Tier(2.5, all_of=_t("8.1", "8.2", "8.3")),
                Tier(2.5, all_of=_t("4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7")),
            ),
        ),
        Criterion(
            "filter: grayscale",
            (
                Tier(5.0, all_of=_t("6.1", "6.2", "6.3", "13.1", "13.2")),
                Tier(2.5, all_of=_t("6.1", "6.2", "6.3")),
                Tier(2.5, all_of=_t("6.1", "6.3", "13.1")),
                Tier(2.5, all_of=_t("6.2", "6.3", "13.1")),
            ),
        ),
        Criterion(
            "image scaling",
            (
                Tier(
                    5.0,
                    all_of=_t(
                        "7.1",
                        # "7.2",
                        "7.3",
                        # "7.4",
                        "14.1",
                        "14.2",
                        "14.3",
                        # "14.4",
                    ),
                ),
                Tier(
                    2.5,
                    all_of=_t(
                        "7.1",
                        # "7.2",
                        "14.1",
                        "14.2",
                    ),
                ),
                Tier(
                    2.5,
                    all_of=_t(
                        "7.3",
                        # "7.4",
                        "14.3",
                        # "14.4",
                    ),
                ),
            ),
        ),
    ),
)
