from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QTabWidget, QTextBrowser, QLineEdit, QLabel,
                                QListWidget, QListWidgetItem, QSplitter)
from PySide6.QtCore import Qt

_TABS: list[tuple[str, str]] = [
    ("Overview", """
<h2>VeriForge — Overview</h2>
<p>VeriForge is a desktop RTL workbench for Verilog/SystemVerilog design and
verification. It wraps Icarus Verilog in a modern, themeable IDE with a
built-in interactive waveform viewer and YAML-driven code generation.</p>

<h3>Key concepts</h3>
<ul>
  <li><b>Project</b> — a folder containing <code>src/</code>, <code>build/</code>,
      <code>sim/</code>, and <code>logs/</code> plus a small JSON manifest.
      Git-friendly and portable.</li>
  <li><b>Top module</b> — the module (usually a testbench) where simulation
      starts. Set it in the toolbar or via <i>Flow → Select Top Module</i>.</li>
  <li><b>Simulation</b> — runs <code>iverilog -g2012</code> then
      <code>vvp</code> in the background; output appears in the Simulation Log panel.</li>
  <li><b>Waveform</b> — VCD produced by <code>$dumpvars</code> is loaded into
      the built-in viewer; GTKWave is an optional fallback.</li>
</ul>

<h3>First steps</h3>
<ol>
  <li>Launch → Welcome page → <b>New Project</b>.</li>
  <li>Create or paste a Verilog file. Press <b>F5</b> to simulate.</li>
  <li>Press <b>F7</b> to view the waveform.</li>
</ol>
"""),

    ("Editor", """
<h2>Editor</h2>
<p>The tabbed code editor supports <b>Verilog 2001</b> and
<b>SystemVerilog-2012</b> with syntax highlighting.</p>

<h3>Key modes</h3>
<table border="0" cellpadding="4">
  <tr><td><b>Standard</b></td><td>Normal Qt key bindings (default)</td></tr>
  <tr><td><b>Vim</b></td><td>Modal editing — Normal / Insert / Visual</td></tr>
  <tr><td><b>Nano</b></td><td>Ctrl shortcuts shown in status bar</td></tr>
</table>
Switch via <i>Tools → Editor Key Mode</i>.

<h3>Shortcuts</h3>
<table border="0" cellpadding="4">
  <tr><td>Ctrl+S</td><td>Save active file</td></tr>
  <tr><td>Ctrl+N</td><td>New file</td></tr>
  <tr><td>Ctrl+O</td><td>Open file</td></tr>
  <tr><td>Ctrl+wheel</td><td>Zoom editor font</td></tr>
  <tr><td>Ctrl+= / Ctrl+-</td><td>Zoom entire UI</td></tr>
  <tr><td>Ctrl+/</td><td>Toggle line comment</td></tr>
</table>

<h3>Diagnostics</h3>
<p>Compiler errors from <code>iverilog</code> are underlined in the editor
after simulation. Hover to see the message.</p>
"""),

    ("Simulation", """
<h2>Simulation</h2>
<p>VeriForge compiles with <code>iverilog -g2012</code> and runs with
<code>vvp</code>. Both run in the background so the GUI never freezes.</p>

<h3>How to simulate</h3>
<ol>
  <li>Set the <b>Top module</b> in the toolbar dropdown (or leave on <i>auto</i>).</li>
  <li>Press <b>F5</b> or <i>Flow → Simulate</i>.</li>
  <li>Watch the colour-coded Simulation Log panel.</li>
  <li>Press <b>F7</b> to open the waveform once the run finishes.</li>
</ol>

<h3>SystemVerilog support</h3>
<p>The <code>-g2012</code> flag enables <code>logic</code>,
<code>always_ff</code>, <code>always_comb</code>, <code>'0</code>/<code>'1</code>
literals, <code>$signed</code>, packed arrays, and more.</p>

<h3>Log severity colours</h3>
<table border="0" cellpadding="4">
  <tr><td style="color:#50fa7b">OK / success</td><td>Compilation passed, simulation finished</td></tr>
  <tr><td style="color:#8be9fd">INFO</td><td>Commands run, normal output</td></tr>
  <tr><td style="color:#f1fa8c">WARNING</td><td>Non-fatal issues</td></tr>
  <tr><td style="color:#ff5555">ERROR</td><td>Compile errors, fatal simulation errors</td></tr>
</table>

<h3>Persistent logs</h3>
<p>Every run is appended to <code>logs/&lt;project&gt;.log</code> with a
timestamp. Open via any text editor or your terminal.</p>
"""),

    ("Waveform Viewer", """
<h2>Waveform Viewer</h2>
<p>The built-in viewer parses VCD files and renders signals using a hardware-accelerated
canvas. It opens as a separate, tileable window.</p>

<h3>Adding signals</h3>
<ul>
  <li>Double-click a signal in the left panel to add it.</li>
  <li>Select multiple and press <b>Add →</b>.</li>
  <li>Press <b>Ctrl+A</b> to select all, then <b>Add →</b>.</li>
  <li>Press <b>Add all</b> to add every signal at once.</li>
</ul>

<h3>Navigation</h3>
<table border="0" cellpadding="4">
  <tr><td>Click waveform</td><td>Move time cursor</td></tr>
  <tr><td>Drag waveform</td><td>Pan in time</td></tr>
  <tr><td>Ctrl+wheel</td><td>Zoom in / out</td></tr>
  <tr><td>+  /  –</td><td>Toolbar zoom buttons</td></tr>
  <tr><td>Fit</td><td>Fit entire simulation to window</td></tr>
  <tr><td>Left / Right arrows</td><td>Jump cursor to prev/next edge of selected signal</td></tr>
  <tr><td>Tab / Shift+Tab</td><td>Same as Left/Right</td></tr>
</table>

<h3>Time Window</h3>
<p>Type a start and end time (e.g. <code>10ns</code>, <code>150ps</code>)
in the <b>Window: From → To</b> fields and press <b>Apply</b> to zoom to
that exact range. Press <b>Full</b> to reset.</p>

<h3>Markers</h3>
<p>Ctrl+click on the waveform places a marker (yellow dashed line).
The Δ label shows the time between the last two markers.
Press <b>Clear markers</b> to remove all.</p>

<h3>Signal options (right-click)</h3>
<p>Right-click a signal row to change <b>Radix</b> (bin/hex/dec/signed/octal/ascii)
or <b>Signal colour</b>. You can also Move up/down or Remove the signal.</p>

<h3>Export</h3>
<p><b>Export PNG</b> — saves the visible canvas as a PNG image.<br>
<b>Export CSV</b> — saves all signal values at every transition timestep.</p>
"""),

    ("YAML Generation", """
<h2>YAML Code Generation</h2>
<p>Describe your module in YAML and let VeriForge generate the Verilog skeleton —
including real combinational, sequential, and FSM logic.</p>

<h3>Basic structure</h3>
<pre>
module: my_module
parameters:
  WIDTH: 8
ports:
  clk:   input
  rst:   input
  data:  {dir: input,  width: WIDTH}
  out:   {dir: output, width: WIDTH, type: reg}
</pre>

<h3>Logic sections</h3>
<ul>
  <li><b>assign:</b> — combinational <code>assign</code> statements</li>
  <li><b>sequential:</b> — clocked <code>always</code> block with async reset</li>
  <li><b>fsm:</b> — state register, next-state case, Moore outputs</li>
  <li><b>testbench:</b> — auto-generate a clock/reset testbench with VCD dump</li>
</ul>

<h3>Rules</h3>
<ul>
  <li>Quote any expression containing <code>:</code> or <code>?</code>
      (YAML treats these specially).</li>
  <li>Use 2-space indentation — no tabs.</li>
  <li>One spec = one module, or use a top-level <code>modules:</code> list
      for multi-module generation.</li>
</ul>

<h3>How to use</h3>
<ol>
  <li>Create or open a <code>.yaml</code> spec file in the editor.</li>
  <li>Press <b>F6</b> (Generate) or <i>Flow → Generate from YAML</i>.</li>
  <li>Generated files appear in <code>src/</code>.</li>
</ol>
<p>See <code>examples/SPEC_REFERENCE.yaml</code> for the full annotated spec.</p>
"""),

    ("TCL Console", """
<h2>TCL Console</h2>
<p>The built-in TCL console lets you script VeriForge exactly like Vivado's
Tcl console. Standard TCL syntax works alongside VeriForge-specific commands.</p>

<h3>VeriForge commands</h3>
<table border="0" cellpadding="4">
  <tr><td><code>open_project &lt;path&gt;</code></td><td>Open a project folder</td></tr>
  <tr><td><code>close_project</code></td><td>Close the current project</td></tr>
  <tr><td><code>new_project &lt;dir&gt; &lt;name&gt;</code></td><td>Create a new project</td></tr>
  <tr><td><code>add_file &lt;name&gt;</code></td><td>Add a source file</td></tr>
  <tr><td><code>list_files</code></td><td>List all source files</td></tr>
  <tr><td><code>set_top &lt;module&gt;</code></td><td>Set the simulation top module</td></tr>
  <tr><td><code>get_top</code></td><td>Show current top module</td></tr>
  <tr><td><code>sim</code></td><td>Run simulation</td></tr>
  <tr><td><code>sim -top &lt;module&gt;</code></td><td>Run with explicit top</td></tr>
  <tr><td><code>wave</code></td><td>Open waveform viewer</td></tr>
  <tr><td><code>gen &lt;yaml&gt;</code></td><td>Generate Verilog from YAML spec</td></tr>
  <tr><td><code>set_theme &lt;name&gt;</code></td><td>Change the editor theme</td></tr>
  <tr><td><code>themes</code></td><td>List available themes</td></tr>
  <tr><td><code>clear</code></td><td>Clear the console</td></tr>
  <tr><td><code>help</code></td><td>Show all commands</td></tr>
</table>

<h3>TCL scripting</h3>
<pre>
# Set a variable and use it
set top counter_tb
set_top $top
sim -top $top

# Loop over files
foreach f {alu.v alu_tb.v} { add_file $f }

# Define a proc for repeated flows
proc resim {top} {
    set_top $top
    sim
    wave
}
resim counter_tb
</pre>

<h3>History</h3>
<p>Use the <b>Up/Down arrow keys</b> in the input field to navigate command history.</p>
"""),

    ("Shortcuts", """
<h2>Keyboard Shortcuts</h2>
<table border="0" cellpadding="6">
  <tr><th align="left">Key</th><th align="left">Action</th></tr>
  <tr><td>F5</td><td>Simulate</td></tr>
  <tr><td>F6</td><td>Generate from YAML spec</td></tr>
  <tr><td>F7</td><td>View Waveform</td></tr>
  <tr><td>Ctrl+S</td><td>Save active file</td></tr>
  <tr><td>Ctrl+N</td><td>New file</td></tr>
  <tr><td>Ctrl+O</td><td>Open file</td></tr>
  <tr><td>Ctrl+Shift+O</td><td>Open project</td></tr>
  <tr><td>Ctrl+Q</td><td>Quit</td></tr>
  <tr><td>Ctrl+Z / Ctrl+Y</td><td>Undo / Redo</td></tr>
  <tr><td>Ctrl+/</td><td>Toggle line comment</td></tr>
  <tr><td>Ctrl+wheel</td><td>Zoom editor font size</td></tr>
  <tr><td>Ctrl+= / Ctrl+-</td><td>Zoom entire UI in / out</td></tr>
  <tr><td>Ctrl+0</td><td>Reset UI zoom</td></tr>
  <tr><td>Ctrl+`</td><td>Open system terminal</td></tr>
</table>

<h3>Waveform viewer</h3>
<table border="0" cellpadding="6">
  <tr><td>Ctrl+wheel</td><td>Zoom waveform in / out</td></tr>
  <tr><td>Shift+wheel</td><td>Pan waveform left / right</td></tr>
  <tr><td>Left / Right</td><td>Jump cursor to prev / next signal edge</td></tr>
  <tr><td>Tab / Shift+Tab</td><td>Same as Left / Right</td></tr>
  <tr><td>Ctrl+A</td><td>Select all signals in left panel</td></tr>
  <tr><td>Ctrl+click</td><td>Place a time marker</td></tr>
  <tr><td>Delete</td><td>Remove selected signal from view</td></tr>
</table>
"""),
]


