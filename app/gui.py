"""Interface graphique de scdl — Tkinter, sans dépendance externe."""
from __future__ import annotations

import queue
import threading
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, StringVar, Tk, BooleanVar, IntVar, filedialog, messagebox
from tkinter import ttk

import core
from core import Downloader, Options

DESTINATIONS = [
    ("Rekordbox (dossier DJ)", "dj"),
    ("Apple Music", "music"),
    ("Autre dossier…", "folder"),
]
FORMATS = [("Meilleure qualité (sans conversion)", ""), ("MP3", "mp3"), ("M4A / AAC", "m4a")]
BROWSERS = ["Aucun", "safari", "chrome", "firefox", "brave", "edge"]


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.custom_folder: Path | None = None

        root.title("scdl — SoundCloud vers Rekordbox et Apple Music")
        root.minsize(640, 560)
        self._build()
        self._check_dependencies()
        self.root.after(100, self._drain)

    # ------------------------------------------------------------ interface ---
    def _build(self) -> None:
        pad = {"padx": 12, "pady": 6}
        frame = ttk.Frame(self.root, padding=14)
        frame.pack(fill=BOTH, expand=True)
        frame.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frame, text="Liens SoundCloud", font=("", 13, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 2))
        row += 1
        ttk.Label(frame, text="Un morceau, un set, un profil ou une playlist — "
                              "une URL par ligne.", foreground="#666").grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
        row += 1

        self.urls = ttk.Entry(frame, font=("", 12))
        self.urls.grid(row=row, column=0, columnspan=3, sticky="ew", ipady=6)
        self.urls.focus()
        row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1

        # destination
        ttk.Label(frame, text="Destination").grid(row=row, column=0, sticky="w", **pad)
        self.destination = StringVar(value=DESTINATIONS[0][0])
        combo = ttk.Combobox(frame, textvariable=self.destination, state="readonly",
                             values=[label for label, _ in DESTINATIONS])
        combo.grid(row=row, column=1, sticky="ew", **pad)
        combo.bind("<<ComboboxSelected>>", self._on_destination)
        self.folder_button = ttk.Button(frame, text="Choisir…", command=self._pick_folder)
        self.folder_button.grid(row=row, column=2, sticky="w", **pad)
        self.folder_button.state(["disabled"])
        row += 1

        self.folder_label = ttk.Label(frame, text="", foreground="#666")
        self.folder_label.grid(row=row, column=1, columnspan=2, sticky="w", padx=12)
        row += 1

        # qualité
        ttk.Label(frame, text="Qualité").grid(row=row, column=0, sticky="w", **pad)
        self.audio_format = StringVar(value=FORMATS[0][0])
        ttk.Combobox(frame, textvariable=self.audio_format, state="readonly",
                     values=[label for label, _ in FORMATS]).grid(
            row=row, column=1, columnspan=2, sticky="ew", **pad)
        row += 1

        # cookies
        ttk.Label(frame, text="Compte SoundCloud").grid(row=row, column=0, sticky="w", **pad)
        self.browser = StringVar(value=BROWSERS[0])
        ttk.Combobox(frame, textvariable=self.browser, state="readonly",
                     values=BROWSERS).grid(row=row, column=1, sticky="ew", **pad)
        ttk.Label(frame, text="via les cookies du navigateur",
                  foreground="#666").grid(row=row, column=2, sticky="w")
        row += 1

        # genre forcé
        ttk.Label(frame, text="Forcer le genre").grid(row=row, column=0, sticky="w", **pad)
        self.genre = ttk.Entry(frame)
        self.genre.grid(row=row, column=1, sticky="ew", **pad)
        ttk.Label(frame, text="facultatif", foreground="#666").grid(
            row=row, column=2, sticky="w")
        row += 1

        # options
        self.by_genre = BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Ranger dans un dossier par genre",
                        variable=self.by_genre).grid(row=row, column=0, columnspan=3,
                                                     sticky="w", padx=12)
        row += 1
        self.split_artist = BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Séparer « Artiste - Titre » automatiquement",
                        variable=self.split_artist).grid(row=row, column=0, columnspan=3,
                                                         sticky="w", padx=12)
        row += 1

        ttk.Label(frame, text="Limiter à").grid(row=row, column=0, sticky="w", **pad)
        self.max_items = IntVar(value=0)
        ttk.Spinbox(frame, from_=0, to=999, textvariable=self.max_items, width=6).grid(
            row=row, column=1, sticky="w", **pad)
        ttk.Label(frame, text="morceaux (0 = tout)", foreground="#666").grid(
            row=row, column=1, sticky="w", padx=90)
        row += 1

        # action
        self.button = ttk.Button(frame, text="Télécharger", command=self._start)
        self.button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(14, 6), ipady=6)
        row += 1

        self.bar = ttk.Progressbar(frame, mode="determinate")
        self.bar.grid(row=row, column=0, columnspan=3, sticky="ew", padx=12)
        row += 1

        self.status = ttk.Label(frame, text="Prêt.", foreground="#666")
        self.status.grid(row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 8))
        row += 1

        frame.rowconfigure(row, weight=1)
        self.log = ttk.Treeview(frame, columns=("f",), show="headings", height=8)
        self.log.heading("f", text="Morceaux téléchargés")
        self.log.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=12)
        row += 1

        self.open_button = ttk.Button(frame, text="Ouvrir le dossier",
                                      command=self._open_folder)
        self.open_button.grid(row=row, column=0, columnspan=3, sticky="ew",
                              padx=12, pady=(8, 0))
        self.open_button.state(["disabled"])
        self.last_root: Path | None = None

    def _check_dependencies(self) -> None:
        if not core.ffmpeg_available():
            self.status.configure(text="ffmpeg introuvable — la conversion échouera.",
                                  foreground="#c00")

    # -------------------------------------------------------------- actions ---
    def _on_destination(self, _event=None) -> None:
        if self._destination_value() == "folder":
            self.folder_button.state(["!disabled"])
            if self.custom_folder is None:
                self._pick_folder()
        else:
            self.folder_button.state(["disabled"])
            self.folder_label.configure(text="")

    def _destination_value(self) -> str:
        return dict(DESTINATIONS)[self.destination.get()]

    def _format_value(self) -> str:
        return dict(FORMATS)[self.audio_format.get()]

    def _pick_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Où enregistrer les morceaux ?")
        if chosen:
            self.custom_folder = Path(chosen)
            self.folder_label.configure(text=str(self.custom_folder))

    def _open_folder(self) -> None:
        if self.last_root:
            webbrowser.open(self.last_root.as_uri())

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        urls = [u for u in self.urls.get().replace(",", " ").split() if u.startswith("http")]
        if not urls:
            messagebox.showwarning("scdl", "Colle au moins un lien SoundCloud.")
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
        self.status.configure(text="Démarrage…", foreground="#666")

        self.worker = threading.Thread(target=self._run, args=(opts, urls), daemon=True)
        self.worker.start()

    def _run(self, opts: Options, urls: list[str]) -> None:
        def progress(message: str, pct: float) -> None:
            self.queue.put(("progress", message, pct))
        try:
            result = Downloader(opts, progress).run(urls)
            self.queue.put(("done", result, None))
        except Exception as exc:                     # noqa: BLE001
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
            self.status.configure(text=message, foreground="#666")
        if pct is not None and pct >= 0:
            self.bar.configure(mode="determinate", value=pct * 100)

    def _on_done(self, result) -> None:
        self.button.state(["!disabled"])
        self.bar.configure(value=100)
        if result.files:
            self.last_root = result.files[0].parent.parent if result.folders else result.files[0].parent
            self.open_button.state(["!disabled"])
        if result.errors:
            self.status.configure(
                text=f"{result.count} morceau(x) — {len(result.errors)} erreur(s).",
                foreground="#c60")
            messagebox.showerror("scdl", "\n\n".join(result.errors[:5]))
        elif result.count:
            self.status.configure(text=f"Terminé — {result.count} morceau(x).",
                                  foreground="#080")
        else:
            self.status.configure(
                text="Rien de nouveau (déjà téléchargé, ou aucun son à cette adresse).",
                foreground="#666")

    def _on_error(self, message: str) -> None:
        self.button.state(["!disabled"])
        self.bar.configure(value=0)
        self.status.configure(text="Échec.", foreground="#c00")
        messagebox.showerror("scdl", message)


def main() -> None:
    root = Tk()
    try:
        ttk.Style().theme_use("aqua")          # macOS ; ignoré ailleurs
    except Exception:                          # noqa: BLE001
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
