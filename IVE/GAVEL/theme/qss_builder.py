"""Astro UXDS inspired Qt Style Sheet for GAVEL.

All palette and geometry values come from the tokens JSON so this file
stays free of hard-coded hex values. The public entry point is
``build_app_qss(tokens)``; helper functions are split per widget to keep
each rule block focused and easy to diff.

Reference: https://www.astrouxds.com
"""

from __future__ import annotations

from GAVEL.theme.tokens import ThemeTokens


def _px(n: int) -> str:
    return f"{n}px"


def _pt(n: int) -> str:
    return f"{n}pt"


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert a #rrggbb hex token and a 0.0–1.0 alpha to a Qt rgba() string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = round(alpha * 255)
    return f"rgba({r}, {g}, {b}, {a})"


def build_app_qss(t: ThemeTokens) -> str:
    sections = [
        _qss_global(t),
        _qss_main(t),
        _qss_labels(t),
        _qss_push_button(t),
        _qss_line_edit(t),
        _qss_text_edit(t),
        _qss_combo_box(t),
        _qss_spin_box(t),
        _qss_check_radio(t),
        _qss_tabs(t),
        _qss_group_box(t),
        _qss_scroll_area(t),
        _qss_scrollbar(t),
        _qss_tooltip(t),
        _qss_splitter(t),
        _qss_nav_drawer(t),
        _qss_surface_card(t),
        _qss_status_pill(t),
        _qss_status_banner(t),
    ]
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------


def _qss_global(t: ThemeTokens) -> str:
    c = t.color
    ty = t.typography
    return f"""
    * {{
        color: {c["text"]};
        font-family: "{ty["font_family"]}";
        font-size: {_pt(int(ty["font_size_base"]))};
        selection-background-color: {c["selection_bg"]};
        selection-color: {c["selection_text"]};
    }}

    QWidget {{
        background-color: {c["app_bg"]};
        color: {c["text"]};
        border: none;
    }}
    """


def _qss_main(t: ThemeTokens) -> str:
    c = t.color
    return f"""
    QMainWindow, QDialog {{
        background-color: {c["app_bg"]};
    }}
    QMainWindow::separator {{
        background-color: {c["border"]};
        width: 1px;
        height: 1px;
    }}
    QStatusBar {{
        background-color: {c["global_status_bar"]};
        border-top: 1px solid {c["border"]};
        color: {c["text_secondary"]};
        font-size: {_pt(int(t.typography["font_size_small"]))};
    }}
    QStatusBar::item {{
        border: none;
    }}
    """


# ---------------------------------------------------------------------------
# Text / labels
# ---------------------------------------------------------------------------


def _qss_labels(t: ThemeTokens) -> str:
    c = t.color
    ty = t.typography
    return f"""
    QLabel {{
        color: {c["text"]};
        background-color: transparent;
    }}
    QLabel[role="h1"] {{
        font-size: {_pt(int(ty["font_size_h1"]))};
        color: {c["text"]};
    }}
    QLabel[role="h2"] {{
        font-size: {_pt(int(ty["font_size_h2"]))};
        color: {c["text"]};
    }}
    QLabel[role="h3"] {{
        font-size: {_pt(int(ty["font_size_h3"]))};
        color: {c["text"]};
    }}
    QLabel[role="text_muted"] {{
        color: {c["text_secondary"]};
        font-size: {_pt(int(ty["font_size_small"]))};
    }}
    """


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------


