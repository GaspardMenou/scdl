"""Interface graphique de scdl — Tkinter, sans dépendance externe."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, PhotoImage, Tk, filedialog, messagebox, ttk

import core
import theme as th
import updater
from core import Downloader, Options
from genres import resource_dir
from version import __version__

DESTINATIONS = [
    ("Rekordbox (dossier DJ)", "dj"),
    ("Apple Music (bibliothèque)", "music"),
    ("Dossier personnalisé…", "folder"),
]
# Libellés fidèles à ce que l'application produit réellement : SoundCloud ne
# sert pas de 320 kbps, l'annoncer serait mensonger.
FORMATS = [("Meilleure qualité (sans conversion)", ""), ("MP3", "mp3"), ("M4A / AAC", "m4a")]
BROWSERS = ["Aucun", "safari", "chrome", "firefox", "brave", "edge"]

LABEL_W = 13          # largeur de la colonne des intitulés, en caractères


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.dark = th.system_prefers_dark()
        self.colors = th.DARK if self.dark else th.LIGHT
        self.queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.custom_folder: Path | None = None
        self.last_root: Path | None = None
        self._icon: PhotoImage | None = None
        self._themed: list = []          # widgets à recolorer lors du basculement

        root.title("SCDL")
        root.minsize(520, 860)            # de quoi laisser respirer la liste des morceaux
        root.geometry("560x900")
        th.apply_ttk(self.colors)
        root.configure(bg=self.colors["bg"])
        self._build()
        self.root.after(100, self._drain)
        # ffmpeg au premier lancement et recherche de mise à jour : en tâche de
        # fond, pour que la fenêtre s'affiche immédiatement.
        threading.Thread(target=self._bootstrap, daemon=True).start()

    # ------------------------------------------------------------ interface ---
    def _build(self) -> None:
        c = self.colors
        self._build_header()

        self._build_banner()

        outer = ttk.Frame(self.root, padding=(24, 22, 24, 20))
        outer.pack(fill=BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        row = 0

        # --- saisie ---
        ttk.Label(outer, text="Liens SoundCloud",
                  font=(th.serif_family(), 17, "bold")).grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Label(outer, style="Dim.TLabel", font=("", 11),
                  text="Un morceau, un set, un profil ou une playlist — une URL par ligne.").grid(
            row=row, column=0, sticky="w", pady=(4, 10))
        row += 1

        self.urls = th.TextArea(outer, c, lines=3)
        self.urls.grid(row=row, column=0, sticky="ew")
        self.urls.text.bind("<Return>", self._on_return)
        self.urls.text.focus()
        self._themed.append(("widget", self.urls))
        row += 1

        self.separator = ttk.Separator(outer)
        self.separator.grid(row=row, column=0, sticky="ew", pady=18)
        row += 1

        settings = ttk.Frame(outer)
        settings.grid(row=row, column=0, sticky="ew")
        settings.columnconfigure(1, weight=1)
        self._build_settings(settings)
        row += 1

        # --- action ---
        self.button = th.AccentButton(outer, "Télécharger", self._start, c)
        self.button.grid(row=row, column=0, sticky="ew", pady=(20, 12))
        self._themed.append(("widget", self.button))
        row += 1

        self.bar = th.ProgressBar(outer, c)
        self.bar.grid(row=row, column=0, sticky="ew")
        self._themed.append(("widget", self.bar))
        row += 1

        self.status = ttk.Label(outer, text="Prêt.", style="Dim.TLabel",
                                font=(th.mono_family(), 11))
        self.status.grid(row=row, column=0, sticky="w", pady=(8, 14))
        row += 1

        # --- résultats ---
        outer.rowconfigure(row, weight=1)
        results = ttk.Frame(outer)
        results.grid(row=row, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.log = ttk.Treeview(results, columns=("track", "dur"), show="headings", height=7)
        self.log.heading("track", text="MORCEAUX TÉLÉCHARGÉS", anchor="w")
        self.log.heading("dur", text="", anchor="e")
        self.log.column("track", anchor="w")
        self.log.column("dur", anchor="e", width=60, stretch=False)
        self.log.tag_configure("done", foreground=c["text"])
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(results, orient="vertical", command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)
        row += 1

        self.open_button = th.AccentButton(outer, "Ouvrir le dossier", self._open_folder,
                                           c, height=38, primary=False)
        self.open_button.grid(row=row, column=0, sticky="ew", pady=(14, 0))
        self.open_button.set_enabled(False)
        self._themed.append(("widget", self.open_button))

    def _build_header(self) -> None:
        c = self.colors
        header = tk.Frame(self.root, bg=c["headerBg"])
        header.pack(fill="x")
        self._themed.append(("header", header))

        inner = tk.Frame(header, bg=c["headerBg"])
        inner.pack(fill="x", padx=18, pady=12)
        self._themed.append(("header", inner))

        self._icon = self._load_icon()
        if self._icon:
            badge = tk.Label(inner, image=self._icon, bg=c["headerBg"])
            badge.pack(side="left", padx=(0, 10))
            self._themed.append(("header", badge))
            try:
                self.root.iconphoto(True, self._icon)
            except Exception:                            # noqa: BLE001
                pass

        name = tk.Label(inner, text="SCDL", bg=c["headerBg"], fg=c["text"],
                        font=("", 13, "bold"))
        name.pack(side="left")
        self._themed.append(("headerText", name))

        subtitle = tk.Label(inner, text="SoundCloud → Rekordbox / Apple Music",
                            bg=c["headerBg"], fg=c["textDim"], font=("", 11))
        subtitle.pack(side="left", padx=(10, 0))
        self._themed.append(("headerDim", subtitle))

        self.theme_button = tk.Label(inner, text=self._theme_label(), bg=c["fieldBg"],
                                     fg=c["text"], font=("", 11), padx=9, pady=4,
                                     cursor=th.HAND)
        self.theme_button.pack(side="right")
        self.theme_button.bind("<Button-1>", lambda _e: self._toggle_theme())
        self._themed.append(("chip", self.theme_button))

    def _build_banner(self) -> None:
        """Bandeau de mise à jour, masqué tant qu'aucune version n'est dispo."""
        c = self.colors
        self.banner = tk.Frame(self.root, bg=c["accent"])
        self.banner_label = tk.Label(self.banner, text="", bg=c["accent"],
                                     fg=c["onAccent"], font=("", 12))
        self.banner_label.pack(side="left", padx=(18, 0), pady=9)
        self.banner_action = tk.Label(self.banner, text="Mettre à jour", bg=c["accent"],
                                      fg=c["onAccent"], font=("", 12, "bold"),
                                      cursor=th.HAND)
        self.banner_action.pack(side="right", padx=18)
        self.banner_action.bind("<Button-1>", lambda _e: self._install_update())
        self._themed += [("banner", self.banner), ("banner", self.banner_label),
                         ("banner", self.banner_action)]
        self._pending_update: updater.Release | None = None

    def _build_settings(self, parent: ttk.Frame) -> None:
        c = self.colors

        def label(text: str, r: int) -> None:
            ttk.Label(parent, text=text, width=LABEL_W, anchor="w", style="Mid.TLabel",
                      font=("", 12)).grid(row=r, column=0, sticky="w", pady=6)

        r = 0
        label("Destination", r)
        self.destination = th.Select(parent, c, [name for name, _ in DESTINATIONS],
                                     on_change=lambda _v: self._on_destination())
        self.destination.grid(row=r, column=1, sticky="ew", pady=6)
        self.folder_button = th.AccentButton(parent, "Choisir…", self._pick_folder, c,
                                             height=36, primary=False)
        self.folder_button.configure(width=100)
        self.folder_button.grid(row=r, column=2, sticky="w", padx=(10, 0))
        self.folder_button.set_enabled(False)
        self._themed += [("widget", self.destination), ("widget", self.folder_button)]
        r += 1

        self.folder_label = ttk.Label(parent, text="", style="Dim.TLabel", font=("", 10))
        self.folder_label.grid(row=r, column=1, columnspan=2, sticky="w")
        self.folder_label.grid_remove()
        r += 1

        label("Qualité", r)
        self.audio_format = th.Select(parent, c, [name for name, _ in FORMATS])
        self.audio_format.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        self._themed.append(("widget", self.audio_format))
        r += 1

        label("Compte", r)
        self.browser = th.Select(parent, c, BROWSERS)
        self.browser.configure(width=150)
        self.browser.grid(row=r, column=1, sticky="w", pady=6)
        ttk.Label(parent, text="cookies du navigateur", style="Dim.TLabel",
                  font=("", 10)).grid(row=r, column=2, sticky="w", padx=(10, 0))
        self._themed.append(("widget", self.browser))
        r += 1

        label("Genre forcé", r)
        self.genre = th.TextField(parent, c)
        self.genre.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6)
        self._themed.append(("widget", self.genre))
        r += 1

        label("Limiter à", r)
        limit = ttk.Frame(parent)
        limit.grid(row=r, column=1, columnspan=2, sticky="w", pady=6)
        self.max_items = th.TextField(limit, c, width=4)
        self.max_items.configure(width=70)
        self.max_items.set("0")
        self.max_items.pack(side="left")
        ttk.Label(limit, text="morceaux (0 = tout)", style="Dim.TLabel",
                  font=("", 10)).pack(side="left", padx=(10, 0))
        self._themed.append(("widget", self.max_items))
        r += 1

        options = ttk.Frame(parent)
        options.grid(row=r, column=0, columnspan=3, sticky="w", pady=(12, 0))
        self.by_genre = th.Checkbox(options, "Ranger dans un dossier par genre", c, True)
        self.by_genre.pack(anchor="w", pady=3)
        self.split_artist = th.Checkbox(options, "Séparer « Artiste – Titre » automatiquement",
                                        c, True)
        self.split_artist.pack(anchor="w", pady=3)
        self._themed += [("widget", self.by_genre), ("widget", self.split_artist)]

    def _load_icon(self) -> PhotoImage | None:
        for candidate in (resource_dir() / "icon-32.png", resource_dir() / "icon-64.png"):
            if candidate.exists():
                try:
                    return PhotoImage(file=str(candidate))
                except Exception:                        # noqa: BLE001
                    continue
        return None

    # ---------------------------------------------------------------- thème ---
    def _theme_label(self) -> str:
        return "☾ Sombre" if self.dark else "☀ Clair"

    def _toggle_theme(self) -> None:
        self.dark = not self.dark
        self.colors = th.DARK if self.dark else th.LIGHT
        c = self.colors
        th.apply_ttk(c)
        self.root.configure(bg=c["bg"])
        self.theme_button.configure(text=self._theme_label())

        for kind, widget in self._themed:
            if kind == "widget":
                widget.configure_colors(c)
            elif kind == "header":
                widget.configure(bg=c["headerBg"])
            elif kind == "headerText":
                widget.configure(bg=c["headerBg"], fg=c["text"])
            elif kind == "headerDim":
                widget.configure(bg=c["headerBg"], fg=c["textDim"])
            elif kind == "chip":
                widget.configure(bg=c["fieldBg"], fg=c["text"])
            elif kind == "banner":
                widget.configure(bg=c["accent"])
                if isinstance(widget, tk.Label):
                    widget.configure(fg=c["onAccent"])
            elif kind == "text":
                widget.configure(bg=c["fieldBg"], fg=c["text"], insertbackground=c["text"],
                                 highlightbackground=c["border"], highlightcolor=c["accent"])
        self.log.tag_configure("done", foreground=c["text"])
        self._set_status(self.status.cget("text"), self._tone)

    # -------------------------------------------------------------- actions ---
    def _destination_value(self) -> str:
        return dict(DESTINATIONS)[self.destination.get()]

    def _format_value(self) -> str:
        return dict(FORMATS)[self.audio_format.get()]

    def _on_return(self, _event):
        self._start()
        return "break"                    # sinon le Text insère un saut de ligne

    def _on_destination(self, _event=None) -> None:
        if self._destination_value() == "folder":
            self.folder_button.set_enabled(True)
            if self.custom_folder is None:
                self._pick_folder()
        else:
            self.folder_button.set_enabled(False)
            self.folder_label.grid_remove()

    def _pick_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Où enregistrer les morceaux ?")
        if chosen:
            self.custom_folder = Path(chosen)
            self.folder_label.configure(text=str(self.custom_folder))
            self.folder_label.grid()

    def _open_folder(self) -> None:
        if self.last_root and self.last_root.exists():
            webbrowser.open(self.last_root.as_uri())

    def _set_status(self, text: str, tone: str = "textDim") -> None:
        self._tone = tone
        self.status.configure(text=text,
                              foreground=self.colors.get(tone, self.colors["textDim"]))

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        raw = self.urls.get()
        urls = [u for u in raw.replace(",", " ").split() if u.startswith("http")]
        if not urls:
            messagebox.showwarning("SCDL", "Collez au moins un lien SoundCloud.")
            return

        destination = self._destination_value()
        if destination == "folder" and self.custom_folder is None:
            self._pick_folder()
            if self.custom_folder is None:
                return

        try:
            limit = max(0, int(self.max_items.get() or 0))
        except ValueError:
            limit = 0

        opts = Options(
            destination=destination,
            folder=self.custom_folder if destination == "folder" else None,
            by_genre=self.by_genre.get(),
            audio_format=self._format_value(),
            genre_override=self.genre.get().strip(),
            browser="" if self.browser.get() == "Aucun" else self.browser.get(),
            max_items=limit,
            split_artist=self.split_artist.get(),
        )

        self.log.delete(*self.log.get_children())
        self.button.set_enabled(False)
        self.button.set_text("Téléchargement…")
        self.open_button.set_enabled(False)
        self.bar.set(0)
        self._set_status("Téléchargement en cours…")

        self.worker = threading.Thread(target=self._run, args=(opts, urls), daemon=True)
        self.worker.start()

    # ------------------------------------------------------- premier lancement ---
    def _bootstrap(self) -> None:
        """Installe ffmpeg s'il manque, puis regarde s'il existe une mise à jour."""
        def progress(message: str, pct: float) -> None:
            self.queue.put(("progress", message, pct))

        if not core.ffmpeg_available():
            self.queue.put(("busy", True, None))
            try:
                core.download_ffmpeg(progress)
            except Exception as exc:                     # noqa: BLE001
                self.queue.put(("progress", f"ffmpeg indisponible : {exc}", -1))
                self.queue.put(("busy", False, None))
                return
            self.queue.put(("progress", "Prêt.", 0.0))
        self.queue.put(("busy", False, None))

        if updater.is_frozen():
            release = updater.check()
            if release:
                self.queue.put(("update", release, None))

    def _show_update(self, release: updater.Release) -> None:
        self._pending_update = release
        self.banner_label.configure(
            text=f"Version {release.version} disponible — vous avez la {__version__}.")
        self.banner.pack(fill="x", after=self.root.winfo_children()[0])

    def _install_update(self) -> None:
        release = self._pending_update
        if not release:
            return
        self.banner_action.configure(text="Installation…")
        self._pending_update = None

        def work() -> None:
            try:
                bundle = updater.download(
                    release, lambda m, p: self.queue.put(("progress", m, p)))
                updater.apply(bundle)
                self.queue.put(("quit", None, None))
            except Exception as exc:                     # noqa: BLE001
                self.queue.put(("error", f"Mise à jour impossible : {exc}", None))

        threading.Thread(target=work, daemon=True).start()

    def _run(self, opts: Options, urls: list[str]) -> None:
        def progress(message: str, pct: float) -> None:
            self.queue.put(("progress", message, pct))
        try:
            self.queue.put(("done", Downloader(opts, progress).run(urls), None))
        except Exception as exc:                         # noqa: BLE001
            self.queue.put(("error", str(exc), None))

    # ------------------------------------------------------------- boucle UI ---
    def _drain(self) -> None:
        try:
            while True:
                kind, payload, extra = self.queue.get_nowait()
                if kind == "progress":
                    self._on_progress(payload, extra)
                elif kind == "done":
                    self._on_done(payload)
                elif kind == "error":
                    self._on_error(payload)
                elif kind == "busy":
                    self.button.set_enabled(not payload)
                elif kind == "update":
                    self._show_update(payload)
                elif kind == "quit":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        # La fenêtre peut être fermée entre deux passages : sans ce garde-fou,
        # Tk se plaint d'une commande invoquée sur une application détruite.
        if self.root.winfo_exists():
            self.root.after(100, self._drain)

    def _on_progress(self, message: str, pct: float) -> None:
        if message.startswith("✓"):
            self.log.insert("", END, values=(message[2:], ""), tags=("done",))
            self.log.yview_moveto(1)
        else:
            self._set_status(message)
        if pct is not None and pct >= 0:
            self.bar.set(pct)

    def _on_done(self, result) -> None:
        self.button.set_enabled(True)
        self.button.set_text("Télécharger")
        self.bar.set(1.0 if result.count else 0.0)
        if result.files:
            first = result.files[0]
            self.last_root = first.parent.parent if result.folders else first.parent
            self.open_button.set_enabled(True)
        if result.errors:
            self._set_status(f"{result.count} morceau(x), {len(result.errors)} erreur(s).",
                             "error")
            messagebox.showerror("SCDL", "\n\n".join(result.errors[:5]))
        elif result.count:
            self._set_status(f"Terminé — {result.count} morceau(x) téléchargé(s).", "ok")
        else:
            self._set_status("Rien de nouveau : déjà téléchargé, ou aucun son ici.")

    def _on_error(self, message: str) -> None:
        self.button.set_enabled(True)
        self.button.set_text("Télécharger")
        self.bar.set(0)
        self._set_status("Erreur : lien invalide ou introuvable.", "error")
        messagebox.showerror("SCDL", message)


def main() -> None:
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
