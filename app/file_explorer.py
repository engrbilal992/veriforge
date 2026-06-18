"""Grouped file explorer.

A tree with sections — Design, Simulation, YAML, Headers — populated by
scanning file content (a testbench is any file with an `initial` block). The
file that declares the current top module is shown in bold. The widget never
touches the filesystem; it only emits the requested action + path.
"""

import os
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu
from PySide6.QtGui import QFont, QBrush, QColor
from PySide6.QtCore import Signal, Qt

from . import vscan

_GROUPS = [
    ("design", "Design"),
    ("sim", "Simulation"),
    ("yaml", "YAML"),
    ("header", "Headers"),
]


class FileExplorer(QTreeWidget):
    fileActivated = Signal(str)
    renameRequested = Signal(str)
    deleteRequested = Signal(str)
    newFileRequested = Signal()
    setTopRequested = Signal(str)     # module name to make top

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.setExpandsOnDoubleClick(False)
        self._root = ""
        self._top_file = None
        self._accent = "#2563eb"
        self.itemDoubleClicked.connect(self._activate)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def apply_chrome(self, c: dict):
        self._accent = c["accent"]
        self.setStyleSheet(
            f"QTreeWidget{{background:{c['panel']};color:{c['text']};border:none;"
            f"padding:4px;outline:none;}}"
            f"QTreeWidget::item{{padding:4px 6px;border-radius:5px;}}"
            f"QTreeWidget::item:hover{{background:{c['hover']};}}"
            f"QTreeWidget::item:selected{{background:{c['accent']};color:{c['on_accent']};}}"
            f"QMenu{{background:{c['panel']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:6px;}}"
            f"QMenu::item:selected{{background:{c['accent']};color:{c['on_accent']};}}")
        self._muted = c["muted"]
        self.refresh_styles()

    def set_files(self, root: str, files: list[str], top_file: str | None = None):
        self._root = root
        self._top_file = top_file
        self.clear()
        buckets = {key: [] for key, _ in _GROUPS}
        # Grouping is by content: a testbench (has an `initial` block) -> Simulation,
        # plain RTL -> Design. The chosen top module is only highlighted (bold + star),
        # it never moves a file between groups.
        for path in files:
            buckets[vscan.classify_file(path)].append(path)

        for key, label in _GROUPS:
            paths = buckets[key]
            if not paths:
                continue
            header = QTreeWidgetItem([f"{label}  ({len(paths)})"])
            header.setFlags(Qt.ItemIsEnabled)
            f = header.font(0); f.setBold(True)
            header.setFont(0, f)
            header.setForeground(0, QBrush(QColor(getattr(self, "_muted", "#888"))))
            self.addTopLevelItem(header)
            header.setExpanded(True)
            for path in sorted(paths, key=lambda p: os.path.basename(p).lower()):
                child = QTreeWidgetItem([os.path.relpath(path, root)])
                child.setData(0, Qt.UserRole, path)
                header.addChild(child)
        self.refresh_styles()

    def set_top_file(self, top_file: str | None):
        self._top_file = top_file
        self.refresh_styles()

    def refresh_styles(self):
        """Bold the file that holds the top module."""
        it = QTreeWidgetItemIteratorAll(self)
        for item in it:
            path = item.data(0, Qt.UserRole)
            if path is None:
                continue
            f = item.font(0)
            is_top = (self._top_file is not None and path == self._top_file)
            f.setBold(is_top)
            item.setFont(0, f)
            if is_top:
                item.setForeground(0, QBrush(QColor(self._accent)))
                item.setText(0, os.path.relpath(path, self._root) + "   \u2605")
            else:
                item.setData(0, Qt.ForegroundRole, None)
                item.setText(0, os.path.relpath(path, self._root))

    def _activate(self, item, _col=0):
        path = item.data(0, Qt.UserRole)
        if path:
            self.fileActivated.emit(path)

    def _menu(self, pos):
        item = self.itemAt(pos)
        path = item.data(0, Qt.UserRole) if item else None
        menu = QMenu(self)
        a_open = a_ren = a_del = a_top = None
        if path:
            a_open = menu.addAction("Open")
            if path.lower().endswith((".v", ".sv")):
                mods = vscan.scan_file(path)["modules"]
                if mods:
                    a_top = menu.addAction(f"Set top module \u2192 {mods[0]}")
            a_ren = menu.addAction("Rename\u2026")
            a_del = menu.addAction("Delete")
            menu.addSeparator()
        a_new = menu.addAction("New File\u2026")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == a_new:
            self.newFileRequested.emit()
        elif chosen == a_open:
            self.fileActivated.emit(path)
        elif chosen == a_top:
            self.setTopRequested.emit(vscan.scan_file(path)["modules"][0])
        elif chosen == a_ren:
            self.renameRequested.emit(path)
        elif chosen == a_del:
            self.deleteRequested.emit(path)

    def keyPressEvent(self, event):
        item = self.currentItem()
        path = item.data(0, Qt.UserRole) if item else None
        if path and event.key() == Qt.Key_Delete:
            self.deleteRequested.emit(path)
        elif path and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.fileActivated.emit(path)
        else:
            super().keyPressEvent(event)


def QTreeWidgetItemIteratorAll(tree):
    """Yield every item (top-level headers and their children)."""
    out = []
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        out.append(top)
        for j in range(top.childCount()):
            out.append(top.child(j))
    return out
