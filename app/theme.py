"""Palette et petits widgets dessinés, d'après la maquette de l'application.

Tkinter ne sait pas arrondir les coins de ses widgets natifs : les éléments les
plus visibles (bouton principal, cases à cocher, barre de progression) sont donc
dessinés sur un Canvas. Le reste est habillé via le thème « clam », le seul que
ttk laisse recolorer entièrement.
"""
from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import ttk

DARK = {
    "bg": "#1e1c1a", "headerBg": "#171514", "border": "#332f2b",
    "text": "#f3ede4", "textMid": "#b3aca2", "textDim": "#8a837a",
    "fieldBg": "#2a2724", "btnGhost": "#332f2b", "trackBg": "#332f2b",
    "listBg": "#141210", "accent": "#d98a4a", "accentHover": "#e59c62",
    "onAccent": "#1e1c1a", "checkOff": "#3a3733",
    "ok": "#8bbf7a", "error": "#e26b5c", "select": "#3a352f",
}

LIGHT = {
    "bg": "#faf7f2", "headerBg": "#f1ece3", "border": "#dcd6cb",
    "text": "#22201d", "textMid": "#57534d", "textDim": "#8a847b",
    "fieldBg": "#ffffff", "btnGhost": "#ffffff", "trackBg": "#e4ded3",
    "listBg": "#ffffff", "accent": "#c9702f", "accentHover": "#d98a4a",
    "onAccent": "#ffffff", "checkOff": "#d5cec3",
    "ok": "#2f7a3d", "error": "#c2402f", "select": "#efe8dc",
}


def system_prefers_dark() -> bool:
    """Thème du système, pour ouvrir l'application dans le bon mode."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                 capture_output=True, text=True, timeout=2)
            return "dark" in out.stdout.lower()
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except Exception:                                   # noqa: BLE001
        pass
    return True


def mono_family() -> str:
    return {"darwin": "Menlo", "win32": "Consolas"}.get(sys.platform, "DejaVu Sans Mono")


def serif_family() -> str:
    return "Georgia"


def apply_ttk(colors: dict[str, str]) -> None:
    """Recolore les widgets ttk qu'on ne peut pas dessiner nous-mêmes."""
    style = ttk.Style()
    style.theme_use("clam")
    c = colors

    style.configure(".", background=c["bg"], foreground=c["text"],
                    fieldbackground=c["fieldBg"], bordercolor=c["border"],
                    lightcolor=c["border"], darkcolor=c["border"], focuscolor=c["accent"])
    style.configure("TFrame", background=c["bg"])
    style.configure("Header.TFrame", background=c["headerBg"])
    style.configure("TLabel", background=c["bg"], foreground=c["text"])
    style.configure("Header.TLabel", background=c["headerBg"], foreground=c["text"])
    style.configure("HeaderDim.TLabel", background=c["headerBg"], foreground=c["textDim"])
    style.configure("Dim.TLabel", background=c["bg"], foreground=c["textDim"])
    style.configure("Mid.TLabel", background=c["bg"], foreground=c["textMid"])

    style.configure("TEntry", foreground=c["text"], fieldbackground=c["fieldBg"],
                    insertcolor=c["text"], bordercolor=c["border"], padding=6)
    style.map("TEntry", bordercolor=[("focus", c["accent"])])

    style.configure("TCombobox", foreground=c["text"], fieldbackground=c["fieldBg"],
                    background=c["fieldBg"], arrowcolor=c["textMid"],
                    bordercolor=c["border"], padding=5)
    style.map("TCombobox",
              fieldbackground=[("readonly", c["fieldBg"])],
              background=[("readonly", c["fieldBg"])],
              bordercolor=[("focus", c["accent"])])

    style.configure("TSpinbox", foreground=c["text"], fieldbackground=c["fieldBg"],
                    background=c["fieldBg"], arrowcolor=c["textMid"],
                    bordercolor=c["border"], padding=4)

    style.configure("Treeview", background=c["listBg"], fieldbackground=c["listBg"],
                    foreground=c["text"], bordercolor=c["border"], rowheight=26)
    style.configure("Treeview.Heading", background=c["headerBg"], foreground=c["textDim"],
                    relief="flat", font=("", 10, "bold"))
    style.map("Treeview.Heading", background=[("active", c["headerBg"])])
    style.map("Treeview", background=[("selected", c["select"])],
              foreground=[("selected", c["text"])])

    style.configure("Ghost.TButton", background=c["btnGhost"], foreground=c["text"],
                    bordercolor=c["border"], relief="flat", padding=(12, 7))
    style.map("Ghost.TButton", background=[("active", c["fieldBg"])])

    style.configure("Vertical.TScrollbar", background=c["fieldBg"],
                    troughcolor=c["bg"], bordercolor=c["bg"], arrowcolor=c["textDim"])