class HelpWindow(QMainWindow):
    def __init__(self, parent=None, chrome=None):
        super().__init__(parent)
        self.setWindowTitle("VeriForge — Help")
        self.resize(860, 620)
        self.setWindowFlags(Qt.Window)

        self._pages: dict[str, str] = {title: html for title, html in _TABS}

        # search bar
        search_bar = QWidget()
        sb_lay = QHBoxLayout(search_bar); sb_lay.setContentsMargins(8, 6, 8, 6)
        sb_lay.addWidget(QLabel("🔍 Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search help topics…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)
        sb_lay.addWidget(self._search, 1)

        # results list (hidden until search active)
        self._results = QListWidget()
        self._results.hide()
        self._results.currentItemChanged.connect(self._on_result_select)

        # tab widget
        self._tabs = QTabWidget()
        for title, html in _TABS:
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            browser.setHtml(html)
            self._tabs.addTab(browser, title)

        # layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._results)
        splitter.addWidget(self._tabs)
        splitter.setSizes([0, 860])
        self._splitter = splitter

        central = QWidget()
        lay = QVBoxLayout(central); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        lay.addWidget(search_bar)
        lay.addWidget(splitter, 1)
        self.setCentralWidget(central)

        if chrome:
            self._apply_chrome(chrome)

    def _apply_chrome(self, c):
        self.setStyleSheet(
            f"QMainWindow,QWidget{{background:{c['win']};color:{c['text']};}}"
            f"QLineEdit{{background:{c['input']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:5px;padding:5px 8px;}}"
            f"QTabBar::tab{{background:{c['tab_bg']};color:{c['muted']};"
            f"padding:6px 14px;border-top-left-radius:5px;border-top-right-radius:5px;}}"
            f"QTabBar::tab:selected{{background:{c['tab_sel']};color:{c['text']};"
            f"border-bottom:2px solid {c['accent']};}}"
            f"QTabBar::tab:hover{{color:{c['text']};}}"
            f"QTextBrowser{{background:{c['panel']};color:{c['text']};border:none;padding:8px;}}"
            f"QListWidget{{background:{c['panel']};color:{c['text']};border:none;}}"
            f"QListWidget::item:selected{{background:{c['accent']};color:{c['on_accent']};}}"
            f"QLabel{{color:{c['muted']};}}"
        )

    def _on_search(self, text: str):
        text = text.strip().lower()
        if not text:
            self._results.hide()
            self._splitter.setSizes([0, self.width()])
            return
        self._results.clear()
        for title, html in _TABS:
            if text in title.lower() or text in html.lower():
                item = QListWidgetItem(title)
                item.setData(Qt.UserRole, title)
                self._results.addItem(item)
        if self._results.count():
            self._results.show()
            self._splitter.setSizes([200, max(600, self.width() - 200)])
        else:
            item = QListWidgetItem("No results")
            self._results.addItem(item)
            self._results.show()
            self._splitter.setSizes([200, max(600, self.width() - 200)])

    def _on_result_select(self, item):
        if item is None:
            return
        title = item.data(Qt.UserRole)
        if not title:
            return
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                break
