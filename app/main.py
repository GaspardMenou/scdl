"""Point d'entrée de scdl.

Sans argument : ouvre l'interface graphique.
Avec des URL : fonctionne en ligne de commande, pour ceux que le terminal
ne fait pas fuir.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import core
from core import Downloader, Options


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="scdl", description="Télécharge des sons SoundCloud, les tague et les range.")
    parser.add_argument("urls", nargs="*", help="liens SoundCloud")
    parser.add_argument("-d", "--destination", choices=["dj", "music", "folder"], default="dj")
    parser.add_argument("-o", "--folder", type=Path, help="dossier de sortie")
    parser.add_argument("-f", "--format", default="", choices=["", "mp3", "m4a"],
                        help="par défaut : aucune conversion")
    parser.add_argument("-g", "--genre", default="", help="force le tag Genre")
    parser.add_argument("-A", "--album", default="", help="force le tag Album")
    parser.add_argument("-c", "--login", default="", help="navigateur pour les cookies")
    parser.add_argument("-n", "--max", type=int, default=0, help="limite de morceaux")
    parser.add_argument("--by-set", action="store_true", help="ne pas ranger par genre")
    parser.add_argument("--no-archive", action="store_true")
    args = parser.parse_args(argv)

    if not args.urls:
        from gui import main as gui_main
        gui_main()
        return 0

    opts = Options(
        destination=args.destination, folder=args.folder, by_genre=not args.by_set,
        audio_format=args.format, genre_override=args.genre, album_override=args.album,
        browser=args.login, max_items=args.max, use_archive=not args.no_archive,
    )
    result = Downloader(opts, progress=lambda m, p: print(f"  {m}", flush=True)).run(args.urls)
    for error in result.errors:
        print(f"erreur : {error}", file=sys.stderr)
    print(f"{result.count} morceau(x).")
    return 1 if result.errors and not result.count else 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
