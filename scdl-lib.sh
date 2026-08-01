#!/usr/bin/env bash
# Fonctions communes à scdl (téléchargement) et scdl-tidy (réorganisation).
# Ce fichier se source, il ne s'exécute pas.

SCDLDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

AUDIO_EXT=(mp3 m4a wav aiff aif flac opus ogg)

bold=$'\033[1m'; dim=$'\033[2m'; red=$'\033[31m'; grn=$'\033[32m'; ylw=$'\033[33m'; off=$'\033[0m'
say()  { printf '%b\n' "${bold}$*${off}"; }
info() { printf '%b\n' "${dim}$*${off}"; }
warn() { printf '%b\n' "${ylw}$*${off}"; }
die()  { printf '%b\n' "${red}erreur :${off} $*" >&2; exit 1; }   # %b : interprète les \n

# Liste les fichiers audio d'un dossier, triés (la numérotation donne l'ordre du set).
list_audio() {
  local dir="$1" expr=() e
  for e in "${AUDIO_EXT[@]}"; do expr+=( -o -name "*.$e" ); done
  find "$dir" -maxdepth 1 -type f \( "${expr[@]:1}" \) -print0 2>/dev/null | sort -z
}

# Déplace un fichier vers un dossier sans jamais écraser l'existant.
move_unique() {
  local src="$1" dir="$2" base target n=2
  base="$(basename "$src")"; target="$dir/$base"
  # -ef compare les inodes : sur un disque insensible à la casse, "hard techno"
  # et "Hard Techno" sont le même dossier. Sans ce garde-fou le fichier se
  # verrait "déjà présent" face à lui-même et serait dupliqué en " (2)".
  [[ "$src" -ef "$target" ]] && { printf '%s' "$src"; return; }
  while [[ -e "$target" ]]; do
    target="$dir/${base%.*} ($n).${base##*.}"; (( n++ ))
  done
  mv "$src" "$target"
  printf '%s' "$target"
}

# Ramène un genre brut à son nom canonique via genres.conf ("hardtechno",
# "Hard-Techno", "#HARD TECHNO" → "Hard Techno"). Un genre inconnu est conservé.
norm_genre() {
  if [[ -x "$SCDLDIR/scdl-genre" ]]; then
    "$SCDLDIR/scdl-genre" canon "$1"
  else
    printf '%s' "${1:-Sans genre}"
  fi
}

# Lit un tag d'un fichier audio.
tag_of() {
  ffprobe -v error -show_entries "format_tags=$2" -of default=nw=1:nk=1 "$1" 2>/dev/null | head -1
}

# Aligne le tag Genre du fichier sur son dossier, sans ré-encoder ni perdre la
# pochette. "Sans genre" n'est pas écrit : mieux vaut un tag vide qu'un faux.
retag_genre() {
  local f="$1" want="$2" cur tmp
  [[ "$want" == "Sans genre" ]] && return 0
  cur="$(tag_of "$f" genre)"
  [[ "$cur" == "$want" ]] && return 0
  tmp="${f%.*}.scdltmp.${f##*.}"
  if ffmpeg -v error -y -i "$f" -map 0 -c copy -metadata genre="$want" "$tmp" 2>/dev/null; then
    mv "$tmp" "$f"
  else
    rm -f "$tmp"
  fi
}

# Nettoie un titre des résidus que SoundCloud y laisse :
#   "Dirty Talk / Hard Techno"          → "Dirty Talk"   (genre collé au titre)
#   "Si Ai (KUZE Remix) *PLAYED BY X"   → "Si Ai (KUZE Remix)"
# Le suffixe après "/" n'est retiré QUE s'il correspond à un genre du
# dictionnaire : un titre légitime comme "A / B" reste intact.
clean_title() {
  local t="$1" suffix
  t="$(printf '%s' "$t" | sed -E 's/[[:space:]]*[*!]+[[:space:]]*(played|supported|premiered)[[:space:]]+by[[:space:]].*$//I')"
  suffix="${t##*/}"
  if [[ "$suffix" != "$t" ]] && [[ -x "$SCDLDIR/scdl-genre" ]] \
     && "$SCDLDIR/scdl-genre" known "$suffix" 2>/dev/null; then
    t="${t%/*}"
  fi
  t="${t#"${t%%[![:space:]]*}"}"
  t="${t%"${t##*[![:space:]]}"}"
  printf '%s' "$t"
}

# Réécrit le tag Titre s'il change après nettoyage. Le nom du FICHIER n'est pas
# touché : Rekordbox référence des chemins, les renommer casserait sa collection.
retitle() {
  local f="$1" cur want tmp
  cur="$(tag_of "$f" title)"
  [[ -z "$cur" ]] && return 0
  want="$(clean_title "$cur")"
  [[ -z "$want" || "$want" == "$cur" ]] && return 0
  tmp="${f%.*}.scdltmp.${f##*.}"
  if ffmpeg -v error -y -i "$f" -map 0 -c copy -metadata title="$want" "$tmp" 2>/dev/null; then
    mv "$tmp" "$f"
  else
    rm -f "$tmp"
  fi
}

# Réutilise un dossier existant qui ne diffère que par la casse ("techno" → "Techno"),
# pour ne pas éclater un même genre en plusieurs bacs.
resolve_dir() {
  local parent="$1" want="$2" d low
  low="$(printf '%s' "$want" | tr '[:upper:]' '[:lower:]')"
  shopt -s nullglob
  for d in "$parent"/*/; do
    if [[ "$(basename "$d" | tr '[:upper:]' '[:lower:]')" == "$low" ]]; then
      printf '%s' "$(basename "$d")"; shopt -u nullglob; return
    fi
  done
  shopt -u nullglob
  printf '%s' "$want"
}

# Garantit que le dossier porte bien le nom canonique. Si un dossier ne diffère
# que par la casse ("hard techno" vs "Hard Techno"), il est renommé — via un nom
# temporaire, car sur APFS insensible à la casse les deux désignent le même
# dossier et un mv direct serait un no-op silencieux.
ensure_canonical_dir() {
  local parent="$1" want="$2" existing tmp
  existing="$(resolve_dir "$parent" "$want")"
  if [[ "$existing" != "$want" && -d "$parent/$existing" ]]; then
    tmp="$parent/.scdl-rename-$$"
    mv "$parent/$existing" "$tmp" && mv "$tmp" "$parent/$want"
  fi
  mkdir -p "$parent/$want"
  printf '%s' "$want"
}

# Écrit la playlist .m3u8 que Rekordbox sait importer (chemins absolus, UTF-8).
# Fins de ligne CRLF : c'est ce que Rekordbox écrit lui-même quand il exporte
# une playlist, on s'aligne sur son format plutôt que sur le LF Unix.
write_m3u8() {
  local dir="$1" name="$2" f dur art tit
  {
    printf '#EXTM3U\r\n'
    while IFS= read -r -d '' f; do
      dur="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null | cut -d. -f1)"
      art="$(tag_of "$f" artist)"
      tit="$(tag_of "$f" title)"
      printf '#EXTINF:%s,%s - %s\r\n%s\r\n' "${dur:--1}" "${art:-Inconnu}" "${tit:-$(basename "$f")}" "$f"
    done < <(list_audio "$dir")
  } > "$dir/$name.m3u8"
  # Certains sélecteurs de fichiers (dont Rekordbox) ne proposent que ".m3u" et
  # grisent les ".m3u8" : on écrit les deux, contenu identique.
  cp -f "$dir/$name.m3u8" "$dir/$name.m3u"
}
