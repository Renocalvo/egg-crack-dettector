# raspi/camera_streamer.py
# ─────────────────────────────────────────────────────────────
# QThread — Capture frame dari Pi Camera V2 via picamera2,
# encode JPEG, simpan ke queue untuk dikirim ke laptop.
# ─────────────────────────────────────────────────────────────
import cv2
import queue
import logging
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from picamera2 import Picamera2
from config import CAM_WIDTH, CAM_HEIGHT, CAM_FPS, JPEG_QUALITY

logger = logging.getLogger(__name__)


class CameraStreamer(QThread):
    """
    Thread kamera.
    Signal:
        frame_ready(bytes) — JPEG bytes frame terbaru
        error_occurred(str) — pesan error kamera
    """
    frame_ready    = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running  = False
        self._picam2   = None
        # Queue kecil agar frame sender tidak ketinggalan
        self.frame_q: queue.Queue = queue.Queue(maxsize=2)

    # ── Lifecycle ─────────────────────────────────────────────
    def run(self):
        try:
            self._picam2 = Picamera2()
            cfg = self._picam2.create_video_configuration(
                main={"size": (CAM_WIDTH, CAM_HEIGHT), "format": "RGB888"},
                controls={"FrameRate": CAM_FPS}
            )
            self._picam2.configure(cfg)
            self._picam2.start()
            logger.info(f"[CAM] Pi Camera V2 aktif — {CAM_WIDTH}x{CAM_HEIGHT}@{CAM_FPS}fps")
        except Exception as e:
            msg = f"[CAM] Gagal inisialisasi kamera: {e}"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return

        self._running = True
        while self._running:
            try:
                frame_rgb = self._picam2.capture_array()            # RGB888
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                ok, buf   = cv2.imencode(
                    '.jpg', frame_bgr,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                if not ok:
                    continue
                jpeg_bytes = buf.tobytes()
                self.frame_ready.emit(jpeg_bytes)   # sinyal ke GUI preview
                # Masukkan ke queue untuk StreamSenderThread
                try:
                    self.frame_q.put_nowait(jpeg_bytes)
                except queue.Full:
                    pass   # drop frame lama — normal saat inference lambat
            except Exception as e:
                logger.warning(f"[CAM] Error capture: {e}")

    def stop(self):
        self._running = False
        if self._picam2:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                pass
        logger.info("[CAM] Kamera dimatikan.")
