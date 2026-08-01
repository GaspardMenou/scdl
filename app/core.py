"""Cœur de scdl : téléchargement, rangement, tags et playlists.

Multiplateforme (macOS / Windows / Linux). Aucune commande shell : yt-dlp et
mutagen sont utilisés comme bibliothèques, seul ffmpeg reste un binaire externe
(embarqué dans l'app packagée).
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import mutagen
import yt_dlp

import meta
from genres import Genres, resource_dir

AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aiff", ".aif", ".flac", ".opus", ".ogg"}
NO_GENRE = "Sans genre"


# --------------------------------------------------------------- chemins ---
def music_dir() -> Path:
    return Path.home() / "Music"


def dj_library() -> Path:
    return music_dir() / "rekordbox" / "SoundCloud"


def apple_music_autoadd() -> Path | None:
    """Dossier d'import automatique d'Apple Music / iTunes, s'il existe."""
    candidates = [
        music_dir() / "Music" / "Media.localized" / "Automatically Add to Music.localized",
        music_dir() / "Music" / "Media" / "Automatically Add to Music",
        music_dir() / "iTunes" / "iTunes Media" / "Automatically Add to iTunes",
        music_dir() / "iTunes" / "iTunes Media" / "Automatically Add to Music",
    ]
    return next((p for p in candidates if p.is_dir()), None)


# ffmpeg pèse 47 Mo à lui seul : le sortir du bundle ramène l'application à
# quelques mégaoctets, et permet de ne mettre à jour qu'elle. Il est téléchargé
# une fois au premier lancement, puis conservé.
FFMPEG_BASE = "https://github.com/imageio/imageio-binaries/raw/master/ffmpeg"
FFMPEG_BUILDS = {
    ("darwin", "arm64"): "ffmpeg-macos-aarch64-v7.1",
    ("darwin", "x86_64"): "ffmpeg-macos-x86_64-v7.1",
    ("win32", "x86_64"): "ffmpeg-win-x86_64-v7.1.exe",
}


def _arch() -> str:
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "arm64"
    return "x86_64"


def exe_name() -> str:
    return "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"


