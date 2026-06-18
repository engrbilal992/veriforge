"""Lightweight Verilog source scanner.

Pure-Python regex scanning — not a real parser, but enough to:
  - list module names declared in a file
  - detect whether a file is a testbench (has an `initial` block)
  - across a project, collect all module names for the top-module picker

Comments and strings are stripped first so commented-out code never counts.
"""

import os
import re

_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
_MODULE = re.compile(r"\bmodule\s+([A-Za-z_]\w*)", re.I)
_INITIAL = re.compile(r"\binitial\b")


def _clean(text: str) -> str:
    return _STRING.sub('""', _COMMENT.sub("", text))


def scan_text(text: str) -> dict:
    """Return {'modules': [names], 'is_tb': bool} for one source's text."""
    clean = _clean(text)
    modules = _MODULE.findall(clean)
    return {"modules": modules, "is_tb": bool(_INITIAL.search(clean))}


def scan_file(path: str) -> dict:
    try:
        with open(path) as fh:
            return scan_text(fh.read())
    except OSError:
        return {"modules": [], "is_tb": False}


def classify_file(path: str) -> str:
    """Group a file for the explorer: 'yaml' | 'header' | 'sim' | 'design'."""
    low = path.lower()
    if low.endswith((".yaml", ".yml")):
        return "yaml"
    if low.endswith((".vh", ".svh")):
        return "header"
    return "sim" if scan_file(path)["is_tb"] else "design"


def all_modules(files: list[str]) -> list[str]:
    """All module names across the given source files, de-duplicated, sorted."""
    seen = []
    for f in files:
        if f.lower().endswith((".v", ".sv")):
            for m in scan_file(f)["modules"]:
                if m not in seen:
                    seen.append(m)
    return sorted(seen)


def file_of_module(files: list[str], module: str) -> str | None:
    """Return the path of the file declaring `module`, or None."""
    for f in files:
        if f.lower().endswith((".v", ".sv")) and module in scan_file(f)["modules"]:
            return f
    return None
