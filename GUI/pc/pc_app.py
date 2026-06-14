#!/usr/bin/env python3
# pc/pc_app.py
# ─────────────────────────────────────────────────────────────
# EggApp — Node Laptop (RTX 4060 / i7)
# Fungsi: Terima stream video dari Raspi, inferensi YOLOv8,
#         tampilkan GUI dengan panel thumbnail, kirim JSON ke Raspi.
# ─────────────────────────────────────────────────────────────
import sys
import cv2
import queue
import logging
import numpy as np
import time
from datetime import datetime
from collections import Counter
from PyQt6.QtCore    import Qt, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui     import QPixmap, QImage, QFont, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QFrame, QLineEdit, QSpinBox,
    QSizePolicy, QFileDialog, QMessageBox, QDoubleSpinBox, QDialog, QDialogButtonBox
)

from pathlib import Path
from dotenv  import load_dotenv, set_key
from config          import (RASPI_IP, VIDEO_PORT, RESULT_PORT,
                              MODEL_PATH, CONF_THRESH, LOG_FILE, LOG_LEVEL)
from yolo_engine           import YoloEngine
from settings_dialog_pc import SettingsDialog
from frame_receiver   import FrameReceiverThread
from result_sender    import ResultSenderThread
#from settings_dialog  import SettingsDialog

# ── Logging ───────────────────────────────────────────────────
import os
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('pc_app')

# ── Stylesheet ─────────────────────────────────────────────────
STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1A1A2E;
    color: #E0E0E0;
    font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
    font-size: 12px;
}
QGroupBox {
    border: 1px solid #2D2D44;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: bold;
    color: #7986CB;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; }
QPushButton {
    background-color: #283593;
    color: #FFFFFF;
    border: none;
    border-radius: 5px;
    padding: 7px 18px;
    font-weight: bold;
}
QPushButton:hover    { background-color: #3949AB; }
QPushButton:disabled { background-color: #37474F; color: #78909C; }
QPushButton#btn_running {
    background-color: #1B5E20;
    min-width: 110px;
}
QPushButton#btn_running:hover  { background-color: #2E7D32; }
QPushButton#btn_running_active {
    background-color: #B71C1C;
    min-width: 110px;
}
QPushButton#btn_running_active:hover { background-color: #E53935; }
QPushButton#btn_capture { background-color: #4A148C; }
QPushButton#btn_capture:hover { background-color: #6A1B9A; }
QLabel#lbl_title {
    font-size: 15px; font-weight: bold;
    color: #7986CB; padding: 2px 0;
}
QLabel#lbl_counter {
    font-size: 13px; font-weight: bold;
    color: #E0E0E0; padding: 2px 6px;
}
QLabel#lbl_status_ok   { color: #69F0AE; font-weight: bold; font-size: 14px; }
QLabel#lbl_status_fail { color: #EF5350; font-weight: bold; font-size: 14px; }
QLabel#lbl_status_none { color: #FFD54F; font-weight: bold; font-size: 14px; }
QLabel#lbl_coord { color: #90CAF9; font-size: 12px; }
QTextEdit {
    background-color: #0D0D1A;
    color: #A5D6A7;
    font-family: 'Courier New', 'Lucida Console', monospace;
    font-size: 11px;
    border: 1px solid #2D2D44;
    border-radius: 4px;
}
QLabel#thumb_label {
    background-color: #0D0D1A;
    border: 1px solid #2D2D44;
    border-radius: 4px;
}
"""


# ═══════════════════════════════════════════════════════════════
# SettingsDialog — PC
# ═══════════════════════════════════════════════════════════════
# class SettingsDialog(QDialog):
#     """
#     Window pengaturan terpisah untuk pc_app.
#     Nilai langsung dibaca dari .env sebagai default.
#     Apply: berlaku sekarang (window/idle/conf/IP).
#     Simpan: tulis ke .env, berlaku permanen setelah restart untuk port/model.
#     """
#     def __init__(self, main_win, parent=None):
#         super().__init__(parent)
#         self.main = main_win
#         self.setWindowTitle("⚙️  Pengaturan — EggApp PC")
#         self.setMinimumWidth(420)
#         self.setStyleSheet(parent.styleSheet() if parent else "")
#         self._build()

#     def _build(self):
#         root = QVBoxLayout(self)
#         root.setSpacing(8)
#         root.setContentsMargins(16, 16, 16, 16)

