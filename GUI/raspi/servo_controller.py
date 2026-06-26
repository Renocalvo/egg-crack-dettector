import time
import lgpio
import logging
from config import (SERVO_PIN, SERVO_STOP_US, SERVO_TERIMA_US,
                    SERVO_TOLAK_US, SERVO_ROTATE_SEC, SERVO_DELAY_SEC)

logger = logging.getLogger(__name__)

_PWM_FREQ   = 50
_PERIOD_US  = 1_000_000 // _PWM_FREQ

def _us_to_duty(pulsewidth_us: int) -> float:
    return (pulsewidth_us / _PERIOD_US) * 100.0

class ServoController:
    def __init__(self, pin: int = SERVO_PIN):
        self.pin = pin
        self._h  = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self._h, self.pin)
        self.stop()  # MG90S 360: "idle" = berhenti, bukan posisi
        logger.info(f"[SERVO] lgpio OK — GPIO {pin}, posisi STOP")

    def _move(self, pulsewidth_us: int):
        duty = _us_to_duty(pulsewidth_us)
        lgpio.tx_pwm(self._h, self.pin, _PWM_FREQ, duty)

    def stop(self):
        self._move(SERVO_STOP_US)   # ~1500us, netral
        logger.debug("[SERVO] -> STOP")

    def _rotate(self, pulsewidth_us: int, label: str):
        if SERVO_DELAY_SEC > 0:
            time.sleep(SERVO_DELAY_SEC)
        self._move(pulsewidth_us)            # mulai putar
        logger.info(f"[SERVO] -> {label} (putar)")
        time.sleep(SERVO_ROTATE_SEC)         # putar selama durasi tertentu
        self.stop()                          # berhenti
        logger.info(f"[SERVO] -> STOP setelah {label}")

    def terima(self):
        self._rotate(SERVO_TERIMA_US, "DITERIMA")

    def tolak(self):
        self._rotate(SERVO_TOLAK_US, "DITOLAK")

    def cleanup(self):
        lgpio.tx_pwm(self._h, self.pin, 0, 0)
        lgpio.gpiochip_close(self._h)
        logger.info("[SERVO] Cleanup selesai.")
