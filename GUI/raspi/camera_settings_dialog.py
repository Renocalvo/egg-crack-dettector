# raspi/camera_settings_dialog.py
# ─────────────────────────────────────────────────────────────
# Dialog pengaturan kamera (image controls) — terpisah dari
# SettingsDialog utama. Mengatur parameter picamera2 seperti
# Contrast, Saturation, Sharpness, Brightness, ExposureValue,
# AwbMode, AeExposureMode, FrameRate, dan NoiseReductionMode.
#
# Perubahan bisa diterapkan LANGSUNG ke kamera yang sedang
# berjalan (Apply Live) atau disimpan ke .env untuk restart.
# ─────────────────────────────────────────────────────────────
from pathlib import Path
from dotenv  import set_key

from PyQt6.QtCore    import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDoubleSpinBox, QSpinBox,
    QComboBox, QGroupBox, QMessageBox, QSlider, QFrame
)

import config as cfg


# ── Konstanta pilihan mode ────────────────────────────────────
AWB_MODES = {
    "Auto":         0,
    "Tungsten":     1,
    "Fluorescent":  2,
    "Indoor":       4,
    "Daylight":     5,
    "Cloudy":       6,
}

AE_MODES = {
    "Normal":    0,
    "Short":     1,
    "Long":      2,
    "Custom":    3,
}

NOISE_MODES = {
    "Off":       0,
    "Fast":      1,
    "HighQuality": 2,
}


