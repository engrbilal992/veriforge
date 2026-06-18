"""A panel with a title bar.

Each panel header carries small buttons: minimize (collapse body), maximize
(emit a request the main window handles), help (?), and close (hide). The panel
emits signals rather than acting globally, so the main window stays in control
of layout.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QToolButton, QSizePolicy)
from PySide6.QtCore import Signal, Qt, QSize


class Panel(QWidget):
    maximizeRequested = Signal(object)   # self
    closeRequested = Signal(object)      # self
    helpRequested = Signal(str)          # panel key

    def __init__(self, title: str, body: QWidget, key: str = "",
                 help_text: str = "", parent=None):
        super().__init__(parent)
        self.key = key
        self.help_text = help_text
        self._collapsed = False
        self._chrome = None

        self._title = QLabel(title)
        self._title.setObjectName("panelTitle")

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 3, 4, 3)
        bar.setSpacing(2)
        bar.addWidget(self._title)
        bar.addStretch()

        self._btn_min = self._mk("\u2013", "Minimize", self._toggle_collapse)
        self._btn_max = self._mk("\u25a1", "Maximize", lambda: self.maximizeRequested.emit(self))
        self._btn_help = self._mk("?", "Help", lambda: self.helpRequested.emit(self.key))
        self._btn_close = self._mk("\u2715", "Close", lambda: self.closeRequested.emit(self))
        for b in (self._btn_min, self._btn_max, self._btn_help, self._btn_close):
            bar.addWidget(b)

        self._header = QWidget()
        self._header.setObjectName("panelHeader")
        self._header.setLayout(bar)

        self.body = body
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header)
        lay.addWidget(self.body)

    def _mk(self, glyph, tip, slot) -> QToolButton:
        b = QToolButton()
        b.setText(glyph)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setAutoRaise(True)
        b.setFixedSize(QSize(26, 22))
        b.clicked.connect(slot)
        return b

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.body.setVisible(not self._collapsed)
        self._btn_min.setText("\u25b8" if self._collapsed else "\u2013")
        self._btn_min.setToolTip("Restore" if self._collapsed else "Minimize")

    def set_title(self, text: str):
        self._title.setText(text)

    def apply_chrome(self, c: dict):
        self._chrome = c
        self._header.setStyleSheet(
            f"#panelHeader{{background:{c['header']};border-bottom:1px solid {c['border']};}}"
            f"#panelTitle{{color:{c['panel_fg']};font-weight:bold;padding:2px 4px;}}")
        btn = (f"QToolButton{{color:{c['muted']};border:none;border-radius:5px;"
               f"font-size:13px;font-weight:bold;}}"
               f"QToolButton:hover{{background:{c['hover']};color:{c['text']};}}")
        for b in (self._btn_min, self._btn_max, self._btn_help):
            b.setStyleSheet(btn)
        self._btn_close.setStyleSheet(
            btn + "QToolButton:hover{background:#e53935;color:#ffffff;}")
