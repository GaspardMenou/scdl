"""Résolution des genres SoundCloud vers des noms canoniques.

Le dictionnaire vit dans genres.conf, à côté du code (ou embarqué dans l'app
une fois packagée). La comparaison ignore casse, espaces et ponctuation :
"Hard-Techno", "HARDTECHNO" et "hard techno" tombent tous sur "Hard Techno".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FALLBACK = "Sans genre"


def resource_dir() -> Path:
    """Dossier des ressources, que l'on tourne depuis les sources ou packagé."""
    bundled = getattr(sys, "_MEIPASS", None)          # PyInstaller
    return Path(bundled) if bundled else Path(__file__).resolve().parent.parent


def key(s: str) -> str:
    """Clé de comparaison : minuscules, sans espaces ni ponctuation."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


class Genres:
    def __init__(self, conf: Path | None = None):
        self.table: dict[str, str] = {}
        self.path = conf or (resource_dir() / "genres.conf")
        self.reload()

    def reload(self) -> None:
        self.table.clear()
        if not self.path.exists():
            return
        canonical = None
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if "=" in line:
                canonical, _, rest = line.partition("=")
                canonical = canonical.strip()
                self.table[key(canonical)] = canonical    # le canonique est sa propre variante
            elif canonical and raw.startswith((" ", "\t")):
                rest = line                               # continuation d'une ligne trop longue
            else:
                continue
            for variant in rest.split(","):
                variant = variant.strip()
                if variant:
                    self.table[key(variant)] = canonical

    def canon(self, raw: str | None) -> str:
        s = (raw or "").strip()
        s = re.sub(r"^#+", "", s).strip()                 # les tags arrivent en "#techno"
        s = re.split(r"[/|｜⧸]", s)[0].strip()             # "Hard Techno/Industrial" -> "Hard Techno"
        s = re.sub(r"\s+", " ", s)
        if not s:
            return FALLBACK
        return self.table.get(key(s), s)

    def known(self, raw: str | None) -> bool:
        """Vrai si la valeur est un genre répertorié — sert à décider si un
        suffixe de titre comme « / Hard Techno » est bien un genre à retirer."""
        return key((raw or "").strip()) in self.table

    def canonical_names(self) -> list[str]:
        return sorted(set(self.table.values()))
