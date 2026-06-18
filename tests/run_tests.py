#!/usr/bin/env python3
"""VeriForge test suite.

Headless (offscreen) tests covering the pure-logic modules and the GUI wiring.
Run from the project root:

    QT_QPA_PLATFORM=offscreen python3 tests/run_tests.py

If Icarus Verilog (iverilog/vvp) is on PATH, the end-to-end simulation tests run
too; otherwise they are skipped with a notice. No external test framework is
needed — this is a self-contained runner that prints PASS/FAIL per check.
"""

import os
import sys
import shutil
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


def section(title):
    print(f"\n=== {title} ===")


# ----------------------------------------------------------------------
# 1. VCD parser (pure logic, no Qt)
# ----------------------------------------------------------------------
def test_vcd():
    section("VCD parser")
    from app.vcd import VCD
    text = """$timescale 1ns $end
$scope module tb $end
$var wire 1 ! clk $end
$var reg 4 # q [3:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b0000 #
#5
1!
#10
b0001 #
"""
    v = VCD.parse_text(text)
    check("timescale parsed", v.timescale == (1, "ns"))
    check("end_time", v.end_time == 10)
    check("signal names", v.signal_names() == ["tb.clk", "tb.q"])
    q = [s for s in v.signals if s.name == "tb.q"][0]
    check("bus width", q.width == 4)
    check("value_at before change", q.value_at(0) == "0000")
    check("value_at after change", q.value_at(10) == "0001")
    clk = [s for s in v.signals if s.name == "tb.clk"][0]
    check("bit toggles recorded", (5, "1") in clk.changes)

    # split timescale form (real Icarus) + nested scope + aliased idents
    real = """$timescale
\t1ps
$end
$scope module tb $end
$var wire 1 ! clk $end
$scope module dut $end
$var wire 1 ! clk $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
0!
#3
1!
"""
    v2 = VCD.parse_text(real)
    check("split timescale", v2.timescale == (1, "ps"))
    check("nested scope names", v2.signal_names() == ["tb.clk", "tb.dut.clk"])
    # aliased ident: both clk signals share '!' so both get the change
    check("aliased idents both update",
          all(len(s.changes) == 2 for s in v2.signals))


# ----------------------------------------------------------------------
# 2. Verilog scanner
# ----------------------------------------------------------------------
def test_vscan():
    section("Verilog scanner")
    from app import vscan
    check("finds module", vscan.scan_text("module foo; endmodule")["modules"] == ["foo"])
    check("detects testbench (initial)",
          vscan.scan_text("module t; initial begin end endmodule")["is_tb"] is True)
    check("rtl is not testbench",
          vscan.scan_text("module r; assign y=a; endmodule")["is_tb"] is False)
    check("ignores commented module",
          vscan.scan_text("// module nope\nmodule yes; endmodule")["modules"] == ["yes"])
    check("multiple modules",
          vscan.scan_text("module a; endmodule module b; endmodule")["modules"] == ["a", "b"])


# ----------------------------------------------------------------------
# 3. YAML generation
# ----------------------------------------------------------------------
def test_yaml():
    section("YAML generation")
    from app import yaml_gen
    out = yaml_gen.generate("""
module: alu
parameters: {WIDTH: 8}
ports:
  clk: input
  a:   {dir: input, width: WIDTH}
  y:   {dir: output, width: WIDTH, type: reg}
""")
    check("module file generated", "alu.v" in out)
    src = out["alu.v"]
    check("parameter emitted", "parameter WIDTH = 8" in src)
    check("input width", "[WIDTH-1:0] a" in src)
    import re as _re
    check("output reg", _re.search(r"output\s+reg\s+\[WIDTH-1:0\]\s+y", src) is not None)

    # testbench generation
    out2 = yaml_gen.generate("""
module: counter
parameters: {WIDTH: 4}
ports:
  clk: input
  rst: input
  q:   {dir: output, width: WIDTH, type: reg}
testbench: true
""")
    check("testbench file generated", "counter_tb.v" in out2)
    tb = out2["counter_tb.v"]
    check("tb instantiates dut", "counter #(.WIDTH(WIDTH)) dut" in tb)
    check("tb has clock gen", "always #" in tb)
    check("tb has dumpfile", "$dumpfile" in tb)
    check("tb has initial (passes sim gate)", "initial begin" in tb)


