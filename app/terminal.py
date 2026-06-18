"""Launch the system's real terminal emulator at a given directory.

We deliberately do NOT embed a terminal. Embedding (xterm -into winId) is
X11-only and breaks on Wayland, which is Ubuntu's default — it would resize
badly and show escape-code artefacts. Launching the user's actual terminal
gives a true, full-featured Ubuntu terminal (colours, vim, htop all work)
because it IS the real terminal, just rooted at the project folder.
"""

import shutil
import subprocess

# ordered by prevalence on desktop Linux; first one found wins
_CANDIDATES = [
    ("gnome-terminal", ["--working-directory={cwd}"]),
    ("konsole", ["--workdir", "{cwd}"]),
    ("xfce4-terminal", ["--working-directory={cwd}"]),
    ("kitty", ["--directory", "{cwd}"]),
    ("alacritty", ["--working-directory", "{cwd}"]),
    ("tilix", ["--working-directory={cwd}"]),
    ("xterm", []),  # last resort; no standard cwd flag, handled below
]


def available_terminal() -> str | None:
    for name, _ in _CANDIDATES:
        if shutil.which(name):
            return name
    return None


def open_terminal(cwd: str) -> tuple[bool, str]:
    """Open the system terminal at `cwd`. Returns (ok, message)."""
    for name, arg_tmpl in _CANDIDATES:
        if not shutil.which(name):
            continue
        try:
            if name == "xterm":
                subprocess.Popen([name], cwd=cwd)
            else:
                args = [a.format(cwd=cwd) for a in arg_tmpl]
                subprocess.Popen([name, *args])
            return True, f"Opened {name} at {cwd}"
        except OSError as e:
            return False, f"Failed to launch {name}: {e}"
    return False, ("No terminal emulator found. Install one, e.g.:\n"
                   "    sudo apt install gnome-terminal")
