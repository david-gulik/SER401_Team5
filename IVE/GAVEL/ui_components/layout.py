from __future__ import annotations

from PyQt6.QtWidgets import QLayout

from GAVEL.theme.context import ThemeContext


def set_margins(layout: QLayout, theme: ThemeContext, n: int) -> None:
    v = theme.tokens.sp(n)
    layout.setContentsMargins(v, v, v, v)


def set_h_margins(layout: QLayout, theme: ThemeContext, h: int, v: int) -> None:
    hv = theme.tokens.sp(h)
    vv = theme.tokens.sp(v)
    layout.setContentsMargins(hv, vv, hv, vv)


def set_spacing(layout: QLayout, theme: ThemeContext, n: int) -> None:
    layout.setSpacing(theme.tokens.sp(n))