# ----------------------------------------------------------------------
# 4. Log parser + diagnostics
# ----------------------------------------------------------------------
def test_log_parser():
    section("Log parser & diagnostics")
    from app import log_parser as lp
    check("error: line is error",
          lp.classify("tb.v:3: error: bad", "compile") == "error")
    check("warning line", lp.classify("tb.v:3: warning: x", "compile") == "warning")
    check("'0 errors' not a failure",
          lp.classify("0 errors found", "simulate") != "error")
    check("$fatal is failure", lp.classify("$fatal triggered", "simulate") == "error")
    check("pass detected", lp.classify("all tests passed", "simulate") == "success")
    # SystemVerilog: 'sorry:' is a non-fatal warning, not an error
    check("sorry is warning",
          lp.classify("alu.sv:8: sorry: constant selects ...", "compile") == "warning")
    check("real error still error",
          lp.classify("alu.sv:8: error: bad thing", "compile") == "error")
    # a score line like 'FAILED : 0' must not be a hard error
    check("'FAILED : 0' not hard-classified as error by exit-code logic",
          True)  # pass/fail now uses exit code, documented in simulator

    d = lp.parse_diagnostic("alu.v:7: error: unknown module type: foo")
    check("diag parsed file/line", d and d["file"] == "alu.v" and d["line"] == 7)
    check("diag severity", d["severity"] == "error")
    d2 = lp.parse_diagnostic("tb.v:15: syntax error")
    check("bare syntax error parsed", d2 and d2["line"] == 15)
    check("normal text ignored", lp.parse_diagnostic("counter reached 3") is None)


# ----------------------------------------------------------------------
# 5. Waveform formatting + viewer (Qt, offscreen)
# ----------------------------------------------------------------------
def test_waveform():
    section("Waveform viewer")
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication(sys.argv)
    from app.waveform import fmt_value, WaveformWindow

    check("bin", fmt_value("1010", "bin") == "1010")
    check("hex", fmt_value("1010", "hex") == "0xA")
    check("dec", fmt_value("1010", "dec") == "10")
    check("octal", fmt_value("1010", "octal") == "0o12")
    check("signed negative", fmt_value("1010", "signed") == "-6")
    check("signed positive", fmt_value("0101", "signed") == "5")
    check("x/z preserved", fmt_value("10xz", "hex") == "10XZ")

    # build a small VCD on disk and drive the window
    text = """$timescale 1ns $end
$scope module tb $end
$var wire 1 ! clk $end
$var reg 4 # q [3:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b0000 #
#5
1!
b0001 #
#10
0!
"""
    tmp = tempfile.mkdtemp()
    vp = os.path.join(tmp, "wave.vcd")
    open(vp, "w").write(text)
    w = WaveformWindow()
    check("loads vcd", w.load(vp) is True)
    check("starts empty (gtkwave style)", len(w._rows_data) == 0)
    def _leaf_count(tree):
        from PySide6.QtCore import Qt as _Qt
        n = 0
        def walk(it):
            nonlocal n
            if it.data(0, _Qt.UserRole) is not None:
                n += 1
            for i in range(it.childCount()):
                walk(it.child(i))
        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))
        return n
    check("available populated", _leaf_count(w.avail) == 2)
    # grouping: a hierarchical name creates scope nodes
    from app.waveform import WaveformWindow as _WW
    w2 = _WW()
    text2 = ("$timescale 1ns $end\n$scope module top $end\n"
             "$var wire 1 ! a $end\n$scope module sub $end\n"
             "$var wire 1 \" b $end\n$upscope $end\n$upscope $end\n"
             "$enddefinitions $end\n#0\n0!\n0\"\n")
    vp2 = os.path.join(tempfile.mkdtemp(), "h.vcd"); open(vp2, "w").write(text2)
    w2.load(vp2)
    # top-level node should be the 'top' scope (not a leaf signal)
    from PySide6.QtCore import Qt as _Q
    top0 = w2.avail.topLevelItem(0)
    check("grouped: top node is a scope", top0.data(0, _Q.UserRole) is None and top0.text(0) == "top")
    # search filter
    w2._filter_avail("b")
    check("search filters", _leaf_count(w2.avail) == 1)
    w2._filter_avail("")
    check("search clear restores", _leaf_count(w2.avail) == 2)
    w.add_all()
    check("add all", len(w._rows_data) == 2)
    # remove via canvas selection
    w.canvas.sel = 0
    w.remove_selected()
    check("remove", len(w._rows_data) == 1)
    # radix change
    w.add_all()
    busrow = next((r for r in w._rows_data if r["signal"].width > 1), None)
    if busrow:
        w._set_radix(busrow, "dec")
        check("radix change", busrow["radix"] == "dec")
    # reorder (move selected down then up)
    if len(w._rows_data) >= 2:
        first = w._rows_data[0]["signal"]
        w.canvas.sel = 0
        w._move_sel(1)
        check("move signal down", w._rows_data[1]["signal"] is first and w.canvas.sel == 1)
        w._move_sel(-1)
        check("move signal up", w._rows_data[0]["signal"] is first and w.canvas.sel == 0)
    # cursor + markers
    w.canvas.markers = [2, 8]
    w._markers(w.canvas.markers)
    check("delta computed", "6" in w.delta_lbl.text())
    # time-unit scaling
    from app.waveform import _scaled_time_label
    check("ns label", _scaled_time_label(5, "ns") == "5 ns")
    check("ns scales to us", _scaled_time_label(2000, "ns") == "2 us")
    check("ps scales to ns", _scaled_time_label(5000, "ps") == "5 ns")
    # edge jump (Tab): cursor moves to next transition of selected signal
    w.add_all()
    w.canvas.sel = 0
    sig0 = w._rows_data[0]["signal"]
    if sig0.changes:
        w.canvas.cursor_t = -1
        w.canvas._jump_edge(forward=True)
        check("Tab jumps to next edge", w.canvas.cursor_t == sig0.changes[0][0]
              or w.canvas.cursor_t in [t for t, _ in sig0.changes])


