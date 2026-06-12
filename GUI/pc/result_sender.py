# pc/result_sender.py
# ─────────────────────────────────────────────────────────────
# QThread — Kirim JSON hasil deteksi ke Raspi via TCP RESULT_PORT
# Setiap JSON diakhiri newline '\n'
# ─────────────────────────────────────────────────────────────
import socket
import json
import time
import queue
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from config import RASPI_IP, RESULT_PORT

logger = logging.getLogger(__name__)


class ResultSenderThread(QThread):
    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running     = False
        self.result_queue: queue.Queue = queue.Queue(maxsize=20)

    def push(self, result_dict: dict):
        try:
            self.result_queue.put_nowait(result_dict)
        except queue.Full:
            pass   # drop jika antrian penuh

    def run(self):
        self._running = True
        while self._running:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((RASPI_IP, RESULT_PORT))
                sock.settimeout(None)
                self.status_changed.emit("RESULT_CONNECTED")
                logger.info(f"[SENDER] Terhubung ke Raspi {RASPI_IP}:{RESULT_PORT}")

                while self._running:
                    try:
                        result = self.result_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    payload = json.dumps(result, ensure_ascii=False) + '\n'
                    sock.sendall(payload.encode('utf-8'))
                    logger.debug(f"[SENDER] JSON terkirim: {result['status']}")

            except Exception as e:
                logger.warning(f"[SENDER] Gagal konek/kirim ke Raspi: {e}")
                self.status_changed.emit("RESULT_DISCONNECTED")
                time.sleep(2.0)
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

    def stop(self):
        self._running = False