#         def _row(label, widget):
#             r = QHBoxLayout()
#             lbl = QLabel(label)
#             lbl.setFixedWidth(190)
#             r.addWidget(lbl)
#             r.addWidget(widget)
#             return r

#         # ── Jaringan ──────────────────────────────────────────
#         grp_net = QGroupBox("Jaringan")
#         net_lay = QVBoxLayout(grp_net)

#         self.edit_raspi_ip = QLineEdit(RASPI_IP)
#         net_lay.addLayout(_row("IP Raspberry Pi:", self.edit_raspi_ip))

#         row_ports = QHBoxLayout()
#         lbl_p = QLabel("Port Video / Result:")
#         lbl_p.setFixedWidth(190)
#         self.spin_vport = QSpinBox(); self.spin_vport.setRange(1024,65535); self.spin_vport.setValue(VIDEO_PORT)
#         lbl_sl = QLabel("/"); lbl_sl.setFixedWidth(12)
#         self.spin_rport = QSpinBox(); self.spin_rport.setRange(1024,65535); self.spin_rport.setValue(RESULT_PORT)
#         row_ports.addWidget(lbl_p); row_ports.addWidget(self.spin_vport)
#         row_ports.addWidget(lbl_sl); row_ports.addWidget(self.spin_rport)
#         net_lay.addLayout(row_ports)
#         root.addWidget(grp_net)

#         # ── Model ─────────────────────────────────────────────
#         grp_model = QGroupBox("Model YOLO")
#         model_lay = QVBoxLayout(grp_model)

#         row_model = QHBoxLayout()
#         lbl_m = QLabel("Path Model (.pt):")
#         lbl_m.setFixedWidth(190)
#         self.edit_model = QLineEdit(MODEL_PATH)
#         self.btn_browse = QPushButton("📂")
#         self.btn_browse.setFixedWidth(36)
#         self.btn_browse.clicked.connect(self._browse_model)
#         row_model.addWidget(lbl_m); row_model.addWidget(self.edit_model); row_model.addWidget(self.btn_browse)
#         model_lay.addLayout(row_model)

#         self.spin_conf = QDoubleSpinBox()
#         self.spin_conf.setRange(0.1, 1.0); self.spin_conf.setSingleStep(0.05)
#         self.spin_conf.setDecimals(2); self.spin_conf.setValue(CONF_THRESH)
#         model_lay.addLayout(_row("Confidence Threshold:", self.spin_conf))
#         root.addWidget(grp_model)

#         # ── Logika Deteksi ────────────────────────────────────
#         grp_logic = QGroupBox("Logika Deteksi")
#         logic_lay = QVBoxLayout(grp_logic)

#         self.spin_window = QDoubleSpinBox()
#         self.spin_window.setRange(1.0, 60.0); self.spin_window.setSingleStep(1.0)
#         self.spin_window.setDecimals(1); self.spin_window.setValue(self.main._detection_window)
#         logic_lay.addLayout(_row("Detection Window (detik):", self.spin_window))

#         self.spin_idle = QDoubleSpinBox()
#         self.spin_idle.setRange(0.5, 30.0); self.spin_idle.setSingleStep(0.5)
#         self.spin_idle.setDecimals(1); self.spin_idle.setValue(self.main._idle_duration)
#         logic_lay.addLayout(_row("Idle Antar Telur (detik):", self.spin_idle))
#         root.addWidget(grp_logic)

#         # ── Tombol ────────────────────────────────────────────
#         btn_apply = QPushButton("✔  Apply Sekarang")
#         btn_apply.setStyleSheet("background:#283593; padding:7px;")
#         btn_save  = QPushButton("💾  Simpan ke .env")
#         btn_save.setStyleSheet("background:#1B5E20; padding:7px;")
#         btn_close = QPushButton("✕  Tutup")
#         btn_close.setStyleSheet("background:#37474F; padding:7px;")

#         btn_apply.clicked.connect(self._apply)
#         btn_save.clicked.connect(self._save)
#         btn_close.clicked.connect(self.close)

#         row_btn = QHBoxLayout()
#         row_btn.addWidget(btn_apply)
#         row_btn.addWidget(btn_save)
#         row_btn.addWidget(btn_close)
#         root.addLayout(row_btn)

