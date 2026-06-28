#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ytmp3_app - Aplicacion de escritorio para descargar audio de YouTube / YouTube Music
            a MP3 con metadata completa (artista, titulo, album, año).

Caracteristicas:
  - Selector de carpeta destino que recuerda la ultima usada y las recientes
    (util para guardar por genero en carpetas distintas).
  - Deteccion opcional de URL copiada al portapapeles: si es una cancion de
    YouTube / YouTube Music, la mete automaticamente a la cola.
  - Descargas en paralelo (numero configurable).
  - Tabla con el estado en vivo de cada descarga.

Requiere: yt-dlp, ffmpeg (instalados con: brew install yt-dlp ffmpeg)
Solo usa la libreria estandar de Python (tkinter).
"""

import os
import re
import json
import queue
import shutil
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --------------------------------------------------------------------------- #
# Configuracion / constantes
# --------------------------------------------------------------------------- #
APP_NAME = "ytmp3"
SETTINGS_PATH = os.path.expanduser("~/.ytmp3gui.json")
DEFAULT_FOLDER = os.path.expanduser("~/Music/ytmp3")

# Detecta URLs de un video/cancion individual de YouTube o YouTube Music.
YT_URL_RE = re.compile(
    r"https?://(?:www\.|music\.)?(?:youtube\.com/watch\?[^\s]*v=[\w-]+|youtu\.be/[\w-]+)",
    re.IGNORECASE,
)
# Detecta URLs de playlist (lista de reproduccion / album).
PLAYLIST_RE = re.compile(
    r"https?://(?:www\.|music\.)?youtube\.com/(?:playlist\?[^\s]*list=|watch\?[^\s]*[?&]list=)[\w-]+",
    re.IGNORECASE,
)
# Extrae el id de lista (list=...) de cualquier URL.
LIST_ID_RE = re.compile(r"[?&]list=([\w-]+)", re.IGNORECASE)
# Progreso de yt-dlp:  [download]  45.5% of ...
PROGRESS_RE = re.compile(r"\[download\]\s+(\d{1,3}(?:\.\d)?)%")
# Nombre final del archivo:  [ExtractAudio] Destination: .../Artista - Titulo.mp3
DEST_RE = re.compile(r"Destination:\s*(.+\.mp3)\s*$")

YTDLP = shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def build_env():
    """PATH con homebrew para que yt-dlp encuentre ffmpeg aunque se abra desde Finder."""
    env = os.environ.copy()
    extra = "/opt/homebrew/bin:/usr/local/bin"
    env["PATH"] = extra + ":" + env.get("PATH", "")
    return env


# --------------------------------------------------------------------------- #
# Persistencia de ajustes
# --------------------------------------------------------------------------- #
def load_settings():
    defaults = {
        "last_folder": DEFAULT_FOLDER,
        "recent_folders": [],
        "clipboard_enabled": False,
        "parallel_workers": 3,
        "audio_quality": "2",
        "embed_cover": False,
        "playlist_enabled": False,
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


# --------------------------------------------------------------------------- #
# Trabajo de descarga (en hilos)
# --------------------------------------------------------------------------- #
def ytdlp_command(url, dest, quality, embed_cover):
    cmd = [
        YTDLP,
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", str(quality),
        "--embed-metadata",
        "--add-metadata",
        "--parse-metadata", "%(artist,uploader)s:%(meta_artist)s",
        "--parse-metadata", "%(title)s:(?:.+? - )?(?P<meta_title>.+)",
        "--parse-metadata", "%(album,playlist,meta_title)s:%(meta_album)s",
        "--parse-metadata", "%(upload_date>%Y)s:%(meta_date)s",
        "--no-playlist",
        "--embed-chapters",
        "--newline",
        "--no-color",
    ]
    if embed_cover:
        cmd += ["--embed-thumbnail", "--convert-thumbnails", "jpg"]
    cmd += [
        "-o", os.path.join(dest, "%(meta_artist)s - %(meta_title)s.%(ext)s"),
        url,
    ]
    return cmd


def expand_playlist(url):
    """Devuelve lista de URLs de video individuales de una playlist."""
    try:
        out = subprocess.run(
            [YTDLP, "--flat-playlist", "--print", "%(id)s", url],
            capture_output=True, text=True, env=build_env(), timeout=120,
        )
        ids = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        return ["https://www.youtube.com/watch?v=" + i for i in ids]
    except (subprocess.SubprocessError, OSError):
        return []


def add_cover_to_file(mp3_path, image_path):
    """Incrusta una imagen como caratula del MP3 (sobreescribe el archivo)."""
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
    """Quita la caratula del MP3 (sobreescribe el archivo)."""
    tmp = mp3_path + ".tmp.mp3"
    cmd = [
        FFMPEG, "-y", "-i", mp3_path,
        "-map", "0:a", "-c:a", "copy", "-id3v2_version", "3", tmp,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, env=build_env())
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, mp3_path)
        return True, ""
    if os.path.exists(tmp):
        os.remove(tmp)
    return False, r.stderr[-300:]


def run_download(item_id, url, dest, quality, embed_cover, ui_queue):
    """Ejecuta yt-dlp y emite eventos de estado a la cola de la UI."""
    def emit(**kw):
        kw["id"] = item_id
        ui_queue.put(kw)

    os.makedirs(dest, exist_ok=True)
    emit(status="Descargando", progress=0)
    try:
        proc = subprocess.Popen(
            ytdlp_command(url, dest, quality, embed_cover),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=build_env(),
        )
    except FileNotFoundError:
        emit(status="Error: yt-dlp no encontrado", progress=0)
        return

    for line in proc.stdout:
        m = PROGRESS_RE.search(line)
        if m:
            emit(progress=float(m.group(1)))
            continue
        d = DEST_RE.search(line)
        if d:
            emit(title=os.path.basename(d.group(1))[:-4])  # sin .mp3
        if "[ExtractAudio]" in line:
            emit(status="Convirtiendo a MP3", progress=100)

    proc.wait()
    if proc.returncode == 0:
        emit(status="Completado", progress=100)
    else:
        emit(status="Error (codigo %d)" % proc.returncode)


# --------------------------------------------------------------------------- #
# Aplicacion
# --------------------------------------------------------------------------- #
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ytmp3 - Descargador de musica de YouTube")
        self.geometry("780x520")
        self.minsize(680, 420)

        self.settings = load_settings()
        self.ui_queue = queue.Queue()
        self.queued_urls = set()       # evita duplicados
        self.last_clipboard = ""
        self.row_counter = 0
        self.executor = ThreadPoolExecutor(
            max_workers=int(self.settings["parallel_workers"])
        )

        self._setup_theme()
        self._build_ui()
        self._poll_ui_queue()
        self._poll_clipboard()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Workaround macOS: fuerza un redibujado para que se vean los widgets.
        self.after(80, self._nudge)

    def _nudge(self):
        self.update_idletasks()
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry("%dx%d" % (w + 1, h + 1))
        self.after(60, lambda: self.geometry("%dx%d" % (w, h)))

    # ---- tema visual ----
    def _setup_theme(self):
        """Tema 'clam' con paleta propia: se dibuja igual en cualquier macOS
        (el tema nativo 'aqua' no renderiza bien en modo oscuro)."""
        BG = "#f5f6f8"        # fondo ventana
        SURFACE = "#ffffff"   # campos
        TEXT = "#1d1f24"      # texto principal
        MUTED = "#5b6068"     # texto secundario
        ACCENT = "#e23b34"    # rojo (acento botones primarios)
        ACCENT_DK = "#c32f29"
        BORDER = "#d6d9de"
        SEL = "#fde8e7"       # seleccion en tabla
        self.COLORS = dict(BG=BG, SURFACE=SURFACE, TEXT=TEXT, MUTED=MUTED,
                           ACCENT=ACCENT, BORDER=BORDER)

        self.configure(bg=BG)
        st = ttk.Style(self)
        st.theme_use("clam")

        base_font = ("Helvetica Neue", 13)
        st.configure(".", background=BG, foreground=TEXT, font=base_font,
                     bordercolor=BORDER, focuscolor=ACCENT)
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=SURFACE)
        st.configure("TLabel", background=BG, foreground=TEXT)
        st.configure("Muted.TLabel", background=BG, foreground=MUTED,
                     font=("Helvetica Neue", 12))
        st.configure("Header.TLabel", background=BG, foreground=TEXT,
                     font=("Helvetica Neue", 17, "bold"))

        # Botones
        st.configure("TButton", background="#e9ebef", foreground=TEXT,
                     bordercolor=BORDER, focusthickness=0, relief="flat",
                     padding=(12, 6))
        st.map("TButton", background=[("active", "#dde0e6")])
        st.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                     padding=(14, 7), relief="flat")
        st.map("Accent.TButton",
               background=[("active", ACCENT_DK), ("pressed", ACCENT_DK)],
               foreground=[("disabled", "#ffd9d7")])

        # Entradas / combos
        st.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT,
                     bordercolor=BORDER, insertcolor=TEXT, padding=6)
        st.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                     foreground=TEXT, bordercolor=BORDER, arrowcolor=MUTED,
                     padding=5)
        st.map("TCombobox", fieldbackground=[("readonly", SURFACE)])
        st.configure("TCheckbutton", background=BG, foreground=TEXT,
                     focuscolor=BG)
        st.map("TCheckbutton", background=[("active", BG)])
        st.configure("TSpinbox", fieldbackground=SURFACE, foreground=TEXT,
                     bordercolor=BORDER, arrowcolor=MUTED, padding=4)

        # Tabla
        st.configure("Treeview", background=SURFACE, fieldbackground=SURFACE,
                     foreground=TEXT, rowheight=28, bordercolor=BORDER,
                     font=("Helvetica Neue", 12))
        st.configure("Treeview.Heading", background="#eceef1", foreground=MUTED,
                     relief="flat", font=("Helvetica Neue", 12, "bold"),
                     padding=6)
        st.map("Treeview.Heading", background=[("active", "#e3e6ea")])
        st.map("Treeview", background=[("selected", SEL)],
               foreground=[("selected", TEXT)])

    # ---- construccion de la interfaz ----
    def _build_ui(self):
        pad = {"padx": 14, "pady": 6}

        # --- Encabezado ---
        head = ttk.Frame(self)
        head.pack(fill="x", padx=14, pady=(12, 2))
        ttk.Label(head, text="ytmp3").pack(side="left")
        ttk.Label(head, text="Descargador de musica de YouTube",
                  style="Header.TLabel").pack(side="left")
        ttk.Label(head, text="MP3 con artista, titulo y portada",
                  style="Muted.TLabel").pack(side="right")
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=14, pady=(6, 4))

        # --- Fila carpeta destino ---
        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Carpeta:", width=8).pack(side="left")
        self.folder_var = tk.StringVar(value=self.settings["last_folder"])
        self.folder_combo = ttk.Combobox(
            top, textvariable=self.folder_var,
            values=self.settings["recent_folders"], width=58,
        )
        self.folder_combo.pack(side="left", padx=6)
        self.folder_combo.bind("<<ComboboxSelected>>", lambda e: self._remember_folder())
        ttk.Button(top, text="Elegir...", command=self._choose_folder).pack(side="left")

        # --- Fila agregar URL ---
        addrow = ttk.Frame(self)
        addrow.pack(fill="x", **pad)
        ttk.Label(addrow, text="URL:", width=8).pack(side="left")
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(addrow, textvariable=self.url_var)
        url_entry.pack(side="left", fill="x", expand=True, padx=6)
        url_entry.bind("<Return>", lambda e: self._add_from_entry())
        ttk.Button(addrow, text="Agregar a la cola", style="Accent.TButton",
                   command=self._add_from_entry).pack(side="left")

        # --- Fila opciones ---
        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)
        self.clip_var = tk.BooleanVar(value=self.settings["clipboard_enabled"])
        ttk.Checkbutton(
            opts, text="Detectar URL copiada (auto-cola)",
            variable=self.clip_var, command=self._toggle_clipboard,
        ).pack(side="left")

        ttk.Label(opts, text="   Descargas en paralelo:").pack(side="left")
        self.workers_var = tk.IntVar(value=int(self.settings["parallel_workers"]))
        ttk.Spinbox(opts, from_=1, to=8, width=4, textvariable=self.workers_var,
                    command=self._change_workers).pack(side="left", padx=4)

        ttk.Label(opts, text="   Calidad:").pack(side="left")
        self.quality_var = tk.StringVar(value=str(self.settings["audio_quality"]))
        quality_box = ttk.Combobox(
            opts, textvariable=self.quality_var, width=14, state="readonly",
            values=["0", "2", "5", "128K", "192K", "256K", "320K"],
        )
        quality_box.pack(side="left", padx=4)
        quality_box.bind("<<ComboboxSelected>>", lambda e: self._save())

        # --- Segunda fila de opciones ---
        opts2 = ttk.Frame(self)
        opts2.pack(fill="x", padx=8)
        self.cover_var = tk.BooleanVar(value=self.settings["embed_cover"])
        ttk.Checkbutton(
            opts2, text="Incrustar portada (caratula) al descargar",
            variable=self.cover_var, command=self._save,
        ).pack(side="left")
        self.playlist_var = tk.BooleanVar(value=self.settings["playlist_enabled"])
        ttk.Checkbutton(
            opts2, text="   Descargar playlist completa",
            variable=self.playlist_var, command=self._save,
        ).pack(side="left")

        # --- Tabla de estado ---
        table = ttk.Frame(self)
        table.pack(fill="both", expand=True, **pad)
        cols = ("cancion", "estado", "progreso")
        self.tree = ttk.Treeview(table, columns=cols, show="headings")
        self.tree.heading("cancion", text="Cancion")
        self.tree.heading("estado", text="Estado")
        self.tree.heading("progreso", text="Progreso")
        self.tree.column("cancion", width=420)
        self.tree.column("estado", width=170)
        self.tree.column("progreso", width=90, anchor="center")
        vs = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        # --- Barra inferior ---
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", **pad)
        ttk.Button(bottom, text="Limpiar completadas",
                   command=self._clear_done).pack(side="left")
        ttk.Button(bottom, text="Abrir carpeta",
                   command=self._open_folder).pack(side="left", padx=6)
        ttk.Button(bottom, text="Poner imagen...",
                   command=self._add_cover).pack(side="left")
        ttk.Button(bottom, text="Quitar imagen",
                   command=self._remove_cover).pack(side="left", padx=6)
        self.status_lbl = ttk.Label(bottom, text="Listo")
        self.status_lbl.pack(side="right")

    # ---- carpeta ----
    def _choose_folder(self):
        d = filedialog.askdirectory(initialdir=self.folder_var.get() or DEFAULT_FOLDER)
        if d:
            self.folder_var.set(d)
            self._remember_folder()

    def _remember_folder(self):
        folder = self.folder_var.get().strip()
        if not folder:
            return
        recents = self.settings["recent_folders"]
        if folder in recents:
            recents.remove(folder)
        recents.insert(0, folder)
        self.settings["recent_folders"] = recents[:10]
        self.folder_combo["values"] = self.settings["recent_folders"]
        self.settings["last_folder"] = folder
        self._save()

    def _open_folder(self):
        folder = self.folder_var.get().strip()
        if folder and os.path.isdir(folder):
            subprocess.Popen(["open", folder])
        else:
            messagebox.showinfo(APP_NAME, "La carpeta aun no existe.")

    # ---- opciones ----
    def _toggle_clipboard(self):
        self.settings["clipboard_enabled"] = self.clip_var.get()
        self._save()

    def _change_workers(self):
        n = int(self.workers_var.get())
        self.settings["parallel_workers"] = n
        # Recrea el pool con el nuevo numero de workers (afecta a futuras tareas).
        old = self.executor
        self.executor = ThreadPoolExecutor(max_workers=n)
        threading.Thread(target=old.shutdown, kwargs={"wait": False}, daemon=True).start()
        self._save()

    def _save(self):
        self.settings["clipboard_enabled"] = self.clip_var.get()
        self.settings["parallel_workers"] = int(self.workers_var.get())
        self.settings["audio_quality"] = self.quality_var.get()
        self.settings["embed_cover"] = self.cover_var.get()
        self.settings["playlist_enabled"] = self.playlist_var.get()
        save_settings(self.settings)

    # ---- agregar / encolar ----
    def _add_from_entry(self):
        url = self.url_var.get().strip()
        if not url:
            return
        if not (YT_URL_RE.search(url) or PLAYLIST_RE.search(url)):
            messagebox.showwarning(APP_NAME, "No parece una URL de YouTube/YouTube Music.")
            return
        self.url_var.set("")
        self._handle_url(url)

    def _handle_url(self, url):
        """Decide si la URL es una sola cancion o una playlist a expandir."""
        is_playlist_url = LIST_ID_RE.search(url) is not None
        if self.playlist_var.get() and is_playlist_url:
            self._remember_folder()
            self.status_lbl.config(text="Leyendo playlist...")
            threading.Thread(target=self._expand_and_enqueue,
                             args=(url,), daemon=True).start()
        else:
            # Solo la cancion: si trae &list=, lo ignoramos (yt-dlp usa --no-playlist).
            self._enqueue(url)

    def _expand_and_enqueue(self, url):
        urls = expand_playlist(url)
        # vuelve al hilo de la UI para encolar
        self.after(0, lambda: self._enqueue_many(urls))

    def _enqueue_many(self, urls):
        if not urls:
            self.status_lbl.config(text="Playlist vacia o no se pudo leer")
            return
        for u in urls:
            self._enqueue(u)
        self.status_lbl.config(text="Playlist: %d canciones encoladas" % len(urls))

    def _enqueue(self, url):
        if url in self.queued_urls:
            self.status_lbl.config(text="Ya estaba en la cola")
            return
        folder = self.folder_var.get().strip() or DEFAULT_FOLDER
        self._remember_folder()
        self.queued_urls.add(url)
        self.row_counter += 1
        item_id = "row%d" % self.row_counter
        short = url if len(url) <= 60 else url[:57] + "..."
        self.tree.insert("", "end", iid=item_id,
                         values=(short, "En cola", "0%"))
        quality = self.quality_var.get()
        cover = self.cover_var.get()
        self.executor.submit(run_download, item_id, url, folder,
                             quality, cover, self.ui_queue)
        self.status_lbl.config(text="Encolada")

    # ---- portapapeles ----
    def _poll_clipboard(self):
        if self.clip_var.get():
            try:
                content = self.clipboard_get()
            except tk.TclError:
                content = ""
            if content and content != self.last_clipboard:
                self.last_clipboard = content
                m = YT_URL_RE.search(content) or PLAYLIST_RE.search(content)
                if m:
                    self._handle_url(m.group(0))
        self.after(1000, self._poll_clipboard)

    # ---- cola de eventos UI ----
    def _poll_ui_queue(self):
        try:
            while True:
                ev = self.ui_queue.get_nowait()
                self._apply_event(ev)
        except queue.Empty:
            pass
        self.after(150, self._poll_ui_queue)

    def _apply_event(self, ev):
        iid = ev["id"]
        if not self.tree.exists(iid):
            return
        vals = list(self.tree.item(iid, "values"))
        if "title" in ev:
            vals[0] = ev["title"]
        if "status" in ev:
            vals[1] = ev["status"]
        if "progress" in ev:
            vals[2] = "%d%%" % round(ev["progress"])
        self.tree.item(iid, values=vals)
        done = sum(1 for r in self.tree.get_children()
                   if self.tree.item(r, "values")[1] == "Completado")
        total = len(self.tree.get_children())
        self.status_lbl.config(text="Completadas %d/%d" % (done, total))

    # ---- portada de archivos existentes ----
    def _add_cover(self):
        mp3 = filedialog.askopenfilename(
            title="Elige el MP3", initialdir=self.folder_var.get() or DEFAULT_FOLDER,
            filetypes=[("MP3", "*.mp3")],
        )
        if not mp3:
            return
        img = filedialog.askopenfilename(
            title="Elige la imagen de portada",
            filetypes=[("Imagenes", "*.jpg *.jpeg *.png *.webp")],
        )
        if not img:
            return
        self.status_lbl.config(text="Poniendo portada...")
        threading.Thread(target=self._cover_worker,
                         args=("add", mp3, img), daemon=True).start()

    def _remove_cover(self):
        mp3 = filedialog.askopenfilename(
            title="Elige el MP3 para quitarle la portada",
            initialdir=self.folder_var.get() or DEFAULT_FOLDER,
            filetypes=[("MP3", "*.mp3")],
        )
        if not mp3:
            return
        self.status_lbl.config(text="Quitando portada...")
        threading.Thread(target=self._cover_worker,
                         args=("remove", mp3, None), daemon=True).start()

    def _cover_worker(self, action, mp3, img):
        if action == "add":
            ok, err = add_cover_to_file(mp3, img)
            msg_ok = "Portada agregada a:\n" + os.path.basename(mp3)
        else:
            ok, err = remove_cover_from_file(mp3)
            msg_ok = "Portada quitada de:\n" + os.path.basename(mp3)
        def report():
            if ok:
                self.status_lbl.config(text="Portada lista")
                messagebox.showinfo(APP_NAME, msg_ok)
            else:
                self.status_lbl.config(text="Error con la portada")
                messagebox.showerror(APP_NAME, "No se pudo:\n" + err)
        self.after(0, report)

    def _clear_done(self):
        for r in list(self.tree.get_children()):
            if self.tree.item(r, "values")[1] == "Completado":
                self.tree.delete(r)

    def _on_close(self):
        self._save()
        self.executor.shutdown(wait=False)
        self.destroy()


if __name__ == "__main__":
    if not YTDLP or not os.path.exists(YTDLP):
        print("ERROR: yt-dlp no encontrado. Instala con: brew install yt-dlp ffmpeg")
    App().mainloop()