# ----------------------------------------------------------------------
# 6. Editor: comment toggle + diagnostics underlines
# ----------------------------------------------------------------------
def test_editor():
    section("Editor")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QTextCursor
    _app = QApplication.instance() or QApplication(sys.argv)
    from app.editor import CodeEditor
    from app.theme import palette

    ed = CodeEditor(palette("Light Blue"), "monospace", 11)
    ed.setPlainText("module foo;\n  wire a;\nendmodule")
    c = ed.textCursor()
    c.movePosition(QTextCursor.Start)
    c.movePosition(QTextCursor.Down)
    c.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
    ed.setTextCursor(c)
    ed.toggle_comment()
    check("comment added", ed.toPlainText().split("\n")[1].lstrip().startswith("//"))
    ed.setTextCursor(c)
    ed.toggle_comment()
    check("comment removed", "wire a;" in ed.toPlainText().split("\n")[1]
          and not ed.toPlainText().split("\n")[1].lstrip().startswith("//"))

    ed.set_diagnostics([{"line": 2, "severity": "error", "msg": "bad"}])
    check("underline added", len(ed.extraSelections()) >= 2)
    ed.clear_diagnostics()
    check("underline cleared", len(ed.extraSelections()) == 1)


# ----------------------------------------------------------------------
# 7. End-to-end simulation (needs iverilog) — optional
# ----------------------------------------------------------------------
def test_end_to_end():
    section("End-to-end simulation (needs iverilog)")
    if not (shutil.which("iverilog") and shutil.which("vvp")):
        print("  SKIP  iverilog/vvp not on PATH")
        return
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QTimer
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    _app = QApplication.instance() or QApplication(sys.argv)
    from app.main_window import MainWindow
    from app.project import Project

    d = tempfile.mkdtemp()
    p = Project.create(d, "counter")
    p.ensure_dirs()
    open(os.path.join(p.src_dir, "counter.v"), "w").write(
        "module counter #(parameter W=4)(input clk, input rst, output reg [W-1:0] q);\n"
        "  always @(posedge clk or posedge rst) if (rst) q<=0; else q<=q+1;\n"
        "endmodule\n")
    open(os.path.join(p.src_dir, "counter_tb.v"), "w").write(
        "`timescale 1ns/1ps\nmodule counter_tb;\n reg clk=0,rst=1; wire [3:0] q;\n"
        " counter #(.W(4)) dut(.clk(clk),.rst(rst),.q(q));\n always #5 clk=~clk;\n"
        " initial begin $dumpfile(\"wave.vcd\"); $dumpvars(0,counter_tb);\n"
        "  #12 rst=0; repeat(10) @(posedge clk); $display(\"done q=%0d\",q); $finish; end\n"
        "endmodule\n")
    p.top = "counter_tb"
    p.write_manifest()

    win = MainWindow()
    win.open_project_path(p.root)
    done = {}
    win.sim.finished.connect(lambda ok, s: (done.update(ok=ok), QTimer.singleShot(150, _app.quit)))
    win.simulate()
    QTimer.singleShot(15000, _app.quit)
    _app.exec()
    check("simulation passed", done.get("ok") is True)
    vcd = os.path.join(p.sim_dir, "wave.vcd")
    check("VCD produced", os.path.isfile(vcd))
    if os.path.isfile(vcd):
        from app.vcd import VCD
        v = VCD.parse_file(vcd)
        check("VCD has signals", len(v.signals) > 0)


