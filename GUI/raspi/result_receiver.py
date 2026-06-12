# raspi/result_receiver.py
# ─────────────────────────────────────────────────────────────
# QThread — Listen JSON dari laptop via TCP port RESULT_PORT
# Setiap JSON diakhiri newline '\n'
# ─────────────────────────────────────────────────────────────
import socket
import json
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from config import RESULT_PORT

logger = logging.getLogger(__name__)


class ResultReceiverThread(QThread):
    """
    Signal:
        result_received(dict) — dict hasil deteksi dari laptop
        error_occurred(str)   — pesan error koneksi
    """
    result_received = pyqtSignal(dict)
    error_occurred  = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self):
        self._running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', RESULT_PORT))
        server.listen(1)
        server.settimeout(1.0)
        logger.info(f"[RESULT] Menunggu JSON dari laptop di port {RESULT_PORT}")

        while self._running:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"[RESULT] Accept error: {e}")
                continue

            logger.info(f"[RESULT] Laptop terhubung dari {addr}")
            buf = ''
            try:
                conn.settimeout(2.0)
                while self._running:
                    try:
                        chunk = conn.recv(4096).decode('utf-8', errors='ignore')
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buf += chunk
                    # Parse setiap baris JSON yang sudah lengkap
                    while '\n' in buf:
                        line, buf = buf.split('\n', 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            result = json.loads(line)
                            self.result_received.emit(result)
                        except json.JSONDecodeError as je:
                            logger.warning(f"[RESULT] JSON parse error: {je} | raw: {line[:80]}")
            except Exception as e:
                logger.warning(f"[RESULT] Koneksi laptop terputus: {e}")
            finally:
                conn.close()

        server.close()
        logger.info("[RESULT] ResultReceiver dihentikan.")

    def stop(self):
        self._running = False
