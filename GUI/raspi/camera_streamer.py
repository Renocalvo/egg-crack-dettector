# raspi/camera_streamer.py
# -------------------------------------------------------------
# QThread ï¿½ Capture frame dari Pi Camera V2 (IMX219) via picamera2
# Raspberry Pi 5 (PiSP / RP1)
#
# Fix: AE + AWB keduanya auto dengan ExposureValue +1.0 EV
# agar sensor tidak underexpose ? DigitalGain tidak turun < 1.0
# -------------------------------------------------------------
import cv2
import time
import queue
import logging
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from picamera2 import Picamera2
from config import CAM_WIDTH, CAM_HEIGHT, CAM_FPS, JPEG_QUALITY

logger = logging.getLogger(__name__)


class CameraStreamer(QThread):
    frame_ready    = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._picam2  = None
        self.frame_q: queue.Queue = queue.Queue(maxsize=2)

    def run(self):
        try:
            self._picam2 = Picamera2()
            cfg = self._picam2.create_video_configuration(
                main={"size": (CAM_WIDTH, CAM_HEIGHT), "format": "RGB888"},
                controls={
                    "FrameRate":          CAM_FPS,
                    "NoiseReductionMode": 1,
                    "Sharpness":          1.0,
                    "Saturation":         1.0,
                    "Contrast":           1.0,
                    "Brightness":         0.0,
                    # -- AE + AWB auto ï¿½ keduanya harus aktif bersamaan --
                    # ExposureValue +1.0 EV ? paksa sensor expose lebih terang
                    # sehingga DigitalGain selalu >= 1.0 (fix bug PiSP)
                    "AeEnable":           True,
                    "AeExposureMode":     0,      # 0 = normal
                    "ExposureValue":      1.0,    # +1 EV, coba 0.0 jika terlalu terang
                    "AwbEnable":          True,
                    "AwbMode":            4,      # 4 = indoor/fluorescent
                }
            )
            self._picam2.configure(cfg)
            self._picam2.start()

            # Warmup 2 detik ï¿½ biarkan AE+AWB konvergen
            time.sleep(2.0)

            logger.info(
                f"[CAM] Kamera aktif ï¿½ "
                f"{CAM_WIDTH}x{CAM_HEIGHT}@{CAM_FPS}fps | "
                f"AE=auto EV=+1.0 AWB=indoor"
            )
        except Exception as e:
            msg = f"[CAM] Gagal inisialisasi: {e}"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return

        self._running = True
        while self._running:
            try:
                frame_rgb = self._picam2.capture_array("main")
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                ok, buf = cv2.imencode(
                    '.jpg', frame_bgr,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                if not ok:
                    continue

                jpeg_bytes = buf.tobytes()
                self.frame_ready.emit(jpeg_bytes)
                try:
                    self.frame_q.put_nowait(jpeg_bytes)
                except queue.Full:
                    pass

            except Exception as e:
                logger.warning(f"[CAM] Error capture: {e}")
                time.sleep(0.01)

    def stop(self):
        self._running = False
        if self._picam2:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                pass
        logger.info("[CAM] Kamera dimatikan.")
