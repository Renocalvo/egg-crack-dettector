# pc/settings_dialog_pc.py
# ─────────────────────────────────────────────────────────────
# Window pengaturan terpisah untuk pc_app
# ─────────────────────────────────────────────────────────────
from pathlib import Path
from dotenv  import set_key

from PyQt6.QtCore    import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFileDialog, QMessageBox
)
import config as cfg


class SettingsDialog(QDialog):
    """
    Window pengaturan EggApp PC — dipanggil via tombol Settings.

    Apply  : berlaku sekarang (Window/Idle/Conf/IP)
    Simpan : tulis ke .env — Port & Model berlaku setelah restart
    """

    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main = main_win
        self.setWindowTitle("Pengaturan — EggApp PC")
        self.setMinimumWidth(440)
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

        self.edit_raspi_ip = QLineEdit(cfg.RASPI_IP)
        net_lay.addLayout(_row("IP Raspberry Pi:", self.edit_raspi_ip))

        self.spin_vport = QSpinBox()
        self.spin_vport.setRange(1024, 65535)
        self.spin_vport.setValue(cfg.VIDEO_PORT)
        net_lay.addLayout(_row("Video Port:", self.spin_vport))

        self.spin_rport = QSpinBox()
        self.spin_rport.setRange(1024, 65535)
        self.spin_rport.setValue(cfg.RESULT_PORT)
        net_lay.addLayout(_row("Result Port:", self.spin_rport))

        root.addWidget(grp_net)

        # ── Model ─────────────────────────────────────────────
        grp_model = QGroupBox("Model YOLO")
        model_lay = QVBoxLayout(grp_model)

        row_path = QHBoxLayout()
        lbl_path = QLabel("Path Model (.pt):")
        lbl_path.setFixedWidth(190)
        self.edit_model  = QLineEdit(cfg.MODEL_PATH)
        self.btn_browse  = QPushButton("...")
        self.btn_browse.setFixedWidth(36)
        self.btn_browse.clicked.connect(self._browse_model)
        row_path.addWidget(lbl_path)
        row_path.addWidget(self.edit_model)
        row_path.addWidget(self.btn_browse)
        model_lay.addLayout(row_path)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.1, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setDecimals(2)
        self.spin_conf.setValue(cfg.CONF_THRESH)
        model_lay.addLayout(_row("Confidence Threshold:", self.spin_conf))

        root.addWidget(grp_model)

        # ── Logika Deteksi ────────────────────────────────────
        grp_logic = QGroupBox("Logika Deteksi")
        logic_lay = QVBoxLayout(grp_logic)

        self.spin_window = QDoubleSpinBox()
        self.spin_window.setRange(1.0, 60.0)
        self.spin_window.setSingleStep(1.0)
        self.spin_window.setDecimals(1)
        self.spin_window.setValue(self.main._detection_window)
        logic_lay.addLayout(_row("Detection Window (detik):", self.spin_window))

        self.spin_idle = QDoubleSpinBox()
        self.spin_idle.setRange(0.5, 30.0)
        self.spin_idle.setSingleStep(0.5)
        self.spin_idle.setDecimals(1)
        self.spin_idle.setValue(self.main._idle_duration)
        logic_lay.addLayout(_row("Idle Antar Telur (detik):", self.spin_idle))

        root.addWidget(grp_logic)

        # ── Catatan ───────────────────────────────────────────
        lbl_note = QLabel(
            "Apply  : Window / Idle / Conf / IP langsung berlaku.\n"
            "Simpan : Port & Model berlaku setelah restart."
        )
        lbl_note.setStyleSheet("color:#78909C; font-size:10px; padding:4px 0;")
        root.addWidget(lbl_note)

        # ── Tombol ────────────────────────────────────────────
        row_btn = QHBoxLayout()
        btn_apply = QPushButton("Apply")
        btn_save  = QPushButton("Simpan ke .env")
        btn_close = QPushButton("Tutup")
        btn_apply.setStyleSheet("background:#283593; padding:7px 16px;")
        btn_save.setStyleSheet("background:#1B5E20; padding:7px 16px;")
        btn_close.setStyleSheet("background:#37474F; padding:7px 16px;")
        btn_apply.clicked.connect(self._apply)
        btn_save.clicked.connect(self._save)
        btn_close.clicked.connect(self.close)
        row_btn.addWidget(btn_apply)
        row_btn.addWidget(btn_save)
        row_btn.addStretch()
        row_btn.addWidget(btn_close)
        root.addLayout(row_btn)

    # ── Slots ─────────────────────────────────────────────────
    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Model YOLO", "",
            "PyTorch Model (*.pt);;All Files (*)"
        )
        if path:
            self.edit_model.setText(path)

    def _apply(self):
        """Terapkan nilai ke runtime tanpa restart."""
        self.main._detection_window = self.spin_window.value()
        self.main._idle_duration    = self.spin_idle.value()
        cfg.CONF_THRESH             = self.spin_conf.value()
        cfg.RASPI_IP                = self.edit_raspi_ip.text().strip()
        self.main._log(
            f"[CONFIG] Applied — "
            f"window:{self.main._detection_window:.1f}s  "
            f"idle:{self.main._idle_duration:.1f}s  "
            f"conf:{cfg.CONF_THRESH:.2f}  "
            f"raspi:{cfg.RASPI_IP}"
        )

    def _save(self):
        """Apply ke runtime + tulis ke .env."""
        self._apply()
        env_path = Path(__file__).parent / '.env'
        vals = {
            'RASPI_IP':    self.edit_raspi_ip.text().strip(),
            'VIDEO_PORT':  str(self.spin_vport.value()),
            'RESULT_PORT': str(self.spin_rport.value()),
            'MODEL_PATH':  self.edit_model.text().strip(),
            'CONF_THRESH': f"{self.spin_conf.value():.2f}",
        }
        for k, v in vals.items():
            set_key(str(env_path), k, v)
        self.main._log(f"[CONFIG] Disimpan ke {env_path}")
        QMessageBox.information(
            self, "Tersimpan",
            "Konfigurasi disimpan ke .env\n"
            "Window / Idle / Conf sudah aktif sekarang.\n"
            "Port & Model berlaku setelah restart."
        )


# ── Helper ────────────────────────────────────────────────────
def _row(label: str, widget) -> QHBoxLayout:
    r = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setFixedWidth(190)
    r.addWidget(lbl)
    r.addWidget(widget)
    return r