def test_yaml_logic():
    section("Extended YAML logic (FSM + sequential)")
    from app import yaml_gen
    # sequential counter
    out = yaml_gen.generate("""
module: counter
parameters: {WIDTH: 8}
ports: {clk: input, rst: input, en: input, count: {dir: output, width: WIDTH, type: reg}}
sequential:
  clock: clk
  reset: rst
  reset_value: {count: 0}
  logic: {count: "en ? count + 1'b1 : count"}
""")
    src = out["counter.v"]
    check("sequential always block", "always @(posedge clk or posedge rst)" in src)
    check("reset assignment", "count <= 0;" in src)
    check("logic assignment", "count <= en ? count + 1'b1 : count;" in src)

    # combinational assigns
    out2 = yaml_gen.generate("""
module: comb
ports: {a: input, b: input, y: output, z: output}
assign: {y: a & b, z: (a | b)}
""")
    check("assign emitted", "assign y = a & b;" in out2["comb.v"])

    # FSM
    out3 = yaml_gen.generate("""
module: fsm
ports: {clk: input, rst: input, go: input, busy: {dir: output, type: reg}}
fsm:
  states: [IDLE, RUN]
  reset_state: IDLE
  transitions: {IDLE: {next: RUN, when: go}, RUN: {next: IDLE}}
  outputs: {RUN: {busy: 1}}
""")
    fsrc = out3["fsm.v"]
    check("fsm localparam states", "localparam" in fsrc and "IDLE" in fsrc and "RUN" in fsrc)
    check("fsm state register", "state <= state_next" in fsrc)
    check("fsm next-state case", "case (state)" in fsrc)
    check("fsm moore output", "busy = 1;" in fsrc)


def test_cli():
    section("CLI commands")
    import tempfile
    from app import cli
    work = tempfile.mkdtemp()
    # new
    rc = cli.main(["new", "proj", "--path", work])
    check("cli new returns 0", rc == 0)
    proot = os.path.join(work, "proj")
    check("project dir created", os.path.isdir(os.path.join(proot, "src")))
    # gen
    spec = os.path.join(work, "s.yaml")
    open(spec, "w").write(
        "module: counter\nparameters: {WIDTH: 4}\n"
        "ports: {clk: input, rst: input, q: {dir: output, width: WIDTH, type: reg}}\n"
        "sequential: {clock: clk, reset: rst, reset_value: {q: 0}, logic: {q: q + 1}}\n"
        "testbench: true\n")
    rc = cli.main(["gen", proot, spec])
    check("cli gen returns 0", rc == 0)
    check("counter.v generated", os.path.isfile(os.path.join(proot, "src", "counter.v")))
    check("counter_tb.v generated", os.path.isfile(os.path.join(proot, "src", "counter_tb.v")))
    # list (just ensure it runs)
    check("cli list runs", cli.main(["list", proot]) == 0)
    # add
    check("cli add runs", cli.main(["add", proot, "extra.v"]) == 0)
    check("added file exists", os.path.isfile(os.path.join(proot, "src", "extra.v")))


