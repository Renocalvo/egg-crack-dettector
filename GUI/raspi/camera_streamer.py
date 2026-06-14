# raspi/camera_streamer.py
# ─────────────────────────────────────────────────────────────
# QThread — Capture frame dari Pi Camera V2 (IMX219) via picamera2
# Raspberry Pi 5 (PiSP / RP1)
#
# Fix: AE + AWB keduanya auto dengan ExposureValue +1.0 EV
# agar sensor tidak underexpose → DigitalGain tidak turun < 1.0
#
# Update: tambah apply_controls() untuk live update dari
# CameraSettingsDialog tanpa perlu restart stream.
# ─────────────────────────────────────────────────────────────
import cv2
import time
import queue
import logging
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from picamera2 import Picamera2
from config import (
    CAM_WIDTH, CAM_HEIGHT, CAM_FPS, JPEG_QUALITY,
    CAM_EV, CAM_CONTRAST, CAM_SATURATION,
    CAM_SHARPNESS, CAM_BRIGHTNESS,
    CAM_AE_MODE, CAM_AWB_MODE, CAM_NOISE_MODE,
)

logger = logging.getLogger(__name__)


class CameraStreamer(QThread):
    frame_ready    = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._picam2: Picamera2 | None = None
        self.frame_q: queue.Queue = queue.Queue(maxsize=2)

    def run(self):
        try:
            self._picam2 = Picamera2()
            cam_cfg = self._picam2.create_video_configuration(
                main={"size": (CAM_WIDTH, CAM_HEIGHT), "format": "RGB888"},
                controls={
                    "FrameRate":          CAM_FPS,
                    "NoiseReductionMode": CAM_NOISE_MODE,
                    "Sharpness":          CAM_SHARPNESS,
                    "Saturation":         CAM_SATURATION,
                    "Contrast":           CAM_CONTRAST,
                    "Brightness":         CAM_BRIGHTNESS,
                    "AeEnable":           True,
                    "AeExposureMode":     CAM_AE_MODE,
                    "ExposureValue":      CAM_EV,
                    "AwbEnable":          True,
                    "AwbMode":            CAM_AWB_MODE,
                }
            )
            self._picam2.configure(cam_cfg)
            self._picam2.start()
            # Warmup 2 detik — biarkan AE+AWB konvergen
            time.sleep(2.0)
            logger.info(
                f"[CAM] Kamera aktif — "
                f"{CAM_WIDTH}x{CAM_HEIGHT}@{CAM_FPS}fps | "
                f"EV={CAM_EV} Contrast={CAM_CONTRAST} "
                f"Sat={CAM_SATURATION} Shrp={CAM_SHARPNESS}"
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
                # picamera2 RGB888 sudah dalam urutan R,G,B yang benar untuk JPEG
                ok, buf = cv2.imencode(
                    '.jpg', frame_rgb,
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

    # ── Live control update ───────────────────────────────────
    def apply_controls(self, controls: dict):
        """
        Terapkan controls ke picamera2 yang sedang berjalan.
        Dipanggil dari CameraSettingsDialog → Apply Live.

        Parameter yang didukung secara live oleh picamera2:
            Contrast, Saturation, Sharpness, Brightness,
            ExposureValue, AeExposureMode, AwbMode,
            NoiseReductionMode, AeEnable, AwbEnable

        FrameRate TIDAK bisa diubah secara live — abaikan jika ada.
        """
        if self._picam2 is None:
            raise RuntimeError("Picamera2 belum diinisialisasi.")

        # Pastikan AE dan AWB tetap aktif saat update
        safe_controls = {
            "AeEnable":  True,
            "AwbEnable": True,
        }
        safe_controls.update({k: v for k, v in controls.items()
                               if k != "FrameRate"})

        self._picam2.set_controls(safe_controls)
        logger.info(f"[CAM] apply_controls: {safe_controls}")

    def stop(self):
        self._running = False
        if self._picam2:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                pass
        logger.info("[CAM] Kamera dimatikan.")
