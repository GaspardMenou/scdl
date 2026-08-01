#!/usr/bin/env python3
"""Construit l'application autonome scdl pour le système courant.

    python3 build.py

PyInstaller ne sait pas compiler pour un autre système que celui sur lequel il
tourne : lance ce script sur macOS pour le .app, sur Windows pour le .exe, sur
Linux pour le binaire. Le résultat atterrit dans dist/.

Prérequis :  pip install yt-dlp mutagen imageio-ffmpeg pyinstaller
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
SEP = ";" if sys.platform == "win32" else ":"


def main() -> int:
    for module in ("yt_dlp", "mutagen", "imageio_ffmpeg", "PyInstaller"):
        try:
            __import__(module)
        except ImportError:
            print(f"Manquant : {module}. Lance d'abord :\n"
                  f"  {sys.executable} -m pip install yt-dlp mutagen imageio-ffmpeg pyinstaller")
            return 1

    for stale in ("build", "dist"):
        shutil.rmtree(ROOT / stale, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", "scdl",
        "--paths", str(APP),
        # genres.conf est lu à l'exécution : il doit être dans le bundle
        "--add-data", f"{ROOT / 'genres.conf'}{SEP}.",
        # le ffmpeg statique fourni par imageio-ffmpeg
        "--collect-binaries", "imageio_ffmpeg",
        # yt-dlp charge ses extracteurs dynamiquement
        "--collect-submodules", "yt_dlp",
        "--hidden-import", "genres", "--hidden-import", "meta", "--hidden-import", "core",
        "--hidden-import", "gui",
        str(APP / "main.py"),
    ]
    icon = ROOT / "scdl.icns" if sys.platform == "darwin" else ROOT / "scdl.ico"
    if icon.exists():
        cmd[cmd.index("--windowed") + 1:1] = []          # garde l'ordre lisible
        cmd += ["--icon", str(icon)]

    print("→", " ".join(cmd[:8]), "…")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode:
        return result.returncode

    produced = sorted(p.name for p in (ROOT / "dist").iterdir())
    print("\nConstruit dans dist/ :", ", ".join(produced))
    return 0


if __name__ == "__main__":
    sys.exit(main())
