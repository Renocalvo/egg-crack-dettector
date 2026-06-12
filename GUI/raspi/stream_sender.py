# raspi/stream_sender.py
# ─────────────────────────────────────────────────────────────
# QThread — Kirim frame JPEG ke laptop via TCP port VIDEO_PORT
# Protokol: [ 4-byte big-endian length ][ N-byte JPEG data ]
# ─────────────────────────────────────────────────────────────
import socket
import struct
import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from config import LAPTOP_IP, VIDEO_PORT

logger = logging.getLogger(__name__)


class StreamSenderThread(QThread):
    """
    Signal:
        status_changed(str) — "CONNECTED" / "DISCONNECTED" / "ERROR: ..."
    """
    status_changed = pyqtSignal(str)

    def __init__(self, frame_queue, parent=None):
        super().__init__(parent)
        self.frame_queue = frame_queue
        self._running    = False

    def run(self):
        self._running = True
        logger.info(f"[STREAM] Mencoba koneksi ke {LAPTOP_IP}:{VIDEO_PORT}")

        while self._running:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((LAPTOP_IP, VIDEO_PORT))
                sock.settimeout(None)
                self.status_changed.emit("CONNECTED")
                logger.info(f"[STREAM] Terhubung ke laptop {LAPTOP_IP}:{VIDEO_PORT}")

                while self._running:
                    try:
                        data = self.frame_queue.get(timeout=1.0)
                    except Exception:
                        continue
                    length = struct.pack('>I', len(data))
                    sock.sendall(length + data)

            except Exception as e:
                logger.warning(f"[STREAM] Koneksi terputus: {e}")
                self.status_changed.emit("DISCONNECTED")
                time.sleep(2.0)
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

    def stop(self):
        self._running = False
        logger.info("[STREAM] StreamSender dihentikan.")
