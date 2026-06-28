#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ytmp3_core - Logica de descarga/metadata/portada (sin interfaz grafica).
Reutilizable desde cualquier UI. Requiere yt-dlp y ffmpeg.
"""
import os
import re
import json
import shutil
import subprocess
import platform

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

APP_NAME = "ytmp3"
SETTINGS_PATH = os.path.expanduser("~/.ytmp3gui.json")
DEFAULT_FOLDER = os.path.expanduser("~/Music/ytmp3")

YT_URL_RE = re.compile(
    r"https?://(?:www\.|music\.)?(?:youtube\.com/watch\?[^\s]*v=[\w-]+|youtu\.be/[\w-]+)",
    re.IGNORECASE,
)
PLAYLIST_RE = re.compile(
    r"https?://(?:www\.|music\.)?youtube\.com/(?:playlist\?[^\s]*list=|watch\?[^\s]*[?&]list=)[\w-]+",
    re.IGNORECASE,
)
LIST_ID_RE = re.compile(r"[?&]list=([\w-]+)", re.IGNORECASE)
PROGRESS_RE = re.compile(r"\[download\]\s+(\d{1,3}(?:\.\d)?)%")
DEST_RE = re.compile(r"Destination:\s*(.+)$")

YTDLP = shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def build_env():
    """Entorno limpio para los subprocesos (yt-dlp/ffmpeg).

    Dentro del .app empaquetado, PyInstaller inyecta variables (PYTHONHOME,
    DYLD_*, etc.) que rompen el interprete propio de yt-dlp. Las quitamos /
    restauramos a su valor original para que los subprocesos corran bien.
    """
    env = os.environ.copy()
    for k in ("PYTHONHOME", "PYTHONPATH", "PYTHONEXECUTABLE",
              "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "DYLD_INSERT_LIBRARIES",
              "LD_LIBRARY_PATH"):
        orig = env.pop(k + "_ORIG", None)   # PyInstaller guarda el original aqui
        if orig is not None:
            env[k] = orig
        else:
            env.pop(k, None)
    if not IS_WIN:
        env["PATH"] = ("/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:"
                       + env.get("PATH", ""))
    return env


# ---------------- ajustes ----------------
def load_settings():
    defaults = {
        "last_folder": DEFAULT_FOLDER,
        "recent_folders": [],
        "clipboard_enabled": False,
        "parallel_workers": 2,
        "audio_quality": "2",
        "embed_cover": False,
        "playlist_enabled": False,
        "skip_existing": True,
        "cookies_browser": "",   # ""=ninguno, o safari/chrome/firefox/brave/edge
        "collapse_state": 0,     # 0 todo / 1 compacto / 2 minimo
        "view_mode": "normal",   # normal / compact / ultra
        "notifications": {       # por tipo, palomeables desde la UI
            "detected": True, "started": True, "done": True,
            "exists": True, "error": True,
        },
        "notif_intro_shown": False,
    }
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults.update({k: data[k] for k in defaults if k in data})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return defaults


def save_settings(s):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print("No se pudo guardar ajustes:", e)


# ---------------- descarga ----------------
ARCHIVE_NAME = ".ytmp3_archive.txt"   # registro de IDs ya descargados por carpeta


def ytdlp_command(url, dest, quality, embed_cover, dedup=True, cookies_browser=None):
    cmd = [
        YTDLP, "-x", "--audio-format", "mp3", "--audio-quality", str(quality),
        "--embed-metadata", "--add-metadata",
        "--parse-metadata", "%(artist,uploader)s:%(meta_artist)s",
        "--parse-metadata", "%(title)s:(?:.+? - )?(?P<meta_title>.+)",
        "--parse-metadata", "%(album,playlist,meta_title)s:%(meta_album)s",
        "--parse-metadata", "%(upload_date>%Y)s:%(meta_date)s",
        "--no-playlist", "--embed-chapters", "--newline", "--no-color",
        # anti-bloqueo de YouTube: ritmo suave + reintentos
        "--sleep-requests", "1.5", "--min-sleep-interval", "1",
        "--max-sleep-interval", "5", "--retries", "10", "--extractor-retries", "3",
    ]
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    if dedup:
        cmd += ["--download-archive", os.path.join(dest, ARCHIVE_NAME)]
    if embed_cover:
        cmd += ["--embed-thumbnail", "--convert-thumbnails", "jpg"]
    cmd += ["-o", os.path.join(dest, "%(meta_artist)s - %(meta_title)s.%(ext)s"), url]
    return cmd


def expand_playlist(url, cookies_browser=None):
    """Lista de URLs de video individuales de una playlist."""
    cmd = [YTDLP, "--flat-playlist", "--print", "%(id)s"]
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    cmd.append(url)
    try:
        out = subprocess.run(
            cmd,
            capture_output=True, text=True, env=build_env(), timeout=120,
        )
        ids = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        return ["https://www.youtube.com/watch?v=" + i for i in ids]
    except (subprocess.SubprocessError, OSError):
        return []


def track_basename(url):
    """Obtiene 'Artista - Titulo' (mismo nombre que tendra el archivo) sin descargar."""
    try:
        r = subprocess.run(
            [YTDLP, "--no-playlist", "--skip-download",
             "-O", "%(artist,uploader)s\t%(title)s", url],
            capture_output=True, text=True, env=build_env(), timeout=60,
        )
        line = r.stdout.strip().splitlines()[0]
        artist, _, title = line.partition("\t")
        title = re.sub(r"^.+? - ", "", title, count=1)   # quita prefijo "Artista - "
        base = ("%s - %s" % (artist, title)).replace("/", "_").strip()
        return base or None
    except (subprocess.SubprocessError, OSError, IndexError):
        return None


def free_space(folder):
    """Espacio libre (bytes, total) del volumen de 'folder'. Usa el primer
    directorio padre que exista. Devuelve (free, total) o None."""
    import shutil
    p = folder or "/"
    while p and not os.path.isdir(p):
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    try:
        u = shutil.disk_usage(p or "/")
        return u.free, u.total
    except OSError:
        return None


def human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024
    return "%.1f PB" % n


def cleanup_partial(dest, base):
    """Borra archivos temporales/incompletos de una descarga cancelada
    (.part, .ytdl, formatos intermedios, miniaturas), conservando .mp3 finales."""
    import glob
    if not base or not os.path.isdir(dest):
        return
    keep_ext = {".mp3"}
    temp_markers = (".part", ".ytdl", ".temp")
    for path in glob.glob(os.path.join(dest, glob.escape(base) + ".*")):
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        is_temp = (ext not in keep_ext) or any(m in name for m in temp_markers)
        if is_temp:
            try:
                os.remove(path)
            except OSError:
                pass


def _notify_native(title, text):
    """Notificacion via NSUserNotification: aparece atribuida a la app (ytmp3)
    y la registra en Ajustes > Notificaciones. Devuelve True si funciono."""
    try:
        from Foundation import NSUserNotification, NSUserNotificationCenter
    except Exception:
        return False
    try:
        center = NSUserNotificationCenter.defaultUserNotificationCenter()
        if center is None:
            return False
        n = NSUserNotification.alloc().init()
        n.setTitle_(title)
        n.setInformativeText_(text)
        center.deliverNotification_(n)
        return True
    except Exception:
        return False


def _notify_linux(title, text):
    try:
        subprocess.Popen(["notify-send", "-a", APP_NAME, title, text])
        return True
    except OSError:
        return False


def _notify_windows(title, text):
    try:
        from winotify import Notification
        Notification(app_id=APP_NAME, title=title, msg=text).show()
        return True
    except Exception:
        pass
    # respaldo: toast via PowerShell (sin dependencias)
    try:
        ps = (
            "[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,"
            "ContentType=WindowsRuntime]>$null;"
            "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
            "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
            "$x=$t.GetElementsByTagName('text');"
            "$x.Item(0).AppendChild($t.CreateTextNode('%s'))>$null;"
            "$x.Item(1).AppendChild($t.CreateTextNode('%s'))>$null;"
            "$n=[Windows.UI.Notifications.ToastNotification]::new($t);"
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
            "'%s').Show($n);"
            % (title.replace("'", " "), text.replace("'", " "), APP_NAME)
        )
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                         creationflags=0x08000000)  # CREATE_NO_WINDOW
        return True
    except Exception:
        return False


def notify(title, text):
    """Notificacion nativa, segun el sistema operativo."""
    if IS_MAC:
        if _notify_native(title, text):
            return
        text = text.replace('"', "'")
        title = title.replace('"', "'")
        try:
            subprocess.Popen(
                ["osascript", "-e",
                 'display notification "%s" with title "%s"' % (text, title)])
        except OSError:
            pass
    elif IS_LINUX:
        _notify_linux(title, text)
    elif IS_WIN:
        _notify_windows(title, text)


# preferencias de notificaciones por tipo (las actualiza la UI al iniciar/cambiar)
NOTIF_PREFS = {
    "detected": True,   # se detecto/copio una URL
    "started": True,    # la descarga arranco bien
    "done": True,       # descarga completada
    "exists": True,     # la cancion ya existia
    "error": True,      # fallo la descarga
}


def notify_kind(kind, title, text):
    """Notifica solo si ese tipo esta activado en NOTIF_PREFS."""
    if NOTIF_PREFS.get(kind, True):
        notify(title, text)


def request_notifications():
    """Primer arranque: emite una notificacion de bienvenida para que macOS
    registre la app en Ajustes > Notificaciones y pida/active el permiso."""
    notify(APP_NAME, "Notificaciones activadas")


class DownloadControl:
    """Permite pausar/cancelar una descarga en curso."""
    def __init__(self):
        self.proc = None
        self.stop = False
        self.mode = None     # 'pause' o 'cancel'

    def pause(self):
        self.mode = "pause"
        self.stop = True
        self._terminate()

    def cancel(self):
        self.mode = "cancel"
        self.stop = True
        self._terminate()

    def _terminate(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except OSError:
                pass


def run_download(item_id, url, dest, quality, embed_cover, emit,
                 check_exists=True, control=None, cookies_browser=None):
    """Ejecuta yt-dlp. 'emit' recibe un dict con el evento. 'control' permite
    pausar/cancelar. Cualquier error se reporta como estado 'error' (nunca cuelga)."""
    def send(**kw):
        kw["id"] = item_id
        emit(kw)

    try:
        # cancelada antes de empezar (p.ej. al cancelar toda una playlist)
        if control is not None and control.stop:
            send(status="Cancelado", state="cancelled")
            return

        try:
            os.makedirs(dest, exist_ok=True)
        except OSError as e:
            send(status="Error: carpeta no accesible", state="error")
            notify_kind("error", APP_NAME, "Error: carpeta no accesible")
            return

        send(status="Descargando", progress=0.0)
        try:
            proc = subprocess.Popen(
                ytdlp_command(url, dest, quality, embed_cover, dedup=check_exists,
                              cookies_browser=cookies_browser),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=build_env(),
            )
        except (FileNotFoundError, OSError):
            send(status="Error: no se pudo iniciar yt-dlp", state="error")
            return
        if control is not None:
            control.proc = proc

        base = None            # nombre, se conoce al ver la 1a linea Destination
        already = False        # ya estaba en el archivo de descargados
        last_err = ""
        for line in proc.stdout:
            if control is not None and control.stop:
                break
            if "has already been recorded in the archive" in line:
                already = True
                continue
            m = PROGRESS_RE.search(line)
            if m:
                send(progress=float(m.group(1)))
                continue
            d = DEST_RE.search(line)
            if d:
                base = os.path.splitext(os.path.basename(d.group(1)))[0]
                send(title=base, path=d.group(1))
                notify_kind("started", APP_NAME, "Descargando: %s" % base)
                continue
            if "[ExtractAudio]" in line:
                send(status="Convirtiendo", progress=100.0)
            if "ERROR:" in line:
                last_err = line.strip()

        proc.wait()

        if control is not None and control.stop:
            if control.mode == "pause":
                send(status="Pausado", state="paused")
            else:
                cleanup_partial(dest, base)   # borra temporales al cancelar
                send(status="Cancelado", state="cancelled")
            return

        if already:
            send(status="Ya existe", state="exists", progress=100.0)
            notify_kind("exists", APP_NAME, "Ya existe: %s" % (base or "la cancion"))
        elif proc.returncode == 0:
            send(status="Completado", progress=100.0, state="done")
            notify_kind("done", APP_NAME, "Descargado: %s" % (base or "la cancion"))
        elif "Sign in to confirm" in last_err or "429" in last_err:
            send(status="YouTube bloqueo (espera/usa cookies)", state="error")
            notify_kind("error", APP_NAME, "Error: YouTube bloqueo la descarga")
        else:
            send(status="Error (codigo %d)" % proc.returncode, state="error")
            notify_kind("error", APP_NAME, "Fallo: %s" % (base or "la cancion"))
    except Exception as e:   # red de seguridad: nunca dejar la tarjeta colgada
        send(status="Error: %s" % str(e)[:60], state="error")


# ---------------- portada ----------------
def add_cover_to_file(mp3_path, image_path):
    tmp = mp3_path + ".tmp.mp3"
    cmd = [
        FFMPEG, "-y", "-i", mp3_path, "-i", image_path,
        "-map", "0:a", "-map", "1:v", "-c:a", "copy", "-c:v", "mjpeg",
        "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)",
        "-id3v2_version", "3", tmp,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, env=build_env())
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, mp3_path)
        return True, ""
    if os.path.exists(tmp):
        os.remove(tmp)
    return False, r.stderr[-300:]


def remove_cover_from_file(mp3_path):
    tmp = mp3_path + ".tmp.mp3"
    cmd = [FFMPEG, "-y", "-i", mp3_path, "-map", "0:a", "-c:a", "copy",
           "-id3v2_version", "3", tmp]
    r = subprocess.run(cmd, capture_output=True, text=True, env=build_env())
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, mp3_path)
        return True, ""
    if os.path.exists(tmp):
        os.remove(tmp)
    return False, r.stderr[-300:]