def round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
               radius: float, **kwargs) -> int:
    """Rectangle à coins arrondis — Canvas n'en propose pas nativement."""
    radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class AccentButton(tk.Canvas):
    """Bouton plein, à coins arrondis, avec état survolé et désactivé."""

    def __init__(self, parent, text: str, command, colors: dict[str, str],
                 height: int = 44, radius: int = 9, primary: bool = True):
        super().__init__(parent, height=height, highlightthickness=0, bd=0,
                         bg=colors["bg"], cursor="hand2")
        self.command = command
        self.colors = colors
        self.radius = radius
        self._text = text
        self._enabled = True
        self._hover = False
        self.primary = primary
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def configure_colors(self, colors: dict[str, str]) -> None:
        self.colors = colors
        self.configure(bg=colors["bg"])
        self._draw()

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _fill(self) -> str:
        c = self.colors
        if self.primary:
            if not self._enabled:
                return c["checkOff"]
            return c["accentHover"] if self._hover else c["accent"]
        return c["fieldBg"] if self._hover else c["btnGhost"]

    def _ink(self) -> str:
        c = self.colors
        if not self._enabled:
            return c["textDim"]
        return c["onAccent"] if self.primary else c["text"]

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        outline = "" if self.primary else self.colors["border"]
        round_rect(self, 1, 1, w - 1, h - 1, self.radius,
                   fill=self._fill(), outline=outline)
        weight = "bold" if self.primary else "normal"
        self.create_text(w / 2, h / 2, text=self._text, fill=self._ink(),
                         font=("", 13, weight))

    def _on_enter(self, _e) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _e) -> None:
        self._hover = False
        self._draw()

    def _on_click(self, _e) -> None:
        if self._enabled and self.command:
            self.command()


class Checkbox(tk.Frame):
    """Case à cocher dessinée : carré arrondi rempli à l'accent quand cochée."""

    def __init__(self, parent, text: str, colors: dict[str, str], value: bool = True):
        super().__init__(parent, bg=colors["bg"])
        self.colors = colors
        self.value = bool(value)
        self.box = tk.Canvas(self, width=18, height=18, highlightthickness=0, bd=0,
                             bg=colors["bg"], cursor="hand2")
        self.box.pack(side="left")
        self.label = tk.Label(self, text=text, bg=colors["bg"], fg=colors["text"],
                              font=("", 12), cursor="hand2")
        self.label.pack(side="left", padx=(9, 0))
        for widget in (self.box, self.label):
            widget.bind("<Button-1>", lambda _e: self.toggle())
        self._draw()

    def configure_colors(self, colors: dict[str, str]) -> None:
        self.colors = colors
        self.configure(bg=colors["bg"])
        self.box.configure(bg=colors["bg"])
        self.label.configure(bg=colors["bg"], fg=colors["text"])
        self._draw()

    def toggle(self) -> None:
        self.value = not self.value
        self._draw()

    def get(self) -> bool:
        return self.value

    def _draw(self) -> None:
        self.box.delete("all")
        c = self.colors
        round_rect(self.box, 1, 1, 17, 17, 4,
                   fill=c["accent"] if self.value else c["checkOff"], outline="")
        if self.value:
            self.box.create_text(9, 9, text="✓", fill=c["onAccent"], font=("", 11, "bold"))


class ProgressBar(tk.Canvas):
    """Barre fine à extrémités arrondies."""

    def __init__(self, parent, colors: dict[str, str], height: int = 6):
        super().__init__(parent, height=height, highlightthickness=0, bd=0, bg=colors["bg"])
        self.colors = colors
        self.value = 0.0
        self.bind("<Configure>", lambda _e: self._draw())

    def configure_colors(self, colors: dict[str, str]) -> None:
        self.colors = colors
        self.configure(bg=colors["bg"])
        self._draw()

    def set(self, fraction: float) -> None:
        self.value = max(0.0, min(1.0, fraction))
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        round_rect(self, 0, 0, w, h, h / 2, fill=self.colors["trackBg"], outline="")
        if self.value > 0:
            filled = max(h, w * self.value)
            round_rect(self, 0, 0, filled, h, h / 2,
                       fill=self.colors["accent"], outline="")
