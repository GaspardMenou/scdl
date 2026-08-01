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


# « hand2 » vient de X11 : macOS le rend en bitmap noir et blanc à l'ancienne
# au lieu de la main du système. Chaque plateforme a son nom natif.
HAND = {"darwin": "pointinghand", "win32": "hand2"}.get(sys.platform, "hand2")


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

    # Barre de défilement sans les flèches d'antan : on redéfinit sa structure,
    # clam ne permet pas de les masquer autrement.
    style.layout("Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]}),
    ])
    style.configure("Vertical.TScrollbar", background=c["checkOff"], troughcolor=c["listBg"],
                    bordercolor=c["listBg"], relief="flat", arrowcolor=c["textDim"], width=8)
    style.map("Vertical.TScrollbar", background=[("active", c["textDim"])])


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
                         bg=colors["bg"], cursor=HAND)
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
        self.configure(cursor=HAND if enabled else "arrow")
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


class RoundedField(tk.Canvas):
    """Base des champs dessinés : rectangle arrondi qui réagit au survol et au
    focus. ttk ne sait pas arrondir ses widgets, on peint donc le fond nous-même
    et on pose la vraie zone de saisie par-dessus."""

    HEIGHT = 36
    RADIUS = 8
    PAD_X = 12

    def __init__(self, parent, colors: dict[str, str], height: int | None = None):
        super().__init__(parent, height=height or self.HEIGHT, highlightthickness=0,
                         bd=0, bg=colors["bg"])
        self.colors = colors
        self._focused = False
        self._hover = False
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    # -- couleurs -----------------------------------------------------------
    def _border(self) -> str:
        c = self.colors
        if self._focused:
            return c["accent"]
        return c["textDim"] if self._hover else c["border"]

    def configure_colors(self, colors: dict[str, str]) -> None:
        self.colors = colors
        self.configure(bg=colors["bg"])
        self._recolor_children()
        self._redraw()

    def _recolor_children(self) -> None:
        pass

    # -- rendu --------------------------------------------------------------
    def _redraw(self) -> None:
        self.delete("bg")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        round_rect(self, 1, 1, w - 1, h - 1, self.RADIUS, fill=self.colors["fieldBg"],
                   outline=self._border(), width=1, tags="bg")
        self.tag_lower("bg")
        self._layout(w, h)

    def _layout(self, width: int, height: int) -> None:
        pass

    def _on_enter(self, _e) -> None:
        self._hover = True
        self._redraw()

    def _on_leave(self, _e) -> None:
        self._hover = False
        self._redraw()

    def _on_focus(self, focused: bool) -> None:
        self._focused = focused
        self._redraw()


class TextField(RoundedField):
    """Champ de saisie sur fond arrondi."""

    def __init__(self, parent, colors: dict[str, str], placeholder: str = "",
                 mono: bool = False, width: int | None = None):
        super().__init__(parent, colors)
        self.placeholder = placeholder
        family = mono_family() if mono else ""
        self.entry = tk.Entry(self, bd=0, relief="flat", highlightthickness=0,
                              bg=colors["fieldBg"], fg=colors["text"],
                              insertbackground=colors["text"], font=(family, 12))
        if width:
            self.entry.configure(width=width)
        self._window = self.create_window(self.PAD_X, self.HEIGHT / 2,
                                          window=self.entry, anchor="w")
        self.entry.bind("<FocusIn>", lambda _e: self._on_focus(True))
        self.entry.bind("<FocusOut>", lambda _e: self._on_focus(False))
        self.entry.bind("<Enter>", self._on_enter)

    def _recolor_children(self) -> None:
        c = self.colors
        self.entry.configure(bg=c["fieldBg"], fg=c["text"], insertbackground=c["text"])

    def _layout(self, width: int, height: int) -> None:
        self.coords(self._window, self.PAD_X, height / 2)
        self.itemconfigure(self._window, width=max(20, width - 2 * self.PAD_X))

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)


class TextArea(RoundedField):
    """Zone de saisie multiligne sur fond arrondi."""

    def __init__(self, parent, colors: dict[str, str], lines: int = 3):
        height = 22 * lines + 20
        super().__init__(parent, colors, height=height)
        self.text = tk.Text(self, bd=0, relief="flat", highlightthickness=0, wrap="word",
                            bg=colors["fieldBg"], fg=colors["text"],
                            insertbackground=colors["text"],
                            font=(mono_family(), 12), height=lines)
        self._window = self.create_window(self.PAD_X, 10, window=self.text, anchor="nw")
        self.text.bind("<FocusIn>", lambda _e: self._on_focus(True))
        self.text.bind("<FocusOut>", lambda _e: self._on_focus(False))

    def _recolor_children(self) -> None:
        c = self.colors
        self.text.configure(bg=c["fieldBg"], fg=c["text"], insertbackground=c["text"])

    def _layout(self, width: int, height: int) -> None:
        self.itemconfigure(self._window, width=max(20, width - 2 * self.PAD_X),
                           height=max(20, height - 20))

    def get(self) -> str:
        return self.text.get("1.0", "end")


class Select(RoundedField):
    """Menu déroulant dessiné : rectangle arrondi, libellé et chevron.
    À l'ouverture on montre un tk.Menu natif, qui gère seul clavier et écrans."""

    def __init__(self, parent, colors: dict[str, str], values: list[str],
                 on_change=None):
        super().__init__(parent, colors)
        self.values = list(values)
        self.on_change = on_change
        self.variable = tk.StringVar(value=self.values[0] if self.values else "")
        self.configure(cursor=HAND)
        self.bind("<Button-1>", self._open)

    def _layout(self, width: int, height: int) -> None:
        self.delete("content")
        c = self.colors
        self.create_text(self.PAD_X, height / 2, anchor="w", text=self.variable.get(),
                         fill=c["text"], font=("", 12), tags="content")
        x = width - 18
        y = height / 2 - 2
        self.create_line(x - 5, y, x, y + 5, x + 5, y, fill=c["textMid"], width=2,
                         capstyle="round", joinstyle="round", tags="content")

    def _open(self, event) -> None:
        menu = tk.Menu(self, tearoff=0)
        for value in self.values:
            menu.add_radiobutton(label=value, variable=self.variable, value=value,
                                 command=self._changed)
        try:
            menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        finally:
            menu.grab_release()

    def _changed(self) -> None:
        self._redraw()
        if self.on_change:
            self.on_change(self.variable.get())

    def get(self) -> str:
        return self.variable.get()

    def set(self, value: str) -> None:
        self.variable.set(value)
        self._redraw()


class Checkbox(tk.Frame):
    """Case à cocher dessinée : carré arrondi rempli à l'accent quand cochée."""

    def __init__(self, parent, text: str, colors: dict[str, str], value: bool = True):
        super().__init__(parent, bg=colors["bg"])
        self.colors = colors
        self.value = bool(value)
        self.box = tk.Canvas(self, width=18, height=18, highlightthickness=0, bd=0,
                             bg=colors["bg"], cursor=HAND)
        self.box.pack(side="left")
        self.label = tk.Label(self, text=text, bg=colors["bg"], fg=colors["text"],
                              font=("", 12), cursor=HAND)
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
