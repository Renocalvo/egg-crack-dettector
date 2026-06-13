# raspi/servo_controller.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Modul kontrol servo SG90 menggunakan pigpio (hardware PWM DMA)
# Lebih stabil dan bebas jitter dibanding RPi.GPIO software PWM
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# raspi/servo_controller.py ï¿½ Pi 5 compatible (lgpio)
import time
import lgpio
import logging
from config import (SERVO_PIN, SERVO_IDLE_US, SERVO_TERIMA_US,
                    SERVO_TOLAK_US, SERVO_RETURN_SEC)

logger = logging.getLogger(__name__)

# SG90  50Hz: period = 20ms = 20000pikos
_PWM_FREQ   = 50
_PERIOD_US  = 1_000_000 // _PWM_FREQ   # 20000 pikos

def _us_to_duty(pulsewidth_us: int) -> float:
    """Konversi pulsewidth ï¿½s ? duty cycle 0-100 untuk lgpio."""
    return (pulsewidth_us / _PERIOD_US) * 100.0


class ServoController:
    def __init__(self, pin: int = SERVO_PIN):
        self.pin = pin
        self._h  = lgpio.gpiochip_open(0)   # /dev/gpiochip0
        lgpio.gpio_claim_output(self._h, self.pin)
        self._move(SERVO_IDLE_US)
        logger.info(f"[SERVO] lgpio OK ï¿½ GPIO {pin}, posisi IDLE")

    def _move(self, pulsewidth_us: int):
        duty = _us_to_duty(pulsewidth_us)
        lgpio.tx_pwm(self._h, self.pin, _PWM_FREQ, duty)

    def idle(self):
        self._move(SERVO_IDLE_US)
        logger.debug("[SERVO] ? IDLE")

    def terima(self):
        self._move(SERVO_TERIMA_US)
        logger.info("[SERVO] ? DITERIMA")
        time.sleep(SERVO_RETURN_SEC)
        self._move(SERVO_IDLE_US)

    def tolak(self):
        self._move(SERVO_TOLAK_US)
        logger.info("[SERVO] ? DITOLAK")
        time.sleep(SERVO_RETURN_SEC)
        self._move(SERVO_IDLE_US)

    def cleanup(self):
        lgpio.tx_pwm(self._h, self.pin, 0, 0)   # stop PWM
        lgpio.gpiochip_close(self._h)
        logger.info("[SERVO] Cleanup selesai.")
