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
from config import (SERVO_IDLE_US, SERVO_TERIMA_US, SERVO_TOLAK_US, SERVO_RETURN_SEC)


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
        grp_servo = QGroupBox("Servo SG90")
        servo_lay = QVBoxLayout(grp_servo)

        self.spin_pin = QSpinBox()
        self.spin_pin.setRange(0, 27)
        self.spin_pin.setValue(cfg.SERVO_PIN)
        servo_lay.addLayout(_row("GPIO PIN (BCM):", self.spin_pin))

        # Pulsewidth — posisi servo (µs)
        self.spin_idle = QSpinBox()
        self.spin_idle.setRange(400, 2600); self.spin_idle.setSingleStep(50)
        self.spin_idle.setValue(SERVO_IDLE_US)
        self.spin_idle.setSuffix(" µs")
        servo_lay.addLayout(_row("Idle (90°):", self.spin_idle))

        self.spin_terima = QSpinBox()
        self.spin_terima.setRange(400, 2600); self.spin_terima.setSingleStep(50)
        self.spin_terima.setValue(SERVO_TERIMA_US)
        self.spin_terima.setSuffix(" µs")
        servo_lay.addLayout(_row("Terima (180°):", self.spin_terima))

        self.spin_tolak = QSpinBox()
        self.spin_tolak.setRange(400, 2600); self.spin_tolak.setSingleStep(50)
        self.spin_tolak.setValue(SERVO_TOLAK_US)
        self.spin_tolak.setSuffix(" µs")
        servo_lay.addLayout(_row("Tolak (0°):", self.spin_tolak))

        self.spin_return = QDoubleSpinBox()
        self.spin_return.setRange(0.2, 5.0); self.spin_return.setSingleStep(0.1)
        self.spin_return.setDecimals(1); self.spin_return.setValue(SERVO_RETURN_SEC)
        self.spin_return.setSuffix(" detik")
        servo_lay.addLayout(_row("Waktu Tahan:", self.spin_return))

        # Tombol test servo
        row_test = QHBoxLayout()
        btn_test_terima = QPushButton("Test TERIMA")
        btn_test_tolak  = QPushButton("Test TOLAK")
        btn_test_idle   = QPushButton("Reset IDLE")
        btn_test_terima.setStyleSheet("background:#1B5E20;")
        btn_test_tolak.setStyleSheet("background:#B71C1C;")
        btn_test_idle.setStyleSheet("background:#37474F;")
        btn_test_terima.clicked.connect(lambda: self._test_servo("TERIMA"))
        btn_test_tolak.clicked.connect(lambda: self._test_servo("TOLAK"))
        btn_test_idle.clicked.connect(lambda: self._test_servo("IDLE"))
        row_test.addWidget(btn_test_terima)
        row_test.addWidget(btn_test_tolak)
        row_test.addWidget(btn_test_idle)
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
            threading.Thread(target=servo.idle, daemon=True).start()

    def _save(self):
        env_path = Path(__file__).parent / '.env'
        vals = {
            'LAPTOP_IP':       self.edit_ip.text().strip(),
            'VIDEO_PORT':      str(self.spin_vport.value()),
            'RESULT_PORT':     str(self.spin_rport.value()),
            'SERVO_PIN':       str(self.spin_pin.value()),
            'SERVO_IDLE_US':   str(self.spin_idle.value()),
            'SERVO_TERIMA_US': str(self.spin_terima.value()),
            'SERVO_TOLAK_US':  str(self.spin_tolak.value()),
            'SERVO_RETURN_SEC':f"{self.spin_return.value():.1f}",
            'CAM_WIDTH':       str(self.spin_camw.value()),
            'CAM_HEIGHT':      str(self.spin_camh.value()),
            'CAM_FPS':         str(self.spin_fps.value()),
            'JPEG_QUALITY':    str(self.spin_jpeg.value()),
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