import datetime
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QColor, QTextCharFormat, QFont, QTextCursor

_CAT = {
    "compile":  "IVRE",
    "simulate": "SIM",
    "gen":      "GEN",
    "tcl":      "TCL",
    "default":  "VFG",
}

_STYLE = {
    "info":     ("INFO",     QColor("#8be9fd")),
    "success":  ("OK",       QColor("#50fa7b")),
    "warning":  ("WARNING",  QColor("#f1fa8c")),
    "error":    ("ERROR",    QColor("#ff5555")),
    "critical": ("CRITICAL", QColor("#ff79c6")),
    "cmd":      ("CMD",      QColor("#ffb86c")),
}
_TEXT_COLOR  = QColor("#f8f8f2")
_DIM         = QColor("#6272a4")
_TS_COLOR    = QColor("#44475a")

_msg_counter = 0


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


class LogConsole(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setMaximumBlockCount(100_000)
        f = QFont("monospace")
        f.setStyleHint(QFont.Monospace)
        f.setPointSize(10)
        self.setFont(f)
        self.setStyleSheet(
            "QPlainTextEdit{background:#1e1f29;color:#f8f8f2;"
            "border:none;padding:6px;}"
        )
        self._stage = "default"

    def set_stage(self, stage: str):
        self._stage = stage

    def append_line(self, text: str, severity: str = "info"):
        global _msg_counter
        _msg_counter += 1
        tag, color = _STYLE.get(severity, _STYLE["info"])
        cat = _CAT.get(self._stage, _CAT["default"])
        msg_id = f"[{cat} {_msg_counter:05d}]"

        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)

        # timestamp
        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(_TS_COLOR)
        cur.insertText(f"[{_ts()}] ", ts_fmt)

        # severity tag
        tag_fmt = QTextCharFormat()
        tag_fmt.setForeground(color)
        tag_fmt.setFontWeight(QFont.Bold)
        cur.insertText(f"[{tag:<8}] ", tag_fmt)

        # message id
        id_fmt = QTextCharFormat()
        id_fmt.setForeground(_DIM)
        cur.insertText(f"{msg_id} ", id_fmt)

        # body
        txt_fmt = QTextCharFormat()
        txt_fmt.setForeground(
            color if severity in ("error", "warning", "critical", "cmd")
            else _TEXT_COLOR
        )
        cur.insertText(text + "\n", txt_fmt)
        self.setTextCursor(cur)
        self.ensureCursorVisible()

    def append_header(self, text: str):
        """Section header (run timestamp, tool invocation, etc.)."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#bd93f9"))
        fmt.setFontWeight(QFont.Bold)
        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        sep = "─" * 60
        cur.insertText(f"\n{sep}\n", QTextCharFormat())
        cur.insertText(f"  {text}\n", fmt)
        cur.insertText(f"{sep}\n", QTextCharFormat())
        self.ensureCursorVisible()

    def append_cmd(self, cmd: str):
        """Highlighted command echo (like Vivado's 'Command: ...' lines)."""
        global _msg_counter
        _msg_counter += 1
        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        ts_fmt = QTextCharFormat(); ts_fmt.setForeground(_TS_COLOR)
        cur.insertText(f"[{_ts()}] ", ts_fmt)
        tag_fmt = QTextCharFormat()
        tag_fmt.setForeground(QColor("#ffb86c")); tag_fmt.setFontWeight(QFont.Bold)
        cur.insertText("[CMD     ] ", tag_fmt)
        id_fmt = QTextCharFormat(); id_fmt.setForeground(_DIM)
        cur.insertText(f"[{_CAT.get(self._stage,'VFG')} {_msg_counter:05d}] ", id_fmt)
        cmd_fmt = QTextCharFormat(); cmd_fmt.setForeground(QColor("#ffb86c"))
        cur.insertText(cmd + "\n", cmd_fmt)
        self.setTextCursor(cur)
        self.ensureCursorVisible()

    def append_summary(self, ok: bool, stats: dict):
        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        sep_fmt = QTextCharFormat(); sep_fmt.setForeground(_DIM)
        cur.insertText("═" * 60 + "\n", sep_fmt)
        self.setTextCursor(cur)
        self.ensureCursorVisible()

        elapsed = stats["elapsed_ms"] / 1000
        self.append_line(
            f"Status: {'PASSED ✓' if ok else 'FAILED ✗'}  │  "
            f"Errors: {stats['errors']}  │  "
            f"Warnings: {stats['warnings']}  │  "
            f"Elapsed: {elapsed:.3f}s",
            "success" if ok else "error",
        )

        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        cur.insertText("═" * 60 + "\n\n", sep_fmt)
        self.setTextCursor(cur)
        self.ensureCursorVisible()
