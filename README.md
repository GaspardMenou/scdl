# scdl

Télécharge des morceaux SoundCloud, les tague proprement et les range —
pour **Rekordbox** ou pour **Apple Music**.

Pensé pour la techno, où les titres SoundCloud sont un champ de bataille :
`PREMIERE:`, `[FREE DL]`, `*PLAYED BY …`, et six orthographes différentes pour
« hard techno ». scdl nettoie tout ça avant que les fichiers n'atterrissent
dans votre bibliothèque.

## Ce qu'il fait

- **Qualité maximale** — récupère l'AAC 160 kbps de SoundCloud plutôt que son
  MP3 128 kbps, sans ré-encodage. Avec les cookies de votre navigateur, il
  accède aux fichiers originaux quand l'artiste les propose.
- **Titres nettoyés** — retire les mentions promotionnelles où qu'elles soient
  dans le titre, sans abîmer les parenthèses légitimes.
- **Artiste et titre séparés** — `TRIPTYKH - Cold` devient artiste `TRIPTYKH`,
  titre `Cold`.
- **Genres unifiés** — un dictionnaire d'environ 90 genres électroniques ramène
  `hardtechno`, `Hard-Techno` et `HARD TECHNO` à un seul `Hard Techno`.
- **Rangement par genre** — un dossier par genre, avec une playlist `.m3u` /
  `.m3u8` au format exact de Rekordbox, régénérée à chaque ajout.
- **Pochettes et métadonnées** embarquées dans chaque fichier.
- **Historique** — un morceau déjà téléchargé n'est pas repris.

Le BPM et la tonalité ne sont volontairement pas écrits : Rekordbox les calcule
mieux à l'analyse, et un BPM approximatif gênerait son beatgrid.

## Installation

Téléchargez l'application depuis la page
[Releases](../../releases) — **rien d'autre à installer**, ni Python ni ffmpeg.

| Système | Fichier |
|---|---|
| macOS Apple Silicon | `scdl-macos-apple-silicon.zip` |
| macOS Intel | `scdl-macos-intel.zip` |
| Windows | `scdl-windows.zip` |

L'application n'est pas signée par un certificat payant. Au premier lancement :
clic droit puis **Ouvrir** sur macOS, ou **Informations complémentaires** puis
**Exécuter quand même** sur Windows.

## En ligne de commande

L'application fait aussi office d'outil terminal :

```
scdl <url>                       # vers la bibliothèque Rekordbox, rangé par genre
scdl -d music <url>              # vers Apple Music
scdl -o ~/Sons <url>             # vers un dossier au choix
scdl -c safari <url>             # avec vos cookies : qualité originale, playlists privées
scdl -g "Hard Techno" <url>      # force le genre
scdl --by-set <url>              # un dossier par set plutôt que par genre
scdl -n 20 <url>                 # ne prend que les 20 premiers morceaux
```

Fonctionne avec un morceau, un set, un profil d'artiste, vos likes ou une
playlist personnalisée (`Your Mix`), ces deux dernières nécessitant `-c`.

## Personnaliser les genres

`genres.conf` est un fichier texte modifiable. Une ligne par genre canonique :

```
Hard Techno = hardtechno, hardtekno, hardtechnorave
```

La comparaison ignore casse, espaces et ponctuation : inutile de lister
`Hard-Techno` si `hardtechno` y est déjà. Un genre absent du fichier est
conservé tel quel, jamais perdu.

## Développement

```
pip install yt-dlp mutagen imageio-ffmpeg pyinstaller
python tests/test_meta.py     # suite de non-régression
python app/main.py            # lance l'interface
python build.py               # construit l'application du système courant
```

PyInstaller ne compile que pour le système sur lequel il tourne : les
applications macOS et Windows sont construites par l'intégration continue.

## Licence

Usage personnel. yt-dlp et ffmpeg conservent leurs licences respectives.
