#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ytmp3 - Interfaz moderna (PySide6 / Qt) para descargar musica de YouTube a MP3.
Backend en ytmp3_core. Motor Qt nativo: render fiable + look profesional.
"""
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
    QSpinBox, QCheckBox, QFrame, QVBoxLayout, QHBoxLayout, QScrollArea,
    QProgressBar, QFileDialog, QMessageBox, QSizePolicy, QGraphicsDropShadowEffect,
    QInputDialog, QMenu,
)
from PySide6.QtGui import QColor, QAction

import ytmp3_core as core

# Ruta a assets: dentro del .app empaquetado usa el directorio temporal de PyInstaller.
if getattr(sys, "frozen", False):
    _BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(_BASE, "assets")

# ----------------------------- paleta / estilos ---------------------------- #
# Tope de descargas en paralelo. Sin cookies YouTube bloquea rapido; con cookies
# de un navegador con sesion iniciada aguanta mas en paralelo.
MAX_WORKERS = 3            # sin cookies
MAX_WORKERS_COOKIE = 8     # con cookies

COOKIE_OPTIONS = [
    ("Sin cookies", ""),
    ("Safari", "safari"),
    ("Chrome", "chrome"),
    ("Firefox", "firefox"),
    ("Brave", "brave"),
    ("Edge", "edge"),
]

ACCENT = "#ff3b30"
ACCENT_DK = "#d62f25"
BG = "#101216"
CARD = "#1a1d24"
CARD2 = "#21252e"
INPUT = "#262b35"
BORDER = "#323845"
TEXT = "#eceef2"
MUTED = "#9097a3"

QSS = f"""
* {{ font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue'; color: {TEXT};
     outline: none; }}
QWidget#root {{ background: {BG}; }}

QLabel#title {{ font-size: 22px; font-weight: 700; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 13px; }}
QLabel#section {{ color: {MUTED}; font-size: 12px; font-weight: 600;
                  letter-spacing: 1px; }}

QFrame#card {{ background: {CARD}; border-radius: 16px; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {INPUT}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 10px 12px; font-size: 14px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url({os.path.join(ASSETS, 'chevron.png')});
    width: 14px; height: 9px; margin-right: 8px; }}
QComboBox QAbstractItemView {{ background: {CARD2}; border: 1px solid {BORDER};
    border-radius: 10px; selection-background-color: transparent;
    padding: 6px; outline: none; }}
QComboBox QAbstractItemView::item {{ border-radius: 7px; padding: 7px 10px;
    min-height: 20px; color: {TEXT}; }}
QComboBox QAbstractItemView::item:selected {{ background: {ACCENT};
    color: white; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; border: none; }}

