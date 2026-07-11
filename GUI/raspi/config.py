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
# ── Kamera — resolusi & encoding ─────────────────────────────
CAM_WIDTH    = int(os.getenv("CAM_WIDTH",    "640"))
CAM_HEIGHT   = int(os.getenv("CAM_HEIGHT",   "480"))
CAM_FPS      = int(os.getenv("CAM_FPS",      "30"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))
# ── Kamera — image controls (picamera2) ──────────────────────
CAM_EV          = float(os.getenv("CAM_EV",         "0.0"))   # -4.0 … +4.0 EV
CAM_CONTRAST    = float(os.getenv("CAM_CONTRAST",   "1.0"))   #  0.0 … 32.0
CAM_SATURATION  = float(os.getenv("CAM_SATURATION", "1.0"))   #  0.0 … 32.0
CAM_SHARPNESS   = float(os.getenv("CAM_SHARPNESS",  "1.0"))   #  0.0 … 16.0
CAM_BRIGHTNESS  = float(os.getenv("CAM_BRIGHTNESS", "0.0"))   # -1.0 …  1.0
CAM_AE_MODE     = int  (os.getenv("CAM_AE_MODE",    "0"))     # 0=Normal,1=Short,2=Long,3=Custom
CAM_AWB_MODE    = int  (os.getenv("CAM_AWB_MODE",   "0"))     # 0=Auto,1=Tungsten,...
CAM_NOISE_MODE  = int  (os.getenv("CAM_NOISE_MODE", "1"))     # 0=Off,1=Fast,2=HQ

# ── Servo — MG90 360° (Continuous Rotation) ───────────────────
# Catatan penting: motor ini TIDAK punya posisi sudut tetap.
# Pulsewidth di sini mengontrol KECEPATAN & ARAH putaran, bukan posisi.
#   ~1500us           -> netral / stop (titik ini WAJIB dikalibrasi per unit,
#                        karena deadband tiap motor bisa sedikit offset,
#                        biasanya di rentang 1480-1520us)
#   < SERVO_STOP_US   -> putar 1 arah, makin jauh dari titik stop = makin cepat
#   > SERVO_STOP_US   -> putar arah sebaliknya
SERVO_PIN         = int  (os.getenv("SERVO_PIN",         "14"))
SERVO_STOP_US     = int  (os.getenv("SERVO_STOP_US",     "1500"))
SERVO_TERIMA_US   = int  (os.getenv("SERVO_TERIMA_US",   "2000"))
SERVO_TOLAK_US    = int  (os.getenv("SERVO_TOLAK_US",    "1000"))
SERVO_DELAY_SEC   = float(os.getenv("SERVO_DELAY_SEC",   "0.0"))
# Durasi putar dipisah per arah karena kecepatan CW/CCW motor tidak simetris
# meskipun offset pulsewidth-nya simetris terhadap SERVO_STOP_US.
# Kalibrasi manual: ukur derajat aktual untuk durasi tertentu, lalu hitung
# durasi_target = (90 / derajat_terukur) * durasi_test
SERVO_ROTATE_SEC_TERIMA = float(os.getenv("SERVO_ROTATE_SEC_TERIMA", "0.35"))
SERVO_ROTATE_SEC_TOLAK  = float(os.getenv("SERVO_ROTATE_SEC_TOLAK",  "0.35"))

# ── Logging ───────────────────────────────────────────────────
LOG_FILE  = "logs/raspi.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
