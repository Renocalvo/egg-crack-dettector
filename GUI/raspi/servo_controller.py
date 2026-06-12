# raspi/servo_controller.py
# ─────────────────────────────────────────────────────────────
# Modul kontrol servo SG90 menggunakan pigpio (hardware PWM DMA)
# Lebih stabil dan bebas jitter dibanding RPi.GPIO software PWM
# ─────────────────────────────────────────────────────────────
import time
import logging
import pigpio
from config import (SERVO_PIN, SERVO_IDLE_US, SERVO_TERIMA_US,
                    SERVO_TOLAK_US, SERVO_RETURN_SEC)

logger = logging.getLogger(__name__)


class ServoController:
    """
    Kontrol servo SG90 via pigpio.
    Gunakan pigpio agar PWM stabil (hardware DMA, bukan software timer).

    Referensi duty cycle SG90 @ 50 Hz:
        500 µs  = 2.5%  =   0° (posisi minimum)
       1500 µs  = 7.5%  =  90° (posisi tengah / IDLE)
       2500 µs = 12.5%  = 180° (posisi maksimum)
    """

    def __init__(self, pin: int = SERVO_PIN):
        self.pin = pin
        self.pi  = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError(
                "[SERVO] pigpiod tidak berjalan!\n"
                "Jalankan terlebih dahulu: sudo pigpiod"
            )
        self._move(SERVO_IDLE_US)
        logger.info(f"[SERVO] Inisialisasi OK — GPIO {pin}, posisi IDLE")

    # ── Private ───────────────────────────────────────────────
    def _move(self, pulsewidth_us: int):
        self.pi.set_servo_pulsewidth(self.pin, pulsewidth_us)

    # ── Public API ────────────────────────────────────────────
    def idle(self):
        """Servo ke posisi tengah (90°)."""
        self._move(SERVO_IDLE_US)
        logger.debug("[SERVO] → IDLE (1500 µs)")

    def terima(self):
        """
        Servo ke posisi TERIMA (180°), tahan SERVO_RETURN_SEC detik,
        lalu kembali ke IDLE otomatis.
        Dipanggil dari thread — BLOCKING selama return delay.
        """
        self._move(SERVO_TERIMA_US)
        logger.info("[SERVO] → DITERIMA (2500 µs / 180°)")
        time.sleep(SERVO_RETURN_SEC)
        self._move(SERVO_IDLE_US)
        logger.debug("[SERVO] → kembali IDLE")

    def tolak(self):
        """
        Servo ke posisi TOLAK (0°), tahan SERVO_RETURN_SEC detik,
        lalu kembali ke IDLE otomatis.
        """
        self._move(SERVO_TOLAK_US)
        logger.info("[SERVO] → DITOLAK (500 µs / 0°)")
        time.sleep(SERVO_RETURN_SEC)
        self._move(SERVO_IDLE_US)
        logger.debug("[SERVO] → kembali IDLE")

    def cleanup(self):
        """Matikan sinyal PWM dan tutup koneksi pigpio."""
        self._move(0)      # 0 = nonaktifkan output PWM
        self.pi.stop()
        logger.info("[SERVO] Cleanup selesai.")
