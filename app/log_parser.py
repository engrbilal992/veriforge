"""Classify a raw line of simulator output into a severity.

Icarus does not emit INFO/WARNING/ERROR tags. We synthesize them
here by pattern-matching the raw text, so the console can colour and count them.
Severities: 'error', 'critical', 'warning', 'success', 'info'.
"""

import re

# Icarus compiler messages look like:  tb.v:12: error: <msg>   /   foo.v:3: warning: <msg>
# 'sorry:' means an unsupported-but-non-fatal construct (compilation continues),
# so it is a warning, not an error.
_COMPILE_ERR = re.compile(r":\s*error\s*:", re.I)
_COMPILE_SORRY = re.compile(r":\s*sorry\s*:", re.I)
_COMPILE_WARN = re.compile(r":\s*warning\s*:", re.I)
# Elaboration summary:  "2 error(s) during elaboration."
_SUMMARY_ERR = re.compile(r"\b(\d+)\s+error", re.I)

# Testbench semantics (from $display strings the user writes).
# Note: bare "error"/"errors" is deliberately NOT a failure trigger, so a line
# like "0 errors found" is not misread as a failure. Real failures use the
# colon form ("error:"), the $error/$fatal tasks, or explicit fail words.
_FAIL = re.compile(r"\b(fail|failed|mismatch|fatal)\b|error\s*:|\$(error|fatal)", re.I)
_PASS = re.compile(r"\b(pass|passed|ok|success|all\s+tests?\s+passed)\b", re.I)
_WARN = re.compile(r"\b(warn|warning)\b", re.I)

# Extract file:line: severity: message for inline editor underlines.
_DIAG = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<sev>error|warning|sorry)\s*:\s*(?P<msg>.*)$", re.I)
# iverilog also emits bare "file:line: syntax error" (no 'error:' keyword)
_DIAG_BARE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<msg>.*(?:syntax error|error|cannot|undefined|unknown).*)$", re.I)


def parse_diagnostic(line: str):
    """Parse one compiler line into a diagnostic dict, or None.
    Returns {file, line, severity, msg}."""
    s = line.strip()
    m = _DIAG.match(s)
    if m:
        sev = m.group("sev").lower()
        sev = "error" if sev in ("error", "sorry") else "warning"
        return {"file": m.group("file"), "line": int(m.group("line")),
                "severity": sev, "msg": m.group("msg").strip()}
    m = _DIAG_BARE.match(s)
    if m:
        msg = m.group("msg").strip()
        sev = "warning" if "warning" in msg.lower() else "error"
        return {"file": m.group("file"), "line": int(m.group("line")),
                "severity": sev, "msg": msg}
    return None


def classify(line: str, stage: str) -> str:
    """Return a severity string for one line, given the current stage
    ('compile' or 'simulate')."""
    s = line.strip()
    if not s:
        return "info"

    if stage == "compile":
        if _COMPILE_ERR.search(s):
            return "error"
        if _COMPILE_SORRY.search(s) or _COMPILE_WARN.search(s):
            return "warning"
        if _SUMMARY_ERR.search(s) and "error" in s.lower():
            return "error"
        return "info"

    # simulate stage -- driven by the user's $display text
    if _FAIL.search(s):
        return "error"
    if _PASS.search(s):
        return "success"
    if _WARN.search(s):
        return "warning"
    return "info"
