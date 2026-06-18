"""Verilog code editor: line-number gutter + themeable syntax highlighting."""

from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PySide6.QtGui import (QColor, QPainter, QTextFormat, QFont,
                           QSyntaxHighlighter, QTextCharFormat)
from PySide6.QtCore import Qt, QRect, QSize, Signal
import re

from .theme import palette as theme_palette, DEFAULT
from .keymodes import KeyMode

_KEYWORDS = (
    r"\b(module|endmodule|input|output|inout|wire|reg|logic|assign|always|"
    r"always_ff|always_comb|always_latch|begin|end|if|else|case|endcase|"
    r"default|for|while|posedge|negedge|initial|parameter|localparam|"
    r"integer|genvar|generate|endgenerate|function|endfunction|task|endtask|"
    r"return|signed|unsigned|typedef|struct|enum|wait|repeat|forever)\b"
)


class VerilogHighlighter(QSyntaxHighlighter):
    def __init__(self, doc, pal):
        super().__init__(doc)
        self.set_palette(pal)

    def set_palette(self, pal):
        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Bold)
            f.setFontItalic(italic)
            return f

        # ordered: keyword first, string/comment last so they override
        self.rules = [
            (re.compile(_KEYWORDS), fmt(pal["keyword"], bold=True)),
            (re.compile(r"\$[A-Za-z_]\w*"), fmt(pal["system"])),
            (re.compile(r"`[A-Za-z_]\w*"), fmt(pal["directive"])),
            (re.compile(r"\b\d+'[bhdo][0-9a-fA-FxXzZ_]+"), fmt(pal["number"])),
            (re.compile(r"\b\d+\b"), fmt(pal["number"])),
            (re.compile(r'"[^"]*"'), fmt(pal["string"])),
            (re.compile(r"//[^\n]*"), fmt(pal["comment"], italic=True)),
        ]
        self.comment_fmt = fmt(pal["comment"], italic=True)
        self.rehighlight()

    def highlightBlock(self, text):
        for rx, f in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), f)
        # multi-line /* */ block comments
        self.setCurrentBlockState(0)
        start = 0 if self.previousBlockState() == 1 else text.find("/*")
        while start >= 0:
            end = text.find("*/", start)
            if end == -1:
                self.setCurrentBlockState(1)
                length = len(text) - start
            else:
                length = end - start + 2
            self.setFormat(start, length, self.comment_fmt)
            start = text.find("/*", start + length)


