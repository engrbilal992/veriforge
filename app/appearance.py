"""Appearance dialog: pick editor font, size, and colour theme, applied live."""

from PySide6.QtWidgets import (QDialog, QFormLayout, QFontComboBox, QSpinBox,
                               QComboBox, QDialogButtonBox, QLabel, QVBoxLayout,
                               QPlainTextEdit)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from .theme import THEMES, palette

_PREVIEW = ("module demo;  // preview\n"
            "  reg clk = 0;\n"
            '  initial $display("hello %0d", 42);\n'
            "endmodule")


class AppearanceDialog(QDialog):
    def __init__(self, current: dict, on_change, parent=None, chrome=None):
        super().__init__(parent)
        self.setWindowTitle("Appearance")
        self.setMinimumWidth(420)
        self._on_change = on_change
        if chrome:
            self.setStyleSheet(
                f"QDialog{{background:{chrome['win']};}}"
                f"QLabel{{color:{chrome['text']};}}"
                f"QComboBox,QSpinBox,QFontComboBox{{background:{chrome['panel']};"
                f"color:{chrome['text']};border:1px solid {chrome['border']};"
                f"border-radius:5px;padding:4px 8px;}}"
                f"QPushButton{{background:{chrome['accent']};color:#fff;"
                f"border:none;border-radius:6px;padding:7px 16px;}}"
                f"QPushButton:hover{{background:{chrome['panel_fg']};}}")

        self.font_combo = QFontComboBox()
        self.font_combo.setFontFilters(QFontComboBox.MonospacedFonts)
        self.font_combo.setCurrentFont(QFont(current["font_family"]))

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 48)
        self.size_spin.setValue(current["font_size"])

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(current["theme"])

        form = QFormLayout()
        form.addRow("Editor font:", self.font_combo)
        form.addRow("Font size:", self.size_spin)
        form.addRow("Theme:", self.theme_combo)

        self.preview = QPlainTextEdit(_PREVIEW)
        self.preview.setReadOnly(True)
        self.preview.setFixedHeight(110)

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Close)
        self._apply_btn = buttons.button(QDialogButtonBox.Apply)
        self._apply_btn.clicked.connect(lambda: self._on_change(self._current()))
        buttons.rejected.connect(self.accept)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("Preview:"))
        lay.addWidget(self.preview)
        lay.addWidget(buttons)

        self.font_combo.currentFontChanged.connect(self._refresh_preview)
        self.size_spin.valueChanged.connect(self._refresh_preview)
        self.theme_combo.currentTextChanged.connect(self._refresh_preview)
        self._refresh_preview()

    def _current(self) -> dict:
        return {
            "theme": self.theme_combo.currentText(),
            "font_family": self.font_combo.currentFont().family(),
            "font_size": self.size_spin.value(),
        }

    def _refresh_preview(self, *_):
        a = self._current()
        pal = palette(a["theme"])
        self.preview.setStyleSheet(
            f"QPlainTextEdit{{background:{pal['bg']};color:{pal['fg']};"
            f"border:1px solid {pal['selection']};}}")
        f = QFont(a["font_family"]); f.setPointSize(a["font_size"])
        self.preview.setFont(f)
