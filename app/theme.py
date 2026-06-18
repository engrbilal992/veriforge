"""Editor colour themes.

Each theme is a flat dict of colours. The editor widget and its syntax
highlighter read from the same dict, so adding a theme here is all it takes to
make it selectable in the Appearance dialog.
"""

DEFAULT = "Dracula"

THEMES = {
    "Light Blue": {
        "bg": "#ffffff", "fg": "#1e2a3a", "current_line": "#eef4ff",
        "selection": "#cfe0fb", "gutter_bg": "#f7f9fc", "gutter_fg": "#aebccd",
        "keyword": "#2563eb", "system": "#0e7490", "directive": "#7c3aed",
        "number": "#c2410c", "string": "#15803d", "comment": "#94a3b8",
    },
    "Dracula": {
        "bg": "#1e1f29", "fg": "#f8f8f2", "current_line": "#282a36",
        "selection": "#44475a", "gutter_bg": "#16171f", "gutter_fg": "#6272a4",
        "keyword": "#ff79c6", "system": "#8be9fd", "directive": "#bd93f9",
        "number": "#bd93f9", "string": "#f1fa8c", "comment": "#6A9955",
    },
    "Monokai": {
        "bg": "#272822", "fg": "#f8f8f2", "current_line": "#3e3d32",
        "selection": "#49483e", "gutter_bg": "#1d1e19", "gutter_fg": "#75715e",
        "keyword": "#f92672", "system": "#66d9ef", "directive": "#ae81ff",
        "number": "#ae81ff", "string": "#e6db74", "comment": "#75715e",
    },
    "One Dark": {
        "bg": "#282c34", "fg": "#abb2bf", "current_line": "#2c313c",
        "selection": "#3e4451", "gutter_bg": "#21252b", "gutter_fg": "#5c6370",
        "keyword": "#c678dd", "system": "#56b6c2", "directive": "#61afef",
        "number": "#d19a66", "string": "#98c379", "comment": "#7f848e",
    },
    "Solarized Dark": {
        "bg": "#002b36", "fg": "#839496", "current_line": "#073642",
        "selection": "#094a54", "gutter_bg": "#00212b", "gutter_fg": "#586e75",
        "keyword": "#859900", "system": "#2aa198", "directive": "#6c71c4",
        "number": "#d33682", "string": "#2aa198", "comment": "#586e75",
    },
    "GitHub Light": {
        "bg": "#ffffff", "fg": "#24292e", "current_line": "#f6f8fa",
        "selection": "#cce5ff", "gutter_bg": "#f6f8fa", "gutter_fg": "#babbbd",
        "keyword": "#d73a49", "system": "#6f42c1", "directive": "#005cc5",
        "number": "#005cc5", "string": "#032f62", "comment": "#6a737d",
    },
}


def palette(name: str) -> dict:
    return THEMES.get(name, THEMES[DEFAULT])


# ---- application chrome (window/menus/toolbar), keyed off theme lightness ----
def is_light(name: str) -> bool:
    bg = palette(name)["bg"].lstrip("#")
    r, g, b = (int(bg[i:i+2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) > 140


def chrome(name: str) -> dict:
    """Full chrome token set for the application stylesheet (not the code area)."""
    if name == "Dracula":
        return {
            "win": "#282a36", "panel": "#1e1f29", "toolbar": "#343746",
            "header": "#21222c", "tab_strip": "#21222c", "tab_bg": "#282a36",
            "tab_sel": "#44475a", "border": "#44475a", "text": "#f8f8f2",
            "muted": "#6272a4", "hover": "#44475a", "input": "#21222c",
            "panel_fg": "#bd93f9", "accent": "#bd93f9", "accent_hi": "#cfa5ff",
            "accent_lo": "#9060e0", "on_accent": "#282a36", "sel": "#3d3f50",
            "scroll": "#44475a", "scroll_hi": "#6272a4",
            "tooltip_bg": "#f8f8f2", "tooltip_fg": "#282a36",
        }
    if name == "Monokai":
        return {
            "win": "#272822", "panel": "#1d1e19", "toolbar": "#3e3d32",
            "header": "#1d1e19", "tab_strip": "#1d1e19", "tab_bg": "#272822",
            "tab_sel": "#49483e", "border": "#49483e", "text": "#f8f8f2",
            "muted": "#75715e", "hover": "#49483e", "input": "#1d1e19",
            "panel_fg": "#a6e22e", "accent": "#a6e22e", "accent_hi": "#c8f050",
            "accent_lo": "#7ab010", "on_accent": "#272822", "sel": "#49483e",
            "scroll": "#49483e", "scroll_hi": "#75715e",
            "tooltip_bg": "#f8f8f2", "tooltip_fg": "#272822",
        }
    if name == "One Dark":
        return {
            "win": "#282c34", "panel": "#21252b", "toolbar": "#2c313c",
            "header": "#21252b", "tab_strip": "#21252b", "tab_bg": "#282c34",
            "tab_sel": "#3e4451", "border": "#3e4451", "text": "#abb2bf",
            "muted": "#5c6370", "hover": "#3e4451", "input": "#21252b",
            "panel_fg": "#61afef", "accent": "#61afef", "accent_hi": "#80c4ff",
            "accent_lo": "#3d8fd0", "on_accent": "#282c34", "sel": "#3e4451",
            "scroll": "#3e4451", "scroll_hi": "#5c6370",
            "tooltip_bg": "#abb2bf", "tooltip_fg": "#282c34",
        }
    if is_light(name):
        accent = "#2563eb"
        return {
            "win": "#f7f9fc", "panel": "#eef2f8", "toolbar": "#ffffff",
            "header": "#e7edf6", "tab_strip": "#eef2f8", "tab_bg": "#e7edf6",
            "tab_sel": "#ffffff", "border": "#d4dde8", "text": "#1e2a3a",
            "muted": "#7b8a9c", "hover": "#dde8f6", "input": "#ffffff",
            "panel_fg": accent, "accent": accent, "accent_hi": "#3b76f0",
            "accent_lo": "#1d4fd0", "on_accent": "#ffffff", "sel": "#cfe0fb",
            "scroll": "#c2cedd", "scroll_hi": "#9fb2c9",
            "tooltip_bg": "#1e2a3a", "tooltip_fg": "#f7f9fc",
        }
    accent = "#7aa2ff"
    return {
        "win": "#1a1c23", "panel": "#15171d", "toolbar": "#20232c",
        "header": "#15171d", "tab_strip": "#1a1c23", "tab_bg": "#20232c",
        "tab_sel": "#262a35", "border": "#2e323d", "text": "#e6e9f0",
        "muted": "#7d8597", "hover": "#2a2e3a", "input": "#15171d",
        "panel_fg": accent, "accent": accent, "accent_hi": "#90b2ff",
        "accent_lo": "#5d86e8", "on_accent": "#101218", "sel": "#2d3850",
        "scroll": "#363b47", "scroll_hi": "#4a5160",
        "tooltip_bg": "#e6e9f0", "tooltip_fg": "#15171d",
    }
