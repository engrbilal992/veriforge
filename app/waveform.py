
import os
import re
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QTreeWidget,
                               QTreeWidgetItem, QLabel, QToolButton, QPushButton,
                               QFileDialog, QMessageBox, QMenu, QColorDialog,
                               QMainWindow, QScrollArea, QLineEdit, QSplitter,
                               QAbstractItemView)
from PySide6.QtGui import (QPainter, QPen, QColor, QFont, QFontMetrics, QPixmap)
from PySide6.QtCore import Qt, Signal, QSize

from .vcd import VCD

RADII = ["bin", "hex", "dec", "signed", "octal", "ascii"]
_DEFAULT_SIG = "#22e06a"
NAME_W = 200          # width of the name gutter inside the canvas


def _parse_time_str(s: str, base_unit: str) -> int | None:
    """Parse a time string like '10ns', '50 ps', '1.5us' into timescale ticks."""
    s = s.strip()
    m = re.match(r'^([\d.]+)\s*(fs|ps|ns|us|ms|s)?$', s, re.I)
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or base_unit).lower()
    base_f = _UNIT_FACTOR.get(base_unit, 1e-9)
    unit_f = _UNIT_FACTOR.get(unit, base_f)
    return int(val * unit_f / base_f)


def fmt_value(bits: str, radix: str) -> str:
    """Format a bus value string per radix. Non-2-state stays as-is (uppercased)."""
    if any(ch in bits for ch in "xzXZ"):
        return bits.upper()
    try:
        n = int(bits, 2)
    except ValueError:
        return bits
    w = len(bits)
    if radix == "hex":
        return "0x" + format(n, "X")
    if radix == "dec":
        return str(n)
    if radix == "signed":
        if w and bits[0] == "1":
            n -= 1 << w
        return str(n)
    if radix == "octal":
        return "0o" + format(n, "o")
    if radix == "ascii":
        try:
            return repr(bytes.fromhex(format(n, "0{}x".format((w + 7) // 8 * 2)))
                        .decode("latin-1"))
        except Exception:
            return "0x" + format(n, "X")
    return bits  # bin


# timescale unit ladder for axis labels
_UNIT_ORDER = ["s", "ms", "us", "ns", "ps", "fs"]
_UNIT_FACTOR = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "ps": 1e-12, "fs": 1e-15}


def _scaled_time_label(t_units, base_unit):
    """Given a time in `base_unit` timescale ticks, pick a human unit/label.
    Returns a string like '12 ns' or '3.5 us'."""
    seconds = t_units * _UNIT_FACTOR.get(base_unit, 1e-9)
    if seconds == 0:
        return f"0 {base_unit}"
    for u in _UNIT_ORDER:                       # largest -> smallest
        v = seconds / _UNIT_FACTOR[u]
        if abs(v) >= 1:
            if v == int(v):
                return f"{int(v)} {u}"
            return f"{v:.3g} {u}"
    return f"{seconds:.3g} s"


class _Canvas(QWidget):
    cursorMoved = Signal(int)
    markersChanged = Signal(list)
    selectionChanged = Signal(int)          # selected row index (-1 none)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.vcd = None
        self.rows = []                       # list of dict(signal, radix, color)
        self.t0 = 0.0                        # left-edge time (in timescale ticks)
        self.px_per_unit = 2.0
        self.cursor_t = 0
        self.markers = []
        self.row_h = 30
        self.sel = -1                        # selected row index
        self._drag = None                    # (start_x, start_t0) while panning
        self._light = False
        self.set_theme(False)

    def set_theme(self, light: bool):
        self._light = light
        if light:
            self._c = {"bg": "#f5f5f5", "grid": "#e0e8f0", "text": "#1a1a2e",
                       "cursor": "#e53935", "marker": "#1565c0", "muted": "#90a4ae",
                       "row": "#eeeeee", "sig": "#00b84a", "gutter": "#e8ecf2",
                       "sel": "#c8e6c9", "end": "#90a4ae"}
        else:
            # Pure black/green matrix aesthetic
            self._c = {"bg": "#000000", "grid": "#0a1a0a", "text": "#00e676",
                       "cursor": "#ff1744", "marker": "#ffd600", "muted": "#1b5e20",
                       "row": "#020d02", "sig": "#00e676", "gutter": "#050e05",
                       "sel": "#0a2e0a", "end": "#1b5e20"}
        self.update()

    def set_rows(self, vcd, rows):
        self.vcd = vcd
        self.rows = rows
        if self.sel >= len(rows):
            self.sel = -1
        self.setMinimumHeight(max(140, len(rows) * self.row_h + 26))
        self._update_width()
        self.update()

    #def _update_width(self):
        # widen so a horizontal scrollbar appears when zoomed in
     #   end = self.vcd.end_time if self.vcd else 0
      #  need = NAME_W + int(end * self.px_per_unit) + 40
       # self.setMinimumWidth(max(need, 400))
       
    def _update_width(self):
    	end = self.vcd.end_time if self.vcd else 0
    	
    	need = NAME_W + int(end * self.px_per_unit)
    	self.setMinimumWidth(max(need, NAME_W + 50))

    # ---- coordinate helpers (wave area starts at NAME_W) ---------------
    def t_to_x(self, t): return NAME_W + (t - self.t0) * self.px_per_unit
    def x_to_t(self, x): return self.t0 + (x - NAME_W) / self.px_per_unit
    
    # def max_t0(self):
    # 	if not self.vcd:
    # 	   return 0
    # 	   visible_time = (self.width() - NAME_W) / self.px_per_unit
    # 	   return max(0,self.vcd.end_time - visible_time)

    def max_t0(self):
        if not self.vcd:
            return 0

        visible_time = (self.width() - NAME_W) / self.px_per_unit

        return max(
            0,
            self.vcd.end_time - visible_time
        )

    def zoom(self, factor, anchor_x=None):
        if anchor_x is None or anchor_x < NAME_W:
            anchor_x = NAME_W + (self.width() - NAME_W) / 2
        at = self.x_to_t(anchor_x)
        self.px_per_unit = max(1e-5, min(1e6, self.px_per_unit * factor))
        self.t0 = max(0, at - (anchor_x - NAME_W) / self.px_per_unit)
        self._update_width()
        self.update()

    def zoom_fit(self):
        if self.vcd and self.vcd.end_time:
            self.t0 = 0
            avail = max(200, self.width() - NAME_W - 20)
            self.px_per_unit = avail / self.vcd.end_time
            self._update_width()
            self.update()

   # def pan_to(self, t0):
        #self.t0 = max(0, t0)
       # self.update()
       
    def pan_to(self, t0):
       self.t0 = max(0, min(t0, self.max_t0()))
       self.update()

    # ---- interaction ---------------------------------------------------
    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.zoom(1.25 if e.angleDelta().y() > 0 else 1/1.25, e.position().x())
            e.accept(); return
        if e.modifiers() & Qt.ShiftModifier:
            self.t0 = max(0, self.t0 - e.angleDelta().y() / self.px_per_unit)
            self.update(); e.accept(); return
        e.ignore()      # vertical scroll handled by the scroll area

    def mousePressEvent(self, e):
        x = e.position().x(); y = e.position().y()
        if x < NAME_W:
            # click in the name gutter -> select the row
            idx = int((y - 22) // self.row_h)
            if 0 <= idx < len(self.rows):
                self.sel = idx
                self.selectionChanged.emit(idx)
                self.setFocus()
                self.update()
            return
        t = max(0, int(round(self.x_to_t(x))))
        if e.modifiers() & Qt.ControlModifier:
            self.markers.append(t); self.markersChanged.emit(self.markers)
        else:
            # also select row by vertical position
            idx = int((y - 22) // self.row_h)
            if 0 <= idx < len(self.rows):
                self.sel = idx; self.selectionChanged.emit(idx)
            self.cursor_t = t; self.cursorMoved.emit(t)
            self._drag = (x, self.t0, t)     # enable drag-pan
        self.setFocus()
        self.update()

    #def mouseMoveEvent(self, e):
     #   if self._drag and (e.buttons() & Qt.LeftButton):
      #      start_x, start_t0, _ = self._drag
       #     dx = e.position().x() - start_x
        #    self.t0 = max(0, start_t0 - dx / self.px_per_unit)
         #   self.update()
    def mouseMoveEvent(self, e):
        if self._drag and (e.buttons() & Qt.LeftButton):
            start_x, start_t0, _ = self._drag
            dx = e.position().x() - start_x

            new_t0 = start_t0 - dx / self.px_per_unit

            self.t0 = max(
                0,
                min(new_t0, self.max_t0())
            )

            self.update()

    def mouseReleaseEvent(self, e):
        # if it was basically a click (no real drag), keep the cursor where set
        self._drag = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Tab:
            self._jump_edge(forward=True); e.accept(); return
        if e.key() == Qt.Key_Backtab:
            self._jump_edge(forward=False); e.accept(); return
        if e.key() == Qt.Key_Right:
            self._jump_edge(forward=True); e.accept(); return
        if e.key() == Qt.Key_Left:
            self._jump_edge(forward=False); e.accept(); return
        super().keyPressEvent(e)

    def _jump_edge(self, forward=True):
        if not (0 <= self.sel < len(self.rows)):
            return
        sig = self.rows[self.sel]["signal"]
        times = [t for t, _ in sig.changes]
        if not times:
            return
        if forward:
            nxt = next((t for t in times if t > self.cursor_t), None)
        else:
            prevs = [t for t in times if t < self.cursor_t]
            nxt = prevs[-1] if prevs else None
        if nxt is not None:
            self.cursor_t = nxt
            self.cursorMoved.emit(nxt)
            # keep cursor in view
            x = self.t_to_x(nxt)
            if x < NAME_W or x > self.width():
                self.t0 = max(0, nxt - (self.width() - NAME_W) / (2 * self.px_per_unit))
            self.update()

    def clear_markers(self):
        self.markers = []; self.markersChanged.emit(self.markers); self.update()

    def sizeHint(self):
        return QSize(800, max(140, len(self.rows) * self.row_h + 26))

    # ---- painting ------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        c = self._c
        p.fillRect(self.rect(), QColor(c["bg"]))
        if not self.rows:
            p.setPen(QColor(c["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Add signals from the left to display waveforms.")
            p.end(); return

        f = QFont("monospace"); f.setPointSize(9); p.setFont(f)
        fm = QFontMetrics(f)
        t_left = self.x_to_t(NAME_W); t_right = self.x_to_t(self.width())

        # row backgrounds + selection highlight (full width)
        y = 22
        for i, _row in enumerate(self.rows):
            if i == self.sel:
                p.fillRect(0, y, self.width(), self.row_h, QColor(c["sel"]))
            elif i % 2:
                p.fillRect(0, y, self.width(), self.row_h, QColor(c["row"]))
            y += self.row_h

        self._grid(p, t_left, t_right, fm)

        # name gutter background + divider
        p.fillRect(0, 0, NAME_W, self.height(), QColor(c["gutter"]))
        p.setPen(QColor(c["grid"])); p.drawLine(NAME_W, 0, NAME_W, self.height())

        y = 22
        for i, row in enumerate(self.rows):
            self._row_name(p, row, i, y, fm)
            self._signal(p, row, y, t_left, t_right, fm)
            y += self.row_h

        # markers + cursor (only in wave area)
        for m in self.markers:
            mx = self.t_to_x(m)
            if NAME_W <= mx <= self.width():
                p.setPen(QPen(QColor(c["marker"]), 1, Qt.DashLine))
                p.drawLine(int(mx), 18, int(mx), self.height())
        cx = self.t_to_x(self.cursor_t)
        if NAME_W <= cx <= self.width():
            p.setPen(QPen(QColor(c["cursor"]), 1))
            p.drawLine(int(cx), 0, int(cx), self.height())
        # end-of-simulation boundary line
        if self.vcd and self.vcd.end_time:
            ex = self.t_to_x(self.vcd.end_time)
            if NAME_W <= ex <= self.width():
                p.setPen(QPen(QColor(c["muted"]), 1, Qt.DotLine))
                p.drawLine(int(ex), 18, int(ex), self.height())
        p.end()

    # def _row_name(self, p, row, idx, y, fm):
    #     c = self._c
    #     sig = row["signal"]
    #     name = sig.name.split(".")[-1] + (f"[{sig.width-1}:0]" if sig.width > 1 else "")
    #     # value at cursor, shown after the name
    #     val = sig.value_at(self.cursor_t)
    #     if val is not None:
    #         vtxt = fmt_value(val, row["radix"]) if sig.width > 1 else val
    #     else:
    #         vtxt = "-"
    #     # p.setPen(QColor(row["color"] if idx == self.sel else c["text"]))
    #     if idx == self.sel:
    #         p.setPen(QColor(row["color"]))
    #     else:
    #         p.setPen(QColor(c["text"]))
    #     p.drawText(8, y + self.row_h // 2 + 4, name)
    #     p.setPen(QColor(c["muted"]))
    #     p.drawText(8, y + self.row_h - 3, f"= {vtxt}")

    def _row_name(self, p, row, idx, y, fm):
        c = self._c
        sig = row["signal"]

        name = sig.name.split(".")[-1]

        if sig.width > 1:
            name += f"[{sig.width-1}:0]"

        val = sig.value_at(self.cursor_t)

        if val is not None:
            if sig.width > 1:
                vtxt = fmt_value(val, row["radix"])
            else:
                vtxt = val
        else:
            vtxt = "-"

        # signal name
        p.setPen(QColor(row["color"] if idx == self.sel else c["text"]))
        p.drawText(
            8,
            y + 13,
            name
        )

        # current value
        p.setPen(QColor(c["muted"]))
        p.drawText(
            8,
            y + 26,
            "= " + vtxt
        )

    def _grid(self, p, t_left, t_right, fm):
        c = self._c
        step = self._nice_step()
        base = self.vcd.timescale[1] if self.vcd else "ns"
        t = (int(t_left) // step) * step
        while t <= t_right:
            x = self.t_to_x(t)
            if x >= NAME_W:
                p.setPen(QColor(c["grid"])); p.drawLine(int(x), 18, int(x), self.height())
                p.setPen(QColor(c["muted"]))
                p.drawText(int(x) + 3, 13, _scaled_time_label(t, base))
            t += step

    def _nice_step(self):
        target = 100 / self.px_per_unit
        mag = 1
        while mag * 10 < target:
            mag *= 10
        for m in (1, 2, 5, 10):
            if mag * m >= target:
                return max(1, mag * m)
        return max(1, mag * 10)

    def _signal(self, p, row, y, t_left, t_right, fm):
        c = self._c
        sig = row["signal"]; color = row["color"]; radix = row["radix"]
        top = y + 5; bot = y + self.row_h - 7; mid = (top + bot) // 2
        end_t = self.vcd.end_time if (self.vcd and self.vcd.end_time) else t_right
        t_right = min(t_right, end_t)
        if not sig.changes:
            x_end = min(int(self.t_to_x(end_t)), self.width())
            if x_end > NAME_W:
                p.setPen(QColor(c["muted"])); p.drawLine(NAME_W, mid, x_end, mid)
            return
        is_bus = sig.width > 1
        prev = None
        for ct, cv in sig.changes:
            if ct <= t_left: prev = cv
            else: break
        seq = [(self.t_to_x(max(t_left, 0)), prev)]
        for ct, cv in sig.changes:
            if t_left <= ct <= t_right:
                seq.append((self.t_to_x(ct), cv))
        seq.append((self.t_to_x(t_right), None))

        # Merge transitions that fall within the same pixel column.
        # Any remaining same-timestamp or sub-pixel changes are collapsed to the
        # final value in that pixel, matching GTKWave's rendering behaviour.
        merged = [list(seq[0])]
        for x, v in seq[1:]:
            if v is None:
                merged.append([x, v])
            elif int(x) == int(merged[-1][0]):
                merged[-1] = [x, v]
            else:
                merged.append([x, v])
        seq = merged

        base = QColor(color)
        prev_v = None   # last drawn value — used to suppress same-value transitions
        for i in range(len(seq) - 1):
            x1, v1 = seq[i]; x2, _ = seq[i + 1]
            if v1 is None:
                prev_v = None
                continue
            x1 = max(x1, NAME_W)
            if x2 <= NAME_W:
                prev_v = v1
                continue
            # Draw a vertical transition edge only when:
            #   • this is not the initial-state segment (i > 0), and
            #   • the value actually changed from the previous segment.
            # This suppresses (a) the false edge at the left gutter boundary and
            # (b) the "ghost spike" produced by same-value redundant VCD entries.
            draw_left = (i > 0) and (v1 != prev_v)
            if is_bus:
                self._bus(p, x1, x2, top, bot, mid, v1, radix, fm, base, draw_left)
            else:
                self._bit(p, x1, x2, top, bot, mid, v1, base, draw_left)
            prev_v = v1

    def _bit(self, p, x1, x2, top, bot, mid, v, base, draw_left=True):
        if v == "x":
            p.setPen(QPen(QColor("#ff5555"), 1.8))
            p.drawLine(int(x1), top, int(x2), bot); p.drawLine(int(x1), bot, int(x2), top); return
        if v == "z":
            p.setPen(QPen(QColor("#4f9dff"), 1.8))
            p.drawLine(int(x1), mid, int(x2), mid); return
        p.setPen(QPen(base, 1.7))
        lvl = top if v == "1" else bot
        p.drawLine(int(x1), lvl, int(x2), lvl)
        if draw_left:
            p.drawLine(int(x1), top, int(x1), bot)

    def _bus(self, p, x1, x2, top, bot, mid, bits, radix, fm, base, draw_left=True):
        has_x = "x" in bits.lower(); has_z = "z" in bits.lower()
        col = QColor("#ff5555") if has_x else (QColor("#4f9dff") if has_z else base)
        p.setPen(QPen(col, 1.7))
        if draw_left:
            p.drawLine(int(x1), mid, int(x1)+3, top); p.drawLine(int(x1), mid, int(x1)+3, bot)
            top_start = int(x1)+3
        else:
            top_start = int(x1)
        p.drawLine(top_start, top, int(x2)-3, top); p.drawLine(top_start, bot, int(x2)-3, bot)
        p.drawLine(int(x2)-3, top, int(x2), mid); p.drawLine(int(x2)-3, bot, int(x2), mid)
        label = fmt_value(bits, radix)
        if (x2 - x1) > fm.horizontalAdvance(label) + 8:
            p.setPen(QColor(self._c["text"])); p.drawText(int(x1)+6, mid+4, label)


class _ScrollArea(QScrollArea):
    """Scroll area that forwards Ctrl+wheel to the canvas for zoom."""
    def __init__(self, canvas):
        super().__init__()
        self._canvas = canvas

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            pos = self._canvas.mapFromGlobal(e.globalPosition().toPoint())
            self._canvas.zoom(
                1.25 if e.angleDelta().y() > 0 else 1 / 1.25,
                pos.x()
            )
            e.accept()
        else:
            super().wheelEvent(e)


class WaveformWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(None)            # independent top-level window (tileable)
        self.setWindowTitle("VeriForge — Waveforms")
        self.setWindowFlags(Qt.Window)
        self.resize(1150, 660)
        self.setMinimumSize(480, 320)
        self.vcd = None
        self._path = None
        self._rows_data = []

        # left: search + grouped available tree
        self.search = QLineEdit(); self.search.setPlaceholderText("Search signals\u2026")
        self.search.textChanged.connect(self._filter_avail)
        self.search.setClearButtonEnabled(True)
        self.avail = QTreeWidget(); self.avail.setHeaderHidden(True)
        self.avail.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.avail.itemDoubleClicked.connect(self._avail_double)
        add_btn = QPushButton("Add \u2192"); add_btn.clicked.connect(self.add_selected)
        addall_btn = QPushButton("Add all"); addall_btn.clicked.connect(self.add_all)
        lbtns = QHBoxLayout(); lbtns.addWidget(add_btn); lbtns.addWidget(addall_btn)
        ltop = QLabel("Signals")
        left = QVBoxLayout(); left.setContentsMargins(6, 6, 3, 6)
        left.addWidget(ltop); left.addWidget(self.search)
        left.addWidget(self.avail, 1); left.addLayout(lbtns)
        lbox = QWidget(); lbox.setLayout(left)
        lbox.setMinimumWidth(180); lbox.setMaximumWidth(340)

        # canvas in a scroll area
        self.canvas = _Canvas()
        self.canvas.cursorMoved.connect(self._cursor)
        self.canvas.markersChanged.connect(self._markers)
        self.canvas.selectionChanged.connect(self._on_select)
        self.scroll = _ScrollArea(self.canvas)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.canvas)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        bar = QHBoxLayout()
        self._zin = QToolButton(); self._zin.setText("+")
        self._zout = QToolButton(); self._zout.setText("\u2013")
        self._zfit = QToolButton(); self._zfit.setText("Fit")
        self._up = QToolButton(); self._up.setText("\u2191"); self._up.setToolTip("Move signal up")
        self._dn = QToolButton(); self._dn.setText("\u2193"); self._dn.setToolTip("Move signal down")
        self._zin.clicked.connect(lambda: self.canvas.zoom(1.3))
        self._zout.clicked.connect(lambda: self.canvas.zoom(1/1.3))
        # self._zfit.clicked.connect(self.canvas.zoom_fit)
        self._zfit.clicked.connect(self.fit_waveform)
        self._up.clicked.connect(lambda: self._move_sel(-1))
        self._dn.clicked.connect(lambda: self._move_sel(1))
        self._addm = QPushButton("Add marker"); self._addm.clicked.connect(self._add_marker_at_cursor)
        self._clrm = QPushButton("Clear markers"); self._clrm.clicked.connect(self.canvas.clear_markers)
        self._png = QPushButton("Export PNG"); self._png.clicked.connect(self.export_png)
        self._csv = QPushButton("Export CSV"); self._csv.clicked.connect(self.export_csv)
        self._gtk = QPushButton("Open in GTKWave")
        self.cursor_lbl = QLabel("cursor: -"); self.delta_lbl = QLabel("")
        for w in (self._zin, self._zout, self._zfit, self._up, self._dn): bar.addWidget(w)
        bar.addWidget(self.cursor_lbl); bar.addWidget(self.delta_lbl)
        bar.addStretch()
        for w in (self._addm, self._clrm, self._png, self._csv, self._gtk): bar.addWidget(w)

        # ── time window row ──────────────────────────────────────────────
        tbar = QHBoxLayout(); tbar.setSpacing(4)
        tbar.addWidget(QLabel("Window:"))
        self._tw_from = QLineEdit(); self._tw_from.setPlaceholderText("From  e.g. 0ns")
        self._tw_from.setFixedWidth(110)
        self._tw_to   = QLineEdit(); self._tw_to.setPlaceholderText("To  e.g. 200ns")
        self._tw_to.setFixedWidth(110)
        self._tw_apply = QPushButton("Apply")
        self._tw_apply.setFixedWidth(60)
        self._tw_apply.clicked.connect(self._apply_time_window)
        self._tw_reset = QPushButton("Full")
        self._tw_reset.setFixedWidth(50)
        self._tw_reset.clicked.connect(self.fit_waveform)
        tbar.addWidget(self._tw_from); tbar.addWidget(QLabel("→"))
        tbar.addWidget(self._tw_to)
        tbar.addWidget(self._tw_apply); tbar.addWidget(self._tw_reset)
        tbar.addStretch()

        right = QVBoxLayout(); right.setContentsMargins(3, 6, 6, 6)
        right.addLayout(bar); right.addLayout(tbar); right.addWidget(self.scroll, 1)
        rb = QWidget(); rb.setLayout(right)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(lbox); split.addWidget(rb)
        split.setStretchFactor(1, 1); split.setSizes([260, 880])
        self.setCentralWidget(split)
        self._lbl_widgets = [ltop]

    # ---- chrome --------------------------------------------------------
    def apply_chrome(self, c, light):
        self.setStyleSheet(
            f"QMainWindow,QWidget{{background:{c['win']};color:{c['text']};}}"
            f"QTreeWidget,QLineEdit{{background:{c['panel']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:6px;padding:4px;}}"
            f"QPushButton{{background:{c['accent']};color:{c['on_accent']};border:none;"
            f"border-radius:6px;padding:6px 12px;}}"
            f"QPushButton:hover{{background:{c['accent_hi']};}}"
            f"QToolButton{{background:{c['panel']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:4px;min-width:26px;min-height:22px;}}"
            f"QToolButton:hover{{background:{c['hover']};}}"
            f"QLabel{{color:{c['muted']};padding:0 8px;}}")
        self.canvas.set_theme(light)

    # ---- load + tree ---------------------------------------------------
    def load(self, path):
        try:
            self.vcd = VCD.parse_file(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Waveform", f"Could not read VCD:\n{e}"); return False
        self._path = path
        self._rows_data = []
        self._build_tree("")
        self.canvas.sel = -1
        self.canvas.set_rows(self.vcd, [])
        return True

    def _build_tree(self, filter_text):
        self.avail.clear()
        ft = filter_text.lower().strip()
        scope_items = {}

        def scope_item(parts):
            if not parts:
                return None
            key = tuple(parts)
            if key in scope_items:
                return scope_items[key]
            parent = scope_item(parts[:-1])
            node = QTreeWidgetItem([parts[-1]])
            if parent is None:
                self.avail.addTopLevelItem(node)
            else:
                parent.addChild(node)
            node.setExpanded(True)
            scope_items[key] = node
            return node

        for s in (self.vcd.signals if self.vcd else []):
            if ft and ft not in s.name.lower():
                continue
            parts = s.name.split(".")
            leaf = parts[-1] + (f" [{s.width-1}:0]" if s.width > 1 else "")
            item = QTreeWidgetItem([leaf]); item.setData(0, Qt.UserRole, s)
            parent = scope_item(parts[:-1])
            (parent.addChild(item) if parent else self.avail.addTopLevelItem(item))

    def _filter_avail(self, text):
        self._build_tree(text)

    def has_signals(self):
        return bool(self.vcd and self.vcd.signals)

    # ---- add / remove / reorder ----------------------------------------
    def _avail_double(self, item, _col=0):
        if item.data(0, Qt.UserRole) is not None:
            self._add_signal(item.data(0, Qt.UserRole)); self._refresh()
        else:
            item.setExpanded(not item.isExpanded())

    def _selected_signals(self, item=None):
        sigs = []
        items = self.avail.selectedItems() if item is None else [item]
        for it in items:
            sig = it.data(0, Qt.UserRole)
            if sig is not None:
                sigs.append(sig)
            else:
                for i in range(it.childCount()):
                    sigs.extend(self._selected_signals(it.child(i)))
        return sigs

    def add_selected(self):
        for sig in self._selected_signals():
            self._add_signal(sig)
        self._refresh()

    def add_all(self):
        for s in (self.vcd.signals if self.vcd else []):
            self._add_signal(s)
        self._refresh()

    def _add_signal(self, sig):
        if any(r["signal"] is sig for r in self._rows_data):
            return
        self._rows_data.append({"signal": sig,
                                "radix": "hex" if sig.width > 1 else "bin",
                                "color": _DEFAULT_SIG})

    def remove_selected(self):
        i = self.canvas.sel
        if 0 <= i < len(self._rows_data):
            del self._rows_data[i]
            self.canvas.sel = min(i, len(self._rows_data) - 1)
            self._refresh()

    def _move_sel(self, delta):
        i = self.canvas.sel
        j = i + delta
        if 0 <= i < len(self._rows_data) and 0 <= j < len(self._rows_data):
            self._rows_data[i], self._rows_data[j] = self._rows_data[j], self._rows_data[i]
            self.canvas.sel = j
            self._refresh()

    def _refresh(self):
        self.canvas.set_rows(self.vcd, self._rows_data)

    def _on_select(self, idx):
        pass     # selection lives in the canvas; hook kept for future use

    # ---- context menu (radix / colour / remove / reorder) --------------
    def contextMenuEvent(self, ev):
        # right-click on the canvas name gutter -> per-signal menu
        pos = self.canvas.mapFrom(self, ev.pos())
        if not self.canvas.rect().contains(pos):
            return
        idx = int((pos.y() - 22) // self.canvas.row_h)
        if not (0 <= idx < len(self._rows_data)):
            return
        self.canvas.sel = idx; self.canvas.update()
        row = self._rows_data[idx]
        menu = QMenu(self)
        rmenu = menu.addMenu("Radix")
        for r in RADII:
            a = rmenu.addAction(r.capitalize()); a.setCheckable(True)
            a.setChecked(row["radix"] == r)
            a.triggered.connect(lambda _=False, rr=r, mm=row: self._set_radix(mm, rr))
        menu.addAction("Set colour\u2026", lambda mm=row: self._set_color(mm))
        menu.addSeparator()
        menu.addAction("Move up", lambda: self._move_sel(-1))
        menu.addAction("Move down", lambda: self._move_sel(1))
        menu.addAction("Remove", self.remove_selected)
        menu.exec(ev.globalPos())

    def _set_radix(self, row, r):
        row["radix"] = r; self._refresh()

    def _set_color(self, row):
        col = QColorDialog.getColor(QColor(row["color"]), self, "Signal colour")
        if col.isValid():
            row["color"] = col.name(); self._refresh()

    # ---- markers / cursor ----------------------------------------------
    def _add_marker_at_cursor(self):
        self.canvas.markers.append(self.canvas.cursor_t)
        self.canvas.markersChanged.emit(self.canvas.markers)
        self.canvas.update()

    def _cursor(self, t):
        base = self.vcd.timescale[1] if self.vcd else "ns"
        self.cursor_lbl.setText(f"cursor: {_scaled_time_label(t, base)}")
        self.canvas.update()         # refresh value-at-cursor in name gutter

    def _markers(self, markers):
        base = self.vcd.timescale[1] if self.vcd else "ns"
        if len(markers) >= 2:
            d = abs(markers[-1] - markers[-2])
            self.delta_lbl.setText(f"\u0394 = {_scaled_time_label(d, base)}")
        elif markers:
            self.delta_lbl.setText(f"marker: {_scaled_time_label(markers[-1], base)}")
        else:
            self.delta_lbl.setText("")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_A and (e.modifiers() & Qt.ControlModifier):
            self.avail.selectAll(); e.accept(); return
        if e.key() == Qt.Key_Delete:
            self.remove_selected(); return
        super().keyPressEvent(e)

    # ---- export --------------------------------------------------------
    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "waveform.png", "PNG (*.png)")
        if not path: return
        pm = QPixmap(self.canvas.size()); self.canvas.render(pm)
        if pm.save(path, "PNG"):
            self.statusBar().showMessage(f"Saved {path}", 4000)

    # --- Fit waveform ---------------------------------------------------
    def fit_waveform(self):
        if not self.vcd:
            return

        if self.vcd.end_time <= 0:
            return

        self.canvas.t0 = 0

        avail = max(
            200,
            self.scroll.viewport().width() - NAME_W - 20
        )

        self.canvas.px_per_unit = avail / self.vcd.end_time

        self.canvas._update_width()
        self.canvas.update()

    def _apply_time_window(self):
        if not self.vcd:
            return
        base = self.vcd.timescale[1] if self.vcd else "ns"
        t_from_str = self._tw_from.text().strip()
        t_to_str   = self._tw_to.text().strip()
        t_from = _parse_time_str(t_from_str, base) if t_from_str else 0
        t_to   = _parse_time_str(t_to_str,   base) if t_to_str   else self.vcd.end_time
        if t_from is None or t_to is None or t_to <= t_from:
            QMessageBox.warning(self, "Time Window",
                                "Invalid time range.\nUse values like '10ns', '50ps', '1us'.")
            return
        avail_px = max(200, self.scroll.viewport().width() - NAME_W - 20)
        self.canvas.t0 = max(0, t_from)
        self.canvas.px_per_unit = avail_px / (t_to - t_from)
        self.canvas._update_width()
        self.canvas.update()

    def export_csv(self):
        if not self.vcd: return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "signals.csv", "CSV (*.csv)")
        if not path: return
        rows = self._rows_data
        try:
            with open(path, "w") as fh:
                fh.write("time," + ",".join(r["signal"].name for r in rows) + "\n")
                times = sorted({t for r in rows for t, _ in r["signal"].changes})
                for t in times:
                    vals = []
                    for r in rows:
                        v = r["signal"].value_at(t) or ""
                        vals.append(fmt_value(v, r["radix"]) if r["signal"].width > 1 else v)
                    fh.write(f"{t}," + ",".join(vals) + "\n")
            self.statusBar().showMessage(f"Saved {path}", 4000)
        except OSError as e:
            QMessageBox.warning(self, "Export CSV", str(e))
