"""Nettoyage des titres SoundCloud et construction des tags.

Toute la logique qui était dispersée dans des regex yt-dlp et des fonctions bash
est ici, en un seul endroit testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from genres import Genres

# --- nettoyage des mentions "free download" -------------------------------
# L'ordre compte. Un groupe entre crochets entièrement consacré au free download
# part en entier ; sinon on retire la mention SANS toucher aux parenthèses, faute
# de quoi "(Free DL extended)" laisserait un "extended)" orphelin.
_FREE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[\[\({<]\s*(?:click\s+)?(?:buy\s*(?:link)?\s*(?:=|for|->|→)\s*)?"
                r"free\s*(?:dl|d\s*/\s*l|download)s?\s*[\]\)}>]", re.I), ""),
    (re.compile(r"(?:click\s+)?buy\s*(?:link)?\s*(?:=|for|->|→)\s*"
                r"free\s*(?:dl|d\s*/\s*l|download)s?", re.I), ""),
    (re.compile(r"[*!|~_]*\s*\bfree\s*(?:dl|d\s*/\s*l|download)s?\b\s*[*!|~_]*", re.I), " "),
    # préfixes de promo en début de titre
    (re.compile(r"^\s*[\[\(]?\s*(?:premi[eè]re|premier|exclusive|exclu|out\s*now)"
                r"\s*[\]\)]?\s*[:|\-–]\s*", re.I), ""),
    # mentions de soutien en fin de titre
    (re.compile(r"\s*[*!]+\s*(?:played|supported|premiered)\s+by\s+.*$", re.I), ""),
    # restes : espaces collés aux parenthèses, groupes vides, séparateurs orphelins
    (re.compile(r"([\(\[\{])\s+"), r"\1"),
    (re.compile(r"\s+([\)\]\}])"), r"\1"),
    (re.compile(r"[\(\[\{]\s*[\)\]\}]"), ""),
    (re.compile(r"\s{2,}"), " "),
    (re.compile(r"^[\s\-–—|:,*]+"), ""),
    (re.compile(r"[\s\-–—|:,*]+$"), ""),
]

_SPLIT = re.compile(r"(.+?)\s+-\s+(.+)")


def scrub(title: str) -> str:
    """Retire les mentions promotionnelles d'un titre."""
    for pattern, repl in _FREE_RULES:
        title = pattern.sub(repl, title)
    return title.strip()


def strip_genre_suffix(title: str, genres: Genres) -> str:
    """« Dirty Talk / Hard Techno » → « Dirty Talk ».

    Ne coupe que si ce qui suit le « / » est un genre répertorié, pour laisser
    intacts les titres légitimes comme « AC/DC Tribute » ou « Track A / Track B ».
    """
    head, sep, tail = title.rpartition("/")
    if sep and genres.known(tail):
        return head.strip()
    return title


@dataclass
class Tags:
    title: str
    artist: str
    album: str
    albumartist: str
    genre: str
    comment: str

    def as_dict(self) -> dict[str, str]:
        return {k: v for k, v in vars(self).items() if v}


def build(info: dict, genres: Genres, *, genre_override: str = "",
          album_override: str = "", split_artist: bool = True) -> Tags:
    """Construit les tags d'un morceau à partir des métadonnées yt-dlp."""
    raw_title = scrub(info.get("title") or "")
    artist = (info.get("uploader") or "").strip()

    # Convention dominante sur SoundCloud : « Artiste - Titre ».
    if split_artist:
        m = _SPLIT.match(raw_title)
        if m:
            artist, raw_title = m.group(1).strip(), m.group(2).strip()

    title = strip_genre_suffix(raw_title, genres) or raw_title

    if genre_override:
        genre = genre_override
    else:
        tags = info.get("tags") or []
        genre = genres.canon(info.get("genre") or (tags[0] if tags else ""))

    playlist = (info.get("playlist") or "").strip()
    album = album_override or playlist or title
    albumartist = (info.get("playlist_uploader") or "").strip() or artist

    return Tags(
        title=title,
        artist=artist,
        album=album,
        albumartist=albumartist,
        genre="" if genre == "Sans genre" else genre,
        comment=info.get("webpage_url") or "",
    )


def safe_filename(name: str, maxlen: int = 150) -> str:
    """Nom de fichier valable sur les trois OS (Windows interdit \\ / : * ? \" < > |)."""
    name = re.sub(r'[\\/:*?"<>|]', "-", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name[:maxlen].strip() or "sans titre")
