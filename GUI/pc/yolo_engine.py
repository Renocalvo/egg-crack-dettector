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

        Catatan penting:
        Satu frame bisa berisi LEBIH DARI SATU deteksi sekaligus —
        misal box "egg" dan box "crack" muncul bersamaan (mis. crack
        adalah sub-fitur di permukaan telur yang sama). Sebelumnya kode
        ini hanya mengambil satu box dengan confidence tertinggi
        (argmax), sehingga kalau confidence "egg" > "crack" pada frame
        itu, class "crack" hilang begitu saja dari result_dict — padahal
        box-nya tetap tergambar di annotated frame (karena plot()
        merender SEMUA box, bukan cuma yang terpilih).
        Sekarang result_dict menyertakan "classes": daftar semua nama
        kelas unik yang terdeteksi pada frame ini, supaya konsumen
        (DetectionWindow di pc_app.py) bisa menghitung egg & crack yang
        muncul bersamaan tanpa kehilangan salah satunya. Field "class"
        (tunggal) tetap dipertahankan untuk kompatibilitas/tampilan —
        isinya class dengan confidence tertinggi seperti sebelumnya.
        """
        results    = self.model(frame_bgr, verbose=False,
                                conf=CONF_THRESH, device=DEVICE)
        annotated  = results[0].plot()   # frame + bbox, label, conf

        result_dict = {
            "status":     "NO_OBJECT",
            "class":      None,
            "classes":    [],
            "confidence": 0.0,
            "bbox":       None,
            "center_x":   None,
            "center_y":   None,
            "timestamp":  datetime.now().isoformat()
        }

        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            cls_ids_all  = boxes.cls.cpu().numpy().astype(int)
            confs_all    = boxes.conf.cpu().numpy()
            classes_all  = [self.model.names[c] for c in cls_ids_all]

            # Box dengan confidence tertinggi — tetap dipakai untuk
            # bbox/center/confidence yang ditampilkan di info bar.
            best     = int(confs_all.argmax())
            cls_id   = cls_ids_all[best]
            cls_name = self.model.names[cls_id]
            conf_val = float(confs_all[best])
            xyxy     = boxes.xyxy[best].cpu().numpy().astype(int).tolist()
            cx       = (xyxy[0] + xyxy[2]) // 2
            cy       = (xyxy[1] + xyxy[3]) // 2

            # Status keseluruhan frame: kalau class apapun yang
            # mengandung "crack" terdeteksi di frame ini (walau bukan
            # yang confidence tertinggi), status frame ini tetap
            # DITOLAK — bukan cuma berdasar cls_name terbaik saja.
            has_crack_in_frame = any('crack' in c.lower() for c in classes_all)
            if has_crack_in_frame:
                status = "DITOLAK"
            else:
                status = CLASS_DECISION.get(cls_name, "DITOLAK")

            result_dict.update({
                "status":     status,
                "class":      cls_name,
                "classes":    list(dict.fromkeys(classes_all)),  # unik, urutan dipertahankan
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
