"""Interface graphique de scdl — Tkinter, sans dépendance externe."""
from __future__ import annotations

import queue
import threading
import webbrowser
from pathlib import Path
from tkinter import (BOTH, END, BooleanVar, IntVar, PhotoImage, StringVar, Tk,
                     filedialog, messagebox, ttk)

import core
from core import Downloader, Options
from genres import resource_dir

DESTINATIONS = [
    ("Rekordbox (dossier DJ)", "dj"),
    ("Apple Music", "music"),
    ("Autre dossier…", "folder"),
]
FORMATS = [("Meilleure qualité, sans conversion", ""), ("MP3", "mp3"), ("M4A / AAC", "m4a")]
BROWSERS = ["Aucun", "safari", "chrome", "firefox", "brave", "edge"]

LABEL_W = 18          # largeur de la colonne des intitulés, en caractères


def palette(root: Tk) -> dict[str, str]:
    """Couleurs lisibles aussi bien en thème clair qu'en thème sombre."""
    try:
        background = ttk.Style().lookup("TFrame", "background") or "#ffffff"
        r, g, b = root.winfo_rgb(background)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 65535
    except Exception:                                    # noqa: BLE001
        luminance = 1.0
    if luminance < 0.5:
        return {"muted": "#9ba1a6", "ok": "#5fd08a", "warn": "#e6b455", "error": "#f0736a"}
    return {"muted": "#6b7280", "ok": "#137333", "warn": "#a8620a", "error": "#c5221f"}


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.colors = palette(root)
        self.queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.custom_folder: Path | None = None
        self.last_root: Path | None = None
        self._icon: PhotoImage | None = None

        root.title("scdl")
        root.minsize(620, 700)
        self._apply_styles()
        self._build()
        if not core.ffmpeg_available():
            self._set_status("ffmpeg est introuvable — la conversion échouera.", "error")
        self.root.after(100, self._drain)

    # ------------------------------------------------------------ apparence ---
    def _apply_styles(self) -> None:
        style = ttk.Style()
        for theme in ("aqua", "vista", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        style.configure("Title.TLabel", font=("", 22, "bold"))
        style.configure("Subtitle.TLabel", font=("", 12), foreground=self.colors["muted"])
        style.configure("Section.TLabel", font=("", 11, "bold"))
        style.configure("Hint.TLabel", font=("", 11), foreground=self.colors["muted"])
        style.configure("Status.TLabel", font=("", 11))
        style.configure("Go.TButton", font=("", 13, "bold"))

    def _load_icon(self) -> PhotoImage | None:
        for candidate in (resource_dir() / "icon-64.png", resource_dir() / "docs" / "icon.png"):
            if candidate.exists():
                try:
                    return PhotoImage(file=str(candidate))
                except Exception:                        # noqa: BLE001
                    continue
        return None

    # ------------------------------------------------------------ interface ---
    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=(22, 18, 22, 18))
        outer.pack(fill=BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        row = 0

        # --- en-tête ---
        header = ttk.Frame(outer)
        header.grid(row=row, column=0, sticky="ew")
        self._icon = self._load_icon()
        if self._icon:
            ttk.Label(header, image=self._icon).pack(side="left", padx=(0, 14))
            try:
                self.root.iconphoto(True, self._icon)
            except Exception:                            # noqa: BLE001
                pass
        titles = ttk.Frame(header)
        titles.pack(side="left", anchor="w")
        ttk.Label(titles, text="scdl", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="SoundCloud vers Rekordbox et Apple Music",
                  style="Subtitle.TLabel").pack(anchor="w")
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, sticky="ew", pady=(16, 16))
        row += 1

        # --- saisie du lien ---
        ttk.Label(outer, text="Lien SoundCloud", style="Section.TLabel").grid(
            row=row, column=0, sticky="w")
        row += 1
        self.urls = ttk.Entry(outer, font=("", 13))
        self.urls.grid(row=row, column=0, sticky="ew", pady=(6, 4), ipady=7)
        self.urls.bind("<Return>", lambda _e: self._start())
        self.urls.focus()
        row += 1
        ttk.Label(outer, style="Hint.TLabel",
                  text="Un morceau, un set, un profil, vos likes ou une playlist "
                       "« Your Mix ». Plusieurs liens : séparez-les par un espace.").grid(
            row=row, column=0, sticky="w")
        row += 1

        # --- réglages ---
        settings = ttk.Frame(outer)
        settings.grid(row=row, column=0, sticky="ew", pady=(18, 0))
        settings.columnconfigure(1, weight=1)
        self._build_settings(settings)
        row += 1

        # --- action ---
        self.button = ttk.Button(outer, text="Télécharger", style="Go.TButton",
                                 command=self._start)
        self.button.grid(row=row, column=0, sticky="ew", pady=(20, 10), ipady=8)
        row += 1

        self.bar = ttk.Progressbar(outer, mode="determinate")
        self.bar.grid(row=row, column=0, sticky="ew")
        row += 1

        self.status = ttk.Label(outer, text="Prêt.", style="Status.TLabel",
                                foreground=self.colors["muted"])
        self.status.grid(row=row, column=0, sticky="w", pady=(8, 12))
        row += 1

        # --- résultats ---
        outer.rowconfigure(row, weight=1)
        results = ttk.Frame(outer)
        results.grid(row=row, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.log = ttk.Treeview(results, columns=("track",), show="headings", height=7)
        self.log.heading("track", text="Morceaux téléchargés")
        self.log.column("track", anchor="w")
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(results, orient="vertical", command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)
        row += 1

        self.open_button = ttk.Button(outer, text="Ouvrir le dossier",
                                      command=self._open_folder)
        self.open_button.grid(row=row, column=0, sticky="ew", pady=(12, 0), ipady=4)
        self.open_button.state(["disabled"])

    def _build_settings(self, parent: ttk.Frame) -> None:
        def label(text: str, r: int) -> None:
            ttk.Label(parent, text=text, width=LABEL_W, anchor="w").grid(
                row=r, column=0, sticky="w", pady=5)

        r = 0
        label("Destination", r)
        self.destination = StringVar(value=DESTINATIONS[0][0])
        combo = ttk.Combobox(parent, textvariable=self.destination, state="readonly",
                             values=[name for name, _ in DESTINATIONS])
        combo.grid(row=r, column=1, sticky="ew", pady=5)
        combo.bind("<<ComboboxSelected>>", self._on_destination)
        self.folder_button = ttk.Button(parent, text="Choisir…", width=10,
                                        command=self._pick_folder)
        self.folder_button.grid(row=r, column=2, sticky="w", padx=(10, 0))
        self.folder_button.state(["disabled"])
        r += 1

        # masquée tant qu'aucun dossier n'est choisi, pour ne pas laisser un blanc
        self.folder_label = ttk.Label(parent, text="", style="Hint.TLabel")
        self.folder_label.grid(row=r, column=1, columnspan=2, sticky="w")
        self.folder_label.grid_remove()
        r += 1

        label("Qualité", r)
        self.audio_format = StringVar(value=FORMATS[0][0])
        ttk.Combobox(parent, textvariable=self.audio_format, state="readonly",
                     values=[name for name, _ in FORMATS]).grid(
            row=r, column=1, columnspan=2, sticky="ew", pady=5)
        r += 1

        label("Compte SoundCloud", r)
        self.browser = StringVar(value=BROWSERS[0])
        ttk.Combobox(parent, textvariable=self.browser, state="readonly", values=BROWSERS,
                     width=12).grid(row=r, column=1, sticky="w", pady=5)
        ttk.Label(parent, text="cookies du navigateur : qualité originale et "
                               "playlists privées", style="Hint.TLabel").grid(
            row=r + 1, column=1, columnspan=2, sticky="w")
        r += 2

        label("Forcer le genre", r)
        genre_row = ttk.Frame(parent)
        genre_row.grid(row=r, column=1, columnspan=2, sticky="w", pady=5)
        self.genre = ttk.Entry(genre_row, width=22)
        self.genre.pack(side="left")
        ttk.Label(genre_row, text="facultatif — sinon celui de SoundCloud",
                  style="Hint.TLabel").pack(side="left", padx=(10, 0))
        r += 1

        label("Limiter à", r)
        limit = ttk.Frame(parent)
        limit.grid(row=r, column=1, columnspan=2, sticky="w", pady=5)
        self.max_items = IntVar(value=0)
        ttk.Spinbox(limit, from_=0, to=999, textvariable=self.max_items, width=5).pack(
            side="left")
        ttk.Label(limit, text="morceaux — 0 pour tout prendre",
                  style="Hint.TLabel").pack(side="left", padx=(10, 0))
        r += 1

        options = ttk.Frame(parent)
        options.grid(row=r, column=0, columnspan=3, sticky="w", pady=(12, 0))
        self.by_genre = BooleanVar(value=True)
        ttk.Checkbutton(options, text="Ranger dans un dossier par genre",
                        variable=self.by_genre).pack(anchor="w", pady=2)
        self.split_artist = BooleanVar(value=True)
        ttk.Checkbutton(options, text="Séparer « Artiste - Titre » automatiquement",
                        variable=self.split_artist).pack(anchor="w", pady=2)

    # -------------------------------------------------------------- actions ---
    def _destination_value(self) -> str:
        return dict(DESTINATIONS)[self.destination.get()]

    def _format_value(self) -> str:
        return dict(FORMATS)[self.audio_format.get()]

    def _on_destination(self, _event=None) -> None:
        if self._destination_value() == "folder":
            self.folder_button.state(["!disabled"])
            if self.custom_folder is None:
                self._pick_folder()
        else:
            self.folder_button.state(["disabled"])
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

    def _set_status(self, text: str, tone: str = "muted") -> None:
        self.status.configure(text=text, foreground=self.colors.get(tone,
                                                                    self.colors["muted"]))

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        urls = [u for u in self.urls.get().replace(",", " ").split() if u.startswith("http")]
        if not urls:
            messagebox.showwarning("scdl", "Collez au moins un lien SoundCloud.")
            return

        destination = self._destination_value()
        if destination == "folder" and self.custom_folder is None:
            self._pick_folder()
            if self.custom_folder is None:
                return

        opts = Options(
            destination=destination,
            folder=self.custom_folder if destination == "folder" else None,
            by_genre=self.by_genre.get(),
            audio_format=self._format_value(),
            genre_override=self.genre.get().strip(),
            browser="" if self.browser.get() == "Aucun" else self.browser.get(),
            max_items=max(0, self.max_items.get()),
            split_artist=self.split_artist.get(),
        )

        self.log.delete(*self.log.get_children())
        self.button.state(["disabled"])
        self.open_button.state(["disabled"])
        self.bar.configure(value=0)
        self._set_status("Démarrage…")

        self.worker = threading.Thread(target=self._run, args=(opts, urls), daemon=True)
        self.worker.start()

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
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _on_progress(self, message: str, pct: float) -> None:
        if message.startswith("✓"):
            self.log.insert("", END, values=(message[2:],))
            self.log.yview_moveto(1)
        else:
            self._set_status(message)
        if pct is not None and pct >= 0:
            self.bar.configure(value=pct * 100)

    def _on_done(self, result) -> None:
        self.button.state(["!disabled"])
        self.bar.configure(value=100 if result.count else 0)
        if result.files:
            first = result.files[0]
            self.last_root = first.parent.parent if result.folders else first.parent
            self.open_button.state(["!disabled"])
        if result.errors:
            self._set_status(f"{result.count} morceau(x), {len(result.errors)} erreur(s).",
                             "warn")
            messagebox.showerror("scdl", "\n\n".join(result.errors[:5]))
        elif result.count:
            self._set_status(f"Terminé — {result.count} morceau(x).", "ok")
        else:
            self._set_status("Rien de nouveau : déjà téléchargé, ou aucun son à cette adresse.")

    def _on_error(self, message: str) -> None:
        self.button.state(["!disabled"])
        self.bar.configure(value=0)
        self._set_status("Échec.", "error")
        messagebox.showerror("scdl", message)


def main() -> None:
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