def data_dir() -> Path:
    """Dossier de données de l'application, propre à chaque système."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "scdl"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cached_ffmpeg() -> Path:
    return data_dir() / "bin" / exe_name()


def ffmpeg_dir() -> str | None:
    """Dossier contenant ffmpeg : téléchargé, embarqué, ou celui du système."""
    cached = cached_ffmpeg()
    if cached.exists():
        return str(cached.parent)
    bundled = resource_dir() / "bin" / exe_name()
    if bundled.exists():
        return str(bundled.parent)
    system = shutil.which("ffmpeg")
    return str(Path(system).parent) if system else None


def ffmpeg_available() -> bool:
    return ffmpeg_dir() is not None


def download_ffmpeg(progress: Callable[[str, float], None] | None = None) -> Path:
    """Récupère ffmpeg pour ce système et le range dans le dossier de données."""
    notify = progress or (lambda msg, pct: None)
    build = FFMPEG_BUILDS.get((sys.platform, _arch()))
    if build is None:
        raise RuntimeError(
            f"Aucun ffmpeg pré-compilé pour {sys.platform}/{_arch()}.\n"
            "Installez ffmpeg vous-même, l'application le détectera.")

    target = cached_ffmpeg()
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")

    notify("Téléchargement de ffmpeg (une seule fois)…", 0.0)
    with urllib.request.urlopen(f"{FFMPEG_BASE}/{build}", timeout=60) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with partial.open("wb") as out:
            while chunk := response.read(262144):
                out.write(chunk)
                done += len(chunk)
                if total:
                    notify(f"Téléchargement de ffmpeg — {done // 1048576} / "
                           f"{total // 1048576} Mo", done / total)

    partial.replace(target)               # remplacement atomique : jamais de binaire tronqué
    if sys.platform != "win32":
        os.chmod(target, 0o755)
    notify("ffmpeg installé.", 1.0)
    return target


# --------------------------------------------------------------- options ---
@dataclass
class Options:
    destination: str = "dj"          # "dj" | "music" (Apple Music) | "folder"
    folder: Path | None = None       # dossier explicite pour "folder"/"dj"
    by_genre: bool = True
    audio_format: str = ""           # "" = pas de conversion (mode DJ), sinon mp3/m4a
    genre_override: str = ""
    album_override: str = ""
    browser: str = ""                # cookies : safari, chrome, firefox…
    max_items: int = 0
    use_archive: bool = True
    split_artist: bool = True


@dataclass
class Result:
    files: list[Path] = field(default_factory=list)
    folders: set[Path] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.files)


Progress = Callable[[str, float], None]   # (message, avancement 0..1 ou -1)


# ------------------------------------------------------------ traitement ---
class Downloader:
    def __init__(self, opts: Options, progress: Progress | None = None):
        self.opts = opts
        self.genres = Genres()
        self.progress = progress or (lambda msg, pct: None)

    # -- destination --------------------------------------------------------
    def target_root(self) -> Path:
        if self.opts.destination == "music":
            root = apple_music_autoadd()
            if root is None:
                raise RuntimeError(
                    "Dossier d'import automatique d'Apple Music introuvable.\n"
                    "Choisis « Dossier » ou « Rekordbox » comme destination."
                )
            return root
        root = self.opts.folder or dj_library()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def archive_path(self, root: Path) -> Path:
        # Apple Music déplace les fichiers : l'historique vit à côté, pas dedans.
        base = root if self.opts.destination != "music" else music_dir() / "SoundCloud-DL"
        base.mkdir(parents=True, exist_ok=True)
        return base / ".scdl-archive.txt"

    # -- options yt-dlp -----------------------------------------------------
    def ydl_options(self, workdir: Path, root: Path) -> dict:
        fmt = self.opts.audio_format
        pps: list[dict] = [
            {"key": "FFmpegExtractAudio",
             "preferredcodec": fmt or "best",
             "preferredquality": "0"},
            {"key": "EmbedThumbnail", "already_have_thumbnail": False},
        ]
        opts: dict = {
            "format": "bestaudio/best",
            # Sans conversion on veut le meilleur débit ; en mp3/m4a on préfère
            # le codec déjà servi par SoundCloud pour éviter un ré-encodage.
            "format_sort": ["abr", "asr"] if not fmt else [f"acodec:{fmt}", "abr"],
            "postprocessors": pps,
            "writethumbnail": True,
            "outtmpl": {"default": str(workdir / "%(autonumber)05d-%(id)s.%(ext)s")},
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "ignoreerrors": True,
            "consoletitle": False,
            "progress_hooks": [self._hook],
        }
        if ffmpeg_dir():
            opts["ffmpeg_location"] = ffmpeg_dir()
        if self.opts.browser:
            opts["cookiesfrombrowser"] = (self.opts.browser.lower(),)
        if self.opts.max_items:
            opts["playlistend"] = self.opts.max_items
        if self.opts.use_archive:
            opts["download_archive"] = str(self.archive_path(root))
        return opts

    def _hook(self, d: dict) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = done / total if total else -1
            self.progress(f"Téléchargement — {d.get('info_dict', {}).get('title', '')}"[:70], pct)
        elif d.get("status") == "finished":
            self.progress("Conversion audio…", -1)

    # -- pipeline -----------------------------------------------------------
    def run(self, urls: Iterable[str]) -> Result:
        urls = [u.strip() for u in urls if u.strip()]
        result = Result()
        if not urls:
            return result
        if not ffmpeg_available():
            result.errors.append("ffmpeg est introuvable — impossible de convertir l'audio.")
            return result

        root = self.target_root()
        with tempfile.TemporaryDirectory(prefix="scdl-") as tmp:
            workdir = Path(tmp)
            with yt_dlp.YoutubeDL(self.ydl_options(workdir, root)) as ydl:
                for url in urls:
                    try:
                        info = ydl.extract_info(url, download=True)
                    except Exception as exc:                  # noqa: BLE001
                        result.errors.append(f"{url} : {exc}")
                        continue
                    if info:
                        for entry in self._entries(info):
                            self._place(entry, root, result)

        for folder in sorted(result.folders):
            write_playlist(folder)
        self.progress("Terminé", 1.0)
        return result

    @staticmethod
    def _entries(info: dict) -> list[dict]:
        if info.get("_type") == "playlist" or "entries" in info:
            return [e for e in (info.get("entries") or []) if e]
        return [info]

    def _downloaded_path(self, entry: dict) -> Path | None:
        for req in entry.get("requested_downloads") or []:
            path = req.get("filepath") or req.get("_filename")
            if path and Path(path).exists():
                return Path(path)
        return None

    def _place(self, entry: dict, root: Path, result: Result) -> None:
        src = self._downloaded_path(entry)
        if src is None or src.suffix.lower() not in AUDIO_EXT:
            return

        tags = meta.build(entry, self.genres,
                          genre_override=self.opts.genre_override,
                          album_override=self.opts.album_override,
                          split_artist=self.opts.split_artist)
        write_tags(src, tags)

        folder = root
        if self.opts.by_genre and self.opts.destination != "music":
            folder = canonical_dir(root, tags.genre or NO_GENRE)

        name = meta.safe_filename(f"{tags.artist} - {tags.title}" if tags.artist else tags.title)
        dest = unique_path(folder / f"{name}{src.suffix.lower()}")
        shutil.move(str(src), str(dest))

        result.files.append(dest)
        if folder != root:
            result.folders.add(folder)
        self.progress(f"✓ {dest.name}", -1)


# ------------------------------------------------------------ utilitaires ---
def write_tags(path: Path, tags: meta.Tags) -> None:
    """Écrit les tags sans remuxer — mutagen édite le conteneur en place."""
    try:
        audio = mutagen.File(str(path), easy=True)
        if audio is None:
            return
        if audio.tags is None:
            audio.add_tags()
        for field_name, value in tags.as_dict().items():
            try:
                audio[field_name] = value
            except (KeyError, ValueError):
                pass          # champ non supporté par ce conteneur (ex. comment en MP4)
        audio.save()
    except Exception:         # noqa: BLE001 — un tag raté ne doit pas perdre le fichier
        pass


def canonical_dir(root: Path, name: str) -> Path:
    """Dossier du genre, en réutilisant un dossier qui ne diffère que par la casse.

    Sur les disques insensibles à la casse « hard techno » et « Hard Techno »
    sont le même dossier : on le renomme vers la forme canonique.
    """
    wanted = meta.safe_filename(name, 80)
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir() and child.name.lower() == wanted.lower():
                if child.name != wanted:
                    tmp = root / f".scdl-rename-{os.getpid()}"
                    child.rename(tmp)
                    tmp.rename(root / wanted)
                break
    target = root / wanted
    target.mkdir(parents=True, exist_ok=True)
    return target


def unique_path(path: Path) -> Path:
    """Ne jamais écraser un fichier existant."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    n = 2
    while (candidate := parent / f"{stem} ({n}){suffix}").exists():
        n += 1
    return candidate


def audio_files(folder: Path) -> list[Path]:
    return sorted((p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in AUDIO_EXT),
                  key=lambda p: p.name.lower())


def write_playlist(folder: Path) -> None:
    """Playlists .m3u8 et .m3u au format exact de Rekordbox : CRLF, chemins absolus."""
    tracks = audio_files(folder)
    if not tracks:
        return
    lines = ["#EXTM3U"]
    for path in tracks:
        audio = None
        try:
            audio = mutagen.File(str(path), easy=True)
        except Exception:             # noqa: BLE001
            pass
        duration = int(getattr(getattr(audio, "info", None), "length", 0) or -1)
        title = _first(audio, "title") or path.stem
        artist = _first(audio, "artist") or "Inconnu"
        lines.append(f"#EXTINF:{duration},{artist} - {title}")
        lines.append(str(path))
    body = "\r\n".join(lines) + "\r\n"
    for ext in (".m3u8", ".m3u"):
        (folder / f"{folder.name}{ext}").write_text(body, encoding="utf-8")


def _first(audio, field_name: str) -> str:
    if not audio:
        return ""
    try:
        value = audio.get(field_name)
    except Exception:                 # noqa: BLE001
        return ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")
