#!/usr/bin/env python3
# pc/pc_app.py
# ─────────────────────────────────────────────────────────────
# EggApp — Node Laptop
# ─────────────────────────────────────────────────────────────
import sys
import cv2
import queue
import logging
import numpy as np
import time
from datetime import datetime
from collections import Counter, deque

from PyQt6.QtCore    import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui     import QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox,
    QSizePolicy, QFileDialog, QMessageBox
)

from pathlib import Path
import config as cfg
from config         import LOG_FILE, LOG_LEVEL
from yolo_engine    import YoloEngine
from frame_receiver import FrameReceiverThread
from result_sender  import ResultSenderThread
from settings_dialog_pc import SettingsDialog

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
}
QPushButton:hover    { background-color: #3949AB; }
QPushButton:disabled { background-color: #37474F; color: #78909C; }
QPushButton#btn_running        { background-color: #1B5E20; min-width: 110px; }
QPushButton#btn_running:hover  { background-color: #2E7D32; }
QPushButton#btn_running_active { background-color: #B71C1C; min-width: 110px; }
QPushButton#btn_running_active:hover { background-color: #E53935; }
QPushButton#btn_capture { background-color: #4A148C; }
QPushButton#btn_capture:hover { background-color: #6A1B9A; }
QPushButton#btn_settings { background-color: #455A64; }
QPushButton#btn_settings:hover { background-color: #546E7A; }
QLabel#lbl_title   { font-size: 15px; font-weight: bold; color: #7986CB; }
QLabel#lbl_counter { font-size: 13px; font-weight: bold; color: #E0E0E0; }
QLabel#lbl_status_ok   { color: #69F0AE; font-weight: bold; font-size: 14px; }
QLabel#lbl_status_fail { color: #EF5350; font-weight: bold; font-size: 14px; }
QLabel#lbl_status_none { color: #FFD54F; font-weight: bold; font-size: 14px; }
QLabel#lbl_coord { color: #90CAF9; font-size: 12px; }
QTextEdit {
    background-color: #0D0D1A;
    color: #A5D6A7;
    font-family: 'Courier New', monospace;
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
    inference_done = pyqtSignal(object, object, object, dict)

    def __init__(self, engine: YoloEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self._running = False

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
            annotated, result      = self.engine.infer(frame)
            false_color, mask      = self.engine.generate_panels(frame)
            self.inference_done.emit(annotated, false_color, mask, result)

    def stop(self):
        self._running = False


# ── Render helper ─────────────────────────────────────────────
def _render_to_label(frame_bgr: np.ndarray, label: QLabel):
    if frame_bgr is None or label.width() < 2 or label.height() < 2:
        return
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
    pix  = QPixmap.fromImage(qimg).scaled(
        label.width(), label.height(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )
    label.setPixmap(pix)


# ═══════════════════════════════════════════════════════════════
# DetectionWindow — logika akumulasi per telur
# ═══════════════════════════════════════════════════════════════
class DetectionWindow:
    """
    Akumulasi hasil inferensi selama N detik untuk satu telur.

    Aturan keputusan:
        early_reject : jika kelas 'crack' muncul >= early_crack_count
                       kali DALAM crack_window_frames frame terakhir
                       (rolling count, tidak harus berurutan mutlak)
                       → langsung DITOLAK tanpa menunggu window selesai
        normal       : setelah window_sec detik, jika ada kelas 'crack'
                       → DITOLAK, else → DITERIMA

    Catatan perbaikan:
    Sebelumnya early-reject memakai "streak" berturut-turut yang
    di-reset ke 0 setiap kali ada satu frame non-crack/None di
    tengah-tengah (mis. deteksi sempat miss 1 frame karena motion
    blur / confidence turun sesaat). Akibatnya crack yang sebenarnya
    sudah terdeteksi berkali-kali dalam beberapa menit tidak pernah
    memicu DITOLAK karena counter selalu balik ke 0.
    Sekarang dipakai rolling window (deque) sepanjang
    `crack_window_frames` frame terakhir — early reject dipicu kalau
    jumlah frame crack di dalam jendela itu sudah mencapai
    `early_crack_count`, walau ada beberapa frame non-crack di
    antaranya.
    """
    def __init__(self, window_sec: float = 10.0,
                 early_crack_count: int = 5,
                 crack_window_frames: int | None = None):
        self.window_sec        = window_sec
        self.early_crack_count = early_crack_count
        # Jendela rolling untuk early-reject. Default: 2x early_crack_count
        # supaya ada toleransi terhadap frame yang miss/meleset.
        self.crack_window_frames = crack_window_frames or max(early_crack_count * 2, early_crack_count)
        self._reset()

    def _reset(self):
        self._classes:      list  = []   # semua kelas terdeteksi (untuk keputusan akhir window)
        self._recent_crack: deque = deque(maxlen=self.crack_window_frames)  # rolling crack flags
        self._start:        float = 0.0
        self._active:       bool  = False

    def start(self):
        self._reset()
        self._start  = time.time()
        self._active = True

    def feed(self, classes) -> str | None:
        """
        Masukkan hasil inferensi SATU FRAME.

        Args:
            classes: bisa berupa list semua kelas yang terdeteksi dalam
                     frame ini (mis. ["egg", "crack"] kalau egg dan crack
                     terdeteksi bersamaan di frame yang sama), ATAU
                     string tunggal / None untuk kompatibilitas lama.

        Returns:
            None           — window belum selesai
            "DITERIMA"     — keputusan final
            "DITOLAK"      — keputusan final (normal atau early reject)
        """
        if not self._active:
            return None

        # Normalisasi input jadi list, supaya egg & crack yang muncul
        # BERSAMAAN di satu frame dua-duanya kehitung, bukan cuma
        # salah satu yang "menang" berdasar confidence tertinggi.
        if classes is None:
            class_list = []
        elif isinstance(classes, str):
            class_list = [classes] if classes not in ("-",) else []
        else:
            class_list = [c for c in classes if c and c not in ("-",)]

        is_crack = any('crack' in c.lower() for c in class_list)

        # Akumulasi kelas (untuk keputusan window normal)
        for c in class_list:
            self._classes.append(c.lower())

        # Rolling crack tracker — HANYA untuk INFORMASI/TAMPILAN (mis.
        # indikator "crack:3/5" di status bar), TIDAK memicu keputusan
        # lebih awal. early_crack_count sengaja tidak lagi dipakai untuk
        # mengambil keputusan, karena:
        #   - Telur berputar/masuk sesuai siklus window_sec. Kalau
        #     keputusan diambil lebih cepat dari window_sec, servo bisa
        #     aktif SEBELUM telur benar-benar berada di posisi yang
        #     tepat, sehingga telur tidak pas ke jalur DITOLAK.
        #   - Dalam window_sec, satu telur bisa "membaca" crack lebih
        #     dari sekali (mis. permukaan crack sempat tidak menghadap
        #     kamera lalu menghadap lagi karena telur bergerak/berputar).
        #     Ini tetap valid sebagai sinyal crack, tapi bukan alasan
        #     untuk memutuskan lebih awal — cukup dicatat.
        # Keputusan akhir SELALU menunggu window_sec penuh, berdasarkan
        # apakah crack pernah tercatat kapan pun selama window berjalan
        # (lihat has_crack di bawah).
        self._recent_crack.append(is_crack)

        # Cek apakah window sudah habis — satu-satunya titik keputusan.
        elapsed = time.time() - self._start
        if elapsed >= self.window_sec:
            self._active = False
            if len(self._classes) == 0:
                return None   # tidak ada deteksi sama sekali
            has_crack = any('crack' in c for c in self._classes)
            return "DITOLAK" if has_crack else "DITERIMA"

        return None   # masih scanning

    def update_params(self, window_sec: float | None = None,
                       early_crack_count: int | None = None,
                       crack_window_frames: int | None = None):
        """
        Update parameter secara live tanpa mereset progres window
        yang sedang berjalan. Dipanggil dari Settings dialog saat
        tombol Apply ditekan, supaya perubahan langsung berlaku
        walau window saat ini belum selesai.
        """
        if window_sec is not None:
            self.window_sec = window_sec
        if early_crack_count is not None:
            self.early_crack_count = early_crack_count
        if crack_window_frames is not None:
            new_maxlen = crack_window_frames
        elif early_crack_count is not None:
            new_maxlen = max(self.early_crack_count * 2, self.early_crack_count)
        else:
            new_maxlen = self.crack_window_frames

        if new_maxlen != self.crack_window_frames:
            self.crack_window_frames = new_maxlen
            # Pertahankan riwayat crack flag yang masih relevan, cuma
            # ganti kapasitas deque-nya (tidak menghapus progres).
            self._recent_crack = deque(self._recent_crack, maxlen=new_maxlen)

    @property
    def active(self) -> bool:
        return self._active

    @property
    def elapsed(self) -> float:
        return time.time() - self._start if self._active else 0.0

    @property
    def classes(self) -> list:
        return list(self._classes)

    @property
    def crack_streak(self) -> int:
        """Jumlah crack dalam rolling window saat ini (dipakai untuk display UI)."""
        return sum(self._recent_crack)

    @property
    def has_crack(self) -> bool:
        return any('crack' in c for c in self._classes)


# ═══════════════════════════════════════════════════════════════
# MainWindow
# ═══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EggApp — PC Inspector")
        self.setMinimumSize(900, 680)

        # ── Parameter deteksi (bisa diubah dari Settings) ────
        self.detection_window_sec  = 10.0   # detik per telur
        self.idle_sec              = 2.0    # detik idle antar telur
        self.early_crack_count     = 5      # jumlah crack dalam rolling window → early reject

        # ── State ────────────────────────────────────────────
        self._inferring      = False
        self._last_annotated = None
        self._last_raw_frame = None
        self._last_false     = None
        self._last_mask      = None
        self._counter_ok     = 0
        self._counter_fail   = 0
        self._fps_times: list = []

        # Detection window state
        self._det_win    = DetectionWindow(
            self.detection_window_sec, self.early_crack_count)
        self._in_idle    = False
        self._idle_start = 0.0

        # ── Threads ──────────────────────────────────────────
        self._engine: YoloEngine | None               = None
        self._recv_thread: FrameReceiverThread | None = None
        self._yolo_thread: YoloInferenceThread | None = None
        self._sender_thread: ResultSenderThread | None = None

        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._start_receiver()

    # ── UI ────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)
        root.setContentsMargins(10, 10, 10, 10)

        # Title + counter
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

        # Video + thumbnail
        mid = QHBoxLayout()
        mid.setSpacing(8)

        self.lbl_main = QLabel("[ Menunggu stream dari Raspi... ]")
        self.lbl_main.setObjectName("thumb_label")
        self.lbl_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_main.setMinimumSize(620, 460)
        self.lbl_main.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        mid.addWidget(self.lbl_main, stretch=3)

        right = QVBoxLayout()
        right.setSpacing(6)
        self.lbl_thumb_rgb   = self._make_thumb("RGB Feed")
        self.lbl_thumb_depth = self._make_thumb("False Color")
        self.lbl_thumb_mask  = self._make_thumb("Edge / Mask")
        right.addWidget(self._wrap_thumb(self.lbl_thumb_rgb,   "RGB Feed"))
        right.addWidget(self._wrap_thumb(self.lbl_thumb_depth, "False Color"))
        right.addWidget(self._wrap_thumb(self.lbl_thumb_mask,  "Edge / Mask"))
        mid.addLayout(right, stretch=1)
        root.addLayout(mid)

        # Tombol
        ctrl = QHBoxLayout()
        self.btn_settings = QPushButton("⚙️  Settings")
        self.btn_running  = QPushButton("▶  Running")
        self.btn_capture  = QPushButton("📷 Capture")
        self.btn_settings.setObjectName("btn_settings")
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

        # Info bar
        info = QHBoxLayout()
        self.lbl_coord  = QLabel("Center\nx: —  y: —")
        self.lbl_coord.setObjectName("lbl_coord")
        self.lbl_fps    = QLabel("FPS: —")
        self.lbl_fps.setStyleSheet("color:#90CAF9;")
        self.lbl_conf   = QLabel("Conf: —")
        self.lbl_conf.setStyleSheet("color:#90CAF9;")
        self.lbl_status = QLabel("● MENUNGGU")
        self.lbl_status.setObjectName("lbl_status_none")
        info.addWidget(self.lbl_coord)
        info.addStretch()
        info.addWidget(self.lbl_fps)
        info.addWidget(QLabel("  |  "))
        info.addWidget(self.lbl_conf)
        info.addWidget(QLabel("  |  "))
        info.addWidget(self.lbl_status)
        root.addLayout(info)

        # Log
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
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lbl.setStyleSheet(
            "background:#0D0D1A; border:1px solid #2D2D44; "
            "border-radius:4px; color:#546E7A; font-size:10px;")
        return lbl

    def _wrap_thumb(self, lbl: QLabel, title: str) -> QGroupBox:
        gb = QGroupBox(title)
        gb.setStyleSheet("QGroupBox { font-size: 10px; }")
        gb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(gb)
        lay.setContentsMargins(2, 12, 2, 2)
        lay.addWidget(lbl)
        return gb

    # ── Threads ───────────────────────────────────────────────
    def _start_receiver(self):
        self._recv_thread = FrameReceiverThread()
        self._recv_thread.frame_ready.connect(self._on_frame_received)
        self._recv_thread.status_changed.connect(
            lambda s: self._log(f"[KONEKSI] Raspi: {s}"))
        self._recv_thread.start()

        self._sender_thread = ResultSenderThread()
        self._sender_thread.start()
        self._log("[RECV] Menunggu koneksi Raspi...")

    def _load_yolo(self) -> bool:
        try:
            self._engine      = YoloEngine()
            self._yolo_thread = YoloInferenceThread(self._engine)
            self._yolo_thread.inference_done.connect(self._on_inference_done)
            self._yolo_thread.start()
            self._log(f"[YOLO] Model siap. Kelas: {list(self._engine.model.names.values())}")
            return True
        except Exception as e:
            self._log(f"[ERROR] Gagal load model: {e}", error=True)
            QMessageBox.critical(self, "Error Model", str(e))
            return False

    # ── Slots tombol ──────────────────────────────────────────
    @pyqtSlot()
    def _on_open_settings(self):
        dlg = SettingsDialog(main_win=self, parent=self)
        dlg.exec()

    @pyqtSlot()
    def _on_toggle_running(self):
        if not self._inferring:
            if self._engine is None:
                self._log("[YOLO] Memuat model...")
                if not self._load_yolo():
                    return
            self._inferring = True
            self._reset_window_state()
            self.btn_running.setText("■  Stop")
            self.btn_running.setObjectName("btn_running_active")
            self.btn_running.setStyleSheet("")
            self._log(
                f"[YOLO] Mulai — window:{self.detection_window_sec:.0f}s  "
                f"idle:{self.idle_sec:.0f}s  "
                f"early_crack:{self.early_crack_count}x")
        else:
            self._inferring = False
            self.btn_running.setText("▶  Running")
            self.btn_running.setObjectName("btn_running")
            self.btn_running.setStyleSheet("")
            self._log("[YOLO] Inferensi dihentikan.")

    @pyqtSlot()
    def _on_capture(self):
        if self._last_annotated is None:
            self._log("[CAPTURE] Belum ada frame.", error=True)
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Screenshot",
            f"eggapp_{ts}.jpg", "JPEG (*.jpg);;PNG (*.png)")
        if path:
            cv2.imwrite(path, self._last_annotated)
            self._log(f"[CAPTURE] Tersimpan: {path}")

    # ── Frame received ────────────────────────────────────────
    @pyqtSlot(object)
    def _on_frame_received(self, frame: np.ndarray):
        self._last_raw_frame = frame
        _render_to_label(frame, self.lbl_thumb_rgb)
        if not self._inferring:
            _render_to_label(frame, self.lbl_main)
        now = time.time()
        self._fps_times.append(now)
        self._fps_times = [t for t in self._fps_times if now - t < 1.0]
        self.lbl_fps.setText(f"FPS: {len(self._fps_times)}")
        if self._inferring and self._yolo_thread:
            self._yolo_thread.push_frame(frame)

    # ── Inference done ────────────────────────────────────────
    @pyqtSlot(object, object, object, dict)
    def _on_inference_done(self,
                           annotated:   np.ndarray,
                           false_color: np.ndarray,
                           mask:        np.ndarray,
                           result:      dict):
        # Update visual panels
        self._last_annotated = annotated
        self._last_false     = false_color
        self._last_mask      = mask
        _render_to_label(annotated,   self.lbl_main)
        _render_to_label(false_color, self.lbl_thumb_depth)
        _render_to_label(mask,        self.lbl_thumb_mask)

        # Update info bar (per frame — hanya tampilan, bukan keputusan)
        conf     = result.get("confidence", 0.0)
        cx       = result.get("center_x")
        cy       = result.get("center_y")
        cls_name = result.get("class")
        # Semua kelas yang terdeteksi di frame ini (egg & crack bisa
        # muncul bersamaan). Fallback ke class tunggal kalau yolo_engine
        # versi lama yang belum mengirim "classes".
        cls_list = result.get("classes")
        if cls_list is None:
            cls_list = [cls_name] if cls_name else []

        self.lbl_conf.setText(f"Conf: {conf:.2f}")
        self.lbl_coord.setText(
            f"Center\nx: {cx}  y: {cy}" if cx is not None else "Center\nx: —  y: —")

        if not self._inferring:
            return

        now = time.time()

        # ── State machine ─────────────────────────────────────

        # 1. Sedang IDLE antar telur
        if self._in_idle:
            sisa = self.idle_sec - (now - self._idle_start)
            self._set_status(f"● IDLE ({sisa:.1f}s)", "lbl_status_none")
            if sisa <= 0:
                self._in_idle = False
                self._start_detection_window()
            return

        # 2. Window belum aktif → mulai
        if not self._det_win.active:
            self._start_detection_window()

        # 3. Feed ke DetectionWindow (kirim SEMUA class di frame ini,
        #    bukan cuma satu class dengan confidence tertinggi — supaya
        #    egg & crack yang muncul bersamaan dua-duanya tercatat)
        keputusan = self._det_win.feed(cls_list)

        # 4. Update status scanning
        sisa_win = max(0, self.detection_window_sec - self._det_win.elapsed)
        crack_ind = "⚠️ crack" if self._det_win.has_crack else "✓ egg"
        streak    = self._det_win.crack_streak
        streak_str = f" crack:{streak}/{self.early_crack_count}" if streak > 0 else ""
        self._set_status(
            f"● SCAN ({sisa_win:.1f}s) {crack_ind}{streak_str}",
            "lbl_status_none")

        # Log per frame (singkat)
        logger.debug(
            f"[FRAME] classes:{cls_list} conf:{conf:.2f} "
            f"rolling_crack:{streak} sisa:{sisa_win:.1f}s")

        # 5. Keputusan final
        if keputusan is not None:
            self._on_decision(keputusan)

    # ── Keputusan final ───────────────────────────────────────
    def _on_decision(self, keputusan: str):
        from collections import Counter as C
        classes = self._det_win.classes
        dist    = dict(C(classes))
        early   = self._det_win.crack_streak >= self.early_crack_count

        if keputusan == "DITERIMA":
            self._counter_ok += 1
            self._set_status("● DITERIMA", "lbl_status_ok")
            tag = "✅ DITERIMA"
        else:
            self._counter_fail += 1
            self._set_status("● DITOLAK", "lbl_status_fail")
            tag = f"❌ DITOLAK {'(EARLY REJECT)' if early else ''}"

        self._log(
            f"[KEPUTUSAN] {tag} | "
            f"distribusi: {dist} | total: {len(classes)} frame")

        self.lbl_counter.setText(
            f"✅ Diterima: {self._counter_ok}   ❌ Ditolak: {self._counter_fail}")

        # Kirim JSON ke Raspi
        result_final = {
            "status":     keputusan,
            "class":      "crack" if keputusan == "DITOLAK" else "egg",
            "confidence": 1.0,
            "timestamp":  datetime.now().isoformat()
        }
        if self._sender_thread:
            self._sender_thread.push(result_final)

        # Masuk idle
        self._in_idle    = True
        self._idle_start = time.time()
        self._log(f"[IDLE] {self.idle_sec:.0f}s sebelum telur berikutnya...")

    # ── Helpers ───────────────────────────────────────────────
    def _start_detection_window(self):
        self._det_win = DetectionWindow(
            self.detection_window_sec, self.early_crack_count)
        self._det_win.start()
        self._log(
            f"[SCAN] Window baru — {self.detection_window_sec:.0f}s  "
            f"early_crack:{self.early_crack_count}x")

    def _reset_window_state(self):
        self._in_idle    = False
        self._idle_start = 0.0
        self._det_win    = DetectionWindow(
            self.detection_window_sec, self.early_crack_count)

    def apply_detection_settings(self, window_sec: float,
                                  idle_sec: float,
                                  early_crack_count: int):
        """
        Dipanggil dari SettingsDialog saat tombol Apply ditekan.
        Mengupdate parameter runtime DAN window yang sedang aktif
        (kalau ada), supaya perubahan langsung berlaku tanpa perlu
        menunggu window/siklus telur saat ini selesai.
        """
        self.detection_window_sec = window_sec
        self.idle_sec             = idle_sec
        self.early_crack_count    = early_crack_count

        if self._det_win is not None:
            self._det_win.update_params(
                window_sec=window_sec,
                early_crack_count=early_crack_count)

    def _set_status(self, text: str, obj_name: str):
        self.lbl_status.setText(text)
        self.lbl_status.setObjectName(obj_name)
        self.lbl_status.setStyleSheet("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _render_to_label(self._last_annotated or self._last_raw_frame, self.lbl_main)
        _render_to_label(self._last_raw_frame,  self.lbl_thumb_rgb)
        _render_to_label(self._last_false,       self.lbl_thumb_depth)
        _render_to_label(self._last_mask,        self.lbl_thumb_mask)

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
        for t in [self._yolo_thread, self._recv_thread, self._sender_thread]:
            if t:
                t.stop()
                t.wait(3000)
        logger.info("[APP] Aplikasi PC ditutup.")
        event.accept()


# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("EggApp PC")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
