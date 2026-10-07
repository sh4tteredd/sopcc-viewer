"""Flat, modern ttk theme for the SOPCC viewer (no third-party dependency).

Provides light and dark palettes and an :func:`apply_theme` function that
restyles the ``clam`` ttk theme into a clean, borderless look with a consistent
accent colour, generous padding and modern typography.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk

_PREFERRED_UI_FONTS = (
    "SF Pro Text",
    "Helvetica Neue",
    "Segoe UI",
    "Inter",
    "Helvetica",
    "Arial",
)
_PREFERRED_MONO_FONTS = (
    "SF Mono",
    "Menlo",
    "JetBrains Mono",
    "Consolas",
    "DejaVu Sans Mono",
    "Courier New",
)


@dataclass(frozen=True)
class Palette:
    """Colours for one theme variant."""

    name: str
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_fg: str
    header_bg: str
    header_fg: str
    select_bg: str
    select_fg: str
    editor_bg: str
    editor_fg: str


LIGHT = Palette(
    name="light",
    bg="#eef1f6",
    surface="#ffffff",
    surface_alt="#f2f5f9",
    border="#dde3ea",
    text="#1f2933",
    text_muted="#6b7a8d",
    accent="#2f6fed",
    accent_hover="#2860d8",
    accent_fg="#ffffff",
    header_bg="#ffffff",
    header_fg="#1f2933",
    select_bg="#d7e4ff",
    select_fg="#123a78",
    editor_bg="#f7f9fc",
    editor_fg="#243b53",
)

DARK = Palette(
    name="dark",
    bg="#14181d",
    surface="#1d232b",
    surface_alt="#252c35",
    border="#323b46",
    text="#e6edf3",
    text_muted="#9aa5b1",
    accent="#4c8dff",
    accent_hover="#3d7de6",
    accent_fg="#0b1220",
    header_bg="#1d232b",
    header_fg="#e6edf3",
    select_bg="#2b4a76",
    select_fg="#ffffff",
    editor_bg="#12161b",
    editor_fg="#cbd5e1",
)


@dataclass(frozen=True)
class Fonts:
    """Resolved font family names for the current system."""

    ui: str
    mono: str


def get_palette(name: str) -> Palette:
    return DARK if name == "dark" else LIGHT


def _resolve_family(root: tk.Misc, preferred: tuple[str, ...], fallback: str) -> str:
    try:
        available = set(tkfont.families(root))
    except tk.TclError:  # pragma: no cover - depends on the display
        return fallback
    for name in preferred:
        if name in available:
            return name
    return fallback


def apply_theme(root: tk.Misc, palette: Palette) -> Fonts:
    """Restyle the whole application for ``palette`` and return resolved fonts."""
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    ui = _resolve_family(root, _PREFERRED_UI_FONTS, "Helvetica")
    mono = _resolve_family(root, _PREFERRED_MONO_FONTS, "Courier")
    fonts = Fonts(ui=ui, mono=mono)

    root.configure(background=palette.bg)

    # --- base defaults -------------------------------------------------
    style.configure(
        ".",
        background=palette.bg,
        foreground=palette.text,
        font=(ui, 13),
        focuscolor=palette.accent,
    )
    style.map(".", foreground=[("disabled", palette.text_muted)])

    # --- frames --------------------------------------------------------
    style.configure("TFrame", background=palette.bg)
    style.configure("Body.TFrame", background=palette.bg)
    style.configure("Card.TFrame", background=palette.surface)
    style.configure("Surface.TFrame", background=palette.surface)
    style.configure("Header.TFrame", background=palette.header_bg)
    style.configure("Toolbar.TFrame", background=palette.surface)
    style.configure("Accent.TFrame", background=palette.accent)
    style.configure("Divider.TFrame", background=palette.border)

    # --- labels --------------------------------------------------------
    style.configure("TLabel", background=palette.bg, foreground=palette.text)
    style.configure("Card.TLabel", background=palette.surface, foreground=palette.text)
    style.configure(
        "Title.TLabel",
        background=palette.surface,
        foreground=palette.text,
        font=(ui, 15, "bold"),
    )
    style.configure(
        "Field.TLabel",
        background=palette.surface,
        foreground=palette.text_muted,
        font=(ui, 12),
    )
    style.configure(
        "Value.TLabel",
        background=palette.surface,
        foreground=palette.text,
        font=(ui, 13),
    )
    style.configure(
        "HeaderTitle.TLabel",
        background=palette.header_bg,
        foreground=palette.header_fg,
        font=(ui, 18, "bold"),
    )
    style.configure(
        "HeaderSub.TLabel",
        background=palette.header_bg,
        foreground=palette.text_muted,
        font=(ui, 12),
    )
    style.configure(
        "Status.TLabel",
        background=palette.surface,
        foreground=palette.text_muted,
        font=(ui, 11),
    )

    # --- buttons -------------------------------------------------------
    for name, bg, fg, hover in (
        ("Flat.TButton", palette.surface, palette.text, palette.surface_alt),
        ("Tab.TButton", palette.surface, palette.text_muted, palette.surface_alt),
        ("Accent.TButton", palette.accent, palette.accent_fg, palette.accent_hover),
        ("TabActive.TButton", palette.accent, palette.accent_fg, palette.accent_hover),
    ):
        style.configure(
            name,
            background=bg,
            foreground=fg,
            borderwidth=0,
            focusthickness=0,
            focuscolor=bg,
            padding=(14, 8),
            font=(ui, 12),
        )
        style.map(
            name,
            background=[("pressed", hover), ("active", hover)],
            foreground=[("disabled", palette.text_muted)],
        )

    # --- inputs --------------------------------------------------------
    style.configure(
        "TEntry",
        fieldbackground=palette.surface_alt,
        background=palette.surface_alt,
        foreground=palette.text,
        insertcolor=palette.text,
        bordercolor=palette.border,
        lightcolor=palette.border,
        darkcolor=palette.border,
        borderwidth=1,
        relief="flat",
        padding=7,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", palette.accent)],
        lightcolor=[("focus", palette.accent)],
        darkcolor=[("focus", palette.accent)],
    )
    style.configure(
        "TCheckbutton",
        background=palette.surface,
        foreground=palette.text,
        focuscolor=palette.surface,
        font=(ui, 12),
    )
    style.map(
        "TCheckbutton",
        background=[("active", palette.surface)],
        indicatorcolor=[
            ("selected", palette.accent),
            ("!selected", palette.surface_alt),
        ],
    )

    # --- tree / table --------------------------------------------------
    style.configure(
        "Treeview",
        background=palette.surface,
        fieldbackground=palette.surface,
        foreground=palette.text,
        bordercolor=palette.surface,
        lightcolor=palette.surface,
        darkcolor=palette.surface,
        borderwidth=0,
        relief="flat",
        rowheight=28,
        font=(ui, 13),
    )
    style.map(
        "Treeview",
        background=[("selected", palette.select_bg)],
        foreground=[("selected", palette.select_fg)],
    )
    style.configure(
        "Treeview.Heading",
        background=palette.surface_alt,
        foreground=palette.text_muted,
        relief="flat",
        borderwidth=0,
        padding=(10, 8),
        font=(ui, 12, "bold"),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", palette.border)],
        foreground=[("active", palette.text)],
    )

    # --- scrollbars ----------------------------------------------------
    for orient in ("Vertical", "Horizontal"):
        name = f"{orient}.TScrollbar"
        style.configure(
            name,
            background=palette.border,
            troughcolor=palette.bg,
            bordercolor=palette.bg,
            arrowcolor=palette.text_muted,
            darkcolor=palette.border,
            lightcolor=palette.border,
            relief="flat",
            borderwidth=0,
            arrowsize=14,
        )
        style.map(name, background=[("active", palette.text_muted)])

    # --- misc ----------------------------------------------------------
    style.configure("TSeparator", background=palette.border)
    style.configure("TPanedwindow", background=palette.bg)
    style.configure(
        "Sash",
        sashthickness=10,
        gripcount=0,
        background=palette.bg,
        bordercolor=palette.bg,
        lightcolor=palette.bg,
        darkcolor=palette.bg,
    )

    return fonts


def configure_row_tags(tree: ttk.Treeview, palette: Palette, striped: bool = True) -> None:
    """(Re)apply alternating-row tag colours to a treeview."""
    if striped:
        tree.tag_configure("odd", background=palette.surface_alt)
    tree.tag_configure("even", background=palette.surface)