QPushButton {{
    background: {CARD2}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 9px 14px; font-size: 13px; font-weight: 600;
}}
QPushButton:hover {{ background: #2b313c; }}
QPushButton:pressed {{ background: #20242c; }}

QPushButton#primary {{
    background: {ACCENT}; border: none; color: white; padding: 11px 22px;
    font-size: 14px; font-weight: 700;
}}
QPushButton#primary:hover {{ background: {ACCENT_DK}; }}
QPushButton#primary:pressed {{ background: {ACCENT_DK}; }}

QCheckBox {{ spacing: 8px; font-size: 13px; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 6px;
    border: 1px solid {BORDER}; background: {INPUT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT};
    image: url({os.path.join(ASSETS, 'check.png')}); }}

QMenu {{ background: {CARD2}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 7px; color: {TEXT};
    font-size: 13px; }}
QMenu::item:selected {{ background: #2b313c; }}
QMenu::indicator {{ width: 16px; height: 16px; left: 8px; }}
QMenu::indicator:checked {{ image: url({os.path.join(ASSETS, 'check.png')}); }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px;
    min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #4a5161; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}

QFrame#dlcard {{ background: {CARD2}; border-radius: 12px; }}
QLabel#dltitle {{ font-size: 14px; font-weight: 600; }}
QLabel#dlstatus {{ color: {MUTED}; font-size: 12px; }}

QProgressBar {{ background: {INPUT}; border: none; border-radius: 4px;
    height: 7px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QProgressBar[state="done"]::chunk {{ background: #2ecc71; }}
QProgressBar[state="error"]::chunk {{ background: #ff6b6b; }}
QProgressBar[state="exists"]::chunk {{ background: #f5a623; }}
QProgressBar[state="paused"]::chunk {{ background: #8a94a6; }}
QProgressBar[state="cancelled"]::chunk {{ background: #5b6470; }}
QLabel#dlurl {{ color: #6b7280; font-size: 11px; }}

QPushButton#iconbtn {{ background: {INPUT}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 0; min-width: 30px; max-width: 30px;
    min-height: 28px; max-height: 28px; font-size: 13px; font-weight: 700;
    color: {MUTED}; }}
QPushButton#iconbtn:hover {{ background: #30363f; color: {TEXT}; }}
QPushButton#cancelbtn {{ background: {INPUT}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 0; min-width: 30px; max-width: 30px;
    min-height: 28px; max-height: 28px; font-size: 14px; font-weight: 700;
    color: #c9656b; }}
QPushButton#cancelbtn:hover {{ background: #3a2326; color: #ff6b6b; }}
"""


def make_check_png():
    """Crea assets/check.png (palomita) y assets/chevron.png (flecha del combo)."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return
    os.makedirs(ASSETS, exist_ok=True)
    chk = os.path.join(ASSETS, "check.png")
    if not os.path.exists(chk):
        img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.line([(9, 21), (17, 29), (31, 11)], fill=(255, 255, 255, 255), width=5,
               joint="curve")
        img.save(chk)
    chev = os.path.join(ASSETS, "chevron.png")
    if not os.path.exists(chev):
        img = Image.new("RGBA", (28, 18), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.line([(6, 5), (14, 13), (22, 5)], fill=(0x90, 0x97, 0xa3, 255), width=3,
               joint="curve")   # chevron hacia abajo
        img.save(chev)


# ----------------------------- combo con popup redondeado ------------------ #
class RoundCombo(QComboBox):
    """QComboBox cuyo menu desplegable tiene esquinas redondeadas (sin caja negra).
    Ignora la rueda/trackpad para que el valor no cambie solo al hacer scroll."""
    def wheelEvent(self, e):
        e.ignore()

    def showPopup(self):
        super().showPopup()
        view = self.view()
        win = view.window()
        win.setWindowFlag(Qt.FramelessWindowHint, True)
        win.setWindowFlag(Qt.NoDropShadowWindowHint, True)
        win.setAttribute(Qt.WA_TranslucentBackground, True)
        win.show()


class NoWheelSpin(QSpinBox):
    """QSpinBox que ignora la rueda/trackpad (no cambia solo al hacer scroll)."""
    def wheelEvent(self, e):
        e.ignore()


# ----------------------------- puente de hilos ----------------------------- #
class Bridge(QObject):
    event = Signal(dict)            # evento de descarga -> UI
    playlist_ready = Signal(list)   # urls expandidas de playlist -> UI


# ----------------------------- tarjeta de descarga ------------------------- #
class DownloadCard(QFrame):
    def __init__(self, url):
        super().__init__()
        self.setObjectName("dlcard")
        self.url = url
        self.view_mode = "normal"
        lay = QVBoxLayout(self)
        self.lay = lay
        lay.setContentsMargins(14, 11, 14, 12)
        lay.setSpacing(4)

        row = QHBoxLayout()
        self.row = row
        col = QVBoxLayout()
        col.setSpacing(1)
        self.title = QLabel("Obteniendo informacion...")
        self.title.setObjectName("dltitle")
        self.title.setWordWrap(False)
        short = url if len(url) <= 70 else url[:67] + "..."
        self.urllbl = QLabel(short)
        self.urllbl.setObjectName("dlurl")
        col.addWidget(self.title)
        col.addWidget(self.urllbl)
        wrap = QWidget()
        wrap.setLayout(col)
        wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.wrap = wrap
        self.status = QLabel("En cola")
        self.status.setObjectName("dlstatus")
        self.btn_pause = QPushButton("❚❚")   # ⏸ pausa
        self.btn_pause.setObjectName("iconbtn")
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.setToolTip("Pausar")
        self.btn_cancel = QPushButton("✕")        # ✕ cancelar / quitar
        self.btn_cancel.setObjectName("cancelbtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setToolTip("Cancelar / quitar")
        row.addWidget(wrap, 1)
        row.addWidget(self.status, 0, Qt.AlignVCenter)
        row.addWidget(self.btn_pause, 0, Qt.AlignVCenter)
        row.addWidget(self.btn_cancel, 0, Qt.AlignVCenter)
        lay.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)

        self.done = False
        self.paused = False
        self.finished = False   # done/exists/error/cancelled -> sin pausa

    def set_paused_look(self, paused):
        self.paused = paused
        self.btn_pause.setText("▶" if paused else "❚❚")  # ▶ / ⏸
        self.btn_pause.setToolTip("Reanudar" if paused else "Pausar")

    def update_event(self, ev):
        if "title" in ev:
            self.title.setText(ev["title"])
        if "status" in ev:
            self.status.setText(ev["status"])
        if "progress" in ev:
            self.bar.setValue(int(round(ev["progress"])))
        state = ev.get("state")
        if state in ("done", "exists"):
            self.done = True
            self.finished = True
            self.btn_pause.hide()
            self.bar.setProperty("state", state)
        elif state in ("error", "cancelled"):
            self.finished = True
            self.btn_pause.hide()
            self.bar.setProperty("state", "error" if state == "error" else "cancelled")
        elif state == "paused":
            self.set_paused_look(True)
            self.bar.setProperty("state", "paused")
        if state:
            self.bar.style().unpolish(self.bar)
            self.bar.style().polish(self.bar)
            colors = {"done": "#2ecc71", "exists": "#f5a623",
                      "error": "#ff6b6b", "cancelled": "#8a94a6"}
            c = colors.get(state)
            if c:
                self.status.setStyleSheet("color: %s; font-size: 12px;"
                                          " font-weight: 600;" % c)
        # en ultra el status va oculto; al terminar lo mostramos para no dejar
        # el titulo "Obteniendo informacion..." colgado (ej. "Ya existe")
        if self.view_mode == "ultra" and state in ("done", "exists", "error",
                                                    "cancelled"):
            self.bar.setVisible(False)
            self.status.setVisible(True)

    def apply_view(self, mode):
        """normal = titulo+url+barra abajo | compact = solo titulo chico |
        ultra = titulo + barra en linea + botones, todo en un renglon."""
        self.view_mode = mode
        # desacopla la barra de cualquier layout antes de recolocarla
        self.row.removeWidget(self.bar)
        self.lay.removeWidget(self.bar)
        self.urllbl.setVisible(mode == "normal")
        if mode == "compact":
            self.lay.setContentsMargins(12, 6, 12, 6)
            self.title.setStyleSheet("font-size: 12px; font-weight: 600;")
            self.status.setVisible(True)
            self.bar.setVisible(True)
            self.bar.setMinimumWidth(0)
            self.bar.setMaximumWidth(16777215)
            self.lay.addWidget(self.bar)
        elif mode == "ultra":
            self.lay.setContentsMargins(12, 5, 12, 5)
            self.title.setStyleSheet("font-size: 12px; font-weight: 600;")
            self.status.setVisible(False)
            self.bar.setVisible(True)
            self.bar.setFixedWidth(140)
            idx = self.row.indexOf(self.status)
            self.row.insertWidget(idx, self.bar, 0, Qt.AlignVCenter)
        else:  # normal
            self.lay.setContentsMargins(14, 11, 14, 12)
            self.title.setStyleSheet("font-size: 14px; font-weight: 600;")
            self.status.setVisible(True)
            self.bar.setVisible(True)
            self.bar.setMinimumWidth(0)
            self.bar.setMaximumWidth(16777215)
            self.lay.addWidget(self.bar)


# ----------------------------- ventana principal --------------------------- #
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("ytmp3 - Descargador de musica de YouTube")
        self.resize(820, 600)
        self.setMinimumSize(720, 520)

        self.settings = core.load_settings()
        self.collapse_state = int(self.settings.get("collapse_state", 0)) % 3
        self.view_mode = self.settings.get("view_mode", "normal")
        if self.view_mode not in ("normal", "compact", "ultra"):
            self.view_mode = "normal"
        self.notif_prefs = dict(core.NOTIF_PREFS)
        saved_notif = self.settings.get("notifications") or {}
        for k, v in saved_notif.items():
            if k in self.notif_prefs:
                self.notif_prefs[k] = bool(v)
        core.NOTIF_PREFS.update(self.notif_prefs)
        cap0 = MAX_WORKERS_COOKIE if self.settings.get("cookies_browser") else MAX_WORKERS
        self.executor = ThreadPoolExecutor(
            max_workers=min(int(self.settings["parallel_workers"]), cap0))
        self.queued_urls = set()
        self.cards = {}
        self.controls = {}      # control de pausa/cancelar por descarga
        self.params = {}        # parametros por descarga (para reanudar)
        self.row_counter = 0
        self.last_clipboard = ""

        self.bridge = Bridge()
        self.bridge.event.connect(self._on_event)
        self.bridge.playlist_ready.connect(self._enqueue_many)

        self._build()
        self._update_space()

        self.clip_timer = QTimer(self)
        self.clip_timer.timeout.connect(self._poll_clipboard)
        self.clip_timer.start(1000)
        # refresca el espacio libre cada 10s (por si cambia el volumen)
        self.space_timer = QTimer(self)
        self.space_timer.timeout.connect(self._update_space)
        self.space_timer.start(10000)

    # ---------- construccion ----------
    def _card(self):
        f = QFrame()
        f.setObjectName("card")
        sh = QGraphicsDropShadowEffect(blurRadius=24, xOffset=0, yOffset=6)
        sh.setColor(QColor(0, 0, 0, 90))
        f.setGraphicsEffect(sh)
        return f

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)

        # --- encabezado ---
        head = QHBoxLayout()
        head.setSpacing(12)
        logo = QLabel()
        ico = os.path.join(ASSETS, "icon_1024.png")
        if os.path.exists(ico):
            logo.setPixmap(QPixmap(ico).scaled(46, 46, Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation))
        htext = QVBoxLayout()
        htext.setSpacing(0)
        t = QLabel("ytmp3")
        t.setObjectName("title")
        s = QLabel("Descargador de musica de YouTube  ·  MP3 con artista, titulo y portada")
        s.setObjectName("subtitle")
        htext.addWidget(t)
        htext.addWidget(s)
        self.logo = logo
        self.header_text = QWidget()
        self.header_text.setLayout(htext)
        head.addWidget(logo)
        head.addWidget(self.header_text)
        head.addStretch(1)
        self.header_bar = QWidget()
        self.header_bar.setLayout(head)
        root.addWidget(self.header_bar)

        self.collapse_btn = QPushButton()
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        self.collapse_btn.clicked.connect(self._cycle_collapse)

        # --- tarjeta de entrada ---
        inp = self._card()
        iv = QVBoxLayout(inp)
        iv.setContentsMargins(18, 18, 18, 18)
        iv.setSpacing(14)

        urlrow = QHBoxLayout()
        urlrow.setSpacing(10)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Pega aqui el enlace de YouTube o YouTube Music...")
        self.url_edit.returnPressed.connect(self._add_from_entry)
        btn = QPushButton("Descargar")
        btn.setObjectName("primary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self._add_from_entry)
        urlrow.addWidget(self.url_edit, 1)
        urlrow.addWidget(btn)
        self.url_row = QWidget()
        self.url_row.setLayout(urlrow)
        iv.addWidget(self.url_row)

        # fila carpeta
        frow = QHBoxLayout()
        frow.setSpacing(10)
        flbl = QLabel("Carpeta")
        flbl.setObjectName("section")
        self.folder = RoundCombo()
        self.folder.setEditable(True)
        self.folder.addItems(self.settings["recent_folders"] or
                             [self.settings["last_folder"]])
        self.folder.setCurrentText(self.settings["last_folder"])
        self.folder.currentTextChanged.connect(lambda _: self._remember_folder())
        choose = QPushButton("Elegir...")
        choose.setCursor(Qt.PointingHandCursor)
        choose.clicked.connect(self._choose_folder)
        frow.addWidget(flbl)
        frow.addWidget(self.folder, 1)
        frow.addWidget(choose)
        frow.addWidget(self.collapse_btn)
        iv.addLayout(frow)

        # fila opciones
        orow = QHBoxLayout()
        orow.setSpacing(16)
        self.cb_clip = QCheckBox("Auto-cola")
        self.cb_clip.setToolTip("Detecta enlaces de YouTube copiados y los encola solos")
        self.cb_clip.setChecked(self.settings["clipboard_enabled"])
        self.cb_clip.setCursor(Qt.PointingHandCursor)
        self.cb_clip.toggled.connect(self._save)
        self.cb_play = QCheckBox("Playlist")
        self.cb_play.setToolTip("Descarga la playlist completa, no solo el video")
        self.cb_play.setChecked(self.settings["playlist_enabled"])
        self.cb_play.setCursor(Qt.PointingHandCursor)
        self.cb_play.toggled.connect(self._save)
        self.cb_cover = QCheckBox("Portada")
        self.cb_cover.setToolTip("Incrusta la caratula del video en el MP3")
        self.cb_cover.setChecked(self.settings["embed_cover"])
        self.cb_cover.setCursor(Qt.PointingHandCursor)
        self.cb_cover.toggled.connect(self._save)
        self.cb_skip = QCheckBox("Evitar duplicados")
        self.cb_skip.setToolTip("Si la cancion ya esta en la carpeta, no la descarga y avisa")
        self.cb_skip.setChecked(self.settings.get("skip_existing", True))
        self.cb_skip.setCursor(Qt.PointingHandCursor)
        self.cb_skip.toggled.connect(self._save)
        orow.addWidget(self.cb_clip)
        orow.addWidget(self.cb_play)
        orow.addWidget(self.cb_cover)
        orow.addWidget(self.cb_skip)
        orow.addStretch(1)
        clbl = QLabel("Cookies")
        clbl.setObjectName("section")
        self.cookie_combo = RoundCombo()
        for label, val in COOKIE_OPTIONS:
            self.cookie_combo.addItem(label, val)
        cidx = self.cookie_combo.findData(self.settings.get("cookies_browser", ""))
        self.cookie_combo.setCurrentIndex(cidx if cidx >= 0 else 0)
        self.cookie_combo.setToolTip("Usa la sesion del navegador para mas descargas en paralelo")
        self.cookie_combo.setFixedWidth(130)
        self.cookie_combo.currentIndexChanged.connect(self._on_cookie_change)
        orow.addWidget(clbl)
        orow.addWidget(self.cookie_combo)
        self.opts_row = QWidget()
        self.opts_row.setLayout(orow)
        iv.addWidget(self.opts_row)

        # segunda fila de opciones: espacio libre (izq) + calidad/paralelas (der)
        orow2 = QHBoxLayout()
        orow2.setSpacing(10)
        self.space_lbl = QLabel("")
        self.space_lbl.setObjectName("subtitle")
        orow2.addWidget(self.space_lbl)
        orow2.addStretch(1)
        qlbl = QLabel("Calidad")
        qlbl.setObjectName("section")
        self.quality = RoundCombo()
        # etiqueta clara -> valor real de yt-dlp
        QUALITY = [
            ("Maxima  (~320 kbps)", "320K"),
            ("Muy alta  (~256 kbps)", "256K"),
            ("Alta  (~192 kbps)", "192K"),
            ("Estandar  (~128 kbps)", "128K"),
        ]
        for label, val in QUALITY:
            self.quality.addItem(label, val)
        # selecciona segun el valor guardado (mapea valores viejos: 0/2/5)
        saved = str(self.settings["audio_quality"])
        legacy = {"0": "320K", "2": "192K", "5": "128K"}
        saved = legacy.get(saved, saved)
        idx = self.quality.findData(saved)
        self.quality.setCurrentIndex(idx if idx >= 0 else 2)  # default Alta 192K
        self.quality.setFixedWidth(210)
        self.quality.currentTextChanged.connect(self._save)
        plbl = QLabel("Paralelas")
        plbl.setObjectName("section")
        self.workers = NoWheelSpin()
        cap = MAX_WORKERS_COOKIE if self.cookie_combo.currentData() else MAX_WORKERS
        self.workers.setRange(1, cap)
        self.workers.setValue(min(int(self.settings["parallel_workers"]), cap))
        self.workers.setToolTip("Maximo %d%s" % (
            cap, " (con cookies)" if self.cookie_combo.currentData() else " sin cookies"))
        self.workers.setFixedWidth(56)
        self.workers.valueChanged.connect(self._change_workers)
        orow2.addWidget(qlbl)
        orow2.addWidget(self.quality)
        orow2.addSpacing(12)
        orow2.addWidget(plbl)
        orow2.addWidget(self.workers)
        self.opts_row2 = QWidget()
        self.opts_row2.setLayout(orow2)
        iv.addWidget(self.opts_row2)

        root.addWidget(inp)

        # --- encabezado de lista + acciones ---
        lhead = QHBoxLayout()
        sec = QLabel("DESCARGAS")
        sec.setObjectName("section")
        self.counter = QLabel("")
        self.counter.setObjectName("subtitle")
        lhead.addWidget(sec)
        lhead.addStretch(1)
        lhead.addWidget(self.counter)
        self.view_btn = QPushButton()
        self.view_btn.setCursor(Qt.PointingHandCursor)
        self.view_btn.clicked.connect(self._cycle_view)
        lhead.addWidget(self.view_btn)
        self.notif_btn = QPushButton("Notificaciones")
        self.notif_btn.setCursor(Qt.PointingHandCursor)
        self.notif_btn.setMenu(self._build_notif_menu())
        lhead.addWidget(self.notif_btn)
        for txt, fn in (("Abrir carpeta", self._open_folder),
                        ("Cancelar todo", self._cancel_all),
                        ("Limpiar", self._clear_done)):
            b = QPushButton(txt)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            lhead.addWidget(b)
        root.addLayout(lhead)

        # --- lista de descargas (scroll) ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        holder = QWidget()
        self.list_lay = QVBoxLayout(holder)
        self.list_lay.setContentsMargins(0, 0, 6, 0)
        self.list_lay.setSpacing(10)
        self.list_lay.addStretch(1)
        self.empty = QLabel("No hay descargas todavia.\nPega un enlace y presiona Descargar.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet(f"color: {MUTED}; font-size: 14px;")
        self.list_lay.insertWidget(0, self.empty)
        self.scroll.setWidget(holder)
        root.addWidget(self.scroll, 1)

        self._apply_collapse()
        self._apply_view()

    # ---------- contraer tarjeta de entrada ----------
    def _cycle_collapse(self):
        self.collapse_state = (self.collapse_state + 1) % 3
        self.settings["collapse_state"] = self.collapse_state
        core.save_settings(self.settings)
        self._apply_collapse()

    def _apply_collapse(self):
        # 0 = todo visible
        # 1 = solo carpeta + calidad/espacio/paralelas (oculta URL y casillas)
        # 2 = solo carpeta + Elegir (oculta todo lo demas)
        st = self.collapse_state
        self.header_bar.setVisible(st == 0)
        self.url_row.setVisible(st == 0)
        self.opts_row.setVisible(st == 0)
        self.opts_row2.setVisible(st in (0, 1))
        labels = {0: "▾  Contraer", 1: "▾  Compactar", 2: "▸  Expandir"}
        tips = {0: "Mostrar solo carpeta y opciones basicas",
                1: "Mostrar solo carpeta",
                2: "Mostrar todo"}
        self.collapse_btn.setText(labels[st])
        self.collapse_btn.setToolTip(tips[st])

    # ---------- vista de descargas ----------
    def _cycle_view(self):
        order = ["normal", "compact", "ultra"]
        self.view_mode = order[(order.index(self.view_mode) + 1) % 3]
        self.settings["view_mode"] = self.view_mode
        core.save_settings(self.settings)
        self._apply_view()

    def _apply_view(self):
        labels = {"normal": "Vista: Normal", "compact": "Vista: Compacta",
                  "ultra": "Vista: Ultra"}
        self.view_btn.setText(labels[self.view_mode])
        for card in self.cards.values():
            card.apply_view(self.view_mode)

    # ---------- menu de notificaciones ----------
    def _build_notif_menu(self):
        menu = QMenu(self)
        items = [
            ("detected", "URL detectada"),
            ("started", "Descarga iniciada"),
            ("done", "Descarga completada"),
            ("exists", "Cancion ya existe"),
            ("error", "Error en descarga"),
        ]
        for kind, label in items:
            act = QAction(label, menu)
            act.setCheckable(True)
            act.setChecked(self.notif_prefs.get(kind, True))
            act.toggled.connect(lambda on, k=kind: self._toggle_notif(k, on))
            menu.addAction(act)
        return menu

    def _toggle_notif(self, kind, on):
        self.notif_prefs[kind] = on
        core.NOTIF_PREFS[kind] = on
        self.settings["notifications"] = self.notif_prefs
        core.save_settings(self.settings)

    # ---------- carpeta ----------
    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Elige carpeta",
                                             self.folder.currentText() or core.DEFAULT_FOLDER)
        if d:
            self.folder.setCurrentText(d)
            self._remember_folder()

    def _remember_folder(self):
        folder = self.folder.currentText().strip()
        if not folder:
            return
        recents = self.settings["recent_folders"]
        if folder in recents:
            recents.remove(folder)
        recents.insert(0, folder)
        self.settings["recent_folders"] = recents[:10]
        self.settings["last_folder"] = folder
        core.save_settings(self.settings)
        self._update_space()

    def _open_folder(self):
        folder = self.folder.currentText().strip()
        if folder and os.path.isdir(folder):
            import subprocess, platform
            s = platform.system()
            if s == "Darwin":
                subprocess.Popen(["open", folder])
            elif s == "Windows":
                os.startfile(folder)   # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", folder])
        else:
            QMessageBox.information(self, core.APP_NAME, "La carpeta aun no existe.")

    # ---------- ajustes ----------
    def _save(self, *_):
        self.settings["clipboard_enabled"] = self.cb_clip.isChecked()
        self.settings["playlist_enabled"] = self.cb_play.isChecked()
        self.settings["embed_cover"] = self.cb_cover.isChecked()
        self.settings["skip_existing"] = self.cb_skip.isChecked()
        self.settings["audio_quality"] = self.quality.currentData() or "192K"
        self.settings["parallel_workers"] = self.workers.value()
        self.settings["cookies_browser"] = self.cookie_combo.currentData() or ""
        core.save_settings(self.settings)

    def _on_cookie_change(self, *_):
        use = bool(self.cookie_combo.currentData())
        cap = MAX_WORKERS_COOKIE if use else MAX_WORKERS
        self.workers.setRange(1, cap)
        if self.workers.value() > cap:
            self.workers.setValue(cap)
        self.workers.setToolTip("Maximo %d%s" % (
            cap, " (con cookies)" if use else " sin cookies"))
        self._save()

    def _change_workers(self, *_):
        n = self.workers.value()
        old = self.executor
        self.executor = ThreadPoolExecutor(max_workers=n)
        threading.Thread(target=old.shutdown, kwargs={"wait": False},
                         daemon=True).start()
        self._save()

    # ---------- agregar / encolar ----------
    def _add_from_entry(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        if not (core.YT_URL_RE.search(url) or core.PLAYLIST_RE.search(url)):
            QMessageBox.warning(self, core.APP_NAME,
                                "No parece una URL de YouTube/YouTube Music.")
            return
        self.url_edit.clear()
        self._handle_url(url)

    def _handle_url(self, url):
        is_playlist = core.LIST_ID_RE.search(url) is not None
        if self.cb_play.isChecked() and is_playlist:
            self._remember_folder()
            self.counter.setText("Leyendo playlist...")
            threading.Thread(target=self._expand, args=(url,), daemon=True).start()
        else:
            self._enqueue(url)

    def _expand(self, url):
        urls = core.expand_playlist(url)
        self.bridge.playlist_ready.emit(urls)

    def _enqueue_many(self, urls):
        if not urls:
            self.counter.setText("Playlist vacia o no se pudo leer")
            return
        total = len(urls)
        # confirma cuantas descargar (1..total)
        n, ok = QInputDialog.getInt(
            self, "Playlist detectada",
            "La playlist tiene %d canciones.\n"
            "¿Cuantas quieres descargar?  (1 a %d)" % (total, total),
            total, 1, total, 1)
        if not ok:
            self.counter.setText("Playlist cancelada")
            return
        for u in urls[:n]:
            self._enqueue(u)

    def _enqueue(self, url):
        if url in self.queued_urls:
            return
        self.queued_urls.add(url)
        self.empty.hide()
        self.row_counter += 1
        item_id = "row%d" % self.row_counter
        card = DownloadCard(url)
        self.cards[item_id] = card
        card.apply_view(self.view_mode)
        card.btn_pause.clicked.connect(lambda _=False, i=item_id: self._toggle_pause(i))
        card.btn_cancel.clicked.connect(lambda _=False, i=item_id: self._cancel(i))
        self.list_lay.insertWidget(self.list_lay.count() - 1, card)
        folder = self.folder.currentText().strip() or core.DEFAULT_FOLDER
        self._remember_folder()
        q = self.quality.currentData() or "192K"
        cover = self.cb_cover.isChecked()
        check = self.cb_skip.isChecked()
        cookies = self.cookie_combo.currentData() or ""
        self.params[item_id] = (url, folder, q, cover, check, cookies)
        self._start(item_id)
        self._update_counter()

    def _start(self, item_id):
        """Lanza (o relanza) la descarga con un control nuevo."""
        url, folder, q, cover, check, cookies = self.params[item_id]
        control = core.DownloadControl()
        self.controls[item_id] = control
        emit = lambda ev: self.bridge.event.emit(ev)
        self.executor.submit(core.run_download, item_id, url, folder, q, cover,
                             emit, check, control, cookies or None)

    # ---------- pausa / reanudar / cancelar ----------
    def _toggle_pause(self, item_id):
        card = self.cards.get(item_id)
        if not card or card.finished:
            return
        if card.paused:
            self._resume(item_id)
        else:
            ctrl = self.controls.get(item_id)
            if ctrl:
                ctrl.pause()   # run_download emitira estado 'paused'

    def _resume(self, item_id):
        card = self.cards.get(item_id)
        if not card:
            return
        card.set_paused_look(False)
        card.bar.setProperty("state", "")
        card.bar.style().unpolish(card.bar)
        card.bar.style().polish(card.bar)
        card.status.setText("Reanudando...")
        self._start(item_id)   # yt-dlp continua el .part automaticamente

    def _cancel(self, item_id):
        ctrl = self.controls.get(item_id)
        card = self.cards.get(item_id)
        if ctrl and card and not card.finished:
            ctrl.cancel()
        # quita la tarjeta (limpiar)
        if card:
            card.setParent(None)
        url = self.params.get(item_id, (None,))[0]
        if url:
            self.queued_urls.discard(url)
        self.cards.pop(item_id, None)
        self.controls.pop(item_id, None)
        self.params.pop(item_id, None)
        if not self.cards:
            self.empty.show()
        self._update_counter()

    def _cancel_all(self):
        if not self.cards:
            return
        running = sum(1 for c in self.cards.values() if not c.finished)
        if running:
            r = QMessageBox.question(
                self, core.APP_NAME,
                "¿Cancelar TODAS las descargas (%d en curso)?" % running,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if r != QMessageBox.Yes:
                return
        # primero marca cancelacion en todos los controles (aborta los pendientes)
        for ctrl in self.controls.values():
            ctrl.cancel()
        for card in self.cards.values():
            card.setParent(None)
        self.cards.clear()
        self.controls.clear()
        self.params.clear()
        self.queued_urls.clear()
        self.empty.show()
        self._update_counter()

    # ---------- espacio en disco ----------
    def _update_space(self):
        folder = self.folder.currentText().strip() if hasattr(self, "folder") else ""
        info = core.free_space(folder)
        if info:
            free, total = info
            self.space_lbl.setText("Espacio libre: %s de %s"
                                   % (core.human_size(free), core.human_size(total)))
        else:
            self.space_lbl.setText("")

    # ---------- eventos ----------
    def _on_event(self, ev):
        card = self.cards.get(ev["id"])
        if card:
            card.update_event(ev)
        if ev.get("state") in ("done", "exists"):
            self._update_space()
        self._update_counter()

    def _update_counter(self):
        total = len(self.cards)
        done = sum(1 for c in self.cards.values() if c.done)
        self.counter.setText("%d/%d completadas" % (done, total) if total else "")

    def _clear_done(self):
        for iid, card in list(self.cards.items()):
            if card.finished:
                card.setParent(None)
                self.cards.pop(iid, None)
                self.controls.pop(iid, None)
                url = self.params.pop(iid, (None,))[0]
                if url:
                    self.queued_urls.discard(url)
        if not self.cards:
            self.empty.show()
        self._update_counter()

    # ---------- clipboard ----------
    def _poll_clipboard(self):
        if not self.cb_clip.isChecked():
            return
        text = QApplication.clipboard().text()
        if text and text != self.last_clipboard:
            self.last_clipboard = text
            m = core.YT_URL_RE.search(text) or core.PLAYLIST_RE.search(text)
            if m:
                core.notify_kind("detected", core.APP_NAME, "Enlace detectado")
                self._handle_url(m.group(0))

    # ---------- portada de archivos ----------
    def _add_cover(self):
        mp3, _ = QFileDialog.getOpenFileName(
            self, "Elige el MP3", self.folder.currentText() or core.DEFAULT_FOLDER,
            "MP3 (*.mp3)")
        if not mp3:
            return
        img, _ = QFileDialog.getOpenFileName(
            self, "Elige la imagen", "", "Imagenes (*.jpg *.jpeg *.png *.webp)")
        if not img:
            return
        threading.Thread(target=self._cover_worker,
                         args=("add", mp3, img), daemon=True).start()

    def _remove_cover(self):
        mp3, _ = QFileDialog.getOpenFileName(
            self, "Elige el MP3", self.folder.currentText() or core.DEFAULT_FOLDER,
            "MP3 (*.mp3)")
        if not mp3:
            return
        threading.Thread(target=self._cover_worker,
                         args=("remove", mp3, None), daemon=True).start()

    def _cover_worker(self, action, mp3, img):
        if action == "add":
            ok, err = core.add_cover_to_file(mp3, img)
            msg = "Portada agregada a:\n" + os.path.basename(mp3)
        else:
            ok, err = core.remove_cover_from_file(mp3)
            msg = "Portada quitada de:\n" + os.path.basename(mp3)
        self.bridge.event.emit({"id": "__cover__", "_cover": (ok, msg if ok else err)})

    def closeEvent(self, e):
        self._save()
        self.executor.shutdown(wait=False)
        super().closeEvent(e)


def main():
    make_check_png()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    ico = os.path.join(ASSETS, "icon.icns")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))
    w = MainWindow()
    # maneja resultado de portada con un dialogo
    def cover_result(ev):
        if ev.get("id") == "__cover__":
            ok, payload = ev["_cover"]
            if ok:
                QMessageBox.information(w, core.APP_NAME, payload)
            else:
                QMessageBox.critical(w, core.APP_NAME, "No se pudo:\n" + payload)
    w.bridge.event.connect(cover_result)
    w.show()
    # primer arranque: registra la app en Notificaciones y pide permiso
    if not w.settings.get("notif_intro_shown"):
        QTimer.singleShot(800, core.request_notifications)
        w.settings["notif_intro_shown"] = True
        core.save_settings(w.settings)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
