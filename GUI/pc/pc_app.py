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
from PyQt6.QtCore    import Qt, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui     import QPixmap, QImage, QFont, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QFrame,
    QSizePolicy, QFileDialog, QMessageBox
)

from config          import (RASPI_IP, VIDEO_PORT, RESULT_PORT,
                              MODEL_PATH, LOG_FILE, LOG_LEVEL)
from yolo_engine      import YoloEngine
from frame_receiver   import FrameReceiverThread
from result_sender    import ResultSenderThread

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
        self.btn_show    = QPushButton("Show")
        self.btn_running = QPushButton("▶  Running")
        self.btn_capture = QPushButton("📷 Capture Screen Shot")
        self.btn_running.setObjectName("btn_running")
        self.btn_capture.setObjectName("btn_capture")

        self.btn_show.clicked.connect(self._on_show)
        self.btn_running.clicked.connect(self._on_toggle_running)
        self.btn_capture.clicked.connect(self._on_capture)

        ctrl.addWidget(self.btn_show)
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
    def _on_toggle_running(self):
        if not self._inferring:
            # Mulai inferensi
            if self._engine is None:
                self._log("[YOLO] Memuat model, harap tunggu...")
                if not self._load_yolo():
                    return
            self._inferring = True
            self.btn_running.setText("■  Stop")
            self.btn_running.setObjectName("btn_running_active")
            self.btn_running.setStyleSheet("")
            self._log("[YOLO] Inferensi dimulai.")
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

        # ── Log ───────────────────────────────────────────────
        cls_name = result.get("class", "-")
        self._log(
            f"[YOLO] {status} | kelas: {cls_name} | "
            f"conf: {conf:.2f} | cx: {cx} cy: {cy}"
        )

        # ── Kirim JSON ke Raspi ───────────────────────────────
        if self._sender_thread:
            self._sender_thread.push(result)

    # ── Helper ────────────────────────────────────────────────
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
