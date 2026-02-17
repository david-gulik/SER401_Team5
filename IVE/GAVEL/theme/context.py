from __future__ import annotations

from dataclasses import dataclass

from GAVEL.theme.tokens import ThemeTokens


@dataclass(frozen=True)
class ThemeContext:
    tokens: ThemeTokens