class _Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    fontZoomed = Signal(int)   # emitted with the new point size on Ctrl+wheel
    modeChanged = Signal(str)  # emitted with the key-mode status string
    requestSave = Signal(object)
    requestClose = Signal(object)

    def __init__(self, pal=None, family="monospace", size=11, parent=None):
        super().__init__(parent)
        self._pal = pal or theme_palette(DEFAULT)
        self._diags = []
        self.highlighter = VerilogHighlighter(self.document(), self._pal)
        self.gutter = _Gutter(self)
        self.keymode = KeyMode(self, on_command=self._run_command)

        self.blockCountChanged.connect(lambda _: self._update_gutter_width())
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self.apply_appearance(self._pal, family, size)

    # ---- appearance ----------------------------------------------------
    def apply_appearance(self, pal: dict, family: str, size: int):
        self._pal = pal
        self._pt = size
        f = QFont(family)
        f.setStyleHint(QFont.Monospace)
        f.setPointSize(size)
        self.setFont(f)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        # Font is set in the widget's OWN stylesheet too: the app-wide stylesheet
        # sets a px font-size on QWidget, and stylesheet rules override setFont(),
        # so without this the editor would ignore its chosen size.
        self.setStyleSheet(
            f"QPlainTextEdit{{background:{pal['bg']};color:{pal['fg']};"
            f"border:none;selection-background-color:{pal['selection']};"
            f"font-family:'{family}';font-size:{size}pt;}}")
        self.highlighter.set_palette(pal)
        self._update_gutter_width()
        self._highlight_current_line()
        self.gutter.update()

    def keyPressEvent(self, event):
        mods = event.modifiers()
        ctrlish = bool(mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))

        # Ctrl+/ toggles line comments on the selection (or current line)
        if (mods & Qt.ControlModifier) and event.key() == Qt.Key_Slash:
            self.toggle_comment()
            return

        # In nano/vim mode, give the keymode first crack (nano needs ^O/^X/^K/^U,
        # vim needs Esc/: etc.). If it consumes the key, we're done.
        if self.keymode.mode_name != "normal" and self.keymode.handle(event):
            return

        # Otherwise let app-level shortcut combos bubble to the window menu
        # (Ctrl+S, Ctrl+N, Ctrl+O...), except the standard editing combos that
        # the text widget itself should keep.
        if ctrlish and event.key() not in (Qt.Key_Z, Qt.Key_Y, Qt.Key_X,
                                           Qt.Key_C, Qt.Key_V, Qt.Key_A):
            event.ignore()
            return
        super().keyPressEvent(event)

    def toggle_comment(self):
        """Toggle `// ` line comments across the selected lines (or current line)."""
        cur = self.textCursor()
        start = cur.selectionStart()
        end = cur.selectionEnd()
        cur.setPosition(start)
        start_block = cur.blockNumber()
        cur.setPosition(end)
        end_block = cur.blockNumber()

        doc = self.document()
        # gather the lines
        lines = [doc.findBlockByNumber(b).text()
                 for b in range(start_block, end_block + 1)]
        non_empty = [ln for ln in lines if ln.strip()]
        # if every non-empty line is already commented -> uncomment, else comment
        all_commented = non_empty and all(ln.lstrip().startswith("//")
                                          for ln in non_empty)

        edit = self.textCursor()
        edit.beginEditBlock()
        for b in range(start_block, end_block + 1):
            block = doc.findBlockByNumber(b)
            text = block.text()
            if not text.strip():
                continue
            bc = self.textCursor()
            bc.setPosition(block.position())
            if all_commented:
                # remove the first "// " (or "//") and any single leading space kept
                stripped = text.lstrip()
                indent = text[:len(text) - len(stripped)]
                rest = stripped[2:]
                if rest.startswith(" "):
                    rest = rest[1:]
                bc.movePosition(bc.MoveOperation.Right, bc.MoveMode.KeepAnchor, len(text))
                bc.removeSelectedText()
                bc.insertText(indent + rest)
            else:
                bc.insertText("// ")
        edit.endEditBlock()

    def set_key_mode(self, name: str):
        self.keymode.set_mode(name)
        self.modeChanged.emit(self.keymode.status())

    def _run_command(self, cmd: str) -> bool:
        """Handle vim :w / :q / :wq style commands. Returns True if consumed."""
        cmd = cmd.lstrip(":")
        if cmd in ("w", "wq", "x"):
            self.requestSave.emit(self)
        if cmd in ("q", "wq", "x", "q!"):
            self.requestClose.emit(self)
        return True

    # ---- gutter --------------------------------------------------------
    def gutter_width(self) -> int:
        digits = max(2, len(str(self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(),
                                      self.gutter_width(), cr.height()))

    def _highlight_current_line(self):
        self._refresh_extra_selections()

    # ---- diagnostics (compile errors / warnings) -----------------------
    def set_diagnostics(self, diags):
        """diags: list of {line:int(1-based), severity:'error'|'warning', msg:str}."""
        self._diags = diags or []
        self._refresh_extra_selections()

    def clear_diagnostics(self):
        self.set_diagnostics([])

    def _refresh_extra_selections(self):
        sels = []
        # current line highlight
        cl = QTextEdit.ExtraSelection()
        cl.format.setBackground(QColor(self._pal["current_line"]))
        cl.format.setProperty(QTextFormat.FullWidthSelection, True)
        cl.cursor = self.textCursor()
        cl.cursor.clearSelection()
        sels.append(cl)
        # diagnostic underlines
        for d in getattr(self, "_diags", []):
            block = self.document().findBlockByNumber(d["line"] - 1)
            if not block.isValid():
                continue
            sel = QTextEdit.ExtraSelection()
            color = "#e53935" if d["severity"] == "error" else "#e6a23c"
            sel.format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            sel.format.setUnderlineColor(QColor(color))
            sel.format.setToolTip(f"{d['severity'].upper()}: {d['msg']}")
            c = self.textCursor()
            c.setPosition(block.position())
            c.select(c.SelectionType.LineUnderCursor)
            sel.cursor = c
            sels.append(sel)
        self.setExtraSelections(sels)

    def event(self, ev):
        # hover tooltip for diagnostics
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.ToolTip and getattr(self, "_diags", None):
            cursor = self.cursorForPosition(ev.pos())
            line = cursor.blockNumber() + 1
            from PySide6.QtWidgets import QToolTip
            for d in self._diags:
                if d["line"] == line:
                    QToolTip.showText(ev.globalPos(),
                                      f"{d['severity'].upper()}: {d['msg']}")
                    return True
            QToolTip.hideText()
        return super().event(ev)

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor(self._pal["gutter_bg"]))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        painter.setPen(QColor(self._pal["gutter_fg"]))
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(0, int(top), self.gutter.width() - 6,
                                 self.fontMetrics().height(),
                                 Qt.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            num += 1
