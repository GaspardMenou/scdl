"""Mise à jour automatique depuis les Releases GitHub.

Un programme ne peut pas s'écraser lui-même pendant qu'il tourne : sous Windows
le fichier est verrouillé, sous macOS on remplacerait un bundle en cours
d'exécution. On passe donc par un script d'accompagnement qui attend la fin du
processus, échange les dossiers, puis relance l'application.

Seule l'application est mise à jour : ffmpeg vit dans le dossier de données et
n'est jamais retéléchargé.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from version import REPO, __version__

API = f"https://api.github.com/repos/{REPO}/releases/latest"
TIMEOUT = 15


@dataclass
class Release:
    version: str
    url: str
    notes: str


def parse_version(tag: str) -> tuple[int, ...]:
    """« v1.2.3 » → (1, 2, 3). Les morceaux non numériques sont ignorés."""
    cleaned = tag.strip().lstrip("vV").split("-")[0]
    parts = []
    for piece in cleaned.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            break
    return tuple(parts) or (0,)


def asset_name() -> str:
    if sys.platform == "win32":
        return "scdl-windows.zip"
    return "scdl-macos-apple-silicon.zip"


def is_frozen() -> bool:
    """La mise à jour n'a de sens que pour une application packagée."""
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    """Dossier à remplacer : le .app sous macOS, le dossier du .exe sous Windows."""
    executable = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        for parent in executable.parents:
            if parent.suffix == ".app":
                return parent
    return executable.parent


def check(timeout: int = TIMEOUT) -> Release | None:
    """Renvoie la dernière version si elle est plus récente, sinon None."""
    try:
        request = urllib.request.Request(
            API, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": f"scdl/{__version__}"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except Exception:                     # noqa: BLE001 — hors ligne : on ne dit rien
        return None

    tag = data.get("tag_name") or ""
    if not tag or parse_version(tag) <= parse_version(__version__):
        return None

    wanted = asset_name()
    for asset in data.get("assets") or []:
        if asset.get("name") == wanted:
            return Release(version=tag.lstrip("vV"),
                           url=asset.get("browser_download_url", ""),
                           notes=(data.get("body") or "").strip())
    return None


def download(release: Release, progress: Callable[[str, float], None] | None = None) -> Path:
    """Télécharge et décompresse la nouvelle version dans un dossier temporaire."""
    notify = progress or (lambda msg, pct: None)
    staging = Path(tempfile.mkdtemp(prefix="scdl-update-"))
    archive = staging / "update.zip"

    notify("Téléchargement de la mise à jour…", 0.0)
    with urllib.request.urlopen(release.url, timeout=60) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with archive.open("wb") as out:
            while chunk := response.read(262144):
                out.write(chunk)
                done += len(chunk)
                if total:
                    notify(f"Mise à jour — {done // 1048576} / {total // 1048576} Mo",
                           done / total)

    notify("Installation…", 1.0)
    extracted = staging / "extracted"
    extracted.mkdir(parents=True, exist_ok=True)
    _extract(archive, extracted)

    if sys.platform == "darwin":
        app = next((p for p in extracted.iterdir() if p.suffix == ".app"), None)
        if app is None:
            raise RuntimeError("Archive inattendue : aucun .app à l'intérieur.")
        _validate(app)
        return app
    # Windows : l'archive contient le contenu du dossier, pas le dossier lui-même
    _validate(extracted)
    return extracted


def _extract(archive: Path, into: Path) -> None:
    """Décompresse en préservant liens symboliques et permissions.

    zipfile ne fait ni l'un ni l'autre : il écrit les liens comme des fichiers
    texte contenant leur cible, ce qui détruit un bundle macOS (Python.framework
    n'est qu'un jeu de liens). ditto, qui a servi à créer l'archive, restitue
    tout — y compris la signature.
    """
    if sys.platform == "darwin" and shutil.which("ditto"):
        subprocess.run(["ditto", "-x", "-k", str(archive), str(into)],
                       check=True, capture_output=True)
        return

    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            target = into / info.filename
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):                      # lien symbolique
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    target.unlink()
                target.symlink_to(zf.read(info).decode())
                continue
            zf.extract(info, into)
            if mode & 0o777:                            # permissions d'origine
                os.chmod(target, mode & 0o777)


def _validate(bundle: Path) -> None:
    """Refuse d'installer un bundle abîmé — mieux vaut échouer que remplacer
    une application qui marche par une qui ne démarre pas."""
    if sys.platform == "darwin":
        executables = list((bundle / "Contents" / "MacOS").glob("*"))
        framework = bundle / "Contents" / "Frameworks" / "Python"
        if framework.exists() and not framework.is_symlink():
            raise RuntimeError("Bundle abîmé : les liens symboliques ont été perdus "
                               "à la décompression. Mise à jour annulée.")
    else:
        executables = list(bundle.glob("*.exe"))

    if not executables:
        raise RuntimeError("Bundle abîmé : aucun exécutable trouvé. Mise à jour annulée.")
    if sys.platform != "win32" and not any(os.access(p, os.X_OK) for p in executables):
        raise RuntimeError("Bundle abîmé : l'exécutable a perdu ses permissions. "
                           "Mise à jour annulée.")


_SWAP_SH = """#!/bin/sh
# Attend la fermeture de l'application, remplace le bundle, puis relance.
while kill -0 {pid} 2>/dev/null; do sleep 0.3; done
rm -rf "{target}"
mv "{new}" "{target}"
xattr -cr "{target}" 2>/dev/null
open "{target}"
rm -rf "{staging}" "$0"
"""

_SWAP_BAT = """@echo off
:wait
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait
)
rmdir /s /q "{target}"
move "{new}" "{target}" >nul
start "" "{target}\\{exe}"
rmdir /s /q "{staging}"
del "%~f0"
"""


def apply(new_bundle: Path) -> None:
    """Lance le script d'échange puis rend la main : l'appelant doit quitter."""
    target = bundle_root()
    staging = new_bundle.parent if sys.platform == "darwin" else new_bundle.parent
    pid = os.getpid()

    if sys.platform == "win32":
        script = Path(tempfile.gettempdir()) / f"scdl-update-{pid}.bat"
        script.write_text(_SWAP_BAT.format(
            pid=pid, target=target, new=new_bundle, staging=staging,
            exe=Path(sys.executable).name), encoding="utf-8")
        subprocess.Popen(["cmd", "/c", str(script)],
                         creationflags=0x00000008 | 0x08000000)   # DETACHED | NO_WINDOW
    else:
        script = Path(tempfile.gettempdir()) / f"scdl-update-{pid}.sh"
        script.write_text(_SWAP_SH.format(
            pid=pid, target=target, new=new_bundle, staging=staging), encoding="utf-8")
        os.chmod(script, 0o755)
        subprocess.Popen(["/bin/sh", str(script)], start_new_session=True)
