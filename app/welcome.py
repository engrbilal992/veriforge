"""Welcome / start page.

Shown when no project is open. Big New / Open buttons plus a recent-projects
list. Emits signals; the main window does the work and swaps this view out.
"""

import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget, QListWidgetItem,
                               QSizePolicy)
from PySide6.QtCore import Signal, Qt


class WelcomePage(QWidget):
    newProject = Signal()
    openProject = Signal()
    openRecent = Signal(str)

    def __init__(self, chrome: dict, recents: list[str], parent=None):
        super().__init__(parent)
        c = chrome
        self.setStyleSheet(f"WelcomePage{{background:{c['win']};}}")

        title = QLabel("VeriForge")
        title.setStyleSheet(f"color:{c['accent']};font-size:34px;font-weight:bold;")
        subtitle = QLabel("Verilog simulation, your way.")
        subtitle.setStyleSheet(f"color:{c['text']};font-size:14px;")

        new_btn = QPushButton("  New Project")
        open_btn = QPushButton("  Open Project")
        for b in (new_btn, open_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(46)
            b.setStyleSheet(
                f"QPushButton{{background:{c['accent']};color:{c.get('on_accent','#fff')};"
                f"border:none;border-radius:9px;font-size:15px;font-weight:600;"
                f"padding:0 24px;}}"
                f"QPushButton:hover{{background:{c.get('accent_hi', c['panel_fg'])};}}"
                f"QPushButton:pressed{{background:{c.get('accent_lo', c['accent'])};}}")
        new_btn.clicked.connect(self.newProject)
        open_btn.clicked.connect(self.openProject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(new_btn)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()

        recent_lbl = QLabel("Recent projects")
        recent_lbl.setStyleSheet(f"color:{c['panel_fg']};font-weight:bold;"
                                 "font-size:13px;margin-top:14px;")
        self.recent = QListWidget()
        self.recent.setStyleSheet(
            f"QListWidget{{background:{c['panel']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:8px;padding:6px;}}"
            f"QListWidget::item{{padding:6px 8px;border-radius:5px;}}"
            f"QListWidget::item:hover{{background:{c['hover']};}}")
        for path in recents:
            if os.path.isdir(path):
                it = QListWidgetItem(f"{os.path.basename(path)}      {path}")
                it.setData(Qt.UserRole, path)
                self.recent.addItem(it)
        self.recent.itemActivated.connect(
            lambda it: self.openRecent.emit(it.data(Qt.UserRole)))
        self.recent.itemClicked.connect(
            lambda it: self.openRecent.emit(it.data(Qt.UserRole)))
        if self.recent.count() == 0:
            self.recent.addItem("No recent projects yet.")
            self.recent.setEnabled(False)

        card = QWidget()
        card.setMaximumWidth(620)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        cl = QVBoxLayout(card)
        cl.setSpacing(10)
        cl.addWidget(title)
        cl.addWidget(subtitle)
        cl.addSpacing(18)
        cl.addLayout(btn_row)
        cl.addWidget(recent_lbl)
        cl.addWidget(self.recent)

        outer = QHBoxLayout(self)
        outer.addStretch()
        col = QVBoxLayout()
        col.addStretch()
        col.addWidget(card)
        col.addStretch()
        outer.addLayout(col)
        outer.addStretch()
