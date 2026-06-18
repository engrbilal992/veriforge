"""Project model.

A project is a folder on disk with Verilog sources plus a small JSON manifest
(`project.rtlproj`). Build artifacts are organised into sibling folders that are
kept out of source scans:
    build/   compiled output (a.out)
    sim/     simulation outputs (wave.vcd, ...)
    logs/    run logs (<project>.log)
No Qt here, so this stays easy to test.
"""

import json
import os
import re
from pathlib import Path

MANIFEST = "project.rtlproj"
SOURCE_EXTS = (".v", ".sv")
TREE_EXTS = (".v", ".sv", ".vh", ".svh")
SPEC_EXTS = (".yaml", ".yml")
TREE_ALL = TREE_EXTS + SPEC_EXTS
ARTIFACT_DIRS = {"build", "sim", "logs", ".build"}  # src/ is intentionally NOT here

_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_INITIAL = re.compile(r"\binitial\b")


def has_testbench(files: list[str]) -> bool:
    """True if any source has an `initial` block (comments stripped first)."""
    for f in files:
        try:
            txt = open(f).read()
        except OSError:
            continue
        if _INITIAL.search(_COMMENT.sub("", txt)):
            return True
    return False


class Project:
    def __init__(self, root: str, name: str, top: str | None = None):
        self.root = os.path.abspath(root)
        self.name = name
        self.top = top

    # ---- create / open -------------------------------------------------
    @classmethod
    def create(cls, parent_dir: str, name: str) -> "Project":
        root = os.path.join(os.path.abspath(parent_dir), name)
        os.makedirs(root, exist_ok=True)
        proj = cls(root, name)
        proj.write_manifest()
        return proj

    @classmethod
    def open(cls, root: str) -> "Project":
        root = os.path.abspath(root)
        manifest = os.path.join(root, MANIFEST)
        if os.path.isfile(manifest):
            with open(manifest) as fh:
                data = json.load(fh)
            return cls(root, data.get("name", os.path.basename(root)),
                       data.get("top"))
        return cls(root, os.path.basename(root))

    def write_manifest(self):
        with open(os.path.join(self.root, MANIFEST), "w") as fh:
            json.dump({"version": 1, "name": self.name, "top": self.top},
                      fh, indent=2)

    # ---- artifact folders ---------------------------------------------
    @property
    def src_dir(self) -> str:
        return os.path.join(self.root, "src")

    @property
    def build_dir(self) -> str:
        return os.path.join(self.root, "build")

    @property
    def sim_dir(self) -> str:
        return os.path.join(self.root, "sim")

    @property
    def logs_dir(self) -> str:
        return os.path.join(self.root, "logs")

    def ensure_dirs(self):
        for d in (self.src_dir, self.build_dir, self.sim_dir, self.logs_dir):
            os.makedirs(d, exist_ok=True)

    # ---- files ---------------------------------------------------------
    def _scan(self, exts) -> list[str]:
        out = []
        for p in sorted(Path(self.root).rglob("*")):
            if not p.is_file() or p.suffix.lower() not in exts:
                continue
            rel_parts = p.relative_to(self.root).parts[:-1]   # parent dirs only
            if ARTIFACT_DIRS & set(rel_parts):
                continue
            out.append(str(p))
        return out

    def source_files(self) -> list[str]:
        files = self._scan(SOURCE_EXTS)
        files.sort(key=lambda f: ("tb" in os.path.basename(f).lower()
                                   or "test" in os.path.basename(f).lower()))
        return files

    def tree_files(self) -> list[str]:
        return self._scan(TREE_ALL)

    def add_file(self, filename: str) -> str:
        # accept Verilog or YAML extensions; default to .v when none given
        low = filename.lower()
        if not low.endswith(TREE_EXTS) and not low.endswith((".yaml", ".yml")):
            filename += ".v"
        os.makedirs(self.src_dir, exist_ok=True)
        path = os.path.join(self.src_dir, filename)
        if os.path.exists(path):
            raise FileExistsError(path)
        with open(path, "w") as fh:
            fh.write(self._skeleton(filename))
        return path

    @staticmethod
    def _skeleton(filename: str) -> str:
        stem = os.path.splitext(os.path.basename(filename))[0]
        ext = os.path.splitext(filename)[1].lower()
        low = stem.lower()
        if ext in (".yaml", ".yml"):         # YAML spec template
            return (
                f"# Module spec for '{stem}'. Fill this in, then click Generate.\n"
                f"module: {stem}\n"
                "parameters:\n"
                "  WIDTH: 8\n"
                "ports:\n"
                "  clk:      {dir: input}\n"
                "  rst:      input\n"
                "  data_in:  {dir: input,  width: WIDTH}\n"
                "  data_out: {dir: output, width: WIDTH, type: reg}\n"
                "  valid:    {dir: output}\n"
                "testbench:               # also generate "
                f"{stem}_tb.v\n"
                "  clock: clk\n"
                "  reset: rst\n"
                "  period: 10\n"
                "  runtime: 200\n"
            )
        if ext in (".vh", ".svh"):           # header file: include guard
            guard = re.sub(r"\W", "_", stem.upper()) + "_VH"
            return f"`ifndef {guard}\n`define {guard}\n\n// shared definitions\n\n`endif\n"
        if "tb" in low or "test" in low:      # testbench skeleton
            return (
                "`timescale 1ns/1ps\n\n"
                f"module {stem};\n"
                "    reg clk = 0;\n"
                "    always #5 clk = ~clk;\n\n"
                "    initial begin\n"
                f'        $dumpfile("wave.vcd");\n'
                f"        $dumpvars(0, {stem});\n"
                "        // drive your DUT here\n"
                "        #100;\n"
                "        $finish;\n"
                "    end\n"
                "endmodule\n"
            )
        return (                              # module skeleton
            f"module {stem} (\n"
            "    input  wire clk,\n"
            "    input  wire rst\n"
            ");\n\n"
            "    // your logic here\n\n"
            "endmodule\n"
        )
