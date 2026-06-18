"""Central design-system stylesheet.

One place that turns a theme's chrome colours into a cohesive Qt stylesheet for
the whole window: consistent radius, spacing, hover/pressed states, scrollbars,
inputs, menus, tabs and tooltips. Keeping it here means the visual language is
uniform instead of scattered inline strings.
"""

# design tokens (constant across themes)
RADIUS = 7
RADIUS_SM = 5
PAD = 7


def app_qss(c: dict, scale: float = 1.0) -> str:
    """Build the application-wide stylesheet from a chrome palette `c`.
    `scale` multiplies font sizes so Ctrl+/Ctrl- zoom the whole UI."""
    def fs(px):
        return f"{round(px * scale)}px"
    base = fs(13)
    small = fs(12)
    return f"""
/* ---- base surfaces ---- */
QMainWindow, QStackedWidget {{ background:{c['win']}; }}
QWidget {{ color:{c['text']}; font-size:{base}; }}
QToolTip {{
    background:{c['tooltip_bg']}; color:{c['tooltip_fg']};
    border:1px solid {c['border']}; border-radius:{RADIUS_SM}px;
    padding:5px 8px; font-size:{small};
}}

/* ---- menu bar ---- */
QMenuBar {{ background:{c['header']}; color:{c['text']}; padding:3px 4px; }}
QMenuBar::item {{ background:transparent; padding:5px 11px; border-radius:{RADIUS_SM}px; }}
QMenuBar::item:selected {{ background:{c['hover']}; color:{c['accent']}; }}
QMenuBar::item:pressed {{ background:{c['accent']}; color:{c['on_accent']}; }}
QMenu {{
    background:{c['panel']}; color:{c['text']};
    border:1px solid {c['border']}; border-radius:{RADIUS}px; padding:5px;
}}
QMenu::item {{ padding:6px 22px 6px 16px; border-radius:{RADIUS_SM}px; }}
QMenu::item:selected {{ background:{c['accent']}; color:{c['on_accent']}; }}
QMenu::item:disabled {{ color:{c['muted']}; }}
QMenu::separator {{ height:1px; background:{c['border']}; margin:5px 8px; }}

/* ---- toolbar ---- */
QToolBar {{
    background:{c['toolbar']}; border:none; padding:5px 6px; spacing:3px;
    border-bottom:1px solid {c['border']};
}}
QToolButton {{ padding:6px; border-radius:{RADIUS_SM}px; color:{c['text']}; }}
QToolButton:hover {{ background:{c['hover']}; }}
QToolButton:pressed {{ background:{c['accent']}; }}
QToolBar::separator {{ width:1px; background:{c['border']}; margin:4px 6px; }}

/* ---- status bar ---- */
QStatusBar {{ background:{c['header']}; color:{c['muted']}; border-top:1px solid {c['border']}; }}
QStatusBar::item {{ border:none; }}

/* ---- tabs ---- */
QTabWidget::pane {{ border:none; background:{c['win']}; }}
QTabBar {{ background:{c['tab_strip']}; }}
QTabBar::tab {{
    background:{c['tab_bg']}; color:{c['muted']};
    padding:7px 16px; margin-right:2px;
    border-top-left-radius:{RADIUS_SM}px; border-top-right-radius:{RADIUS_SM}px;
    border:1px solid transparent; border-bottom:2px solid transparent;
}}
QTabBar::tab:hover {{ color:{c['text']}; background:{c['hover']}; }}
QTabBar::tab:selected {{
    background:{c['tab_sel']}; color:{c['text']};
    border-bottom:2px solid {c['accent']};
}}

/* ---- splitter handles ---- */
QSplitter::handle {{ background:{c['border']}; }}
QSplitter::handle:horizontal {{ width:1px; }}
QSplitter::handle:vertical {{ height:1px; }}
QSplitter::handle:hover {{ background:{c['accent']}; }}

/* ---- scrollbars (slim, modern) ---- */
QScrollBar:vertical {{ background:transparent; width:11px; margin:2px; }}
QScrollBar::handle:vertical {{
    background:{c['scroll']}; border-radius:5px; min-height:28px;
}}
QScrollBar::handle:vertical:hover {{ background:{c['scroll_hi']}; }}
QScrollBar:horizontal {{ background:transparent; height:11px; margin:2px; }}
QScrollBar::handle:horizontal {{
    background:{c['scroll']}; border-radius:5px; min-width:28px;
}}
QScrollBar::handle:horizontal:hover {{ background:{c['scroll_hi']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; width:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}

/* ---- inputs / dialogs ---- */
QDialog {{ background:{c['win']}; }}
QLineEdit, QComboBox, QSpinBox, QFontComboBox, QPlainTextEdit {{
    background:{c['input']}; color:{c['text']};
    border:1px solid {c['border']}; border-radius:{RADIUS_SM}px; padding:6px 9px;
    selection-background-color:{c['accent']}; selection-color:{c['on_accent']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QFontComboBox:focus {{
    border:1px solid {c['accent']};
}}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{
    background:{c['panel']}; color:{c['text']};
    border:1px solid {c['border']}; border-radius:{RADIUS_SM}px;
    selection-background-color:{c['accent']}; selection-color:{c['on_accent']};
    outline:none;
}}

/* ---- push buttons ---- */
QPushButton {{
    background:{c['accent']}; color:{c['on_accent']};
    border:none; border-radius:{RADIUS}px; padding:8px 18px; font-weight:600;
}}
QPushButton:hover {{ background:{c['accent_hi']}; }}
QPushButton:pressed {{ background:{c['accent_lo']}; }}
QPushButton:disabled {{ background:{c['muted']}; color:{c['panel']}; }}

/* ---- lists / explorer ---- */
QListWidget {{
    background:{c['panel']}; color:{c['text']}; border:none; padding:5px;
    outline:none;
}}
QListWidget::item {{ padding:6px 9px; border-radius:{RADIUS_SM}px; }}
QListWidget::item:hover {{ background:{c['hover']}; }}
QListWidget::item:selected {{ background:{c['accent']}; color:{c['on_accent']}; }}

/* ---- dock ---- */
QDockWidget {{ color:{c['accent']}; titlebar-close-icon:none; }}
QDockWidget::title {{
    background:{c['header']}; padding:6px; border-bottom:1px solid {c['border']};
}}

/* ---- message boxes ---- */
QMessageBox {{ background:{c['win']}; }}
QMessageBox QLabel {{ color:{c['text']}; }}
"""
