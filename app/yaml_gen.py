"""Generate a Verilog module skeleton from a YAML spec.

Spec format (one or many modules):

    module: counter
    parameters:
      WIDTH: 8
    ports:
      clk:        {dir: input,  width: 1}
      rst:        {dir: input}
      data_in:    {dir: input,  width: WIDTH}
      data_out:   {dir: output, width: WIDTH, type: reg}
      valid:      {dir: output}
    testbench: true            # or a mapping (see below) -> also emits counter_tb.v

Testbench block (all fields optional):
    testbench:
      clock: clk               # which input is the clock (default: a port named clk)
      reset: rst               # which input is the reset (default: a port named rst)
      period: 10               # clock period in ns (default 10)
      runtime: 200             # ns to run before $finish (default 100)
      dump: true               # emit $dumpfile/$dumpvars (default true)

Shorthands accepted:
  - a port value can be a bare string "input" / "output" / "inout"
  - width may be an int, a parameter name, or an expression like "WIDTH-1:0"
  - top-level may be a single module dict, or {modules: [ ... ]}
  - testbench: true is shorthand for testbench: {}

PyYAML is optional; if missing we raise a clear error the GUI shows.
"""

try:
    import yaml
    _HAVE_YAML = True
except ImportError:
    _HAVE_YAML = False

_DIRS = {"input", "output", "inout"}


class SpecError(Exception):
    pass


def _width_token(width) -> str:
    """Turn a width spec into a Verilog range prefix, e.g. '' or '[7:0] '."""
    if width is None:
        return ""
    w = str(width).strip()
    if w in ("", "1"):
        return ""
    if ":" in w:                       # explicit range "WIDTH-1:0"
        return f"[{w}] "
    # a number or parameter name -> [w-1:0]
    if w.isdigit():
        return f"[{int(w)-1}:0] "
    return f"[{w}-1:0] "


def _norm_port(name: str, spec) -> dict:
    if isinstance(spec, str):
        spec = {"dir": spec}
    if not isinstance(spec, dict):
        raise SpecError(f"Port '{name}' must be a string or mapping.")
    direction = str(spec.get("dir", spec.get("direction", "input"))).lower()
    if direction not in _DIRS:
        raise SpecError(f"Port '{name}' has invalid dir '{direction}' "
                        f"(use input/output/inout).")
    return {
        "name": name,
        "dir": direction,
        "width": spec.get("width", spec.get("size")),
        "type": str(spec.get("type", "wire")).lower(),
    }


def _emit_logic(m: dict, ports: list, params: dict) -> list:
    """Emit real logic from optional spec blocks:

    assign:                       # combinational continuous assignments
      y: a & b
      zero: (count == 0)

    sequential:                   # clocked always block(s)
      clock: clk
      reset: rst
      reset_value: {count: 0}
      logic:
        count: count + 1

    fsm:                          # finite state machine
      clock: clk
      reset: rst
      state_reg: state
      states: [IDLE, RUN, DONE]
      reset_state: IDLE
      transitions:
        IDLE:  {next: RUN, when: start}
        RUN:   {next: DONE, when: done}
        DONE:  {next: IDLE}
      outputs:                    # Moore outputs per state (optional)
        RUN:   {busy: 1}
        DONE:  {valid: 1}
    """
    out = []

    # ---- combinational assigns ----
    assigns = m.get("assign") or m.get("assigns") or {}
    if assigns:
        out.append("    // combinational logic")
        for lhs, rhs in assigns.items():
            out.append(f"    assign {lhs} = {rhs};")
        out.append("")

    # ---- sequential block ----
    seq = m.get("sequential") or m.get("seq")
    if seq:
        clk = seq.get("clock", "clk")
        rst = seq.get("reset", "rst")
        rst_edge = seq.get("reset_edge", "posedge")
        rvals = seq.get("reset_value", seq.get("reset_values", {})) or {}
        logic = seq.get("logic", {}) or {}
        sens = f"posedge {clk}"
        if rst:
            sens += f" or {rst_edge} {rst}"
        out.append(f"    // sequential logic")
        out.append(f"    always @({sens}) begin")
        if rst:
            out.append(f"        if ({rst}) begin")
            for r, v in rvals.items():
                out.append(f"            {r} <= {v};")
            out.append("        end else begin")
            indent = "            "
        else:
            indent = "        "
        for lhs, rhs in logic.items():
            out.append(f"{indent}{lhs} <= {rhs};")
        if rst:
            out.append("        end")
        out.append("    end")
        out.append("")

    # ---- FSM ----
    fsm = m.get("fsm")
    if fsm:
        out += _emit_fsm(fsm)
    return out