def _qss_push_button(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_xs = t.sp(4)
    sp_md = t.sp(16)
    return f"""
    QPushButton {{
        background-color: {c["app_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: {_px(r_sm)};
        padding: {_px(sp_xs)} {_px(sp_md)};
        min-width: 80px;
    }}
    QPushButton:hover {{
        border-color: {c["border_focus"]};
        color: {c["text"]};
    }}
    QPushButton:pressed {{
        background-color: {c["interactive_ghost"]};
        border-color: {c["border_focus"]};
    }}
    QPushButton:focus {{
        border-color: {c["border_focus"]};
        outline: none;
    }}
    QPushButton:disabled {{
        background-color: {c["interactive_disabled"]};
        color: {c["text_disabled"]};
        border-color: {c["border"]};
    }}

    /* Primary — filled accent background */
    QPushButton[role="primary"] {{
        background-color: {c["interactive"]};
        color: {c["interactive_text"]};
        border: 1px solid {c["interactive"]};
    }}
    QPushButton[role="primary"]:hover {{
        background-color: {c["interactive_hover"]};
        border-color: {c["interactive_hover"]};
    }}
    QPushButton[role="primary"]:pressed {{
        background-color: {c["interactive_active"]};
        border-color: {c["interactive_active"]};
    }}
    QPushButton[role="primary"]:disabled {{
        background-color: {c["interactive_disabled"]};
        color: {c["text_disabled"]};
        border-color: {c["border"]};
    }}

    /* Secondary — transparent background, accent border and text */
    QPushButton[role="secondary"] {{
        background-color: transparent;
        color: {c["interactive"]};
        border: 1px solid {c["interactive"]};
    }}
    QPushButton[role="secondary"]:hover {{
        background-color: transparent;
        color: {c["interactive_hover"]};
        border-color: {c["interactive_hover"]};
    }}
    QPushButton[role="secondary"]:pressed {{
        background-color: {c["interactive_ghost"]};
        color: {c["interactive_active"]};
        border-color: {c["interactive_active"]};
    }}
    QPushButton[role="secondary"]:disabled {{
        background-color: transparent;
        color: {c["text_disabled"]};
        border-color: {c["border"]};
    }}

    /* Borderless — no background or border, accent text only */
    QPushButton[role="borderless"] {{
        background-color: transparent;
        color: {c["interactive"]};
        border: 1px solid transparent;
        min-width: 0;
    }}
    QPushButton[role="borderless"]:hover {{
        background-color: transparent;
        color: {c["interactive_hover"]};
        border-color: transparent;
    }}
    QPushButton[role="borderless"]:pressed {{
        background-color: {c["interactive_ghost"]};
        color: {c["interactive_active"]};
    }}
    QPushButton[role="borderless"]:disabled {{
        background-color: transparent;
        color: {c["text_disabled"]};
        border-color: transparent;
    }}
    """


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def _qss_line_edit(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_xs = t.sp(4)
    sp_sm = t.sp(8)
    return f"""
    QLineEdit {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["input_border"]};
        border-radius: {_px(r_sm)};
        padding: {_px(sp_xs)} {_px(sp_sm)};
    }}
    QLineEdit:focus {{
        border-color: {c["border_focus"]};
    }}
    QLineEdit:disabled {{
        background-color: {c["app_bg"]};
        color: {c["text_disabled"]};
        border-color: {c["border"]};
    }}
    QLineEdit[placeholderText] {{
        color: {c["input_placeholder"]};
    }}
    """


def _qss_text_edit(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_xs = t.sp(4)
    return f"""
    QTextEdit, QPlainTextEdit {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["input_border"]};
        border-radius: {_px(r_sm)};
        padding: {_px(sp_xs)};
    }}
    QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {c["border_focus"]};
    }}
    """


def _qss_combo_box(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_xs = t.sp(4)
    sp_sm = t.sp(8)
    sp_lg = t.sp(24)
    return f"""
    QComboBox {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["input_border"]};
        border-radius: {_px(r_sm)};
        padding: {_px(sp_xs)} {_px(sp_sm)};
        min-width: 120px;
    }}
    QComboBox:focus {{
        border-color: {c["border_focus"]};
    }}
    QComboBox:disabled {{
        background-color: {c["app_bg"]};
        color: {c["text_disabled"]};
        border-color: {c["border"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: {_px(sp_lg)};
    }}
    QComboBox::down-arrow {{
        image: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c["panel_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        selection-background-color: {c["selection_bg"]};
        selection-color: {c["selection_text"]};
    }}
    """


def _qss_spin_box(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_xs = t.sp(4)
    sp_sm = t.sp(8)
    return f"""
    QSpinBox, QDoubleSpinBox {{
        background-color: {c["input_bg"]};
        color: {c["text"]};
        border: 1px solid {c["input_border"]};
        border-radius: {_px(r_sm)};
        padding: {_px(sp_xs)} {_px(sp_sm)};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {c["border_focus"]};
    }}
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        background-color: {c["panel_bg"]};
        border: none;
        width: 16px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {c["interactive_ghost"]};
    }}
    """


def _qss_check_radio(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_sm = t.sp(8)
    sp_md = t.sp(16)
    return f"""
    QCheckBox, QRadioButton {{
        color: {c["text"]};
        spacing: {_px(sp_sm)};
        background-color: transparent;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: {_px(sp_md)};
        height: {_px(sp_md)};
        border: 1px solid {c["border"]};
        border-radius: {_px(r_sm)};
        background-color: {c["input_bg"]};
    }}
    QRadioButton::indicator {{
        border-radius: 8px;
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {c["interactive"]};
        border-color: {c["interactive"]};
    }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {c["interactive"]};
    }}
    QCheckBox:disabled, QRadioButton:disabled {{
        color: {c["text_disabled"]};
    }}
    """


# ---------------------------------------------------------------------------
# Tabs / groups / scroll
# ---------------------------------------------------------------------------


def _qss_tabs(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_xs = t.sp(4)
    sp_sm = t.sp(8)
    sp_md = t.sp(16)
    return f"""
    QTabWidget::pane {{
        background-color: {c["panel_bg"]};
        border: 1px solid {c["border"]};
        border-top: none;
        margin-top: {_px(sp_sm)};
    }}
    QTabBar::tab {{
        background-color: {c["app_bg"]};
        color: {c["text_secondary"]};
        padding: {_px(sp_xs)} {_px(sp_md)};
        border: 1px solid {c["border"]};
        border-bottom: none;
        border-top-left-radius: {_px(r_sm)};
        border-top-right-radius: {_px(r_sm)};
    }}
    QTabBar::tab:selected {{
        background-color: {c["panel_bg"]};
        color: {c["text"]};
        border-bottom: 2px solid {c["interactive"]};
    }}
    QTabBar::tab:hover:!selected {{
        color: {c["text"]};
        background-color: {c["panel_bg"]};
    }}
    """


def _qss_group_box(t: ThemeTokens) -> str:
    c = t.color
    r_md = int(t.shape["radius_md"])
    sp_xs = t.sp(4)
    sp_sm = t.sp(8)
    sp_md = t.sp(16)
    return f"""
    QGroupBox {{
        background-color: {c["panel_bg"]};
        border: 1px solid {c["border"]};
        border-radius: {_px(r_md)};
        margin-top: {_px(sp_md)};
        padding: {_px(sp_sm)};
    }}
    QGroupBox::title {{
        color: {c["text_secondary"]};
        subcontrol-origin: margin;
        left: {_px(sp_sm)};
        padding: 0 {_px(sp_xs)};
        font-size: {_pt(int(t.typography["font_size_small"]))};
    }}
    """


def _qss_scroll_area(t: ThemeTokens) -> str:
    return """
    QScrollArea {
        border: none;
        background: transparent;
    }
    """


def _qss_scrollbar(t: ThemeTokens) -> str:
    c = t.color
    return f"""
    QScrollBar:vertical {{
        background-color: {c["scrollbar_track"]};
        width: 10px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background-color: {c["scrollbar_handle"]};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {c["scrollbar_handle_hover"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background-color: {c["scrollbar_track"]};
        height: 10px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {c["scrollbar_handle"]};
        border-radius: 5px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {c["scrollbar_handle_hover"]};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    """


def _qss_tooltip(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_xs = t.sp(4)
    sp_sm = t.sp(8)
    return f"""
    QToolTip {{
        background-color: {c["tooltip_bg"]};
        color: {c["tooltip_text"]};
        border: 1px solid {c["tooltip_border"]};
        border-radius: {_px(r_sm)};
        padding: {_px(sp_xs)} {_px(sp_sm)};
        font-size: {_pt(int(t.typography["font_size_small"]))};
    }}
    """


def _qss_splitter(t: ThemeTokens) -> str:
    c = t.color
    return f"""
    QSplitter::handle {{
        background-color: {c["border"]};
    }}
    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    QSplitter::handle:vertical {{
        height: 1px;
    }}
    QSplitter::handle:hover {{
        background-color: {c["interactive"]};
    }}
    """


# ---------------------------------------------------------------------------
# GAVEL role-based components
# ---------------------------------------------------------------------------


def _qss_nav_drawer(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_sm = t.sp(8)
    return f"""
    QFrame[role="nav_drawer"] {{
        background-color: {c["global_status_bar"]};
        border-right: 1px solid {c["border"]};
    }}
    QToolButton[role="nav_toggle"] {{
        background: transparent;
        border: none;
        padding: {_px(sp_sm)};
        color: {c["text"]};
    }}
    QToolButton[role="nav_toggle"]:hover {{
        color: {c["interactive"]};
    }}
    QToolButton[role="nav_item"] {{
        background: transparent;
        border: 1px solid transparent;
        border-left: 3px solid transparent;
        border-radius: {_px(r_sm)};
        padding: {_px(sp_sm)};
        text-align: left;
        color: {c["text_secondary"]};
    }}
    QToolButton[role="nav_item"]:hover {{
        color: {c["text"]};
        background-color: {c["panel_bg"]};
    }}
    QToolButton[role="nav_item"]:checked {{
        background-color: {c["panel_bg"]};
        border-left: 3px solid {c["interactive"]};
        color: {c["text"]};
    }}
    """


def _qss_surface_card(t: ThemeTokens) -> str:
    c = t.color
    r_md = int(t.shape["radius_md"])
    return f"""
    QFrame[role="card_header"] {{
        background-color: {c["surface"]};
        border: none;
        border-bottom: 1px solid {c["border"]};
        border-top-left-radius: {_px(r_md)};
        border-top-right-radius: {_px(r_md)};
    }}
    QFrame[role="card_header"] QWidget,
    QFrame[role="card_header"] QLabel {{
        background-color: transparent;
    }}
    QFrame[role="app_bg"] {{
        background-color: {c["app_bg"]};
        border: 1px solid {c["border"]};
        border-radius: {_px(r_md)};
    }}
    QFrame[role="app_bg"] QWidget,
    QFrame[role="app_bg"] QLabel {{
        background-color: transparent;
    }}
    QFrame[role="panel_bg"] {{
        background-color: {c["panel_bg"]};
        border: 1px solid {c["border"]};
        border-radius: {_px(r_md)};
    }}
    QFrame[role="panel_bg"] QWidget,
    QFrame[role="panel_bg"] QLabel {{
        background-color: transparent;
    }}
    QFrame[role="surface"] {{
        background-color: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: {_px(r_md)};
    }}
    QFrame[role="surface"] QWidget,
    QFrame[role="surface"] QLabel {{
        background-color: transparent;
    }}

    /* Re-assert card_header and input widget backgrounds after the broad
       QWidget transparency overrides above. These selectors have specificity
       (0,1,2), matching the transparency rules, but appear later so they win. */
    QFrame[role="app_bg"] QFrame[role="card_header"],
    QFrame[role="panel_bg"] QFrame[role="card_header"],
    QFrame[role="surface"] QFrame[role="card_header"] {{
        background-color: {c["surface"]};
        border-bottom: 1px solid {c["border"]};
    }}
    QFrame[role="app_bg"] QFrame[role="surface"],
    QFrame[role="panel_bg"] QFrame[role="surface"] {{
        background-color: {c["surface"]};
        border: 1px solid {c["border"]};
    }}
    QFrame[role="app_bg"] QLineEdit,
    QFrame[role="panel_bg"] QLineEdit,
    QFrame[role="surface"] QLineEdit,
    QFrame[role="card_header"] QLineEdit {{
        background-color: {c["input_bg"]};
    }}
    QFrame[role="app_bg"] QComboBox,
    QFrame[role="panel_bg"] QComboBox,
    QFrame[role="surface"] QComboBox,
    QFrame[role="card_header"] QComboBox {{
        background-color: {c["input_bg"]};
    }}
    QFrame[role="app_bg"] QComboBox QAbstractItemView,
    QFrame[role="panel_bg"] QComboBox QAbstractItemView,
    QFrame[role="surface"] QComboBox QAbstractItemView,
    QFrame[role="card_header"] QComboBox QAbstractItemView {{
        background-color: {c["panel_bg"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        selection-background-color: {c["selection_bg"]};
        selection-color: {c["selection_text"]};
    }}
    QFrame[role="app_bg"] QTextEdit,
    QFrame[role="panel_bg"] QTextEdit,
    QFrame[role="surface"] QTextEdit,
    QFrame[role="card_header"] QTextEdit {{
        background-color: {c["input_bg"]};
    }}
    QFrame[role="app_bg"] QSpinBox,
    QFrame[role="panel_bg"] QSpinBox,
    QFrame[role="surface"] QSpinBox,
    QFrame[role="card_header"] QSpinBox {{
        background-color: {c["input_bg"]};
    }}
    QFrame[role="app_bg"] QPushButton,
    QFrame[role="panel_bg"] QPushButton,
    QFrame[role="surface"] QPushButton,
    QFrame[role="card_header"] QPushButton {{
        background-color: {c["app_bg"]};
    }}
    QFrame[role="app_bg"] QPushButton[role="primary"],
    QFrame[role="panel_bg"] QPushButton[role="primary"],
    QFrame[role="surface"] QPushButton[role="primary"],
    QFrame[role="card_header"] QPushButton[role="primary"] {{
        background-color: {c["interactive"]};
    }}
    QFrame[role="app_bg"] QPushButton[role="secondary"],
    QFrame[role="panel_bg"] QPushButton[role="secondary"],
    QFrame[role="surface"] QPushButton[role="secondary"],
    QFrame[role="card_header"] QPushButton[role="secondary"],
    QFrame[role="app_bg"] QPushButton[role="borderless"],
    QFrame[role="panel_bg"] QPushButton[role="borderless"],
    QFrame[role="surface"] QPushButton[role="borderless"],
    QFrame[role="card_header"] QPushButton[role="borderless"] {{
        background-color: transparent;
    }}
    QFrame[role="app_bg"] QPushButton:disabled,
    QFrame[role="panel_bg"] QPushButton:disabled,
    QFrame[role="surface"] QPushButton:disabled,
    QFrame[role="card_header"] QPushButton:disabled {{
        background-color: {c["interactive_disabled"]};
        color: {c["text_disabled"]};
        border-color: {c["border"]};
    }}
    QFrame[role="app_bg"] QPushButton[role="secondary"]:disabled,
    QFrame[role="panel_bg"] QPushButton[role="secondary"]:disabled,
    QFrame[role="surface"] QPushButton[role="secondary"]:disabled,
    QFrame[role="card_header"] QPushButton[role="secondary"]:disabled,
    QFrame[role="app_bg"] QPushButton[role="borderless"]:disabled,
    QFrame[role="panel_bg"] QPushButton[role="borderless"]:disabled,
    QFrame[role="surface"] QPushButton[role="borderless"]:disabled,
    QFrame[role="card_header"] QPushButton[role="borderless"]:disabled {{
        background-color: transparent;
    }}
    """


def _qss_status_pill(t: ThemeTokens) -> str:
    c = t.color
    ty = t.typography
    return f"""
    QWidget[role="status_pill"] {{
        background: transparent;
    }}
    QLabel[role="status_dot"] {{
        font-size: {_pt(int(ty["font_size_base"]))};
        background: transparent;
    }}
    QLabel[role="status_text"] {{
        color: {c["text_secondary"]};
        background: transparent;
    }}
    """


def _qss_status_banner(t: ThemeTokens) -> str:
    c = t.color
    r_sm = int(t.shape["radius_sm"])
    sp_sm = t.sp(8)
    sp_md = t.sp(16)
    return f"""
    QLabel[role="warning"] {{
        background-color: {c["panel_bg"]};
        color: {c["status_critical"]};
        border: 1px solid {c["status_critical"]};
        border-radius: {_px(r_sm)};
        padding: {_px(sp_sm)} {_px(sp_md)};
    }}
    """
