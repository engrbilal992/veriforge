import os
import shutil
import datetime
import tempfile
from PySide6.QtWidgets import (QMainWindow, QSplitter, QWidget, QVBoxLayout,
                               QLabel, QFileDialog, QToolBar, QStatusBar,
                               QTabWidget, QInputDialog, QMessageBox, QStyle,
                               QDockWidget, QStackedWidget, QComboBox, QLineEdit,
                               QDialog, QFormLayout, QDialogButtonBox)
from PySide6.QtGui import (QAction, QKeySequence, QIcon, QPixmap, QPainter,
                           QPen, QColor, QActionGroup)
from PySide6.QtCore import Qt, QSize, QTimer, QRectF, QSettings

from .editor import CodeEditor
from .log_console import LogConsole
from .simulator import Simulator
from .file_explorer import FileExplorer
from .project import Project, has_testbench
from .theme import THEMES, DEFAULT, palette, chrome
from .appearance import AppearanceDialog
from .welcome import WelcomePage
from . import terminal as term_launcher
from .waveform import WaveformWindow
from .panel import Panel
from . import yaml_gen
from .tcl_console import TclConsole
from .help_window import HelpWindow

_BADGE = {
    "idle":     ("No project", "#7d8597"),
    "ready":    ("Ready",      "#7d8597"),
    "compile":  ("Compiling",  "#d97706"),
    "simulate": ("Simulating", "#2563eb"),
    "passed":   ("Passed",     "#16a34a"),
    "failed":   ("Failed",     "#dc2626"),
}


def _spinner_icon(angle: int, color: str, size: int = 22) -> QIcon:
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.translate(size / 2, size / 2); p.rotate(angle)
    pen = QPen(QColor(color)); pen.setWidth(2); pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen); r = size / 2 - 3
    p.drawArc(QRectF(-r, -r, 2 * r, 2 * r), 0, 270 * 16); p.end()
    return QIcon(pm)


