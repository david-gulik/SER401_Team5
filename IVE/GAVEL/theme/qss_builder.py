from __future__ import annotations

from GAVEL.theme.tokens import ThemeTokens


def build_app_qss(t: ThemeTokens) -> str:
    c = t.color
    bw = int(t.shape["border_width"])
    r_sm = int(t.shape["radius_sm"])
    r_md = int(t.shape["radius_md"])

    sp4 = t.sp(4)
    sp8 = t.sp(8)
    sp12 = t.sp(12)

    ff = t.typography["font_family"]
    fs = int(t.typography["font_size_base"])
    h2 = int(t.typography["font_size_h2"])

    return f"""
    QWidget {{
        background: {c["bg"]};
        color: {c["text"]};
        font-family: "{ff}";
        font-size: {fs}pt;
    }}

    QLabel[role="h2"] {{
        font-size: {h2}pt;
        color: {c["text"]};
    }}

    QTabWidget::pane {{
        border: {bw}px solid {c["border"]};
        background: {c["surface"]};
        border-radius: {r_md}px;
        margin-top: {sp8}px;
    }}

    QTabBar::tab {{
        background: {c["surface_alt"]};
        border: {bw}px solid {c["border"]};
        border-bottom: none;
        padding: {sp8}px {sp12}px;
        margin-right: {sp4}px;
        border-top-left-radius: {r_sm}px;
        border-top-right-radius: {r_sm}px;
        color: {c["text_muted"]};
    }}

    QTabBar::tab:selected {{
        background: {c["surface"]};
        color: {c["text"]};
    }}

    QTabBar::tab:hover {{
        color: {c["text"]};
        border-color: {c["focus"]};
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {c["surface_alt"]};
        border: {bw}px solid {c["border"]};
        border-radius: {r_sm}px;
        padding: {sp8}px;
        selection-background-color: {c["selection"]};
        selection-color: {c["text"]};
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {c["focus"]};
    }}

    QPushButton {{
        background: {c["surface_alt"]};
        border: {bw}px solid {c["border"]};
        border-radius: {r_sm}px;
        padding: {sp8}px {sp12}px;
    }}

    QPushButton:hover {{
        border-color: {c["focus"]};
    }}

    QPushButton:disabled {{
        color: {c["text_muted"]};
        border-color: {c["border"]};
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {c["border"]};
        border-radius: 6px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c["focus"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Navigation drawer */
    QFrame[role="nav_drawer"] {{
        background: {c["surface_alt"]};
        border-right: {bw}px solid {c["border"]};
    }}

    QToolButton[role="nav_toggle"] {{
        background: transparent;
        border: none;
        padding: {sp8}px;
        color: {c["text"]};
    }}

    QToolButton[role="nav_item"] {{
        background: transparent;
        border: {bw}px solid transparent;
        border-radius: {r_sm}px;
        padding: {sp8}px;
        text-align: left;
        color: {c["text_muted"]};
    }}

    QToolButton[role="nav_item"]:hover {{
        border-color: {c["focus"]};
        color: {c["text"]};
    }}

    QToolButton[role="nav_item"]:checked {{
        background: {c["selection"]};
        border-color: {c["focus"]};
        color: {c["text"]};
    }}


    /* Status pill */
    QWidget[role="status_pill"] {{
        background: transparent;
    }}

    QLabel[role="status_dot"] {{
        font-size: {fs}pt;
    }}

    QLabel[role="status_text"] {{
        color: {c["text_muted"]};
    }}

    """