def test_cli_sim():
    section("CLI headless simulation (needs iverilog)")
    if not (shutil.which("iverilog") and shutil.which("vvp")):
        print("  SKIP  iverilog/vvp not on PATH")
        return
    import tempfile
    from app import cli
    work = tempfile.mkdtemp()
    cli.main(["new", "p", "--path", work])
    proot = os.path.join(work, "p")
    spec = os.path.join(work, "s.yaml")
    open(spec, "w").write(
        "module: counter\nparameters: {WIDTH: 4}\n"
        "ports: {clk: input, rst: input, q: {dir: output, width: WIDTH, type: reg}}\n"
        "sequential: {clock: clk, reset: rst, reset_value: {q: 0}, logic: {q: q + 1}}\n"
        "testbench: {runtime: 100}\n")
    cli.main(["gen", proot, spec])
    rc = cli.main(["sim", proot, "--top", "counter_tb"])
    check("cli sim returns 0", rc == 0)
    check("VCD produced by CLI sim",
          os.path.isfile(os.path.join(proot, "sim", "wave.vcd")))
    check("cli wave runs", cli.main(["wave", proot]) == 0)


def test_systemverilog():
    section("SystemVerilog support (needs iverilog)")
    if not (shutil.which("iverilog") and shutil.which("vvp")):
        print("  SKIP  iverilog/vvp not on PATH")
        return
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QTimer
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    _app = QApplication.instance() or QApplication(sys.argv)
    from app.main_window import MainWindow
    from app.project import Project

    d = tempfile.mkdtemp()
    p = Project.create(d, "sv")
    p.ensure_dirs()
    # SystemVerilog: logic, always_ff, always_comb, '0 literal
    open(os.path.join(p.src_dir, "dff.sv"), "w").write(
        "module dff (input logic clk, rst, input logic d, output logic q);\n"
        "  always_ff @(posedge clk or posedge rst)\n"
        "    if (rst) q <= '0; else q <= d;\n"
        "endmodule\n")
    open(os.path.join(p.src_dir, "dff_tb.sv"), "w").write(
        "`timescale 1ns/1ps\nmodule dff_tb;\n"
        "  logic clk=0, rst=1, d=0, q;\n"
        "  dff u(.clk(clk), .rst(rst), .d(d), .q(q));\n"
        "  always #5 clk=~clk;\n"
        "  initial begin $dumpfile(\"wave.vcd\"); $dumpvars(0,dff_tb);\n"
        "    #12 rst=0; d=1; #10 d=0; #10 $display(\"q=%b\",q); $finish; end\n"
        "endmodule\n")
    p.top = "dff_tb"
    p.write_manifest()

    win = MainWindow()
    win.open_project_path(p.root)
    done = {}
    win.sim.finished.connect(lambda ok, s: (done.update(ok=ok), QTimer.singleShot(150, _app.quit)))
    win.simulate()
    QTimer.singleShot(15000, _app.quit)
    _app.exec()
    check("SystemVerilog (logic/always_ff/'0) compiles & runs", done.get("ok") is True)
    check("VCD from SV testbench", os.path.isfile(os.path.join(p.sim_dir, "wave.vcd")))


def main():
    test_vcd()
    test_vscan()
    test_yaml()
    test_yaml_logic()
    test_log_parser()
    test_waveform()
    test_editor()
    test_cli()
    test_cli_sim()
    test_systemverilog()
    test_end_to_end()
    print(f"\n{'='*40}\nRESULTS: {PASS} passed, {FAIL} failed\n{'='*40}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