class StyledInputDialog(QDialog):
    """A themed single-line input dialog (replaces plain QInputDialog)."""
    @staticmethod
    def get_text(parent, title, label, text="", chrome_c=None):
        d = QDialog(parent)
        d.setWindowTitle(title)
        d.setMinimumWidth(380)
        if chrome_c:
            d.setStyleSheet(
                f"QDialog{{background:{chrome_c['win']};}}"
                f"QLabel{{color:{chrome_c['text']};}}"
                f"QLineEdit{{background:{chrome_c['panel']};color:{chrome_c['text']};"
                f"border:1px solid {chrome_c['border']};border-radius:5px;padding:6px;}}"
                f"QPushButton{{background:{chrome_c['accent']};color:#fff;border:none;"
                f"border-radius:6px;padding:7px 16px;}}"
                f"QPushButton:hover{{background:{chrome_c['panel_fg']};}}")
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel(label))
        edit = QLineEdit(text); lay.addWidget(edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        edit.setFocus(); edit.selectAll()
        ok = d.exec() == QDialog.Accepted
        return edit.text(), ok


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VeriForge")
        self.resize(1280, 820)
        self.project = None
        self._log_fh = None
        self._scratch_dir = None
        self._run_diags = []
        self._pending_wave = False
        self._spin_angle = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._spin)

        self.settings = QSettings("VeriForge", "VeriForge")
        theme = self.settings.value("theme", DEFAULT)
        self.appearance = {
            "theme": theme if theme in THEMES else DEFAULT,
            "font_family": self.settings.value("font_family", "monospace"),
            "font_size": int(self.settings.value("font_size", 11)),
            "key_mode": self.settings.value("key_mode", "normal"),
        }
        self.recents = self.settings.value("recents", []) or []
        if isinstance(self.recents, str):
            self.recents = [self.recents]
        from PySide6.QtWidgets import QApplication
        self._base_ui_pt = QApplication.instance().font().pointSizeF()
        if self._base_ui_pt <= 0:
            self._base_ui_pt = 10.0
        self._ui_scale = float(self.settings.value("ui_scale", 1.0))
        self._state_key = "idle"
        self.wave_win = None

        # --- editor-side widgets ---
        self.explorer = FileExplorer()
        self.explorer.fileActivated.connect(self.open_path)
        self.explorer.renameRequested.connect(self.rename_file)
        self.explorer.deleteRequested.connect(self.delete_file)
        self.explorer.newFileRequested.connect(self.new_file)
        self.explorer.setTopRequested.connect(self.set_top_module)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.console = LogConsole()

        self.tcl = TclConsole()
        self._wire_tcl()

        self._panels = []
        self.explorer_panel = self._panel("Explorer", self.explorer, "explorer",
            "Lists your project's Verilog files. Double-click to open. "
            "Right-click for New/Rename/Delete.")
        self.editor_panel = self._panel("Editor", self.tabs, "editor",
            "Tabbed code editor. Tools \u2192 Editor Key Mode switches Standard/Vim/Nano. "
            "Ctrl+wheel zooms.")
        self.log_panel = self._panel("Simulation Log", self.console, "log",
            "Compile and simulation output. Each run is timestamped and also "
            "appended to logs/<project>.log.")
        self.tcl_panel = self._panel("TCL Console", self.tcl, "tcl",
            "Interactive TCL console. Type 'help' for all VeriForge commands.")

        top = QSplitter(Qt.Horizontal)
        top.addWidget(self.explorer_panel)
        top.addWidget(self.editor_panel)
        top.setSizes([250, 1000])
        self._top_split = top

        bottom = QSplitter(Qt.Horizontal)
        bottom.addWidget(self.log_panel)
        bottom.addWidget(self.tcl_panel)
        bottom.setSizes([700, 400])
        self._bottom_split = bottom

        self._editor_split = QSplitter(Qt.Vertical)
        self._editor_split.addWidget(top)
        self._editor_split.addWidget(bottom)
        self._editor_split.setSizes([580, 240])

        # --- welcome page + stack ---
        self.welcome = WelcomePage(chrome(self.appearance["theme"]), self.recents)
        self.welcome.newProject.connect(self.new_project)
        self.welcome.openProject.connect(self.open_project)
        self.welcome.openRecent.connect(self.open_project_path)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome)        # index 0
        self.stack.addWidget(self._editor_split)  # index 1
        self.setCentralWidget(self.stack)

        self._build_menubar()
        self._build_toolbar()
        self._build_statusbar()

        self.sim = Simulator(self)
        self.sim.started.connect(lambda: self._set_state("compile"))
        self.sim.stageChanged.connect(self._on_stage_changed)
        self.sim.logLine.connect(self._on_log_line)
        self.sim.finished.connect(self._on_finished)

        self._apply_chrome()
        if self._ui_scale != 1.0:
            self._apply_ui_scale()
        self._set_state("idle")
        # Ctrl+wheel anywhere zooms the workspace (VS Code style)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        # Ctrl+wheel = editor font zoom only (whole-UI zoom is Ctrl+= / Ctrl+-)
        if event.type() == QEvent.Wheel and (event.modifiers() & Qt.ControlModifier):
            dy = event.angleDelta().y()
            self._zoom_editor(1 if dy > 0 else -1)
            return True
        return super().eventFilter(obj, event)

    def _on_stage_changed(self, stage: str):
        self._set_state(stage)
        self.console.set_stage(stage)

    # ---- chrome / theming ----------------------------------------------
    def _chrome(self):
        return chrome(self.appearance["theme"])

    def _apply_chrome(self):
        c = self._chrome()
        from .style import app_qss
        self.setStyleSheet(app_qss(c, self._ui_scale))
        for p in self._panels:
            p.apply_chrome(c)
        self.explorer.apply_chrome(c)
        if getattr(self, "wave_win", None) is not None:
            self.wave_win.apply_chrome(c, self._is_light())

    def _panel(self, title, widget, key, help_text):
        p = Panel(title, widget, key, help_text)
        p.maximizeRequested.connect(self._maximize_panel)
        p.closeRequested.connect(self._close_panel)
        p.helpRequested.connect(lambda k, pan=p: self._panel_help(pan))
        self._panels.append(p)
        return p

    def _maximize_panel(self, panel):
        # toggle: if already maximized, restore even splits; else give panel all space
        split = self._editor_split
        if panel is self.log_panel:
            sizes = split.sizes()
            if sizes[1] > sizes[0]:
                split.setSizes([580, 240])
            else:
                split.setSizes([60, 900])
        else:
            sizes = self._top_split.sizes()
            if panel is self.editor_panel:
                self._top_split.setSizes([0, 1] if sizes[0] else [250, 1000])
            else:
                self._top_split.setSizes([1, 0] if sizes[1] else [250, 1000])

    def _close_panel(self, panel):
        panel.hide()

    def _wire_tcl(self):
        t = self.tcl
        t.runRequested.connect(self.simulate)
        t.waveRequested.connect(self.view_waveform)
        t.openProjectReq.connect(self.open_project_path)
        t.closeProjectReq.connect(self.close_project)
        t.setTopReq.connect(self.set_top_module)
        t.getTopReq.connect(lambda: self.tcl.print_result(
            self.project.top or "(auto)" if self.project else "No project"))
        t.listFilesReq.connect(self._tcl_list_files)
        t.addFileReq.connect(self._tcl_add_file)
        t.genReq.connect(self._tcl_gen)
        t.setThemeReq.connect(self._tcl_set_theme)
        t.simTopReq.connect(self._tcl_sim_top)
        t.newProjectReq.connect(self._tcl_new_project)

    def _tcl_list_files(self):
        if not self.project:
            self.tcl.print_result("ERROR: no project open"); return
        files = self.project.source_files()
        self.tcl.print_result("\n".join(files) if files else "(no source files)")

    def _tcl_add_file(self, name):
        if not self.project:
            self.tcl.print_result("ERROR: no project open"); return
        try:
            path = self.project.add_file(name)
            self.refresh_explorer(); self.open_path(path)
            self.tcl.print_result(f"Added: {path}")
        except Exception as e:
            self.tcl.print_result(f"ERROR: {e}")

    def _tcl_gen(self, path):
        if not self.project:
            self.tcl.print_result("ERROR: no project open"); return
        try:
            with open(path) as fh:
                files = yaml_gen.generate(fh.read())
            self._write_generated(files)
            self.tcl.print_result(f"Generated {len(files)} file(s)")
        except Exception as e:
            self.tcl.print_result(f"ERROR: {e}")

    def _tcl_set_theme(self, name):
        if name not in THEMES:
            self.tcl.print_result(f"Unknown theme '{name}'. Run: themes")
            return
        self.appearance["theme"] = name
        self._apply_appearance_all(); self._apply_chrome()
        self.tcl.print_result(f"Theme set to: {name}")

    def _tcl_sim_top(self, top):
        self.set_top_module(top)
        self.simulate()

    def _tcl_new_project(self, parent_dir, name):
        import os as _os
        try:
            self.project = Project.create(parent_dir, name)
            self.project.ensure_dirs()
            self._load_project()
            self.tcl.print_result(f"Project '{name}' created at {parent_dir}")
        except Exception as e:
            self.tcl.print_result(f"ERROR: {e}")

    def show_all_panels(self):
        for p in self._panels:
            p.show()
            if p._collapsed:
                p._toggle_collapse()
        self._top_split.setSizes([250, 1000])
        self._editor_split.setSizes([580, 240])
        self._bottom_split.setSizes([700, 400])

    def _panel_help(self, panel):
        QMessageBox.information(self, f"{panel.key.title()} — Help",
                                panel.help_text or "No help available.")

    # ---- menus ---------------------------------------------------------
    def _build_menubar(self):
        mb = self.menuBar()

        filem = mb.addMenu("File")
        self._m(filem, "New Project", self.new_project)
        self._m(filem, "Open Project", self.open_project, "Ctrl+Shift+O")
        filem.addSeparator()
        self._m(filem, "New File", self.new_file, "Ctrl+N")
        self._m(filem, "Open File", self.open_file, "Ctrl+O")
        self._m(filem, "Save", self.save_active, "Ctrl+S")
        filem.addSeparator()
        self._m(filem, "Close Project", self.close_project)
        self._m(filem, "Exit", self.close, "Ctrl+Q")

        editm = mb.addMenu("Edit")
        self._m(editm, "Undo", lambda: self._ed_call("undo"))
        self._m(editm, "Redo", lambda: self._ed_call("redo"))
        editm.addSeparator()
        self._m(editm, "Cut", lambda: self._ed_call("cut"))
        self._m(editm, "Copy", lambda: self._ed_call("copy"))
        self._m(editm, "Paste", lambda: self._ed_call("paste"))

        viewm = mb.addMenu("View")
        self._m(viewm, "Appearance\u2026", self.open_appearance)
        viewm.addSeparator()
        self._m(viewm, "File Explorer", lambda: self.explorer_panel.show())
        self._m(viewm, "Editor", lambda: self.editor_panel.show())
        self._m(viewm, "Simulation Log", lambda: self.log_panel.show())
        self._m(viewm, "TCL Console", lambda: self.tcl_panel.show())
        self._m(viewm, "Show All Panels", self.show_all_panels)
        viewm.addSeparator()
        self._m(viewm, "Zoom In (UI)", lambda: self._ui_zoom(0.1), "Ctrl+=")
        self._m(viewm, "Zoom Out (UI)", lambda: self._ui_zoom(-0.1), "Ctrl+-")
        self._m(viewm, "Reset Zoom (UI)", self._ui_zoom_reset, "Ctrl+0")
        viewm.addSeparator()
        self._m(viewm, "Editor Font Larger", lambda: self._zoom_editor(1), "Ctrl+Shift+=")
        self._m(viewm, "Editor Font Smaller", lambda: self._zoom_editor(-1), "Ctrl+Shift+-")

        toolsm = mb.addMenu("Tools")
        km = toolsm.addMenu("Editor Key Mode")
        grp = QActionGroup(self); grp.setExclusive(True)
        for label, mode in (("Standard", "normal"), ("Vim", "vim"), ("Nano", "nano")):
            a = km.addAction(label); a.setCheckable(True)
            a.setChecked(self.appearance["key_mode"] == mode)
            a.triggered.connect(lambda _=False, m=mode: self.set_key_mode(m))
            grp.addAction(a)
        toolsm.addSeparator()
        self._m(toolsm, "Generate from YAML spec\u2026", self.import_yaml)
        toolsm.addSeparator()
        self._m(toolsm, "Open System Terminal Here", self.open_terminal, "Ctrl+`")

        winm = mb.addMenu("Window")
        self._m(winm, "Show All Panels", self.show_all_panels)
        self._m(winm, "Show Welcome Page", self.show_welcome)

        flowm = mb.addMenu("Flow")
        self._m(flowm, "Select Top Module\u2026", self.choose_top_module)
        flowm.addSeparator()
        self._m(flowm, "Simulate", self.simulate, "F5")
        self._m(flowm, "Stop", self.stop)
        flowm.addSeparator()
        self._m(flowm, "View Waveform", self.view_waveform, "F7")

        helpm = mb.addMenu("Help")
        self._m(helpm, "VeriForge Help", self.open_help, "F1")
        helpm.addSeparator()
        self._m(helpm, "About VeriForge", self.about)

    def _m(self, menu, text, slot, sc=None):
        a = menu.addAction(text); a.triggered.connect(slot)
        if sc:
            a.setShortcut(QKeySequence(sc))
        return a

    def _build_toolbar(self):
        tb = QToolBar(); tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly); tb.setIconSize(QSize(22, 22))
        self.addToolBar(tb)
        st = self.style()

        def act(tip, icon, slot, shortcut=None):
            a = QAction(icon, tip, self)
            a.setToolTip(tip + (f"  ({shortcut})" if shortcut else ""))
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            tb.addAction(a); return a

        act("New Project", st.standardIcon(QStyle.SP_FileDialogNewFolder), self.new_project)
        act("Open Project", st.standardIcon(QStyle.SP_DirOpenIcon), self.open_project)
        tb.addSeparator()
        act("New File", st.standardIcon(QStyle.SP_FileIcon), self.new_file)
        act("Open File", st.standardIcon(QStyle.SP_DialogOpenButton), self.open_file)
        act("Save", st.standardIcon(QStyle.SP_DialogSaveButton), self.save_active)
        tb.addSeparator()
        self._play_icon = st.standardIcon(QStyle.SP_MediaPlay)
        self.run_act = act("Simulate", self._play_icon, self.simulate, "F5")
        self.stop_act = act("Stop", st.standardIcon(QStyle.SP_MediaStop), self.stop)
        self.stop_act.setEnabled(False)
        self.gen_act = act("Generate from YAML",
                           st.standardIcon(QStyle.SP_ArrowDown),
                           self.generate_active, "F6")
        act("View Waveform", st.standardIcon(QStyle.SP_FileDialogContentsView),
            self.view_waveform, "F7")
        tb.addSeparator()
        act("Open Terminal", st.standardIcon(QStyle.SP_ComputerIcon), self.open_terminal)
        act("Clear Log", st.standardIcon(QStyle.SP_DialogResetButton), self.console.clear)

        # top-module selector (right-aligned)
        from PySide6.QtWidgets import QWidget as _QW, QSizePolicy, QLabel as _QL
        spacer = _QW(); spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(_QL(" Top: "))
        self.top_combo = QComboBox()
        self.top_combo.setMinimumWidth(150)
        self.top_combo.setToolTip("Top module — simulation starts here (RTL or testbench)")
        self.top_combo.currentTextChanged.connect(self._top_combo_changed)
        tb.addWidget(self.top_combo)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.mode_label = QLabel("")
        sb.addPermanentWidget(self.mode_label)
        self.badge = QLabel()
        sb.addPermanentWidget(self.badge)
        self.setStatusBar(sb)
        self._refresh_mode_label()

    # ---- spinner -------------------------------------------------------
    def _spin(self):
        self._spin_angle = (self._spin_angle + 30) % 360
        self.run_act.setIcon(_spinner_icon(self._spin_angle, self._chrome()["accent"]))

    def _start_spinner(self):
        self._spin_timer.start(80)

    def _stop_spinner(self):
        self._spin_timer.stop()
        self.run_act.setIcon(self._play_icon)

    # ---- appearance / key mode -----------------------------------------
    def _palette(self):
        return palette(self.appearance["theme"])

    def open_appearance(self):
        AppearanceDialog(self.appearance, self._set_appearance, self,
                         chrome=self._chrome()).exec()

    def _set_appearance(self, app):
        self.appearance.update(app)
        self._apply_appearance_all()
        self._apply_chrome()

    def set_key_mode(self, mode):
        self.appearance["key_mode"] = mode
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_key_mode(mode)
        self.settings.setValue("key_mode", mode)
        self._refresh_mode_label()

    def _refresh_mode_label(self):
        m = self.appearance["key_mode"]
        txt = {"normal": "", "vim": "VIM", "nano": "NANO"}.get(m, "")
        self.mode_label.setText(f"  {txt}  " if txt else "")
        self.mode_label.setStyleSheet(
            f"color:{self._chrome()['accent']};font-weight:bold;")

    # --- editor-only font zoom (Ctrl+Shift+wheel / menu) ---
    def _zoom_editor(self, delta):
        self.appearance["font_size"] = max(6, min(48,
            self.appearance["font_size"] + delta))
        self._apply_appearance_all()

    def _zoom_editor_to(self, size):
        self.appearance["font_size"] = max(6, min(48, size))
        self._apply_appearance_all()

    # --- whole-workspace zoom (Ctrl+= / Ctrl+- / Ctrl+0 / Ctrl+wheel) ---
    def _ui_zoom(self, delta):
        self._ui_scale = max(0.7, min(2.4, round(self._ui_scale + delta, 2)))
        self._apply_ui_scale()

    def _ui_zoom_reset(self):
        self._ui_scale = 1.0
        self._apply_ui_scale()

    def _apply_ui_scale(self):
        # 1) rescale the whole UI by regenerating the stylesheet at the new scale
        self._apply_chrome()
        # 2) editors set their own font, so scale them explicitly too
        self._apply_appearance_all()
        self.settings.setValue("ui_scale", self._ui_scale)
        self.statusBar().showMessage(f"Zoom: {int(self._ui_scale*100)}%", 2000)

    def _effective_font_size(self):
        return max(6, round(self.appearance["font_size"] * self._ui_scale))

    def _apply_appearance_all(self):
        pal = self._palette()
        eff = self._effective_font_size()
        for i in range(self.tabs.count()):
            self.tabs.widget(i).apply_appearance(
                pal, self.appearance["font_family"], eff)
        for k, v in self.appearance.items():
            self.settings.setValue(k, v)

    def _ed_call(self, method):
        ed = self.current_editor()
        if ed and hasattr(ed, method):
            getattr(ed, method)()

    # ---- welcome / project lifecycle -----------------------------------
    def show_welcome(self):
        self.welcome.recent.clear()
        for path in self.recents:
            if os.path.isdir(path):
                from PySide6.QtWidgets import QListWidgetItem
                it = QListWidgetItem(f"{os.path.basename(path)}      {path}")
                it.setData(Qt.UserRole, path)
                self.welcome.recent.addItem(it)
        self.stack.setCurrentIndex(0)

    def _show_editor(self):
        self.stack.setCurrentIndex(1)

    def _remember(self, root):
        self.recents = [root] + [r for r in self.recents if r != root]
        self.recents = self.recents[:8]
        self.settings.setValue("recents", self.recents)

    def new_project(self):
        parent = QFileDialog.getExistingDirectory(self, "Choose where to create the project")
        if not parent:
            return
        name, ok = StyledInputDialog.get_text(self, "New Project", "Project name:",
                                              chrome_c=self._chrome())
        if not ok or not name.strip():
            return
        try:
            self.project = Project.create(parent, name.strip())
        except OSError as e:
            QMessageBox.warning(self, "New Project", str(e)); return
        self.project.ensure_dirs()
        self._load_project()

    def open_project(self):
        root = QFileDialog.getExistingDirectory(self, "Open project folder")
        if root:
            self.open_project_path(root)

    def open_project_path(self, root):
        if not os.path.isdir(root):
            QMessageBox.warning(self, "Open Project", "Folder no longer exists."); return
        self.project = Project.open(root)
        self._load_project()

    def _load_project(self):
        self._remember(self.project.root)
        self.refresh_explorer()
        self.setWindowTitle(f"VeriForge — {self.project.name}")
        self._show_editor()
        self._set_state("ready")

    def close_project(self):
        self.project = None
        self.tabs.clear()
        self.setWindowTitle("VeriForge")
        self.show_welcome()
        self._set_state("idle")

    def refresh_explorer(self):
        if not self.project:
            return
        files = self.project.tree_files()
        top_file = None
        if self.project.top:
            from . import vscan
            top_file = vscan.file_of_module(
                [f for f in files if f.lower().endswith((".v", ".sv"))],
                self.project.top)
        self.explorer.set_files(self.project.root, files, top_file)
        self._refresh_top_combo()

    # ---- file actions --------------------------------------------------
    def new_file(self):
        if not self.project:
            QMessageBox.information(self, "New File", "Create or open a project first."); return
        # choose how to create the file
        box = QMessageBox(self)
        box.setWindowTitle("New File")
        box.setText("How do you want to create this file?")
        b_v = box.addButton("Verilog (from scratch)", QMessageBox.AcceptRole)
        b_y = box.addButton("YAML spec (generate skeleton)", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        if self._chrome():
            c = self._chrome()
            box.setStyleSheet(f"QMessageBox{{background:{c['win']};}}"
                              f"QLabel{{color:{c['text']};}}"
                              f"QPushButton{{background:{c['accent']};color:#fff;"
                              f"border:none;border-radius:6px;padding:7px 14px;}}"
                              f"QPushButton:hover{{background:{c['panel_fg']};}}")
        box.exec()
        clicked = box.clickedButton()
        if clicked not in (b_v, b_y):
            return
        is_yaml = clicked is b_y
        hint = ("Spec name (e.g. alu \u2014 creates alu.yaml):" if is_yaml
                else "File name (e.g. alu.v, alu_tb.v, defs.vh):")
        name, ok = StyledInputDialog.get_text(self, "New File", hint,
                                              chrome_c=self._chrome())
        if not ok or not name.strip():
            return
        name = name.strip()
        if is_yaml and not name.lower().endswith((".yaml", ".yml")):
            name += ".yaml"
        try:
            path = self.project.add_file(name)
        except FileExistsError:
            QMessageBox.warning(self, "New File", "That file already exists."); return
        self.refresh_explorer()
        self.open_path(path)

    def open_file(self):
        start = self.project.root if self.project else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open file", start, "Verilog (*.v *.sv *.vh *.svh);;All (*)")
        if path:
            self.open_path(path)

    def open_path(self, path):
        i = self._tab_for(path)
        if i >= 0:
            self.tabs.setCurrentIndex(i); return
        ed = CodeEditor(self._palette(), self.appearance["font_family"],
                        self._effective_font_size())
        if path.lower().endswith((".yaml", ".yml")):
            ed.highlighter.setDocument(None)   # plain text for YAML specs
        ed.fontZoomed.connect(self._zoom_editor_to)
        ed.modeChanged.connect(lambda s: self.mode_label.setText(f"  {s}  " if s else ""))
        ed.requestSave.connect(lambda e: self._write(e))
        ed.requestClose.connect(lambda e: self.close_tab(self.tabs.indexOf(e)))
        try:
            with open(path) as fh:
                ed.setPlainText(fh.read())
        except OSError as e:
            QMessageBox.warning(self, "Open file", str(e)); return
        ed.file_path = path
        ed.document().setModified(False)
        ed.set_key_mode(self.appearance["key_mode"])
        ed.document().modificationChanged.connect(
            lambda dirty, e=ed: self._update_tab_title(e, dirty))
        idx = self.tabs.addTab(ed, os.path.basename(path))
        self.tabs.setCurrentIndex(idx)

    def _tab_for(self, path):
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i), "file_path", None) == path:
                return i
        return -1

    def rename_file(self, path):
        base = os.path.basename(path)
        new, ok = StyledInputDialog.get_text(self, "Rename", "New name:", base,
                                            chrome_c=self._chrome())
        new = new.strip() if ok else ""
        if not new or new == base:
            return
        newpath = os.path.join(os.path.dirname(path), new)
        if os.path.exists(newpath):
            QMessageBox.warning(self, "Rename", "A file with that name already exists."); return
        try:
            os.rename(path, newpath)
        except OSError as e:
            QMessageBox.warning(self, "Rename", str(e)); return
        i = self._tab_for(path)
        if i >= 0:
            self.tabs.widget(i).file_path = newpath
            self.tabs.setTabText(i, new)
        self.refresh_explorer()

    def delete_file(self, path):
        base = os.path.basename(path)
        if QMessageBox.question(self, "Delete", f"Delete {base}? This cannot be undone.",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        i = self._tab_for(path)
        if i >= 0:
            self.tabs.removeTab(i)
        try:
            os.remove(path)
        except OSError as e:
            QMessageBox.warning(self, "Delete", str(e)); return
        self.refresh_explorer()

    def close_tab(self, index):
        if index < 0:
            return
        ed = self.tabs.widget(index)
        if ed.document().isModified():
            r = QMessageBox.question(
                self, "Unsaved changes",
                f"Save {os.path.basename(ed.file_path)} before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                return
            if r == QMessageBox.Yes:
                self._write(ed)
        self.tabs.removeTab(index)

    def current_editor(self):
        return self.tabs.currentWidget()

    def _write(self, ed):
        with open(ed.file_path, "w") as fh:
            fh.write(ed.toPlainText())
        ed.document().setModified(False)

    def save_active(self):
        ed = self.current_editor()
        if ed:
            self._write(ed)

    def save_all_dirty(self):
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if ed.document().isModified():
                self._write(ed)

    def _update_tab_title(self, ed, dirty):
        idx = self.tabs.indexOf(ed)
        if idx >= 0:
            base = os.path.basename(ed.file_path)
            self.tabs.setTabText(idx, base + (" *" if dirty else ""))

    # ---- terminal ------------------------------------------------------
    def open_terminal(self):
        cwd = self.project.root if self.project else os.path.expanduser("~")
        ok, msg = term_launcher.open_terminal(cwd)
        if not ok:
            QMessageBox.warning(self, "Open Terminal", msg)

    # ---- YAML scaffolding ----------------------------------------------
    def generate_active(self):
        """Generate Verilog from the YAML in the active editor tab (F6)."""
        if not self.project:
            QMessageBox.information(self, "Generate", "Open a project first."); return
        ed = self.current_editor()
        if not ed or not getattr(ed, "file_path", "").lower().endswith((".yaml", ".yml")):
            QMessageBox.information(
                self, "Generate from YAML",
                "Open a .yaml spec file in the editor first, then press Generate (F6).\n"
                "Tip: File \u2192 New File \u2192 YAML spec.")
            return
        self._write(ed)   # save the spec first
        try:
            files = yaml_gen.generate(ed.toPlainText())
        except yaml_gen.SpecError as e:
            QMessageBox.warning(self, "Generate from YAML", str(e)); return
        self._write_generated(files)

    def import_yaml(self):
        """Generate from a YAML file chosen on disk (Tools menu)."""
        if not self.project:
            QMessageBox.information(self, "Generate from YAML",
                                    "Create or open a project first."); return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a YAML spec", self.project.root, "YAML (*.yaml *.yml);;All (*)")
        if not path:
            return
        try:
            with open(path) as fh:
                files = yaml_gen.generate(fh.read())
        except (yaml_gen.SpecError, OSError) as e:
            QMessageBox.warning(self, "Generate from YAML", str(e)); return
        self._write_generated(files)

    def _write_generated(self, files: dict):
        os.makedirs(self.project.src_dir, exist_ok=True)
        written, skipped = [], []
        for fname, src in files.items():
            dest = os.path.join(self.project.src_dir, fname)
            if os.path.exists(dest):
                skipped.append(fname); continue
            with open(dest, "w") as fh:
                fh.write(src)
            written.append(dest)
        self.refresh_explorer()
        for d in written:
            self.open_path(d)
        msg = f"Generated {len(written)} file(s) in src/."
        if skipped:
            msg += f"\nSkipped (already exist): {', '.join(skipped)}"
        QMessageBox.information(self, "Generate from YAML", msg)

    # ---- logging -------------------------------------------------------
    def _open_log(self):
        self._close_log()
        if self.project:
            try:
                self._log_fh = open(
                    os.path.join(self.project.logs_dir, f"{self.project.name}.log"), "a")
            except OSError:
                self._log_fh = None

    def _close_log(self):
        if self._log_fh:
            try:
                self._log_fh.close()
            except OSError:
                pass
            self._log_fh = None

    def _on_log_line(self, text, sev):
        self.console.append_line(text, sev)
        if self._log_fh:
            self._log_fh.write(f"[{sev.upper():<8}] {text}\n")
        from .log_parser import parse_diagnostic
        d = parse_diagnostic(text)
        if d:
            self._run_diags.append(d)

    # ---- top module ----------------------------------------------------
    def _refresh_top_combo(self):
        if not hasattr(self, "top_combo"):
            return
        from . import vscan
        mods = vscan.all_modules(self.project.source_files()) if self.project else []
        self.top_combo.blockSignals(True)
        self.top_combo.clear()
        self.top_combo.addItem("(auto)")
        self.top_combo.addItems(mods)
        cur = self.project.top if self.project else None
        if cur and cur in mods:
            self.top_combo.setCurrentText(cur)
        else:
            self.top_combo.setCurrentIndex(0)
        self.top_combo.blockSignals(False)

    def _top_combo_changed(self, text):
        if not self.project:
            return
        self.set_top_module(None if text == "(auto)" else text)

    def set_top_module(self, module):
        if not self.project:
            return
        self.project.top = module or None
        self.project.write_manifest()
        self._refresh_top_combo()
        self.refresh_explorer()
        if module:
            self.statusBar().showMessage(f"Top module: '{module}'", 4000)

    def choose_top_module(self):
        if not self.project:
            QMessageBox.information(self, "Top Module", "Open a project first."); return
        from . import vscan
        mods = vscan.all_modules(self.project.source_files())
        if not mods:
            QMessageBox.information(self, "Top Module",
                                    "No modules found in the project's sources."); return
        options = ["(auto — let iverilog decide)"] + mods
        from PySide6.QtWidgets import QInputDialog
        cur = self.project.top
        start = options.index(cur) if cur in mods else 0
        choice, ok = QInputDialog.getItem(
            self, "Select Top Module",
            "Top module (RTL or testbench — simulation starts here):",
            options, start, False)
        if ok:
            self.set_top_module(None if choice.startswith("(auto") else choice)

    # ---- waveform ------------------------------------------------------
    def _wave_path(self):
        if not self.project:
            return None
        cands = [os.path.join(self.project.sim_dir, "wave.vcd")]
        # also accept any *.vcd in sim/
        if os.path.isdir(self.project.sim_dir):
            for fn in os.listdir(self.project.sim_dir):
                if fn.lower().endswith((".vcd", ".fst")):
                    cands.append(os.path.join(self.project.sim_dir, fn))
        for c in cands:
            if os.path.isfile(c):
                return c
        return None

    def view_waveform(self):
        if not self.project:
            QMessageBox.information(self, "Waveform", "Open a project first."); return
        # Re-run the simulation first so the waveform always reflects the current
        # source. If the testbench no longer dumps (e.g. $dumpvars commented out),
        # no fresh VCD is produced and the viewer opens empty.
        old = self._wave_path()
        if old and os.path.isfile(old):
            try:
                os.remove(old)
            except OSError:
                pass
        self._pending_wave = True
        self.simulate()

    def _show_waveform_now(self):
        path = self._wave_path()
        if getattr(self, "wave_win", None) is None:
            self.wave_win = WaveformWindow()
            self.wave_win._gtk.clicked.connect(self.open_in_gtkwave)
            self.wave_win.apply_chrome(self._chrome(), self._is_light())
        if path:
            self.wave_win.load(path)
            self.statusBar().showMessage(f"Loaded {os.path.basename(path)}", 4000)
        else:
            # no dump produced -> show empty viewer and tell the user why
            self.wave_win.vcd = None
            self.wave_win.avail.clear()
            self.wave_win._rows_data = []
            self.wave_win.canvas.sel = -1
            self.wave_win.canvas.set_rows(None, [])
            QMessageBox.information(
                self.wave_win, "No waveform data",
                "The simulation produced no VCD. Make sure your testbench calls\n"
                "$dumpfile(\"wave.vcd\"); and $dumpvars(0, <tb>);")
        self.wave_win.show()
        self.wave_win.raise_()
        self.wave_win.activateWindow()

    def open_in_gtkwave(self):
        path = self._wave_path()
        if not path:
            return
        import shutil as _sh
        import subprocess
        if not _sh.which("gtkwave"):
            QMessageBox.information(self, "GTKWave",
                                    "GTKWave is not installed.\n"
                                    "Install it with:  sudo apt install gtkwave")
            return
        try:
            subprocess.Popen(["gtkwave", path])
        except OSError as e:
            QMessageBox.warning(self, "GTKWave", str(e))

    def _is_light(self):
        from .theme import is_light
        return is_light(self.appearance["theme"])

    # ---- simulation ----------------------------------------------------
    def simulate(self):
        self.save_all_dirty()
        if self.project:
            files = self.project.source_files()
            if not files:
                QMessageBox.information(self, "Simulate",
                                        "No .v/.sv source files in this project yet."); return
            self.project.ensure_dirs()
            work = self.project.root
        else:
            ed = self.current_editor()
            if not ed:
                QMessageBox.information(self, "Simulate", "Open a file first."); return
            work = tempfile.mkdtemp(prefix="rtlsim_")
            self._scratch_dir = work
            scratch = os.path.join(work, "design.v")
            with open(scratch, "w") as fh:
                fh.write(ed.toPlainText())
            files = [scratch]

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._run_diags = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if hasattr(w, "clear_diagnostics"):
                w.clear_diagnostics()
        self._open_log()
        if self._log_fh:
            self._log_fh.write(f"\n===== Run {ts} =====\n")
        top = self.project.top if self.project else None
        proj_name = self.project.name if self.project else "scratch"
        src_count = len(files)
        self.console.set_stage("compile")
        self.console.append_header(
            f"VeriForge Simulation Run  ·  {ts}\n"
            f"  Project : {proj_name}\n"
            f"  Top     : {top or '(auto)'}\n"
            f"  Sources : {src_count} file(s)\n"
            f"  Tool    : iverilog -g2012  →  vvp"
        )
        self.stop_act.setEnabled(True)
        self._start_spinner()
        self.sim.run(files, work, has_testbench(files), top)

    def stop(self):
        self.sim.stop()

    def _on_finished(self, ok, stats):
        self.console.append_summary(ok, stats)
        if self._log_fh:
            self._log_fh.write(
                f"[{'OK' if ok else 'ERROR':<8}] Status: {'PASSED' if ok else 'FAILED'}  "
                f"Errors: {stats['errors']}  Warnings: {stats['warnings']}  "
                f"Elapsed: {stats['elapsed_ms']/1000:.2f}s\n")
            self._close_log()
        if self._scratch_dir:
            shutil.rmtree(self._scratch_dir, ignore_errors=True)
            self._scratch_dir = None
        self._stop_spinner()
        self.stop_act.setEnabled(False)
        self._set_state("passed" if ok else "failed")
        self.refresh_explorer()
        self._apply_diagnostics()
        # if View Waveform triggered this run, open the viewer now
        if getattr(self, "_pending_wave", False):
            self._pending_wave = False
            self._show_waveform_now()
        elif getattr(self, "wave_win", None) is not None and self.wave_win.isVisible() and ok:
            wp = self._wave_path()
            if wp:
                self.wave_win.load(wp)

    def _apply_diagnostics(self):
        """Route collected compiler diagnostics to the matching open editor tabs."""
        by_base = {}
        for d in getattr(self, "_run_diags", []):
            by_base.setdefault(os.path.basename(d["file"]), []).append(d)
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            fp = getattr(w, "file_path", None)
            if fp and hasattr(w, "set_diagnostics"):
                w.set_diagnostics(by_base.get(os.path.basename(fp), []))

    def _set_state(self, key):
        self._state_key = key
        text, color = _BADGE.get(key, _BADGE["idle"])
        self.badge.setText(f"  \u25cf  {text}  ")
        self.badge.setStyleSheet(f"color:{color};font-weight:bold;")

    def open_help(self):
        if not hasattr(self, "_help_win") or self._help_win is None:
            self._help_win = HelpWindow(None, chrome=self._chrome())
        self._help_win.show()
        self._help_win.raise_()
        self._help_win.activateWindow()

    def about(self):
        QMessageBox.about(self, "About VeriForge",
                          "VeriForge — RTL Design & Simulation IDE\n\n"
                          "Built on Icarus Verilog + PySide6.\n"
                          "Supports Verilog 2001 and SystemVerilog-2012.\n\n"
                          "Features: tabbed editor · built-in waveform viewer ·\n"
                          "YAML code generation · TCL console · 6 themes.\n\n"
                          "Press F1 for full help.")

    def closeEvent(self, event):
        super().closeEvent(event)
