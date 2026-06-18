"""Simulation engine.

Runs `iverilog` then `vvp` as background QProcesses so the GUI never blocks.
Layout inside the working directory:
    build/  -> a.out (compiled)
    sim/    -> wave.vcd (moved here after the run)
Both tools run with cwd = working dir and are given source paths relative to it,
so iverilog's error messages cite the same paths shown in the log.
"""

import glob
import os
import shutil
from PySide6.QtCore import QObject, QProcess, QElapsedTimer, Signal

from .log_parser import classify


class Simulator(QObject):
    logLine = Signal(str, str)
    stageChanged = Signal(str)
    finished = Signal(bool, dict)
    started = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._timer = QElapsedTimer()
        self._stage = ""
        self._buf_out = ""
        self._buf_err = ""
        self._errors = 0
        self._warnings = 0
        self._fatal_seen = False
        self._work_dir = ""
        self._build_dir = ""
        self._sim_dir = ""
        self._has_tb = True
        self._top = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.NotRunning

    def run(self, source_files, work_dir, has_testbench=True, top=None):
        if self.is_running():
            self.logLine.emit("A simulation is already running.", "warning")
            return
        self._errors = self._warnings = 0
        self._fatal_seen = False
        self._work_dir = work_dir
        self._top = top
        self._build_dir = os.path.join(work_dir, "build")
        self._sim_dir = os.path.join(work_dir, "sim")
        os.makedirs(self._build_dir, exist_ok=True)
        os.makedirs(self._sim_dir, exist_ok=True)
        self._has_tb = has_testbench
        self._timer.start()
        self.started.emit()
        self._start_compile(source_files)

    def stop(self):
        if self.is_running():
            self._proc.kill()
            self.logLine.emit("Simulation killed by user.", "warning")

    # ---- compile -------------------------------------------------------
    def _start_compile(self, files):
        self._stage = "compile"
        self.stageChanged.emit("compile")
        rel = [os.path.relpath(f, self._work_dir) for f in files]
        top_args = ["-s", self._top] if self._top else []
        shown_top = f"-s {self._top} " if self._top else ""
        # -g2012 enables SystemVerilog-2012 (logic, always_ff/comb, '0 literals,
        # $signed, etc.). It is a superset, so plain Verilog still compiles.
        std = ["-g2012"]
        self.logLine.emit(
            f"$ iverilog -g2012 -o build/a.out {shown_top}{' '.join(rel)}", "info")
        self._proc = self._new_process()
        self._proc.finished.connect(self._compile_done)
        self._proc.start("iverilog",
                         ["-o", os.path.join("build", "a.out"), *std, *top_args, *rel])
        if not self._proc.waitForStarted(3000):
            self.logLine.emit("Could not start 'iverilog'. Is it installed and on PATH?", "error")
            self._errors += 1
            self._emit_finished(False)

    def _compile_done(self, exit_code, _status):
        self._flush_buffers()
        if exit_code != 0 or self._errors > 0:
            self.logLine.emit(f"Compilation failed (exit {exit_code}).", "error")
            self._emit_finished(False)
            return
        self.logLine.emit("Compilation successful.", "success")
        if not self._has_tb:
            self.logLine.emit(
                "No testbench found: no `initial` block in any source file. "
                "Nothing to simulate — add a testbench with an initial block.", "error")
            self._errors += 1
            self._emit_finished(False)
            return
        self._start_simulate()

    # ---- simulate ------------------------------------------------------
    def _start_simulate(self):
        self._stage = "simulate"
        self.stageChanged.emit("simulate")
        self.logLine.emit("$ vvp build/a.out", "info")
        self._proc = self._new_process()
        self._proc.finished.connect(self._simulate_done)
        self._proc.start("vvp", [os.path.join("build", "a.out")])

    def _simulate_done(self, exit_code, _status):
        self._flush_buffers()
        self._collect_waves()
        # Simulation success is decided by the tool's exit code and genuine
        # $fatal/$error tasks — NOT by counting 'fail' words in the user's
        # $display output (a line like "FAILED : 0" means zero failures).
        ok = (exit_code == 0) and (self._fatal_seen is False)
        self.logLine.emit(f"Simulation finished (exit {exit_code}).",
                          "success" if ok else "error")
        self._emit_finished(ok)

    def _collect_waves(self):
        """Move any dump files the testbench produced into sim/."""
        for pat in ("*.vcd", "*.fst"):
            for f in glob.glob(os.path.join(self._work_dir, pat)):
                dest = os.path.join(self._sim_dir, os.path.basename(f))
                try:
                    if os.path.exists(dest):
                        os.remove(dest)
                    shutil.move(f, dest)
                except OSError:
                    pass

    # ---- process plumbing ----------------------------------------------
    def _new_process(self):
        proc = QProcess(self)
        proc.setWorkingDirectory(self._work_dir)
        proc.readyReadStandardOutput.connect(self._read_stdout)
        proc.readyReadStandardError.connect(self._read_stderr)
        return proc

    def _read_stdout(self):
        self._buf_out += bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        self._buf_out = self._drain(self._buf_out)

    def _read_stderr(self):
        self._buf_err += bytes(self._proc.readAllStandardError()).decode(errors="replace")
        self._buf_err = self._drain(self._buf_err)

    def _drain(self, buf):
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            self._emit(line)
        return buf

    def _flush_buffers(self):
        for name in ("_buf_out", "_buf_err"):
            rest = getattr(self, name)
            if rest.strip():
                self._emit(rest)
            setattr(self, name, "")

    def _emit(self, line):
        sev = classify(line, self._stage)
        if self._stage == "compile" and sev == "error":
            self._errors += 1
        elif sev == "warning":
            self._warnings += 1
        # genuine runtime failure: $fatal/$error tasks emit a recognisable prefix
        low = line.lower()
        if self._stage == "simulate" and (
                "$fatal" in low or "$error" in low
                or low.lstrip().startswith("fatal:")
                or ": error:" in low):
            self._fatal_seen = True
        self.logLine.emit(line.rstrip(), sev)

    def _emit_finished(self, ok):
        self.finished.emit(ok, {
            "errors": self._errors,
            "warnings": self._warnings,
            "elapsed_ms": self._timer.elapsed(),
        })
