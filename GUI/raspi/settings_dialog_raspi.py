# raspi/settings_dialog_raspi.py
# ─────────────────────────────────────────────────────────────
# Window pengaturan terpisah untuk raspi_app
# ─────────────────────────────────────────────────────────────
from pathlib import Path
from dotenv  import set_key

from PyQt6.QtCore    import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
    QGroupBox, QMessageBox
)
import config as cfg
from config import (SERVO_STOP_US, SERVO_TERIMA_US, SERVO_TOLAK_US,
                     SERVO_ROTATE_SEC, SERVO_DELAY_SEC)


class SettingsDialog(QDialog):
    """
    Window pengaturan EggApp Raspi — dipanggil via tombol Settings.

    Simpan : tulis ke .env — berlaku setelah restart
    """

    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main = main_win
        self.setWindowTitle("Pengaturan — EggApp Raspi")
        self.setMinimumWidth(420)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build()

    # ── Build UI ──────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Jaringan ──────────────────────────────────────────
        grp_net = QGroupBox("Jaringan")
        net_lay = QVBoxLayout(grp_net)

        self.edit_ip = QLineEdit(cfg.LAPTOP_IP)
        net_lay.addLayout(_row("IP Laptop:", self.edit_ip))

        self.spin_vport = QSpinBox()
        self.spin_vport.setRange(1024, 65535)
        self.spin_vport.setValue(cfg.VIDEO_PORT)
        net_lay.addLayout(_row("Video Port:", self.spin_vport))

        self.spin_rport = QSpinBox()
        self.spin_rport.setRange(1024, 65535)
        self.spin_rport.setValue(cfg.RESULT_PORT)
        net_lay.addLayout(_row("Result Port:", self.spin_rport))

        root.addWidget(grp_net)

        # ── Servo ─────────────────────────────────────────────
        grp_servo = QGroupBox("Servo MG90 360° (Continuous Rotation)")
        servo_lay = QVBoxLayout(grp_servo)

        lbl_info = QLabel(
            "Motor ini tidak memiliki posisi sudut tetap — pulsewidth\n"
            "mengatur KECEPATAN & ARAH putaran, bukan posisi."
        )
        lbl_info.setStyleSheet("color:#78909C; font-size:10px;")
        lbl_info.setWordWrap(True)
        servo_lay.addWidget(lbl_info)

        self.spin_pin = QSpinBox()
        self.spin_pin.setRange(0, 27)
        self.spin_pin.setValue(cfg.SERVO_PIN)
        servo_lay.addLayout(_row("GPIO PIN (BCM):", self.spin_pin))

        # Pulsewidth — kecepatan & arah putaran (µs)
        self.spin_stop = QSpinBox()
        self.spin_stop.setRange(1400, 1600); self.spin_stop.setSingleStep(5)
        self.spin_stop.setValue(SERVO_STOP_US)
        self.spin_stop.setSuffix(" µs")
        self.spin_stop.setToolTip(
            "Titik netral/stop. WAJIB dikalibrasi per unit motor\n"
            "(biasanya 1480-1520 µs) — gunakan tombol 'Test STOP'\n"
            "dan geser nilai ini sampai motor benar-benar diam."
        )
        servo_lay.addLayout(_row("Netral / Stop:", self.spin_stop))

        self.spin_terima = QSpinBox()
        self.spin_terima.setRange(400, 2600); self.spin_terima.setSingleStep(50)
        self.spin_terima.setValue(SERVO_TERIMA_US)
        self.spin_terima.setSuffix(" µs")
        self.spin_terima.setToolTip("Arah & kecepatan putar saat DITERIMA.")
        servo_lay.addLayout(_row("Diterima (arah/speed):", self.spin_terima))

        self.spin_tolak = QSpinBox()
        self.spin_tolak.setRange(400, 2600); self.spin_tolak.setSingleStep(50)
        self.spin_tolak.setValue(SERVO_TOLAK_US)
        self.spin_tolak.setSuffix(" µs")
        self.spin_tolak.setToolTip("Arah & kecepatan putar saat DITOLAK.")
        servo_lay.addLayout(_row("Ditolak (arah/speed):", self.spin_tolak))

        self.spin_rotate = QDoubleSpinBox()
        self.spin_rotate.setRange(0.1, 5.0); self.spin_rotate.setSingleStep(0.1)
        self.spin_rotate.setDecimals(2); self.spin_rotate.setValue(SERVO_ROTATE_SEC)
        self.spin_rotate.setSuffix(" detik")
        self.spin_rotate.setToolTip(
            "Lama motor berputar sebelum otomatis stop.\n"
            "Tidak ada feedback posisi, jadi sudut gerak ditentukan\n"
            "murni dari kombinasi kecepatan (µs) x durasi ini."
        )
        servo_lay.addLayout(_row("Durasi Putar:", self.spin_rotate))

        # ── Delay Respon — waktu tunggu sebelum servo mulai bergerak ──
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.0, 5.0); self.spin_delay.setSingleStep(0.1)
        self.spin_delay.setDecimals(2); self.spin_delay.setValue(SERVO_DELAY_SEC)
        self.spin_delay.setSuffix(" detik")
        self.spin_delay.setToolTip(
            "Waktu tunggu sebelum servo mulai bergerak setelah\n"
            "menerima sinyal DITERIMA/DITOLAK dari laptop."
        )
        servo_lay.addLayout(_row("Delay Respon:", self.spin_delay))

        # Tombol test servo
        row_test = QHBoxLayout()
        btn_test_terima = QPushButton("Test TERIMA")
        btn_test_tolak  = QPushButton("Test TOLAK")
        btn_test_stop   = QPushButton("Test STOP")
        btn_test_terima.setStyleSheet("background:#1B5E20;")
        btn_test_tolak.setStyleSheet("background:#B71C1C;")
        btn_test_stop.setStyleSheet("background:#37474F;")
        btn_test_terima.clicked.connect(lambda: self._test_servo("TERIMA"))
        btn_test_tolak.clicked.connect(lambda: self._test_servo("TOLAK"))
        btn_test_stop.clicked.connect(lambda: self._test_servo("STOP"))
        row_test.addWidget(btn_test_terima)
        row_test.addWidget(btn_test_tolak)
        row_test.addWidget(btn_test_stop)
        servo_lay.addLayout(row_test)

        root.addWidget(grp_servo)

        # ── Kamera ────────────────────────────────────────────
        grp_cam = QGroupBox("Kamera (Pi Camera V2)")
        cam_lay = QVBoxLayout(grp_cam)

        row_res = QHBoxLayout()
        lbl_res = QLabel("Resolusi (W x H):")
        lbl_res.setFixedWidth(190)
        self.spin_camw = QSpinBox()
        self.spin_camw.setRange(160, 1920)
        self.spin_camw.setValue(cfg.CAM_WIDTH)
        lbl_x = QLabel("x")
        lbl_x.setFixedWidth(14)
        lbl_x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_camh = QSpinBox()
        self.spin_camh.setRange(120, 1080)
        self.spin_camh.setValue(cfg.CAM_HEIGHT)
        row_res.addWidget(lbl_res)
        row_res.addWidget(self.spin_camw)
        row_res.addWidget(lbl_x)
        row_res.addWidget(self.spin_camh)
        cam_lay.addLayout(row_res)

        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(5, 60)
        self.spin_fps.setValue(cfg.CAM_FPS)
        cam_lay.addLayout(_row("FPS:", self.spin_fps))

        self.spin_jpeg = QSpinBox()
        self.spin_jpeg.setRange(20, 100)
        self.spin_jpeg.setValue(cfg.JPEG_QUALITY)
        cam_lay.addLayout(_row("JPEG Quality:", self.spin_jpeg))

        root.addWidget(grp_cam)

        # ── Catatan ───────────────────────────────────────────
        lbl_note = QLabel(
            "Semua perubahan berlaku setelah restart aplikasi."
        )
        lbl_note.setStyleSheet("color:#78909C; font-size:10px; padding:4px 0;")
        root.addWidget(lbl_note)

        # ── Tombol ────────────────────────────────────────────
        row_btn = QHBoxLayout()
        btn_save  = QPushButton("Simpan ke .env")
        btn_close = QPushButton("Tutup")
        btn_save.setStyleSheet("background:#1B5E20; padding:7px 16px;")
        btn_close.setStyleSheet("background:#37474F; padding:7px 16px;")
        btn_save.clicked.connect(self._save)
        btn_close.clicked.connect(self.close)
        row_btn.addWidget(btn_save)
        row_btn.addStretch()
        row_btn.addWidget(btn_close)
        root.addLayout(row_btn)

    # ── Slots ─────────────────────────────────────────────────
    def _test_servo(self, action: str):
        """Test gerakan servo langsung dari dialog."""
        servo = self.main._servo
        if servo is None:
            QMessageBox.warning(self, "Servo", "Servo belum diinisialisasi.")
            return
        import threading
        if action == "TERIMA":
            threading.Thread(target=servo.terima, daemon=True).start()
        elif action == "TOLAK":
            threading.Thread(target=servo.tolak, daemon=True).start()
        else:
            threading.Thread(target=servo.stop, daemon=True).start()

    def _save(self):
        env_path = Path(__file__).parent / '.env'
        vals = {
            'LAPTOP_IP':        self.edit_ip.text().strip(),
            'VIDEO_PORT':       str(self.spin_vport.value()),
            'RESULT_PORT':      str(self.spin_rport.value()),
            'SERVO_PIN':        str(self.spin_pin.value()),
            'SERVO_STOP_US':    str(self.spin_stop.value()),
            'SERVO_TERIMA_US':  str(self.spin_terima.value()),
            'SERVO_TOLAK_US':   str(self.spin_tolak.value()),
            'SERVO_ROTATE_SEC': f"{self.spin_rotate.value():.2f}",
            'SERVO_DELAY_SEC':  f"{self.spin_delay.value():.2f}",
            'CAM_WIDTH':        str(self.spin_camw.value()),
            'CAM_HEIGHT':       str(self.spin_camh.value()),
            'CAM_FPS':          str(self.spin_fps.value()),
            'JPEG_QUALITY':     str(self.spin_jpeg.value()),
        }
        for k, v in vals.items():
            set_key(str(env_path), k, v)
        self.main._log(f"[CONFIG] Disimpan ke {env_path}")
        QMessageBox.information(
            self, "Tersimpan",
            "Konfigurasi disimpan ke .env\n"
            "Restart aplikasi untuk menerapkan perubahan."
        )
        self.close()


# ── Helper ────────────────────────────────────────────────────
def _row(label: str, widget) -> QHBoxLayout:
    r = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setFixedWidth(190)
    r.addWidget(lbl)
    r.addWidget(widget)
    return r
