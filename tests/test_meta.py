#!/usr/bin/env python3
"""Non-régression du nettoyage des titres et de la résolution des genres.

Chaque cas vient d'un vrai morceau SoundCloud rencontré à l'usage. Lancer :

    python tests/test_meta.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import meta                                    # noqa: E402
from genres import Genres                      # noqa: E402

GENRES = [
    ("Hard Techno", "Hard Techno"), ("hardtechno", "Hard Techno"),
    ("HardTechno", "Hard Techno"), ("Hard techno", "Hard Techno"),
    ("Hard Techno/Industrial", "Hard Techno"), ("#HARDCORE #TECHNO", "Hardcore"),
    ("HybridTechno", "Hybrid Techno"), ("Dance & EDM", "EDM"),
    ("djset", "Sans genre"), ("free download", "Sans genre"),
    ("drum n bass", "Drum & Bass"), ("DNB", "Drum & Bass"),
    ("psy trance", "Psytrance"), ("tech-house", "Tech House"),
    ("KOSMIC", "KOSMIC"), ("#larp", "larp"), ("Schranz", "Schranz"),
    ("", "Sans genre"), (None, "Sans genre"),
]

TITLES = [
    ("PIPIPI - GAMABE & MEDUSA (Free DL extended)", "PIPIPI - GAMABE & MEDUSA (extended)"),
    ("GAMABE & MEDUSA - BECA  [FREE DL]", "GAMABE & MEDUSA - BECA"),
    ("TRIPTYKH - Cold (Original Mix) [FREE DOWNLOAD]", "TRIPTYKH - Cold (Original Mix)"),
    ("ARTIST - Track Name *FREE DL*", "ARTIST - Track Name"),
    ("PREMIERE: Someone - Hypnotic Loop [Free DL]", "Someone - Hypnotic Loop"),
    ("FREE DL | Producer - Raw Kick", "Producer - Raw Kick"),
    ("Producer - Banger [BUY = FREE DOWNLOAD]", "Producer - Banger"),
    ("Producer - Thing click buy for free dl", "Producer - Thing"),
    ("Si Ai (KUZE Hard Techno Remix) *PLAYED BY CARAVEL", "Si Ai (KUZE Hard Techno Remix)"),
    ("Just A Normal Track (Original Mix)", "Just A Normal Track (Original Mix)"),
    ("BECA (Medusa x Gamabe) EDIT/Mashup by RagenoirE",
     "BECA (Medusa x Gamabe) EDIT/Mashup by RagenoirE"),
]

# Le suffixe n'est retiré que si c'est un genre : "AC/DC" doit survivre.
SUFFIXES = [
    ("Dirty Talk / Hard Techno", "Dirty Talk"),
    ("Let's play / Hard Techno", "Let's play"),
    ("AC/DC Tribute", "AC/DC Tribute"),
    ("Track A / Track B", "Track A / Track B"),
    ("Cold (Original Mix)", "Cold (Original Mix)"),
]

FILENAMES = [
    ("Benefice - Let's play / Hard Techno", "Benefice - Let's play - Hard Techno"),
    ('A: B? C* D"E<F>G|H', "A- B- C- D-E-F-G-H"),
]


def main() -> int:
    genres = Genres()
    failures: list[str] = []
    checks = 0

    def check(label: str, got, want) -> None:
        nonlocal checks
        checks += 1
        if got != want:
            failures.append(f"{label}\n    obtenu  : {got!r}\n    attendu : {want!r}")

    for raw, want in GENRES:
        check(f"genre {raw!r}", genres.canon(raw), want)
    for raw, want in TITLES:
        check(f"titre {raw[:40]!r}", meta.scrub(raw), want)
    for raw, want in SUFFIXES:
        check(f"suffixe {raw!r}", meta.strip_genre_suffix(raw, genres), want)
    for raw, want in FILENAMES:
        check(f"fichier {raw[:26]!r}", meta.safe_filename(raw), want)

    # construction complète des tags
    tags = meta.build({"title": "Benefice - Dirty Talk / Hard Techno", "uploader": "Benefice",
                       "genre": "hardtechno", "playlist": "Your Mix 1",
                       "playlist_uploader": "SoundCloud"}, genres)
    check("tags.artist", tags.artist, "Benefice")
    check("tags.title", tags.title, "Dirty Talk")
    check("tags.genre", tags.genre, "Hard Techno")
    check("tags.album", tags.album, "Your Mix 1")

    # titre sans tiret : l'artiste vient du compte, le titre reste entier
    plain = meta.build({"title": "FUCK THE CLUB UP", "uploader": "WILLIAM LUCK", "tags": []}, genres)
    check("sans tiret : artiste", plain.artist, "WILLIAM LUCK")
    check("sans tiret : titre", plain.title, "FUCK THE CLUB UP")
    check("sans genre : tag vide", plain.genre, "")
    check("album = titre hors set", plain.album, "FUCK THE CLUB UP")

    for failure in failures:
        print(f"ECHEC {failure}")
    print(f"\n{checks - len(failures)}/{checks} tests réussis")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
