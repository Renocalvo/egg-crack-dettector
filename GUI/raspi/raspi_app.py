#!/usr/bin/env python3
# raspi/raspi_app.py
# ─────────────────────────────────────────────────────────────
# EggApp — Node Raspberry Pi 5
# ─────────────────────────────────────────────────────────────
import sys
import cv2
import logging
import numpy as np
from datetime import datetime

from PyQt6.QtCore    import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui     import QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QSizePolicy, QMessageBox
)

import config as cfg
from config               import LOG_FILE, LOG_LEVEL
from camera_streamer      import CameraStreamer
from stream_sender        import StreamSenderThread
from result_receiver      import ResultReceiverThread
from servo_controller     import ServoController
from settings_dialog_raspi   import SettingsDialog
from camera_settings_dialog  import CameraSettingsDialog   # ← dialog kamera baru

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
logger = logging.getLogger('raspi_app')

# ── Stylesheet ────────────────────────────────────────────────
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
    font-size: 12px;
}
QPushButton:hover    { background-color: #3949AB; }
QPushButton:disabled { background-color: #37474F; color: #78909C; }
QPushButton#btn_stop     { background-color: #B71C1C; }
QPushButton#btn_stop:hover     { background-color: #E53935; }
QPushButton#btn_reset    { background-color: #37474F; }
QPushButton#btn_reset:hover    { background-color: #546E7A; }
QPushButton#btn_settings { background-color: #455A64; }
QPushButton#btn_settings:hover { background-color: #546E7A; }
QPushButton#btn_cam_settings { background-color: #00695C; }
QPushButton#btn_cam_settings:hover { background-color: #00897B; }
QTextEdit {
    background-color: #0D0D1A;
    color: #A5D6A7;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    border: 1px solid #2D2D44;
    border-radius: 4px;
}
QLabel#lbl_title { font-size: 16px; font-weight: bold; color: #7986CB; padding: 4px 0; }
QLabel#lbl_connected    { color: #69F0AE; font-weight: bold; }
QLabel#lbl_disconnected { color: #EF5350; font-weight: bold; }
QLabel#lbl_servo_idle   { color: #FFD54F; font-weight: bold; }
QLabel#lbl_servo_terima { color: #69F0AE; font-weight: bold; }
QLabel#lbl_servo_tolak  { color: #EF5350; font-weight: bold; }
"""


# ═══════════════════════════════════════════════════════════════
# ServoWorker
# ═══════════════════════════════════════════════════════════════
class ServoWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, servo: ServoController, action: str, parent=None):
        super().__init__(parent)
        self.servo  = servo
        self.action = action

    def run(self):
        if self.action == "DITERIMA":
            self.servo.terima()
        elif self.action == "DITOLAK":
            self.servo.tolak()
        else:
            self.servo.idle()
        self.done.emit(self.action)


# ═══════════════════════════════════════════════════════════════
# MainWindow
# ═══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EggApp — Raspberry Pi Controller")
        self.setMinimumSize(560, 700)

        self._streaming       = False
        self._servo: ServoController | None   = None
        self._servo_worker: ServoWorker | None = None
        self._cam_thread: CameraStreamer | None       = None
        self._sender_thread: StreamSenderThread | None  = None
        self._receiver_thread: ResultReceiverThread | None = None
        self._counter_ok   = 0
        self._counter_fail = 0
        self._last_frame   = None

        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._init_servo()

    # ── UI ────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # Title
        lbl_title = QLabel("🥚 EggApp — Raspberry Pi Controller")
        lbl_title.setObjectName("lbl_title")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(lbl_title)

        # ── Kontrol Stream ────────────────────────────────────
        grp_ctrl = QGroupBox("Kontrol Stream")
        ctrl_lay = QHBoxLayout(grp_ctrl)

        self.btn_start = QPushButton("▶  Start Stream")
        self.btn_stop  = QPushButton("■  Stop Stream")
        self.btn_reset = QPushButton("↺  Reset Servo")

        self.btn_stop.setObjectName("btn_stop")
        self.btn_reset.setObjectName("btn_reset")
        self.btn_stop.setEnabled(False)

        ctrl_lay.addWidget(self.btn_start)
        ctrl_lay.addWidget(self.btn_stop)
        ctrl_lay.addWidget(self.btn_reset)

        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_reset.clicked.connect(self._on_reset_servo)
        root.addWidget(grp_ctrl)

        # ── Pengaturan (Settings) ─────────────────────────────
        grp_settings = QGroupBox("Pengaturan")
        settings_lay = QHBoxLayout(grp_settings)

        self.btn_settings     = QPushButton("⚙️  Umum")
        self.btn_cam_settings = QPushButton("📷  Kamera")

        self.btn_settings.setObjectName("btn_settings")
        self.btn_cam_settings.setObjectName("btn_cam_settings")

        # Deskripsi singkat di sebelah tombol
        lbl_settings_hint = QLabel("Jaringan, servo, resolusi")
        lbl_settings_hint.setStyleSheet("color:#78909C; font-size:10px;")
        lbl_cam_hint = QLabel("Contrast, EV, AWB, Noise…")
        lbl_cam_hint.setStyleSheet("color:#78909C; font-size:10px;")

        col_gen = QVBoxLayout()
        col_gen.setSpacing(2)
        col_gen.addWidget(self.btn_settings)
        col_gen.addWidget(lbl_settings_hint)

        col_cam = QVBoxLayout()
        col_cam.setSpacing(2)
        col_cam.addWidget(self.btn_cam_settings)
        col_cam.addWidget(lbl_cam_hint)

        settings_lay.addLayout(col_gen)
        settings_lay.addLayout(col_cam)
        settings_lay.addStretch()

        self.btn_settings.clicked.connect(self._on_open_settings)
        self.btn_cam_settings.clicked.connect(self._on_open_cam_settings)
        root.addWidget(grp_settings)

        # ── Status ────────────────────────────────────────────
        grp_status = QGroupBox("Status")
        st_lay = QVBoxLayout(grp_status)

        row_conn = QHBoxLayout()
        row_conn.addWidget(QLabel("Koneksi Laptop:"))
        self.lbl_conn = QLabel("● BELUM TERHUBUNG")
        self.lbl_conn.setObjectName("lbl_disconnected")
        row_conn.addWidget(self.lbl_conn)
        row_conn.addStretch()
        st_lay.addLayout(row_conn)

        row_servo = QHBoxLayout()
        row_servo.addWidget(QLabel("Status Servo:"))
        self.lbl_servo = QLabel("● IDLE")
        self.lbl_servo.setObjectName("lbl_servo_idle")
        row_servo.addWidget(self.lbl_servo)
        row_servo.addStretch()
        st_lay.addLayout(row_servo)

        self.lbl_count = QLabel("✅ Diterima: 0     ❌ Ditolak: 0")
        self.lbl_count.setStyleSheet("font-size: 13px; font-weight: bold;")
        st_lay.addWidget(self.lbl_count)
        root.addWidget(grp_status)

        # ── Preview kamera ────────────────────────────────────
        grp_cam = QGroupBox("Preview Kamera (Pi Camera V2)")
        cam_lay = QVBoxLayout(grp_cam)
        cam_lay.setContentsMargins(4, 4, 4, 4)
        self.lbl_preview = QLabel("[ Kamera belum aktif ]")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setMinimumHeight(160)
        self.lbl_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lbl_preview.setStyleSheet(
            "background:#0D0D1A; border:1px solid #2D2D44; "
            "border-radius:4px; color:#546E7A;")
        cam_lay.addWidget(self.lbl_preview)
        grp_cam.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(grp_cam, stretch=1)

        # ── Log ───────────────────────────────────────────────
        grp_log = QGroupBox("Log Aktivitas")
        log_lay = QVBoxLayout(grp_log)
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setFixedHeight(160)
        log_lay.addWidget(self.log_widget)
        root.addWidget(grp_log)

    # ── Settings ──────────────────────────────────────────────
    @pyqtSlot()
    def _on_open_settings(self):
        dlg = SettingsDialog(main_win=self, parent=self)
        dlg.exec()

    @pyqtSlot()
    def _on_open_cam_settings(self):
        dlg = CameraSettingsDialog(main_win=self, parent=self)
        dlg.exec()

    # ── Servo init ────────────────────────────────────────────
    def _init_servo(self):
        try:
            self._servo = ServoController(pin=cfg.SERVO_PIN)
            self._log(f"[SERVO] Inisialisasi OK — GPIO {cfg.SERVO_PIN}")
        except RuntimeError as e:
            self._log(f"[ERROR] {e}", error=True)
            QMessageBox.critical(self, "Error Servo",
                str(e) + "\n\nPastikan lgpio terinstall dan pin benar.")

    # ── Slot tombol ───────────────────────────────────────────
    @pyqtSlot()
    def _on_start(self):
        if self._streaming:
            return
        self._cam_thread = CameraStreamer()
        self._cam_thread.frame_ready.connect(self._on_frame)
        self._cam_thread.error_occurred.connect(
            lambda msg: self._log(msg, error=True))

        self._sender_thread = StreamSenderThread(self._cam_thread.frame_q)
        self._sender_thread.status_changed.connect(self._on_conn_status)

        self._receiver_thread = ResultReceiverThread()
        self._receiver_thread.result_received.connect(self._on_result)
        self._receiver_thread.error_occurred.connect(
            lambda msg: self._log(msg, error=True))

        self._cam_thread.start()
        self._sender_thread.start()
        self._receiver_thread.start()

        self._streaming = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._log("[STREAM] Stream dimulai...")

    @pyqtSlot()
    def _on_stop(self):
        self._streaming = False
        for t in [self._cam_thread, self._sender_thread, self._receiver_thread]:
            if t:
                t.stop()
                t.wait(3000)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._on_conn_status("DISCONNECTED")
        self._log("[STREAM] Stream dihentikan.")

    @pyqtSlot()
    def _on_reset_servo(self):
        if self._servo:
            self._run_servo("RESET")
            self._log("[SERVO] Reset ke posisi IDLE.")

    # ── Frame preview ─────────────────────────────────────────
    def _display_frame(self, frame_bgr: np.ndarray):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data.tobytes(), w, h, ch * w,
                      QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.lbl_preview.width(), self.lbl_preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self.lbl_preview.setPixmap(pix)

    @pyqtSlot(bytes)
    def _on_frame(self, jpeg_bytes: bytes):
        arr   = np.frombuffer(jpeg_bytes, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return
        self._last_frame = frame
        self._display_frame(frame)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._last_frame is not None:
            self._display_frame(self._last_frame)

    # ── Signal slots ──────────────────────────────────────────
    @pyqtSlot(str)
    def _on_conn_status(self, status: str):
        if status == "CONNECTED":
            self.lbl_conn.setText("● TERHUBUNG")
            self.lbl_conn.setObjectName("lbl_connected")
        else:
            self.lbl_conn.setText("● TIDAK TERHUBUNG")
            self.lbl_conn.setObjectName("lbl_disconnected")
        self.lbl_conn.setStyleSheet("")
        self._log(f"[KONEKSI] {status}")

    @pyqtSlot(dict)
    def _on_result(self, result: dict):
        status    = result.get("status", "NO_OBJECT")
        cls_name  = result.get("class", "-")
        conf      = result.get("confidence", 0.0)
        timestamp = result.get("timestamp", "")
        self._log(
            f"[HASIL] {status} | kelas: {cls_name} | "
            f"conf: {conf:.2f} | {timestamp}")
        if status == "DITERIMA":
            self._counter_ok += 1
            self._update_servo_label("DITERIMA")
            self._run_servo("DITERIMA")
        elif status == "DITOLAK":
            self._counter_fail += 1
            self._update_servo_label("DITOLAK")
            self._run_servo("DITOLAK")
        self.lbl_count.setText(
            f"✅ Diterima: {self._counter_ok}     ❌ Ditolak: {self._counter_fail}")

    # ── Helpers ───────────────────────────────────────────────
    def _run_servo(self, action: str):
        if self._servo_worker and self._servo_worker.isRunning():
            return
        if self._servo is None:
            return
        self._servo_worker = ServoWorker(self._servo, action)
        self._servo_worker.done.connect(lambda a: self._update_servo_label("IDLE"))
        self._servo_worker.start()

    def _update_servo_label(self, state: str):
        labels = {
            "IDLE":     ("● IDLE",     "lbl_servo_idle"),
            "DITERIMA": ("● DITERIMA", "lbl_servo_terima"),
            "DITOLAK":  ("● DITOLAK",  "lbl_servo_tolak"),
        }
        text, obj = labels.get(state, ("● IDLE", "lbl_servo_idle"))
        self.lbl_servo.setText(text)
        self.lbl_servo.setObjectName(obj)
        self.lbl_servo.setStyleSheet("")

    def _log(self, msg: str, error: bool = False):
        now  = datetime.now().strftime("%H:%M:%S")
        line = f"[{now}] {msg}"
        if error:
            self.log_widget.append(f'<span style="color:#EF5350;">{line}</span>')
        else:
            self.log_widget.append(line)
        self.log_widget.verticalScrollBar().setValue(
            self.log_widget.verticalScrollBar().maximum())
        logger.info(msg)

    # ── Cleanup ───────────────────────────────────────────────
    def closeEvent(self, event):
        self._on_stop()
        if self._servo:
            self._servo.cleanup()
        logger.info("[APP] Aplikasi Raspi ditutup.")
        event.accept()


# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("EggApp Raspi")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
