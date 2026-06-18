"""Editor key modes: 'normal' (default), 'vim', 'nano'.

This is a pragmatic vim core — the motions and operators people actually use
every day — not a complete vim. Returns True if it consumed the key, False to
let the editor handle it normally.

Supported in vim mode:
  modes: normal / insert / visual  (Esc returns to normal)
  motion: h j k l, w b, 0 $, gg G, counts (e.g. 5j)
  enter insert: i a o O A I
  edit: x, dd, dw, yy, p, P, u (undo), D, C
  command line: :w :q :wq :q!  (handled via a callback)
"""

from PySide6.QtGui import QTextCursor, QKeyEvent
from PySide6.QtCore import Qt


class KeyMode:
    def __init__(self, editor, on_command=None):
        self.ed = editor
        self.on_command = on_command or (lambda cmd: False)
        self.mode_name = "normal"      # 'normal' = plain modeless editing
        self.vim_state = "insert"      # when in vim: normal/insert/visual
        self._count = ""
        self._pending = ""             # pending operator like 'd', 'y', 'g'
        self._clip = ""
        self._clip_line = False

    # ---- configuration -------------------------------------------------
    def set_mode(self, name: str):
        self.mode_name = name
        if name == "vim":
            self.vim_state = "normal"
        else:
            self.vim_state = "insert"
        self._count = self._pending = ""

    def status(self) -> str:
        if self.mode_name == "vim":
            return f"VIM — {self.vim_state.upper()}"
        if self.mode_name == "nano":
            return "NANO"
        return ""

    # ---- entry point ---------------------------------------------------
    def handle(self, event: QKeyEvent) -> bool:
        if self.mode_name == "nano":
            return self._nano(event)
        if self.mode_name == "vim":
            return self._vim(event)
        return False

    # ---- nano ----------------------------------------------------------
    def _nano(self, event) -> bool:
        if event.modifiers() & Qt.ControlModifier:
            k = event.key()
            if k == Qt.Key_O:                      # ^O save
                return bool(self.on_command("w"))
            if k == Qt.Key_X:                      # ^X quit
                return bool(self.on_command("q"))
            if k == Qt.Key_K:                      # ^K cut line
                self._cut_line()
                return True
            if k == Qt.Key_U:                      # ^U paste
                self.ed.insertPlainText(self._clip)
                return True
        return False

    # ---- vim -----------------------------------------------------------
    def _vim(self, event) -> bool:
        if self.vim_state == "insert":
            if event.key() == Qt.Key_Escape:
                self.vim_state = "normal"
                self._notify()
                return True
            return False  # normal typing
        # normal / visual
        return self._vim_normal(event)

    def _move(self, op, n=1, mode=QTextCursor.MoveAnchor):
        cur = self.ed.textCursor()
        cur.movePosition(op, mode, n)
        self.ed.setTextCursor(cur)

    def _vim_normal(self, event) -> bool:
        t = event.text()
        key = event.key()
        if key == Qt.Key_Escape:
            self.vim_state = "normal"
            self._count = self._pending = ""
            self._notify()
            return True

        if t.isdigit() and not (t == "0" and not self._count):
            self._count += t
            return True
        n = int(self._count) if self._count else 1

        # operators waiting for a motion / doubled key
        if self._pending == "d":
            self._count = ""
            if t == "d":
                self._delete_lines(n); self._pending = ""; return True
            if t == "w":
                self._delete_word(n); self._pending = ""; return True
            self._pending = ""
        elif self._pending == "y":
            self._count = ""
            if t == "y":
                self._yank_lines(n); self._pending = ""; return True
            self._pending = ""
        elif self._pending == "g":
            self._pending = ""
            self._count = ""
            if t == "g":
                self._move(QTextCursor.Start); return True

        # motions
        if t == "h":
            self._move(QTextCursor.Left, n)
        elif t == "l":
            self._move(QTextCursor.Right, n)
        elif t == "j":
            self._move(QTextCursor.Down, n)
        elif t == "k":
            self._move(QTextCursor.Up, n)
        elif t == "w":
            self._move(QTextCursor.NextWord, n)
        elif t == "b":
            self._move(QTextCursor.PreviousWord, n)
        elif t == "0":
            self._move(QTextCursor.StartOfLine)
        elif t == "$":
            self._move(QTextCursor.EndOfLine)
        elif t == "G":
            self._move(QTextCursor.End)
        elif t == "g":
            self._pending = "g"; return True
        # enter insert
        elif t == "i":
            self._enter_insert()
        elif t == "a":
            self._move(QTextCursor.Right); self._enter_insert()
        elif t == "I":
            self._move(QTextCursor.StartOfLine); self._enter_insert()
        elif t == "A":
            self._move(QTextCursor.EndOfLine); self._enter_insert()
        elif t == "o":
            self._open_line(below=True)
        elif t == "O":
            self._open_line(below=False)
        # edits
        elif t == "x":
            cur = self.ed.textCursor()
            cur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, n)
            cur.removeSelectedText()
        elif t == "D":
            cur = self.ed.textCursor()
            cur.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            cur.removeSelectedText()
        elif t == "C":
            cur = self.ed.textCursor()
            cur.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            cur.removeSelectedText(); self._enter_insert()
        elif t == "d":
            self._pending = "d"; return True
        elif t == "y":
            self._pending = "y"; return True
        elif t == "p":
            self._paste(after=True)
        elif t == "P":
            self._paste(after=False)
        elif t == "u":
            self.ed.undo()
        elif t == ":":
            self._command_line()
        else:
            self._count = ""
            return True   # swallow unknown keys in normal mode

        self._count = ""
        return True

    # ---- vim helpers ---------------------------------------------------
    def _enter_insert(self):
        self.vim_state = "insert"; self._notify()

    def _notify(self):
        cb = getattr(self.ed, "modeChanged", None)
        if cb:
            cb.emit(self.status())

    def _open_line(self, below: bool):
        cur = self.ed.textCursor()
        cur.movePosition(QTextCursor.EndOfLine if below else QTextCursor.StartOfLine)
        if below:
            cur.insertText("\n")
        else:
            cur.insertText("\n"); cur.movePosition(QTextCursor.Up)
        self.ed.setTextCursor(cur); self._enter_insert()

    def _delete_lines(self, n):
        cur = self.ed.textCursor()
        cur.movePosition(QTextCursor.StartOfLine)
        cur.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, n)
        self._clip = cur.selectedText().replace("\u2029", "\n")
        self._clip_line = True
        cur.removeSelectedText()

    def _delete_word(self, n):
        cur = self.ed.textCursor()
        cur.movePosition(QTextCursor.NextWord, QTextCursor.KeepAnchor, n)
        self._clip = cur.selectedText(); self._clip_line = False
        cur.removeSelectedText()

    def _yank_lines(self, n):
        cur = self.ed.textCursor()
        cur.movePosition(QTextCursor.StartOfLine)
        cur.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, n)
        self._clip = cur.selectedText().replace("\u2029", "\n")
        self._clip_line = True

    def _cut_line(self):
        cur = self.ed.textCursor()
        cur.movePosition(QTextCursor.StartOfLine)
        cur.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
        self._clip = cur.selectedText().replace("\u2029", "\n")
        cur.removeSelectedText()

    def _paste(self, after: bool):
        cur = self.ed.textCursor()
        if self._clip_line:
            cur.movePosition(QTextCursor.EndOfLine if after else QTextCursor.StartOfLine)
            if after:
                cur.insertText("\n" + self._clip.rstrip("\n"))
            else:
                cur.insertText(self._clip.rstrip("\n") + "\n")
        else:
            if after:
                cur.movePosition(QTextCursor.Right)
            cur.insertText(self._clip)
        self.ed.setTextCursor(cur)

    def _command_line(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self.ed, "Vim command", ":")
        if ok and text:
            self.on_command(text.strip())
