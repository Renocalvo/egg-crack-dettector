# raspi/config.py
# ─────────────────────────────────────────────────────────────
# Konfigurasi global EggApp — Node Raspberry Pi
# Nilai default dapat di-override via file .env
# ─────────────────────────────────────────────────────────────
import os
from dotenv import load_dotenv

load_dotenv()

# ── Jaringan ──────────────────────────────────────────────────
LAPTOP_IP   = os.getenv("LAPTOP_IP",   "192.168.137.1")
VIDEO_PORT  = int(os.getenv("VIDEO_PORT",  "9999"))
RESULT_PORT = int(os.getenv("RESULT_PORT", "9998"))

# ── Kamera ────────────────────────────────────────────────────
CAM_WIDTH    = int(os.getenv("CAM_WIDTH",    "640"))
CAM_HEIGHT   = int(os.getenv("CAM_HEIGHT",   "480"))
CAM_FPS      = int(os.getenv("CAM_FPS",      "30"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))

# ── Servo ─────────────────────────────────────────────────────
SERVO_PIN        = int(os.getenv("SERVO_PIN", "14"))
SERVO_IDLE_US    = 1500   # microseconds → 90° (tengah)
SERVO_TERIMA_US  = 2500   # microseconds → 180° (DITERIMA)
SERVO_TOLAK_US   = 500    # microseconds → 0°   (DITOLAK)
SERVO_RETURN_SEC = 1.2    # detik sebelum kembali ke IDLE

# ── Logging ───────────────────────────────────────────────────
LOG_FILE  = "logs/raspi.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
