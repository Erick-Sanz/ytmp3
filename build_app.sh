#!/usr/bin/env bash
#
# build_app.sh - Construye ytmp3.app (Apple Silicon) y un instalador .dmg
#
# Genera:
#   dist/ytmp3.app   -> la aplicacion (doble clic para abrir)
#   dist/ytmp3.dmg   -> instalador arrastrable a Aplicaciones
#
# Nota: la app usa yt-dlp y ffmpeg instalados con homebrew
#       (busca en /opt/homebrew/bin). Manten esos instalados:
#           brew install yt-dlp ffmpeg
#
set -euo pipefail
cd "$(dirname "$0")"

VENV=".buildvenv"
APP_NAME="ytmp3"

# Usa python de homebrew con Tk 9 moderno (el Tk 8.5 del sistema no se ve bien
# en macOS reciente). Requiere: brew install python-tk@3.14
PYBIN="/opt/homebrew/bin/python3.14"
if [[ ! -x "$PYBIN" ]]; then
  echo "ERROR: falta $PYBIN. Instala con: brew install python@3.14 python-tk@3.14" >&2
  exit 1
fi

echo "==> Preparando entorno de build (Tk moderno)"
if [[ ! -d "$VENV" ]]; then
  "$PYBIN" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip pyinstaller PySide6 pillow pyobjc-framework-Cocoa

echo "==> Limpiando builds anteriores"
rm -rf build dist "${APP_NAME}.spec"

echo "==> Generando icono y fondo del instalador"
python make_icon.py
python make_dmg_bg.py

echo "==> Construyendo ${APP_NAME}.app (arm64, Qt)"
pyinstaller --noconfirm --windowed --clean \
  --name "$APP_NAME" \
  --target-arch arm64 \
  --icon assets/icon.icns \
  --osx-bundle-identifier "com.erick.ytmp3" \
  --add-data "assets:assets" \
  --hidden-import ytmp3_core \
  --hidden-import Foundation \
  ytmp3_qt.py

echo "==> Creando instalador DMG profesional"
rm -f "dist/${APP_NAME}.dmg"
STAGE="$(mktemp -d)"
cp -R "dist/${APP_NAME}.app" "$STAGE/"
create-dmg \
  --volname "$APP_NAME" \
  --volicon "assets/icon.icns" \
  --background "assets/dmg_bg.png" \
  --window-pos 200 120 \
  --window-size 660 420 \
  --icon-size 120 \
  --icon "${APP_NAME}.app" 165 232 \
  --app-drop-link 495 232 \
  --hide-extension "${APP_NAME}.app" \
  --no-internet-enable \
  "dist/${APP_NAME}.dmg" \
  "$STAGE" || true
rm -rf "$STAGE"

deactivate
echo ""
echo "LISTO."
echo "  App: dist/${APP_NAME}.app"
echo "  Instalador: dist/${APP_NAME}.dmg  (abrelo y arrastra a Aplicaciones)"
