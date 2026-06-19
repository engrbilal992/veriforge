"""VCD (Value Change Dump) parser.

Pure-Python, no dependency. Reads the format Icarus' $dumpvars produces into a
structure the waveform widget can render:

    VCD.timescale            -> (number, unit) e.g. (1, 'ns')
    VCD.end_time             -> last timestamp seen
    VCD.signals              -> list of Signal, each with:
        .name (hierarchical), .width, .changes = [(time, value_str), ...]

Values are kept as strings ('0','1','x','z' for 1-bit; bit-strings for buses)
so the renderer can show transitions and bus values without lossy conversion.
"""

import re

_TS = re.compile(r"\$timescale\s+(\d+)\s*([munpfs]?s)\s*\$end", re.I)
_TS2 = re.compile(r"\$timescale\s+(\d+)\s*([munpfs]?s)", re.I)


class Signal:
    __slots__ = ("name", "ident", "width", "changes")

    def __init__(self, name, ident, width):
        self.name = name
        self.ident = ident
        self.width = width
        self.changes = []          # list of (time:int, value:str)

    def value_at(self, t):
        """Value active at time t (last change <= t)."""
        v = None
        for ct, cv in self.changes:
            if ct <= t:
                v = cv
            else:
                break
        return v


class VCD:
    def __init__(self):
        self.timescale = (1, "ns")
        self.end_time = 0
        self.signals = []           # list[Signal]
        self._by_ident = {}         # ident -> list[Signal] (alias-safe)

    # ---- parsing -------------------------------------------------------
    @classmethod
    def parse_file(cls, path):
        with open(path, "r", errors="replace") as fh:
            return cls.parse_text(fh.read())

    @classmethod
    def parse_text(cls, text):
        v = cls()
        scope = []
        in_defs = True
        time = 0

        # timescale (may span tokens)
        m = _TS.search(text) or _TS2.search(text)
        if m:
            v.timescale = (int(m.group(1)), m.group(2).lower())

        # tokenise the header; body parsed line-by-line for speed
        lines = text.splitlines()
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i].strip()
            i += 1
            if not line:
                continue
            if in_defs:
                if line.startswith("$scope"):
                    parts = line.split()
                    if len(parts) >= 3:
                        scope.append(parts[2])
                elif line.startswith("$upscope"):
                    if scope:
                        scope.pop()
                elif line.startswith("$var"):
                    # $var wire 4 ! q [3:0] $end
                    parts = line.split()
                    if len(parts) >= 5:
                        width = int(parts[2])
                        ident = parts[3]
                        nm = parts[4]
                        full = ".".join(scope + [nm])
                        sig = Signal(full, ident, width)
                        v.signals.append(sig)
                        v._by_ident.setdefault(ident, []).append(sig)
                elif line.startswith("$enddefinitions"):
                    in_defs = False
                continue

            # ---- value-change section ----
            c0 = line[0]
            if c0 == "#":
                time = int(line[1:])
                v.end_time = max(v.end_time, time)
            elif c0 in "01xXzZ":
                val = c0.lower()
                ident = line[1:]
                for s in v._by_ident.get(ident, ()):
                    # Skip redundant same-value entries (Icarus emits these for
                    # delta-cycle settling).  GTKWave filters them the same way.
                    if not s.changes or s.changes[-1][1] != val:
                        s.changes.append((time, val))
            elif c0 in "bB":
                # bus: b1010 ident
                sp = line.split()
                if len(sp) == 2:
                    val = sp[0][1:]
                    for s in v._by_ident.get(sp[1], ()):
                        if not s.changes or s.changes[-1][1] != val:
                            s.changes.append((time, val))
            elif c0 in "rR":
                sp = line.split()
                if len(sp) == 2:
                    val = sp[0][1:]
                    for s in v._by_ident.get(sp[1], ()):
                        if not s.changes or s.changes[-1][1] != val:
                            s.changes.append((time, val))
            # ignore $dumpvars/$end markers
        return v

    def signal_names(self):
        return [s.name for s in self.signals]