#         lbl_note = QLabel(
#             "ℹ️  Apply: Window/Idle/Conf/IP langsung berlaku.\n"
#             "    Port & Model berlaku setelah restart."
#         )
#         lbl_note.setStyleSheet("color:#78909C; font-size:10px;")
#         root.addWidget(lbl_note)

#     def _browse_model(self):
#         path, _ = QFileDialog.getOpenFileName(
#             self, "Pilih Model YOLO", "", "PyTorch Model (*.pt);;All Files (*)"
#         )
#         if path:
#             self.edit_model.setText(path)

#     def _apply(self):
#         import config as cfg
#         self.main._detection_window = self.spin_window.value()
#         self.main._idle_duration    = self.spin_idle.value()
#         cfg.CONF_THRESH             = self.spin_conf.value()
#         cfg.RASPI_IP                = self.edit_raspi_ip.text().strip()
#         self.main._log(
#             f"[CONFIG] Applied — "
#             f"window:{self.main._detection_window:.1f}s  "
#             f"idle:{self.main._idle_duration:.1f}s  "
#             f"conf:{cfg.CONF_THRESH:.2f}  "
#             f"raspi:{cfg.RASPI_IP}"
#         )

#     def _save(self):
#         self._apply()
#         env_path = Path(__file__).parent / '.env'
#         vals = {
#             'RASPI_IP':    self.edit_raspi_ip.text().strip(),
#             'VIDEO_PORT':  str(self.spin_vport.value()),
#             'RESULT_PORT': str(self.spin_rport.value()),
#             'MODEL_PATH':  self.edit_model.text().strip(),
#             'CONF_THRESH': f"{self.spin_conf.value():.2f}",
#         }
#         for k, v in vals.items():
#             set_key(str(env_path), k, v)
#         self.main._log(f"[CONFIG] Disimpan ke {env_path}")
#         QMessageBox.information(self, "Tersimpan",
#             "Konfigurasi disimpan ke .env\n"
#             "Window / Idle / Conf sudah aktif sekarang.\n"
#             "Port & Model berlaku setelah restart.")


# ═══════════════════════════════════════════════════════════════
# YoloInferenceThread
# ═══════════════════════════════════════════════════════════════
class YoloInferenceThread(QThread):
    """
    Ambil frame dari queue, jalankan YoloEngine, emit hasilnya.
    Queue maxsize=1 → selalu inferensi frame terbaru.
    """
    inference_done = pyqtSignal(object, object, object, dict)
    # args: annotated_frame, false_color, mask, result_dict

    def __init__(self, engine: YoloEngine, parent=None):
        super().__init__(parent)
        self.engine      = engine
        self.frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self._running    = False

    def push_frame(self, frame: np.ndarray):
        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            pass

    def run(self):
        self._running = True
        while self._running:
            try:
                frame = self.frame_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # frame dari frame_receiver sudah BGR (hasil cv2.imdecode)
            annotated, result  = self.engine.infer(frame)
            false_color, mask  = self.engine.generate_panels(frame)
            self.inference_done.emit(annotated, false_color, mask, result)

    def stop(self):
        self._running = False


# ═══════════════════════════════════════════════════════════════
# Utility: ndarray BGR → QPixmap
# ═══════════════════════════════════════════════════════════════
def bgr_to_pixmap(frame_bgr: np.ndarray, w: int, h: int) -> QPixmap:
    rgb   = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    hh, ww, ch = rgb.shape
    qimg  = QImage(rgb.data.tobytes(), ww, hh, ch * ww, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg).scaled(
        w, h,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )

def _render_to_label(frame_bgr: np.ndarray, label: QLabel):
    """Render frame BGR ke QLabel — scale fit dengan ukuran label saat ini."""
    if frame_bgr is None or label.width() < 2 or label.height() < 2:
        return
    pix = bgr_to_pixmap(frame_bgr, label.width(), label.height())
    label.setPixmap(pix)