class CameraSettingsDialog(QDialog):
    """
    Dialog kontrol gambar Pi Camera V2.

    - Apply Live  : kirim controls ke picamera2 yang sedang berjalan
    - Reset Default : kembalikan ke nilai default
    - Simpan ke .env: tulis nilai ke .env (berlaku setelah restart)
    """

    # Nilai default (sesuai camera_streamer.py bawaan)
    DEFAULTS = {
        "FrameRate":          cfg.CAM_FPS,
        "Contrast":           1.0,
        "Saturation":         1.0,
        "Sharpness":          1.0,
        "Brightness":         0.0,
        "ExposureValue":      0.0,
        "AeExposureMode":     0,
        "AwbMode":            0,
        "NoiseReductionMode": 1,
    }

    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main = main_win
        self.setWindowTitle("Pengaturan Kamera — EggApp Raspi")
        self.setMinimumWidth(460)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build()

    # ── Build UI ──────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Exposure & AE ─────────────────────────────────────
        grp_ae = QGroupBox("Eksposur (Auto Exposure)")
        ae_lay = QVBoxLayout(grp_ae)

        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(5, 60)
        self.spin_fps.setValue(cfg.CAM_FPS)
        self.spin_fps.setSuffix(" fps")
        ae_lay.addLayout(_row("Frame Rate:", self.spin_fps))

        self.combo_ae_mode = QComboBox()
        for name in AE_MODES:
            self.combo_ae_mode.addItem(name)
        ae_lay.addLayout(_row("AE Mode:", self.combo_ae_mode))

        self.spin_ev = _dbl_spin(-4.0, 4.0, 0.5, 0.0, " EV")
        ae_lay.addLayout(_row("Exposure Value (EV):", self.spin_ev))

        root.addWidget(grp_ae)

        # ── White Balance ─────────────────────────────────────
        grp_awb = QGroupBox("White Balance (AWB)")
        awb_lay = QVBoxLayout(grp_awb)

        self.combo_awb = QComboBox()
        for name in AWB_MODES:
            self.combo_awb.addItem(name)
        awb_lay.addLayout(_row("AWB Mode:", self.combo_awb))

        root.addWidget(grp_awb)

        # ── Image Quality ─────────────────────────────────────
        grp_img = QGroupBox("Kualitas Gambar")
        img_lay = QVBoxLayout(grp_img)

        self.spin_contrast = _dbl_spin(0.0, 32.0, 0.1, 1.0)
        img_lay.addLayout(_row("Contrast:", self.spin_contrast))

        self.spin_saturation = _dbl_spin(0.0, 32.0, 0.1, 1.0)
        img_lay.addLayout(_row("Saturation:", self.spin_saturation))

        self.spin_sharpness = _dbl_spin(0.0, 16.0, 0.1, 1.0)
        img_lay.addLayout(_row("Sharpness:", self.spin_sharpness))

        self.spin_brightness = _dbl_spin(-1.0, 1.0, 0.05, 0.0)
        img_lay.addLayout(_row("Brightness:", self.spin_brightness))

        root.addWidget(grp_img)

        # ── Noise Reduction ───────────────────────────────────
        grp_nr = QGroupBox("Noise Reduction")
        nr_lay = QVBoxLayout(grp_nr)

        self.combo_nr = QComboBox()
        for name in NOISE_MODES:
            self.combo_nr.addItem(name)
        self.combo_nr.setCurrentIndex(1)   # default: Fast
        nr_lay.addLayout(_row("Mode:", self.combo_nr))

        root.addWidget(grp_nr)

        # ── Status live ───────────────────────────────────────
        self.lbl_live = QLabel("")
        self.lbl_live.setStyleSheet("color:#78909C; font-size:10px;")
        self.lbl_live.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.lbl_live)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#2D2D44;")
        root.addWidget(line)

        # ── Catatan ───────────────────────────────────────────
        lbl_note = QLabel(
            "Apply Live: terapkan langsung ke kamera aktif.\n"
            "Simpan ke .env: tersimpan permanen (berlaku setelah restart)."
        )
        lbl_note.setStyleSheet("color:#78909C; font-size:10px; padding:2px 0;")
        root.addWidget(lbl_note)

        # ── Tombol ────────────────────────────────────────────
        row_btn = QHBoxLayout()

        btn_apply   = QPushButton("▶  Apply Live")
        btn_reset   = QPushButton("↺  Reset Default")
        btn_save    = QPushButton("💾  Simpan ke .env")
        btn_close   = QPushButton("Tutup")

        btn_apply.setStyleSheet("background:#1565C0; padding:7px 12px; font-weight:bold;")
        btn_reset.setStyleSheet("background:#37474F; padding:7px 12px;")
        btn_save.setStyleSheet("background:#1B5E20; padding:7px 12px;")
        btn_close.setStyleSheet("background:#37474F; padding:7px 12px;")

        btn_apply.clicked.connect(self._apply_live)
        btn_reset.clicked.connect(self._reset_defaults)
        btn_save.clicked.connect(self._save)
        btn_close.clicked.connect(self.close)

        row_btn.addWidget(btn_apply)
        row_btn.addWidget(btn_reset)
        row_btn.addWidget(btn_save)
        row_btn.addStretch()
        row_btn.addWidget(btn_close)
        root.addLayout(row_btn)

        # Load nilai dari config / .env
        self._load_from_config()

    # ── Load nilai awal ───────────────────────────────────────
    def _load_from_config(self):
        """Isi widget dengan nilai dari config.py (yg sudah baca .env)."""
        self.spin_fps.setValue(cfg.CAM_FPS)

        ev   = float(getattr(cfg, "CAM_EV",          self.DEFAULTS["ExposureValue"]))
        ct   = float(getattr(cfg, "CAM_CONTRAST",     self.DEFAULTS["Contrast"]))
        sat  = float(getattr(cfg, "CAM_SATURATION",   self.DEFAULTS["Saturation"]))
        shrp = float(getattr(cfg, "CAM_SHARPNESS",    self.DEFAULTS["Sharpness"]))
        brt  = float(getattr(cfg, "CAM_BRIGHTNESS",   self.DEFAULTS["Brightness"]))
        ae   = int  (getattr(cfg, "CAM_AE_MODE",      self.DEFAULTS["AeExposureMode"]))
        awb  = int  (getattr(cfg, "CAM_AWB_MODE",     self.DEFAULTS["AwbMode"]))
        nr   = int  (getattr(cfg, "CAM_NOISE_MODE",   self.DEFAULTS["NoiseReductionMode"]))

        self.spin_ev.setValue(ev)
        self.spin_contrast.setValue(ct)
        self.spin_saturation.setValue(sat)
        self.spin_sharpness.setValue(shrp)
        self.spin_brightness.setValue(brt)

        # Set combo AE mode
        for i, v in enumerate(AE_MODES.values()):
            if v == ae:
                self.combo_ae_mode.setCurrentIndex(i)
                break

        # Set combo AWB mode
        for i, v in enumerate(AWB_MODES.values()):
            if v == awb:
                self.combo_awb.setCurrentIndex(i)
                break

        # Set combo Noise mode
        for i, v in enumerate(NOISE_MODES.values()):
            if v == nr:
                self.combo_nr.setCurrentIndex(i)
                break

    # ── Kumpulkan nilai widget ────────────────────────────────
    def _collect(self) -> dict:
        return {
            "FrameRate":          self.spin_fps.value(),
            "ExposureValue":      self.spin_ev.value(),
            "Contrast":           self.spin_contrast.value(),
            "Saturation":         self.spin_saturation.value(),
            "Sharpness":          self.spin_sharpness.value(),
            "Brightness":         self.spin_brightness.value(),
            "AeExposureMode":     AE_MODES[self.combo_ae_mode.currentText()],
            "AwbMode":            AWB_MODES[self.combo_awb.currentText()],
            "NoiseReductionMode": NOISE_MODES[self.combo_nr.currentText()],
        }

    # ── Apply Live ────────────────────────────────────────────
    def _apply_live(self):
        cam: "CameraStreamer | None" = getattr(self.main, "_cam_thread", None)
        if cam is None or not cam.isRunning():
            self.lbl_live.setText("⚠️  Kamera tidak aktif — stream belum dimulai.")
            self.lbl_live.setStyleSheet("color:#FFD54F; font-size:10px;")
            return

        controls = self._collect()
        # Hapus FrameRate dari set_controls (tidak bisa diubah live di picamera2)
        live_controls = {k: v for k, v in controls.items() if k != "FrameRate"}

        try:
            cam.apply_controls(live_controls)
            self.lbl_live.setText("✅  Kontrol diterapkan ke kamera aktif.")
            self.lbl_live.setStyleSheet("color:#69F0AE; font-size:10px;")
            self.main._log(f"[CAM] Controls live: {live_controls}")
        except Exception as e:
            self.lbl_live.setText(f"❌  Gagal: {e}")
            self.lbl_live.setStyleSheet("color:#EF5350; font-size:10px;")

    # ── Reset ke default ──────────────────────────────────────
    def _reset_defaults(self):
        d = self.DEFAULTS
        self.spin_fps.setValue(int(d["FrameRate"]))
        self.spin_ev.setValue(d["ExposureValue"])
        self.spin_contrast.setValue(d["Contrast"])
        self.spin_saturation.setValue(d["Saturation"])
        self.spin_sharpness.setValue(d["Sharpness"])
        self.spin_brightness.setValue(d["Brightness"])
        self.combo_ae_mode.setCurrentIndex(0)
        self.combo_awb.setCurrentIndex(0)
        self.combo_nr.setCurrentIndex(1)
        self.lbl_live.setText("↺  Nilai direset ke default.")
        self.lbl_live.setStyleSheet("color:#78909C; font-size:10px;")

    # ── Simpan ke .env ────────────────────────────────────────
    def _save(self):
        env_path = Path(__file__).parent / '.env'
        c = self._collect()
        vals = {
            'CAM_FPS':         str(c["FrameRate"]),
            'CAM_EV':          f"{c['ExposureValue']:.2f}",
            'CAM_CONTRAST':    f"{c['Contrast']:.2f}",
            'CAM_SATURATION':  f"{c['Saturation']:.2f}",
            'CAM_SHARPNESS':   f"{c['Sharpness']:.2f}",
            'CAM_BRIGHTNESS':  f"{c['Brightness']:.2f}",
            'CAM_AE_MODE':     str(c["AeExposureMode"]),
            'CAM_AWB_MODE':    str(c["AwbMode"]),
            'CAM_NOISE_MODE':  str(c["NoiseReductionMode"]),
        }
        for k, v in vals.items():
            set_key(str(env_path), k, v)
        self.main._log(f"[CAM] Pengaturan kamera disimpan ke {env_path}")
        QMessageBox.information(
            self, "Tersimpan",
            "Pengaturan kamera disimpan ke .env\n"
            "FrameRate baru berlaku setelah restart aplikasi.\n"
            "Controls lainnya bisa diterapkan langsung via 'Apply Live'."
        )
        self.lbl_live.setText("💾  Tersimpan ke .env.")
        self.lbl_live.setStyleSheet("color:#69F0AE; font-size:10px;")


# ── Helpers ───────────────────────────────────────────────────
def _row(label: str, widget) -> QHBoxLayout:
    r = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setFixedWidth(200)
    r.addWidget(lbl)
    r.addWidget(widget)
    return r


def _dbl_spin(mn: float, mx: float, step: float, val: float,
              suffix: str = "") -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(mn, mx)
    sp.setSingleStep(step)
    sp.setDecimals(2)
    sp.setValue(val)
    if suffix:
        sp.setSuffix(suffix)
    return sp
