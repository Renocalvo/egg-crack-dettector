# raspi/camera_streamer.py
# -------------------------------------------------------------
# QThread – Capture frame dari Pi Camera V2 (IMX219) via picamera2
# Raspberry Pi 5 (PiSP / RP1)
#
# Perbaikan:
#   - AwbMode  → 0 (Auto) agar tidak bias warna ungu/biru
#   - ExposureValue → 0.0 (netral, tidak overexpose)
#   - Warmup  → 4 detik agar AE+AWB benar-benar konvergen
#   - Tambah koreksi warna opsional via ColourGains manual
#   - Tambah capture metadata untuk logging gain & colour info
#   - Graceful shutdown lebih robust
# -------------------------------------------------------------

import cv2
import time
import queue
import logging
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from picamera2 import Picamera2
from libcamera import controls as libcontrols

from config import CAM_WIDTH, CAM_HEIGHT, CAM_FPS, JPEG_QUALITY

logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Konstanta AWB Mode (libcamera / picamera2)
# -------------------------------------------------------------
AWB_AUTO        = 0
AWB_INCANDESCENT = 1
AWB_TUNGSTEN    = 2
AWB_FLUORESCENT = 3
AWB_INDOOR      = 4
AWB_DAYLIGHT    = 5
AWB_CLOUDY      = 6

# Tuning manual ColourGains jika AWB auto masih salah.
# Format: (red_gain, blue_gain)
# Sesuaikan dengan kondisi cahaya ruangan Anda.
# Set ke None untuk memakai AWB otomatis.
MANUAL_COLOUR_GAINS = None   # contoh: (1.8, 1.4)

# Warmup – detik yang diberikan agar AE+AWB konvergen
WARMUP_SECONDS = 4.0


class CameraStreamer(QThread):
    """
    QThread yang mengambil frame dari Pi Camera V2 (IMX219)
    via picamera2, lalu mengemisi bytes JPEG lewat sinyal frame_ready.
    """

    frame_ready    = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._picam2: Picamera2 | None = None
        self.frame_q: queue.Queue = queue.Queue(maxsize=2)

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _build_controls(self) -> dict:
        """
        Mengembalikan dict controls picamera2.

        AWB disetel ke Auto (0) agar tidak bias warna.
        Jika MANUAL_COLOUR_GAINS diisi, AWB dinonaktifkan dan
        ColourGains dipakai langsung.
        """
        base = {
            "FrameRate":          float(CAM_FPS),
            "NoiseReductionMode": 1,
            "Sharpness":          1.0,
            "Saturation":         1.0,
            "Contrast":           1.0,
            "Brightness":         0.0,
            # AE – tetap auto, EV netral
            "AeEnable":           True,
            "AeExposureMode":     0,       # 0 = normal
            "ExposureValue":      0.0,     # 0.0 = netral (tidak overexpose)
        }

        if MANUAL_COLOUR_GAINS is not None:
            # Mode manual: matikan AWB, terapkan gain eksplisit
            rg, bg = MANUAL_COLOUR_GAINS
            base.update({
                "AwbEnable":    False,
                "ColourGains":  (rg, bg),
            })
            logger.info(
                f"[CAM] ColourGains manual → R={rg:.2f} B={bg:.2f}"
            )
        else:
            # Mode auto: biarkan AWB bekerja sendiri
            base.update({
                "AwbEnable": True,
                "AwbMode":   AWB_AUTO,   # 0 = Auto (tidak bias warna)
            })

        return base

    def _log_metadata(self) -> None:
        """
        Ambil metadata satu frame untuk logging diagnostik
        (DigitalGain, AnalogueGain, ColourGains, ExposureTime).
        """
        try:
            meta = self._picam2.capture_metadata()
            dg   = meta.get("DigitalGain",    "?")
            ag   = meta.get("AnalogueGain",   "?")
            cg   = meta.get("ColourGains",    ("?", "?"))
            exp  = meta.get("ExposureTime",   "?")
            logger.info(
                f"[CAM] Metadata → "
                f"DigitalGain={dg:.3f}  AnalogueGain={ag:.3f}  "
                f"ColourGains=R{cg[0]:.3f}/B{cg[1]:.3f}  "
                f"ExposureTime={exp}µs"
            )
        except Exception as exc:
            logger.debug(f"[CAM] Gagal baca metadata: {exc}")

    # ----------------------------------------------------------
    # QThread.run
    # ----------------------------------------------------------

    def run(self) -> None:
        # ---------- inisialisasi kamera ----------
        try:
            self._picam2 = Picamera2()

            cfg = self._picam2.create_video_configuration(
                main={
                    "size":   (CAM_WIDTH, CAM_HEIGHT),
                    "format": "RGB888",
                },
                controls=self._build_controls(),
            )
            self._picam2.configure(cfg)
            self._picam2.start()

            logger.info(
                f"[CAM] Warmup {WARMUP_SECONDS}s – menunggu AE+AWB konvergen..."
            )
            time.sleep(WARMUP_SECONDS)

            self._log_metadata()   # cetak gain & colour setelah warmup

            logger.info(
                f"[CAM] Kamera aktif – "
                f"{CAM_WIDTH}x{CAM_HEIGHT}@{CAM_FPS}fps | "
                f"AWB={'manual' if MANUAL_COLOUR_GAINS else 'auto'} | "
                f"EV=0.0"
            )

        except Exception as exc:
            msg = f"[CAM] Gagal inisialisasi: {exc}"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return

        # ---------- loop capture ----------
        self._running = True
        while self._running:
            try:
                frame_rgb = self._picam2.capture_array("main")

                # RGB → BGR untuk OpenCV / JPEG encoding
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                ok, buf = cv2.imencode(
                    ".jpg",
                    frame_bgr,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
                )
                if not ok:
                    logger.warning("[CAM] imencode gagal, skip frame.")
                    continue

                jpeg_bytes = buf.tobytes()

                # Emit ke UI
                self.frame_ready.emit(jpeg_bytes)

                # Simpan ke queue (non-blocking, drop jika penuh)
                try:
                    self.frame_q.put_nowait(jpeg_bytes)
                except queue.Full:
                    pass

            except Exception as exc:
                logger.warning(f"[CAM] Error saat capture: {exc}")
                time.sleep(0.01)

    # ----------------------------------------------------------
    # Stop
    # ----------------------------------------------------------

    def stop(self) -> None:
        self._running = False
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception as exc:
                logger.debug(f"[CAM] Error saat stop: {exc}")
            finally:
                self._picam2 = None
        logger.info("[CAM] Kamera dimatikan.")
