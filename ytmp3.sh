#!/usr/bin/env bash
#
# ytmp3 - Extrae audio de YouTube a MP3 con metadata completa
#         (artista, titulo, album, año) para reproductores tradicionales.
#
# Uso:
#   ./ytmp3.sh "URL"                 -> guarda en ./musica
#   ./ytmp3.sh "URL" "/ruta/destino" -> guarda en la ruta indicada
#
# Requiere: yt-dlp, ffmpeg
#
set -euo pipefail

# --- Comprobacion de dependencias -------------------------------------------
for cmd in yt-dlp ffmpeg; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: falta '$cmd'. Instala con: brew install yt-dlp ffmpeg" >&2
    exit 1
  fi
done

# --- Argumentos --------------------------------------------------------------
URL="${1:-}"
DEST="${2:-./musica}"

if [[ -z "$URL" ]]; then
  echo "Uso: $0 \"URL_de_youtube\" [carpeta_destino]" >&2
  exit 1
fi

mkdir -p "$DEST"

# --- Descarga + conversion + metadata ---------------------------------------
# -x                    extrae solo audio
# --audio-format mp3    convierte a mp3
# --audio-quality 0     mejor calidad VBR
# --embed-metadata      escribe tags ID3 (artista, titulo, album, fecha...)
# --embed-thumbnail     incrusta la miniatura como portada del disco
# --convert-thumbnails  portada en jpg (compatible con todos los reproductores)
# --parse-metadata      si no hay campo 'artist', intenta sacarlo del titulo
#                       con formato "Artista - Titulo"
# -o ...                nombra el archivo "Artista - Titulo.mp3"
# Logica de metadata:
#  meta_artist <- artist real (YouTube Music) o, si no hay, el canal (uploader)
#  meta_title  <- titulo quitando el prefijo "Artista - " si viene duplicado
#  meta_album  <- album/playlist real o, si no hay, el titulo limpio
#  meta_date   <- año de subida
yt-dlp \
  -x \
  --audio-format mp3 \
  --audio-quality 2 \
  --embed-metadata \
  --add-metadata \
  --parse-metadata "%(artist,uploader)s:%(meta_artist)s" \
  --parse-metadata "%(title)s:(?:.+? - )?(?P<meta_title>.+)" \
  --parse-metadata "%(album,playlist,meta_title)s:%(meta_album)s" \
  --parse-metadata "%(upload_date>%Y)s:%(meta_date)s" \
  --no-playlist \
  --embed-chapters \
  -o "${DEST}/%(meta_artist)s - %(meta_title)s.%(ext)s" \
  "$URL"

echo ""
echo "Listo. Archivos en: $DEST"
