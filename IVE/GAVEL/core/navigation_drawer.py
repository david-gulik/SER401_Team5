from __future__ import annotations

from functools import partial
from typing import Callable, Dict, List

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.core.page_registry import PageSpec
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing


class NavigationDrawer(QFrame):
    """
    Left navigation drawer with:
    - exclusive selection
    - animated collapse/expand
    - icon-only collapsed mode
    """

    def __init__(
        self,
        theme: ThemeContext,
        pages: List[PageSpec],
        on_navigate: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = theme
        self._on_navigate = on_navigate
        self._specs_by_id: Dict[str, PageSpec] = {p.page_id: p for p in pages}

        self._expanded_width = 260
        self._collapsed_width = 64
        self._is_collapsed = False

        self.setProperty("role", "nav_drawer")
        self.setMinimumWidth(self._expanded_width)
        self.setMaximumWidth(self._expanded_width)

        self._anim_group: QParallelAnimationGroup | None = None

        header = QHBoxLayout()
        header.setContentsMargins(
            theme.tokens.sp(8),
            theme.tokens.sp(8),
            theme.tokens.sp(8),
            theme.tokens.sp(8),
        )
        set_spacing(header, theme, 8)

        self._toggle = QToolButton(self)
        self._toggle.setText("≡")
        self._toggle.setProperty("role", "nav_toggle")
        self._toggle.clicked.connect(self.toggle)

        self._title = QLabel("My App", self)

        header.addWidget(self._toggle)
        header.addWidget(self._title)
        header.addStretch(1)

        self._buttons_layout = QVBoxLayout()
        self._buttons_layout.setContentsMargins(
            theme.tokens.sp(8),
            0,
            theme.tokens.sp(8),
            theme.tokens.sp(8),
        )
        set_spacing(self._buttons_layout, theme, 8)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._buttons_by_id: Dict[str, QToolButton] = {}
        for spec in pages:
            btn = QToolButton(self)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setProperty("role", "nav_item")
            btn.setToolTip(spec.title)
            btn.clicked.connect(partial(self._handle_clicked, spec.page_id))

            self._buttons_by_id[spec.page_id] = btn
            self._group.addButton(btn)
            self._buttons_layout.addWidget(btn)

        self._buttons_layout.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(header)
        root.addLayout(self._buttons_layout)

        self._render_buttons()

    def set_current(self, page_id: str) -> None:
        btn = self._buttons_by_id.get(page_id)
        if btn is None:
            return
        if not btn.isChecked():
            btn.setChecked(True)

    def _handle_clicked(self, page_id: str) -> None:
        self._on_navigate(page_id)

    def toggle(self) -> None:
        self._is_collapsed = not self._is_collapsed
        target = self._collapsed_width if self._is_collapsed else self._expanded_width

        if self._anim_group is not None and self._anim_group.state() == self._anim_group.State.Running:
            self._anim_group.stop()

        self._anim_group = QParallelAnimationGroup(self)

        anim_min = QPropertyAnimation(self, b"minimumWidth")
        anim_min.setDuration(180)
        anim_min.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim_min.setStartValue(self.minimumWidth())
        anim_min.setEndValue(target)

        anim_max = QPropertyAnimation(self, b"maximumWidth")
        anim_max.setDuration(180)
        anim_max.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim_max.setStartValue(self.maximumWidth())
        anim_max.setEndValue(target)

        self._anim_group.addAnimation(anim_min)
        self._anim_group.addAnimation(anim_max)

        self._title.setVisible(not self._is_collapsed)
        self._render_buttons()

        self._anim_group.start()

    def _render_buttons(self) -> None:
        for page_id, btn in self._buttons_by_id.items():
            spec = self._specs_by_id[page_id]
            btn.setText(self._nav_label(spec))
            # Keep left alignment in expanded mode, in collapsed mode it will still look centered enough
            btn.setMinimumHeight(self._theme.tokens.sp(32))

    def _nav_label(self, spec: PageSpec) -> str:
        if self._is_collapsed:
            return spec.icon_text
        return f"{spec.icon_text}  {spec.title}"
