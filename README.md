# ytmp3

Descargador de música de YouTube a MP3 (artista, título y portada). Interfaz Qt (PySide6).

## Requisitos en tiempo de ejecución

La app llama a **yt-dlp** y **ffmpeg** (deben estar instalados y en el PATH):

- macOS: `brew install yt-dlp ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg` y `pipx install yt-dlp` (o `pip install yt-dlp`)
- Windows: `winget install yt-dlp.yt-dlp Gyan.FFmpeg` (o equivalente)

## Ejecutar desde el código

```bash
python -m venv .venv && source .venv/bin/activate
pip install PySide6 pillow
python ytmp3_qt.py
```

## Instaladores

### macOS (local)

```bash
./build_app.sh      # genera dist/ytmp3.app y dist/ytmp3.dmg
```

### Los 3 sistemas (GitHub Actions)

El workflow `.github/workflows/build.yml` compila en runners nativos:

- macOS  → `ytmp3.dmg`
- Ubuntu → `ytmp3-x86_64.AppImage`
- Windows → `ytmp3-setup.exe` (Inno Setup)

Dispáralo manualmente en la pestaña **Actions** (`Run workflow`) o publicando un tag:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

Los instaladores quedan como *artifacts* de la corrida.

## Funciones

- Cola con descargas en paralelo (tope 3 sin cookies, 8 con cookies del navegador).
- Cookies de Safari/Chrome/Firefox/Brave/Edge para evitar bloqueos de YouTube.
- 3 modos de vista de la lista (Normal / Compacta / Ultra) y 3 niveles de contracción del panel.
- Notificaciones de escritorio configurables por tipo.
- Recuerda todas las opciones entre sesiones.