def _emit_fsm(fsm: dict) -> list:
    clk = fsm.get("clock", "clk")
    rst = fsm.get("reset", "rst")
    sreg = fsm.get("state_reg", "state")
    states = fsm.get("states", [])
    if not states:
        raise SpecError("fsm needs a 'states' list.")
    reset_state = fsm.get("reset_state", states[0])
    transitions = fsm.get("transitions", {}) or {}
    outputs = fsm.get("outputs", {}) or {}
    import math
    sw = max(1, math.ceil(math.log2(len(states))))

    L = []
    L.append("    // ---- FSM ----")
    L.append(f"    localparam [{sw-1}:0]")
    for i, s in enumerate(states):
        sep = "," if i < len(states) - 1 else ";"
        L.append(f"        {s} = {sw}'d{i}{sep}")
    L.append(f"    reg [{sw-1}:0] {sreg}, {sreg}_next;")
    L.append("")
    # state register
    L.append(f"    always @(posedge {clk}{' or posedge ' + rst if rst else ''}) begin")
    if rst:
        L.append(f"        if ({rst}) {sreg} <= {reset_state};")
        L.append(f"        else        {sreg} <= {sreg}_next;")
    else:
        L.append(f"        {sreg} <= {sreg}_next;")
    L.append("    end")
    L.append("")
    # next-state logic
    L.append("    always @(*) begin")
    L.append(f"        {sreg}_next = {sreg};")
    L.append(f"        case ({sreg})")
    for s in states:
        tr = transitions.get(s)
        if isinstance(tr, dict) and "when" in tr:
            L.append(f"            {s}: if ({tr['when']}) {sreg}_next = {tr['next']};")
        elif isinstance(tr, dict) and "next" in tr:
            L.append(f"            {s}: {sreg}_next = {tr['next']};")
        else:
            L.append(f"            {s}: {sreg}_next = {s};")
    L.append("            default: " + f"{sreg}_next = {reset_state};")
    L.append("        endcase")
    L.append("    end")
    L.append("")
    # Moore outputs
    if outputs:
        all_outs = sorted({o for st in outputs.values() for o in st})
        L.append("    always @(*) begin")
        for o in all_outs:
            L.append(f"        {o} = 0;")
        L.append(f"        case ({sreg})")
        for st, outs in outputs.items():
            assigns = " ".join(f"{o} = {v};" for o, v in outs.items())
            L.append(f"            {st}: begin {assigns} end")
        L.append("            default: ;")
        L.append("        endcase")
        L.append("    end")
        L.append("")
    return L


