from __future__ import annotations

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                                QLineEdit, QPushButton, QLabel)
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QKeyEvent
from PySide6.QtCore import Qt, Signal

_PROMPT = "veriforge% "

_HELP_TEXT = """\
VeriForge TCL Console
---------------------
  open_project <path>        Open a project folder
  close_project              Close the current project
  new_project <dir> <name>   Create a new project
  add_file <name>            Add a source file to the project
  list_files                 List all project source files
  set_top <module>           Set the top module
  get_top                    Print the current top module
  sim                        Run simulation (save + compile + vvp)
  sim -top <module>          Run simulation with explicit top
  wave                       Open the waveform viewer
  gen <yaml_file>            Generate Verilog from a YAML spec
  set_theme <name>           Change the editor theme
  themes                     List available themes
  clear                      Clear this console
  help                       Show this help
  exit / quit                Close VeriForge

Standard TCL is also supported (set, if, for, proc, puts, …).
Use [sim] / [wave] inside TCL expressions to call VeriForge commands.
"""


class TclConsole(QWidget):
    """Interactive TCL console panel."""

    # Signals emitted so MainWindow can act without tight coupling
    runRequested      = Signal()
    waveRequested     = Signal()
    openProjectReq    = Signal(str)
    closeProjectReq   = Signal()
    newProjectReq     = Signal(str, str)   # parent_dir, name
    addFileReq        = Signal(str)
    setTopReq         = Signal(str)
    getTopReq         = Signal()
    listFilesReq      = Signal()
    genReq            = Signal(str)
    setThemeReq       = Signal(str)
    getThemesReq      = Signal()
    simTopReq         = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._hist_idx = -1
        self._tcl = None
        self._init_tcl()
        self._build_ui()

    def _init_tcl(self):
        try:
            import tkinter
            self._tcl = tkinter.Tcl()
            # Register VeriForge procs in the TCL interpreter
            self._tcl.createcommand("open_project",  lambda *a: self._cmd_open_project(a))
            self._tcl.createcommand("close_project", lambda *a: self._cmd_close_project(a))
            self._tcl.createcommand("new_project",   lambda *a: self._cmd_new_project(a))
            self._tcl.createcommand("add_file",      lambda *a: self._cmd_add_file(a))
            self._tcl.createcommand("list_files",    lambda *a: self._cmd_list_files(a))
            self._tcl.createcommand("set_top",       lambda *a: self._cmd_set_top(a))
            self._tcl.createcommand("get_top",       lambda *a: self._cmd_get_top(a))
            self._tcl.createcommand("sim",           lambda *a: self._cmd_sim(a))
            self._tcl.createcommand("wave",          lambda *a: self._cmd_wave(a))
            self._tcl.createcommand("gen",           lambda *a: self._cmd_gen(a))
            self._tcl.createcommand("set_theme",     lambda *a: self._cmd_set_theme(a))
            self._tcl.createcommand("themes",        lambda *a: self._cmd_themes(a))
            self._tcl.createcommand("help",          lambda *a: self._cmd_help(a))
            self._tcl.createcommand("clear",         lambda *a: self._output.clear())
        except Exception:
            self._tcl = None

    def _build_ui(self):
        self.setMinimumHeight(160)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setUndoRedoEnabled(False)
        self._output.setMaximumBlockCount(20_000)
        f = QFont("monospace"); f.setStyleHint(QFont.Monospace); f.setPointSize(10)
        self._output.setFont(f)
        self._output.setStyleSheet(
            "QPlainTextEdit{background:#1e1f29;color:#f8f8f2;border:none;padding:4px;}")

        row = QHBoxLayout(); row.setContentsMargins(4, 2, 4, 4); row.setSpacing(4)
        self._prompt_lbl = QLabel(_PROMPT)
        self._prompt_lbl.setStyleSheet("color:#bd93f9;font-weight:bold;font-family:monospace;")
        self._input = QLineEdit()
        self._input.setFont(f)
        self._input.setStyleSheet(
            "QLineEdit{background:#282a36;color:#f8f8f2;"
            "border:1px solid #44475a;border-radius:4px;padding:4px 8px;}")
        self._input.setPlaceholderText("Enter TCL command…")
        self._input.returnPressed.connect(self._execute)
        run_btn = QPushButton("Run")
        run_btn.setFixedWidth(48)
        run_btn.setStyleSheet(
            "QPushButton{background:#bd93f9;color:#282a36;border:none;"
            "border-radius:4px;padding:4px 8px;font-weight:bold;}"
            "QPushButton:hover{background:#cfa5ff;}")
        run_btn.clicked.connect(self._execute)

        row.addWidget(self._prompt_lbl)
        row.addWidget(self._input, 1)
        row.addWidget(run_btn)
        input_bar = QWidget()
        input_bar.setStyleSheet("background:#21222c;")
        input_bar.setLayout(row)

        lay.addWidget(self._output, 1)
        lay.addWidget(input_bar)

        self._print(f"VeriForge TCL Console  (type 'help' for commands)\n"
                    f"TCL interpreter: {'tkinter.Tcl' if self._tcl else 'built-in dispatcher'}")

    # ── key handling (history) ────────────────────────────────────────────
    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key_Up and self._history:
            self._hist_idx = min(self._hist_idx + 1, len(self._history) - 1)
            self._input.setText(self._history[-(self._hist_idx + 1)])
        elif e.key() == Qt.Key_Down:
            if self._hist_idx > 0:
                self._hist_idx -= 1
                self._input.setText(self._history[-(self._hist_idx + 1)])
            else:
                self._hist_idx = -1; self._input.clear()
        else:
            super().keyPressEvent(e)

    # ── execution ─────────────────────────────────────────────────────────
    def _execute(self):
        cmd = self._input.text().strip()
        if not cmd:
            return
        self._history.append(cmd); self._hist_idx = -1
        self._input.clear()
        self._echo(cmd)

        if self._tcl:
            try:
                result = self._tcl.eval(cmd)
                if result:
                    self._print(result)
            except Exception as exc:
                self._error(str(exc))
        else:
            self._dispatch(cmd)

    def _dispatch(self, cmd: str):
        """Fallback dispatcher used when tkinter is unavailable."""
        parts = cmd.split()
        if not parts:
            return
        name, args = parts[0], tuple(parts[1:])
        dispatch = {
            "open_project": self._cmd_open_project,
            "close_project": self._cmd_close_project,
            "new_project": self._cmd_new_project,
            "add_file": self._cmd_add_file,
            "list_files": self._cmd_list_files,
            "set_top": self._cmd_set_top,
            "get_top": self._cmd_get_top,
            "sim": self._cmd_sim,
            "wave": self._cmd_wave,
            "gen": self._cmd_gen,
            "set_theme": self._cmd_set_theme,
            "themes": self._cmd_themes,
            "help": self._cmd_help,
            "clear": lambda _: self._output.clear(),
            "exit": lambda _: self._error("Use File → Exit to close VeriForge."),
            "quit": lambda _: self._error("Use File → Exit to close VeriForge."),
        }
        fn = dispatch.get(name)
        if fn:
            fn(args)
        else:
            self._error(f"Unknown command: '{name}'. Type 'help' for a list.")

    # ── command handlers ──────────────────────────────────────────────────
    def _cmd_open_project(self, args):
        if not args:
            self._error("Usage: open_project <path>"); return ""
        self.openProjectReq.emit(str(args[0])); return ""

    def _cmd_close_project(self, args):
        self.closeProjectReq.emit(); return ""

    def _cmd_new_project(self, args):
        if len(args) < 2:
            self._error("Usage: new_project <parent_dir> <name>"); return ""
        self.newProjectReq.emit(str(args[0]), str(args[1])); return ""

    def _cmd_add_file(self, args):
        if not args:
            self._error("Usage: add_file <filename>"); return ""
        self.addFileReq.emit(str(args[0])); return ""

    def _cmd_list_files(self, args):
        self.listFilesReq.emit(); return ""

    def _cmd_set_top(self, args):
        if not args:
            self._error("Usage: set_top <module_name>"); return ""
        self.setTopReq.emit(str(args[0])); return ""

    def _cmd_get_top(self, args):
        self.getTopReq.emit(); return ""

    def _cmd_sim(self, args):
        if len(args) >= 2 and args[0] == "-top":
            self.simTopReq.emit(str(args[1]))
        else:
            self.runRequested.emit()
        return ""

    def _cmd_wave(self, args):
        self.waveRequested.emit(); return ""

    def _cmd_gen(self, args):
        if not args:
            self._error("Usage: gen <yaml_file>"); return ""
        self.genReq.emit(str(args[0])); return ""

    def _cmd_set_theme(self, args):
        if not args:
            self._error("Usage: set_theme <theme_name>"); return ""
        self.setThemeReq.emit(str(args[0])); return ""

    def _cmd_themes(self, args):
        from .theme import THEMES
        self._print("Available themes: " + ", ".join(THEMES.keys()))
        return ""

    def _cmd_help(self, args):
        self._print(_HELP_TEXT); return ""

    # ── output helpers ────────────────────────────────────────────────────
    def _echo(self, cmd: str):
        self._insert(_PROMPT + cmd + "\n", "#bd93f9")

    def _print(self, text: str):
        self._insert(text + ("\n" if not text.endswith("\n") else ""), "#f8f8f2")

    def _error(self, text: str):
        self._insert(f"ERROR: {text}\n", "#ff5555")

    def print_result(self, text: str):
        self._print(text)

    def _insert(self, text: str, color: str):
        cur = self._output.textCursor()
        cur.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cur.insertText(text, fmt)
        self._output.setTextCursor(cur)
        self._output.ensureCursorVisible()