# ═══════════════════════════════════════════════════════════════
# MainWindow
# ═══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EggApp — PC Inspector")
        self.setMinimumSize(900, 680)

        # State
        self._inferring       = False
        self._last_annotated  = None   # simpan frame terakhir untuk screenshot
        self._last_raw_frame  = None   # frame mentah (non-inferring)
        self._last_false      = None   # false color thumbnail
        self._last_mask       = None   # mask thumbnail
        self._counter_ok      = 0
        self._counter_fail    = 0
        self._fps_times: list = []

        # ── Logika akumulasi deteksi 10 detik ────────────────
        self._detection_window = 10.0   # detik pengamatan per telur
        self._idle_duration    = 2.0    # detik idle antar telur
        self._accum_classes: list = []  # kelas terdeteksi selama window
        self._window_start: float = 0.0
        self._in_idle      = False      # sedang idle antar telur
        self._idle_start   = 0.0
        self._window_active = False     # window sedang berjalan

        # Thread & Engine
        self._engine: YoloEngine | None          = None
        self._recv_thread: FrameReceiverThread | None   = None
        self._yolo_thread: YoloInferenceThread | None   = None
        self._sender_thread: ResultSenderThread | None  = None

        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._start_receiver()   # mulai listen Raspi otomatis saat GUI dibuka

    # ── UI Builder ────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Title + Counter ───────────────────────────────────
        top = QHBoxLayout()
        lbl_title = QLabel("🥚 EggApp — PC Inspector")
        lbl_title.setObjectName("lbl_title")
        self.lbl_counter = QLabel("✅ Diterima: 0   ❌ Ditolak: 0")
        self.lbl_counter.setObjectName("lbl_counter")
        self.lbl_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(lbl_title)
        top.addStretch()
        top.addWidget(self.lbl_counter)
        root.addLayout(top)

        # ── Area utama (video + thumbnail) ───────────────────
        mid = QHBoxLayout()
        mid.setSpacing(8)

        # Video utama
        self.lbl_main = QLabel("[ Menunggu stream dari Raspi... ]")
        self.lbl_main.setObjectName("thumb_label")
        self.lbl_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_main.setMinimumSize(620, 460)
        self.lbl_main.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        mid.addWidget(self.lbl_main, stretch=3)

        # Panel thumbnail kanan
        right = QVBoxLayout()
        right.setSpacing(6)

        self.lbl_thumb_rgb   = self._make_thumb("RGB Feed")
        self.lbl_thumb_depth = self._make_thumb("Depth / False Color")
        self.lbl_thumb_mask  = self._make_thumb("Mask / Edge")
        right.addWidget(self._wrap_thumb(self.lbl_thumb_rgb,   "RGB Feed"))
        right.addWidget(self._wrap_thumb(self.lbl_thumb_depth, "Depth / False Color"))
        right.addWidget(self._wrap_thumb(self.lbl_thumb_mask,  "Mask / Edge"))
        mid.addLayout(right, stretch=1)

        root.addLayout(mid)

        # ── Tombol kontrol ────────────────────────────────────
        ctrl = QHBoxLayout()
        self.btn_settings = QPushButton("⚙️  Settings")
        self.btn_running = QPushButton("▶  Running")
        self.btn_capture = QPushButton("📷 Capture Screen Shot")
        self.btn_running.setObjectName("btn_running")
        self.btn_capture.setObjectName("btn_capture")

        self.btn_settings.clicked.connect(self._on_open_settings)
        self.btn_running.clicked.connect(self._on_toggle_running)
        self.btn_capture.clicked.connect(self._on_capture)

        ctrl.addWidget(self.btn_settings)
        ctrl.addWidget(self.btn_running)
        ctrl.addStretch()
        ctrl.addWidget(self.btn_capture)
        root.addLayout(ctrl)

        # ── Info bar ─────────────────────────────────────────
        info = QHBoxLayout()
        self.lbl_coord   = QLabel("Center Coordinate\nx: —,  y: —")
        self.lbl_coord.setObjectName("lbl_coord")
        self.lbl_fps     = QLabel("FPS: —")
        self.lbl_fps.setStyleSheet("color:#90CAF9;")
        self.lbl_conf    = QLabel("Confidence: —")
        self.lbl_conf.setStyleSheet("color:#90CAF9;")
        self.lbl_status  = QLabel("● MENUNGGU")
        self.lbl_status.setObjectName("lbl_status_none")
        info.addWidget(self.lbl_coord)
        info.addStretch()
        info.addWidget(self.lbl_fps)
        info.addWidget(QLabel("  |  "))
        info.addWidget(self.lbl_conf)
        info.addWidget(QLabel("  |  Status:"))
        info.addWidget(self.lbl_status)
        root.addLayout(info)

        # ── Log ───────────────────────────────────────────────
        grp_log = QGroupBox("Log Inferensi")
        log_lay = QVBoxLayout(grp_log)
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setFixedHeight(130)
        log_lay.addWidget(self.log_widget)
        root.addWidget(grp_log)

    def _make_thumb(self, placeholder: str) -> QLabel:
        lbl = QLabel(placeholder)
        lbl.setObjectName("thumb_label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setMinimumSize(160, 110)
        lbl.setMaximumWidth(280)
        lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        lbl.setStyleSheet(
            "background:#0D0D1A; border:1px solid #2D2D44; "
            "border-radius:4px; color:#546E7A; font-size:10px;"
        )
        return lbl

    def _wrap_thumb(self, lbl: QLabel, title: str) -> QGroupBox:
        gb  = QGroupBox(title)
        gb.setStyleSheet("QGroupBox { font-size: 10px; }")
        gb.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        lay = QVBoxLayout(gb)
        lay.setContentsMargins(2, 12, 2, 2)
        lay.addWidget(lbl)
        return gb

    # ── Start background threads ──────────────────────────────
    def _start_receiver(self):
        self._recv_thread = FrameReceiverThread()
        self._recv_thread.frame_ready.connect(self._on_frame_received)
        self._recv_thread.status_changed.connect(self._on_recv_status)
        self._recv_thread.start()

        self._sender_thread = ResultSenderThread()
        self._sender_thread.start()

        self._log("[RECV] Menunggu koneksi Raspi...")

    def _load_yolo(self):
        """Load YOLO engine (blocking, dipanggil saat tombol Running ditekan)."""
        try:
            self._engine      = YoloEngine()
            self._yolo_thread = YoloInferenceThread(self._engine)
            self._yolo_thread.inference_done.connect(self._on_inference_done)
            self._yolo_thread.start()
            self._log(f"[YOLO] Model dimuat. Kelas: {list(self._engine.model.names.values())}")
            return True
        except Exception as e:
            self._log(f"[ERROR] Gagal load model: {e}", error=True)
            QMessageBox.critical(self, "Error Model", str(e))
            return False

    # ── Slot Tombol ───────────────────────────────────────────
    @pyqtSlot()
    def _on_show(self):
        """Tampilkan info model dan koneksi saat ini."""
        info = (
            f"Raspi IP    : {RASPI_IP}\n"
            f"Video Port  : {VIDEO_PORT}\n"
            f"Result Port : {RESULT_PORT}\n"
            f"Model       : {MODEL_PATH}\n"
            f"Running     : {'Ya' if self._inferring else 'Tidak'}\n"
            f"Diterima    : {self._counter_ok}\n"
            f"Ditolak     : {self._counter_fail}"
        )
        QMessageBox.information(self, "Info Sistem", info)

    @pyqtSlot()
    def _on_open_settings(self):
        dlg = SettingsDialog(self, parent=self)
        dlg.exec()

    @pyqtSlot()
    def _on_show(self):
        info = (
            f"Raspi IP    : {RASPI_IP}\n"
            f"Video Port  : {VIDEO_PORT}\n"
            f"Result Port : {RESULT_PORT}\n"
            f"Model       : {MODEL_PATH}\n"
            f"Running     : {'Ya' if self._inferring else 'Tidak'}\n"
            f"Diterima    : {self._counter_ok}\n"
            f"Ditolak     : {self._counter_fail}"
        )
        QMessageBox.information(self, "Info Sistem", info)

    @pyqtSlot()
    def _on_toggle_running(self):
        if not self._inferring:
            # Mulai inferensi
            if self._engine is None:
                self._log("[YOLO] Memuat model, harap tunggu...")
                if not self._load_yolo():
                    return
            self._inferring      = True
            self._window_active  = False
            self._in_idle        = False
            self._accum_classes  = []
            self.btn_running.setText("■  Stop")
            self.btn_running.setObjectName("btn_running_active")
            self.btn_running.setStyleSheet("")
            self._log(f"[YOLO] Inferensi dimulai — window: {self._detection_window:.0f}s, idle: {self._idle_duration:.0f}s")
        else:
            # Stop inferensi
            self._inferring = False
            self.btn_running.setText("▶  Running")
            self.btn_running.setObjectName("btn_running")
            self.btn_running.setStyleSheet("")
            self._log("[YOLO] Inferensi dihentikan.")

    @pyqtSlot()
    def _on_capture(self):
        if self._last_annotated is None:
            self._log("[CAPTURE] Belum ada frame untuk disimpan.", error=True)
            return
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Screenshot",
            f"eggapp_capture_{ts}.jpg",
            "JPEG (*.jpg);;PNG (*.png)"
        )
        if path:
            cv2.imwrite(path, self._last_annotated)
            self._log(f"[CAPTURE] Tersimpan: {path}")

    # ── Slot Signal Internal ──────────────────────────────────
    @pyqtSlot(object)
    def _on_frame_received(self, frame: np.ndarray):
        """Frame diterima dari Raspi — update thumbnail RGB, push ke YOLO."""
        self._last_raw_frame = frame
        _render_to_label(frame, self.lbl_thumb_rgb)

        # Jika tidak inferring, tampilkan frame mentah di video utama
        if not self._inferring:
            _render_to_label(frame, self.lbl_main)

        # Hitung FPS penerimaan
        now = time.time()
        self._fps_times.append(now)
        self._fps_times = [t for t in self._fps_times if now - t < 1.0]
        self.lbl_fps.setText(f"FPS: {len(self._fps_times)}")

        # Push ke YOLO jika aktif
        if self._inferring and self._yolo_thread:
            self._yolo_thread.push_frame(frame)

    @pyqtSlot(str)
    def _on_recv_status(self, status: str):
        self._log(f"[KONEKSI] Raspi: {status}")

    @pyqtSlot(object, object, object, dict)
    def _on_inference_done(self,
                           annotated:    np.ndarray,
                           false_color:  np.ndarray,
                           mask:         np.ndarray,
                           result:       dict):
        """
        Dipanggil tiap kali YOLO selesai inferensi satu frame.
        Update semua panel GUI dan kirim JSON ke Raspi.
        """
        # ── Video utama ───────────────────────────────────────
        self._last_annotated = annotated
        _render_to_label(annotated, self.lbl_main)

        # ── Thumbnail kanan ───────────────────────────────────
        self._last_false = false_color
        self._last_mask  = mask
        _render_to_label(false_color, self.lbl_thumb_depth)
        _render_to_label(mask,        self.lbl_thumb_mask)

        # ── Info bar ─────────────────────────────────────────
        status = result.get("status", "NO_OBJECT")
        conf   = result.get("confidence", 0.0)
        cx     = result.get("center_x")
        cy     = result.get("center_y")

        self.lbl_conf.setText(f"Confidence: {conf:.2f}")
        if cx is not None:
            self.lbl_coord.setText(f"Center Coordinate\nx: {cx},  y: {cy}")
        else:
            self.lbl_coord.setText("Center Coordinate\nx: —,  y: —")

        # Status label
        if status == "DITERIMA":
            self.lbl_status.setText("● DITERIMA")
            self.lbl_status.setObjectName("lbl_status_ok")
            self._counter_ok += 1
        elif status == "DITOLAK":
            self.lbl_status.setText("● DITOLAK")
            self.lbl_status.setObjectName("lbl_status_fail")
            self._counter_fail += 1
        else:
            self.lbl_status.setText("● NO OBJECT")
            self.lbl_status.setObjectName("lbl_status_none")
        self.lbl_status.setStyleSheet("")

        self.lbl_counter.setText(
            f"✅ Diterima: {self._counter_ok}   ❌ Ditolak: {self._counter_fail}"
        )

        # ── Log per frame ────────────────────────────────────
        cls_name = result.get("class", "-")
        self._log(
            f"[YOLO] {status} | kelas: {cls_name} | "
            f"conf: {conf:.2f} | cx: {cx} cy: {cy}"
        )

        # ── Akumulasi deteksi selama window 10 detik ─────────
        if not self._inferring:
            return

        now = time.time()

        # Jika sedang idle antar telur, tunggu dulu
        if self._in_idle:
            sisa = self._idle_duration - (now - self._idle_start)
            self.lbl_status.setText(f"● IDLE ({sisa:.1f}s)")
            self.lbl_status.setObjectName("lbl_status_none")
            self.lbl_status.setStyleSheet("")
            if now - self._idle_start >= self._idle_duration:
                self._in_idle = False
                self._start_window()
            return

        # Mulai window baru jika belum aktif
        if not self._window_active:
            self._start_window()

        # Akumulasi kelas yang terdeteksi (bukan NO_OBJECT)
        if cls_name not in ("-", None) and status != "NO_OBJECT":
            self._accum_classes.append(cls_name.lower())

        # Update countdown di status bar
        elapsed  = now - self._window_start
        sisa_win = max(0, self._detection_window - elapsed)
        detected = set(self._accum_classes)
        self.lbl_status.setText(
            f"● SCANNING ({sisa_win:.1f}s) | "
            f"{'crack ⚠️' if any('crack' in c for c in detected) else 'egg ✓'}"
        )
        self.lbl_status.setObjectName("lbl_status_none")
        self.lbl_status.setStyleSheet("")

        # Window selesai → ambil kesimpulan
        if elapsed >= self._detection_window:
            self._conclude()

    # ── Helper ────────────────────────────────────────────────
    def _start_window(self):
        """Mulai window pengamatan baru untuk satu telur."""
        self._accum_classes  = []
        self._window_start   = time.time()
        self._window_active  = True
        self._log(f"[SCAN] Window deteksi dimulai ({self._detection_window:.0f} detik)...")

    def _conclude(self):
        """
        Ambil kesimpulan dari akumulasi kelas selama window 10 detik.
        Aturan:
          - Ada kelas 'crack' (apapun) → DITOLAK
          - Hanya 'egg' / tidak ada deteksi → DITERIMA
        """
        self._window_active = False
        classes = self._accum_classes
        total   = len(classes)

        has_crack = any('crack' in c for c in classes)
        has_egg   = any(c == 'egg' for c in classes)

        if total == 0:
            # Tidak ada deteksi sama sekali — skip, mulai window baru
            self._log("[SCAN] Tidak ada objek terdeteksi — skip.")
            self._start_window()
            return

        count = Counter(classes)
        self._log(
            f"[SCAN] Selesai — total deteksi: {total} | "
            f"distribusi: {dict(count)}"
        )

        if has_crack:
            keputusan = "DITOLAK"
            self._counter_fail += 1
            self._log(f"[KEPUTUSAN] ❌ DITOLAK — ditemukan kelas crack")
        else:
            keputusan = "DITERIMA"
            self._counter_ok += 1
            self._log(f"[KEPUTUSAN] ✅ DITERIMA — tidak ada crack")

        # Update counter label
        self.lbl_counter.setText(
            f"✅ Diterima: {self._counter_ok}   ❌ Ditolak: {self._counter_fail}"
        )

        # Update status label
        if keputusan == "DITERIMA":
            self.lbl_status.setText("● DITERIMA")
            self.lbl_status.setObjectName("lbl_status_ok")
        else:
            self.lbl_status.setText("● DITOLAK")
            self.lbl_status.setObjectName("lbl_status_fail")
        self.lbl_status.setStyleSheet("")

        # Kirim JSON ke Raspi
        result_final = {
            "status":    keputusan,
            "class":     "crack" if has_crack else "egg",
            "confidence": 1.0,
            "timestamp": datetime.now().isoformat()
        }
        if self._sender_thread:
            self._sender_thread.push(result_final)

        # Mulai idle sebelum telur berikutnya
        self._in_idle    = True
        self._idle_start = time.time()
        self._log(f"[IDLE] Menunggu {self._idle_duration:.0f} detik untuk telur berikutnya...")

    def _log(self, msg: str, error: bool = False):
        now  = datetime.now().strftime("%H:%M:%S")
        line = f"[{now}] {msg}"
        if error:
            self.log_widget.append(
                f'<span style="color:#EF5350;">{line}</span>')
        else:
            self.log_widget.append(line)
        self.log_widget.verticalScrollBar().setValue(
            self.log_widget.verticalScrollBar().maximum())
        logger.info(msg)

    # ── Cleanup ───────────────────────────────────────────────
    def closeEvent(self, event):
        if self._yolo_thread:
            self._yolo_thread.stop()
            self._yolo_thread.wait(3000)
        if self._recv_thread:
            self._recv_thread.stop()
            self._recv_thread.wait(3000)
        if self._sender_thread:
            self._sender_thread.stop()
            self._sender_thread.wait(3000)
        logger.info("[APP] Aplikasi PC ditutup.")
        event.accept()


# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("EggApp PC")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