def _emit_module(m: dict) -> str:
    name = m.get("module") or m.get("name")
    if not name:
        raise SpecError("Each module needs a 'module' (or 'name') field.")
    params = m.get("parameters", m.get("params", {})) or {}
    ports_raw = m.get("ports", {}) or {}
    if not ports_raw:
        raise SpecError(f"Module '{name}' has no ports.")

    ports = [_norm_port(n, s) for n, s in ports_raw.items()]

    lines = []
    # timescale + header comment
    lines.append("`timescale 1ns/1ps")
    lines.append(f"// Auto-generated skeleton for module '{name}'.")
    lines.append("")

    # parameter list
    if params:
        plist = ",\n".join(f"    parameter {k} = {v}" for k, v in params.items())
        head = f"module {name} #(\n{plist}\n) ("
    else:
        head = f"module {name} ("
    lines.append(head)

    # ports, aligned
    port_lines = []
    for p in ports:
        kind = "reg " if (p["dir"] == "output" and p["type"] == "reg") else "wire"
        decl = f"{p['dir']:<6} {kind:<4} {_width_token(p['width'])}{p['name']}"
        port_lines.append("    " + decl.rstrip())
    lines.append(",\n".join(port_lines))
    lines.append(");")
    lines.append("")

    # body: real logic from spec blocks, else helpful stubs
    logic = _emit_logic(m, ports, params)
    if logic:
        lines.extend(logic)
    else:
        outs = [p for p in ports if p["dir"] == "output"]
        if outs:
            lines.append("    // TODO: drive the outputs")
            for p in outs:
                if p["type"] == "reg":
                    lines.append(f"    // always @(posedge clk) {p['name']} <= ...;")
                else:
                    lines.append(f"    // assign {p['name']} = ...;")
            lines.append("")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def _emit_testbench(name: str, params: dict, ports: list, tb: dict) -> str:
    """Emit a self-driving testbench that instantiates the module."""
    tbname = f"{name}_tb"
    inputs = [p for p in ports if p["dir"] == "input"]
    outputs = [p for p in ports if p["dir"] in ("output", "inout")]

    # find clock / reset by config or by conventional names
    in_names = {p["name"] for p in inputs}
    clock = tb.get("clock") or ("clk" if "clk" in in_names else None)
    reset = tb.get("reset") or ("rst" if "rst" in in_names else
                                ("reset" if "reset" in in_names else None))
    period = tb.get("period", 10)
    half = period / 2 if isinstance(period, (int, float)) else 5
    if half == int(half):
        half = int(half)
    runtime = tb.get("runtime", 100)
    dump = tb.get("dump", True)

    L = []
    L.append("`timescale 1ns/1ps")
    L.append(f"// Auto-generated testbench for module '{name}'.")
    L.append("")
    L.append(f"module {tbname};")

    # declare regs for inputs, wires for outputs
    for p in inputs:
        init = " = 0" if p["name"] in (clock, reset) else ""
        L.append(f"    reg  {_width_token(p['width'])}{p['name']}{init};")
    for p in outputs:
        L.append(f"    wire {_width_token(p['width'])}{p['name']};")
    L.append("")

    # parameter override + instantiation
    conns = ", ".join(f".{p['name']}({p['name']})" for p in ports)
    if params:
        pov = ", ".join(f".{k}({k})" for k in params)
        # declare localparams mirroring defaults so the override is explicit
        for k, v in params.items():
            L.append(f"    localparam {k} = {v};")
        L.append(f"    {name} #({pov}) dut ({conns});")
    else:
        L.append(f"    {name} dut ({conns});")
    L.append("")

    # clock generator
    if clock:
        L.append(f"    always #{half} {clock} = ~{clock};")
        L.append("")

    # stimulus
    L.append("    initial begin")
    if dump:
        L.append(f'        $dumpfile("wave.vcd");')
        L.append(f"        $dumpvars(0, {tbname});")
    if reset:
        L.append(f"        {reset} = 1;")
        L.append(f"        #{period}; {reset} = 0;   // release reset")
    # default-drive the remaining inputs once, as a starting point
    driven = {clock, reset}
    others = [p for p in inputs if p["name"] not in driven]
    if others:
        L.append("        // TODO: drive stimulus")
        for p in others:
            L.append(f"        {p['name']} = 0;")
    L.append(f"        #{runtime};")
    L.append('        $display("TODO: add checks. Simulation finished.");')
    L.append("        $finish;")
    L.append("    end")
    L.append("endmodule")
    return "\n".join(L) + "\n"


def generate(yaml_text: str) -> dict[str, str]:
    """Parse YAML text -> {filename: verilog_source}."""
    if not _HAVE_YAML:
        raise SpecError("PyYAML is not installed. Run:  pip install pyyaml")
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise SpecError(f"YAML parse error: {e}")
    if data is None:
        raise SpecError("The YAML file is empty.")

    if isinstance(data, dict) and "modules" in data:
        modules = data["modules"]
    elif isinstance(data, list):
        modules = data
    else:
        modules = [data]

    out = {}
    for m in modules:
        if not isinstance(m, dict):
            raise SpecError("Each module entry must be a mapping.")
        name = m.get("module") or m.get("name")
        src = _emit_module(m)
        out[name + ".v"] = src

        tb = m.get("testbench")
        if tb:
            if tb is True:
                tb = {}
            if not isinstance(tb, dict):
                raise SpecError(f"'testbench' for '{name}' must be true or a mapping.")
            params = m.get("parameters", m.get("params", {})) or {}
            ports = [_norm_port(n, s) for n, s in (m.get("ports", {}) or {}).items()]
            out[f"{name}_tb.v"] = _emit_testbench(name, params, ports, tb)
    return out
