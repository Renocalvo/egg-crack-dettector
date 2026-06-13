# pc/config.py
# ─────────────────────────────────────────────────────────────
# Konfigurasi global EggApp — Node Laptop
# ─────────────────────────────────────────────────────────────
import os
import torch
from dotenv import load_dotenv

load_dotenv()

# ── Jaringan ──────────────────────────────────────────────────
RASPI_IP    = os.getenv("RASPI_IP",    "192.168.137.2")
VIDEO_PORT  = int(os.getenv("VIDEO_PORT",  "9999"))
RESULT_PORT = int(os.getenv("RESULT_PORT", "9998"))

# ── Model YOLO ────────────────────────────────────────────────
MODEL_PATH  = os.getenv("MODEL_PATH", "models/best.pt")
CONF_THRESH = float(os.getenv("CONF_THRESH", "0.6"))
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"

# ── Mapping class → keputusan ─────────────────────────────────
# Sesuaikan dengan nama kelas di file best.pt Anda.
# Cek dengan: from ultralytics import YOLO; print(YOLO('models/best.pt').names)
CLASS_DECISION: dict[str, str] = {
    "egg":         "DITERIMA",
    "crack":       "DITOLAK",
}

# ── Logging ───────────────────────────────────────────────────
LOG_FILE  = "logs/pc.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
