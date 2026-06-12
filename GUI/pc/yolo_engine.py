# pc/yolo_engine.py
# ─────────────────────────────────────────────────────────────
# Modul inferensi YOLOv8 — berjalan di YoloInferenceThread
# Referensi: Uji_Yolo.py — model(frame, verbose=False, conf=0.6)
# ─────────────────────────────────────────────────────────────
import logging
import numpy as np
import cv2
from datetime import datetime
from ultralytics import YOLO
from config import MODEL_PATH, CONF_THRESH, DEVICE, CLASS_DECISION

logger = logging.getLogger(__name__)


class YoloEngine:
    """
    Wrapper YOLOv8 — load sekali, infer berkali-kali.
    Menggunakan CUDA jika tersedia (RTX 4060).
    """

    def __init__(self):
        logger.info(f"[YOLO] Memuat model: {MODEL_PATH}")
        logger.info(f"[YOLO] Device: {DEVICE.upper()}")
        self.model = YOLO(MODEL_PATH)
        # Warm-up agar inferensi pertama tidak lambat
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        self.model(dummy, verbose=False, conf=CONF_THRESH, device=DEVICE)
        logger.info(f"[YOLO] Model siap. Kelas: {self.model.names}")

    def infer(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, dict]:
        """
        Jalankan inferensi pada satu frame BGR.

        Returns:
            annotated_frame (np.ndarray): Frame BGR + bounding box overlay
            result_dict (dict)          : Hasil deteksi terstruktur
        """
        results    = self.model(frame_bgr, verbose=False,
                                conf=CONF_THRESH, device=DEVICE)
        annotated  = results[0].plot()   # frame + bbox, label, conf

        result_dict = {
            "status":     "NO_OBJECT",
            "class":      None,
            "confidence": 0.0,
            "bbox":       None,
            "center_x":   None,
            "center_y":   None,
            "timestamp":  datetime.now().isoformat()
        }

        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            # Pilih deteksi dengan confidence tertinggi
            best     = int(boxes.conf.argmax())
            cls_id   = int(boxes.cls[best])
            cls_name = self.model.names[cls_id]
            conf_val = float(boxes.conf[best])
            xyxy     = boxes.xyxy[best].cpu().numpy().astype(int).tolist()
            cx       = (xyxy[0] + xyxy[2]) // 2
            cy       = (xyxy[1] + xyxy[3]) // 2
            status   = CLASS_DECISION.get(cls_name, "DITOLAK")

            result_dict.update({
                "status":     status,
                "class":      cls_name,
                "confidence": round(conf_val, 4),
                "bbox":       xyxy,
                "center_x":   cx,
                "center_y":   cy,
            })

        return annotated, result_dict

    def generate_panels(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Hasilkan dua panel thumbnail untuk sidebar GUI:
            - false_color : COLORMAP_JET untuk visualisasi intensitas
            - mask        : Canny edge / binary untuk segmentasi visual
        """
        gray        = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        false_color = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
        edges       = cv2.Canny(gray, 50, 150)
        mask_bgr    = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        return false_color, mask_bgr
