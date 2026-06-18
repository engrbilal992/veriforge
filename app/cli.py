"""VeriForge command-line interface.

A full CLI so the tool is usable without the GUI — and can also launch the GUI
on a chosen project. Subcommands:

    veriforge new <name> [--path DIR]                create a project
    veriforge add <project> <file>                   add a source/YAML file
    veriforge gen <project> <spec.yaml>              YAML spec -> Verilog into src/
    veriforge sim <project> [--top NAME]             headless simulation
    veriforge wave <project>                          print VCD signal summary
    veriforge list <project>                          list project files
    veriforge open [project]                          launch the GUI (optionally on a project)
    veriforge ide  [project]                          alias for 'open'

The headless commands (new/add/gen/sim/list/wave) never import Qt, so they run
on machines without a display. 'open'/'ide' import the GUI lazily.
"""

import argparse
import os
import sys


def _p(*a):
    print("veriforge:", *a)


def _err(*a):
    print("veriforge: error:", *a, file=sys.stderr)
    return 1


# ---- headless commands -------------------------------------------------
def cmd_new(args):
    from .project import Project
    parent = os.path.abspath(args.path or ".")
    proj = Project.create(parent, args.name)
    proj.ensure_dirs()
    proj.write_manifest()
    _p(f"created project '{args.name}' at {proj.root}")
    _p("  dirs: src/ build/ sim/ logs/")
    return 0


def cmd_add(args):
    from .project import Project
    proj = Project.open(args.project)
    path = proj.add_file(args.file)
    _p(f"added {os.path.relpath(path, proj.root)}")
    return 0


def cmd_gen(args):
    from .project import Project
    from . import yaml_gen
    proj = Project.open(args.project)
    proj.ensure_dirs()
    with open(args.spec) as fh:
        text = fh.read()
    try:
        files = yaml_gen.generate(text)
    except yaml_gen.SpecError as e:
        return _err(str(e))
    written = []
    for fname, src in files.items():
        dest = os.path.join(proj.src_dir, fname)
        with open(dest, "w") as fh:
            fh.write(src)
        written.append(fname)
    _p(f"generated {len(written)} file(s): {', '.join(written)}")
    return 0


def cmd_sim(args):
    """Headless simulation: run iverilog + vvp directly, stream output."""
    import shutil
    import subprocess
    from .project import Project
    from . import vscan

    if not (shutil.which("iverilog") and shutil.which("vvp")):
        return _err("iverilog/vvp not found on PATH. Install with: sudo apt install iverilog")

    proj = Project.open(args.project)
    proj.ensure_dirs()
    files = proj.source_files()
    if not files:
        return _err("no .v/.sv sources in project")

    top = args.top or proj.top
    rel = [os.path.relpath(f, proj.root) for f in files]
    out = os.path.join("build", "a.out")
    cmd = ["iverilog", "-g2012", "-o", out]
    if top:
        cmd += ["-s", top]
    cmd += rel
    _p("$ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=proj.root, capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
    if r.returncode != 0:
        return _err("compilation failed")

    _p("$ vvp build/a.out")
    r2 = subprocess.run(["vvp", out], cwd=proj.root, capture_output=True, text=True)
    sys.stdout.write(r2.stdout); sys.stderr.write(r2.stderr)

    # sweep any VCD into sim/
    for fn in os.listdir(proj.root):
        if fn.endswith((".vcd", ".fst")):
            os.replace(os.path.join(proj.root, fn), os.path.join(proj.sim_dir, fn))
    _p("done" if r2.returncode == 0 else "simulation reported errors")
    return r2.returncode


def cmd_wave(args):
    from .project import Project
    from .vcd import VCD
    proj = Project.open(args.project)
    vcd = None
    if os.path.isdir(proj.sim_dir):
        for fn in os.listdir(proj.sim_dir):
            if fn.endswith(".vcd"):
                vcd = os.path.join(proj.sim_dir, fn); break
    if not vcd:
        return _err("no VCD in sim/. Run 'veriforge sim' first.")
    v = VCD.parse_file(vcd)
    _p(f"{os.path.basename(vcd)}: {len(v.signals)} signals, "
       f"end={v.end_time}{v.timescale[1]}")
    for s in v.signals:
        w = f"[{s.width-1}:0]" if s.width > 1 else ""
        print(f"    {s.name} {w} ({len(s.changes)} changes)")
    return 0


def cmd_list(args):
    from .project import Project
    proj = Project.open(args.project)
    _p(f"project '{proj.name}' (top: {proj.top or '(auto)'})")
    for f in proj.tree_files():
        print("    " + os.path.relpath(f, proj.root))
    return 0


def cmd_open(args):
    # Launch the GUI, optionally opening a project.
    from PySide6.QtWidgets import QApplication
    from .main_window import MainWindow
    app = QApplication(sys.argv[:1])
    win = MainWindow()
    if args.project:
        win.open_project_path(os.path.abspath(args.project))
    win.show()
    return app.exec()


def build_parser():
    p = argparse.ArgumentParser(prog="veriforge",
                                description="VeriForge — Verilog simulation IDE & CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="create a project")
    s.add_argument("name"); s.add_argument("--path", default=".")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("add", help="add a file to a project")
    s.add_argument("project"); s.add_argument("file")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("gen", help="generate Verilog from a YAML spec")
    s.add_argument("project"); s.add_argument("spec")
    s.set_defaults(func=cmd_gen)

    s = sub.add_parser("sim", help="run a headless simulation")
    s.add_argument("project"); s.add_argument("--top", default=None)
    s.set_defaults(func=cmd_sim)

    s = sub.add_parser("wave", help="summarise the latest VCD")
    s.add_argument("project")
    s.set_defaults(func=cmd_wave)

    s = sub.add_parser("list", help="list project files")
    s.add_argument("project")
    s.set_defaults(func=cmd_list)

    for name in ("open", "ide"):
        s = sub.add_parser(name, help="launch the GUI (optionally on a project)")
        s.add_argument("project", nargs="?", default=None)
        s.set_defaults(func=cmd_open)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        return _err(str(e))
    except Exception as e:  # noqa: BLE001 - surface a clean message
        return _err(str(e))


if __name__ == "__main__":
    sys.exit(main())
