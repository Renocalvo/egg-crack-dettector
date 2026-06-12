# pc/frame_receiver.py
# ─────────────────────────────────────────────────────────────
# QThread — Listen frame JPEG dari Raspi via TCP VIDEO_PORT
# Protokol: [ 4-byte big-endian length ][ N-byte JPEG ]
# ─────────────────────────────────────────────────────────────
import socket
import struct
import logging
import numpy as np
import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from config import VIDEO_PORT

logger = logging.getLogger(__name__)


class FrameReceiverThread(QThread):
    """
    Signal:
        frame_ready(np.ndarray)  — frame BGR siap diproses
        status_changed(str)      — "CONNECTED" / "DISCONNECTED"
    """
    frame_ready    = pyqtSignal(object)   # np.ndarray
    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self):
        self._running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', VIDEO_PORT))
        server.listen(1)
        server.settimeout(1.0)
        logger.info(f"[RECV] Menunggu stream dari Raspi di port {VIDEO_PORT}")

        while self._running:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"[RECV] Accept error: {e}")
                continue

            logger.info(f"[RECV] Raspi terhubung dari {addr}")
            self.status_changed.emit("CONNECTED")

            try:
                while self._running:
                    raw_len = self._recv_exact(conn, 4)
                    if raw_len is None:
                        break
                    length = struct.unpack('>I', raw_len)[0]
                    if length > 5_000_000:   # sanity check (>5MB reject)
                        logger.warning(f"[RECV] Frame terlalu besar: {length} bytes")
                        break
                    data = self._recv_exact(conn, length)
                    if data is None:
                        break
                    frame = cv2.imdecode(
                        np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        self.frame_ready.emit(frame)
            except Exception as e:
                logger.warning(f"[RECV] Koneksi Raspi terputus: {e}")
            finally:
                conn.close()
                self.status_changed.emit("DISCONNECTED")
                logger.info("[RECV] Raspi disconnect — menunggu koneksi baru...")

        server.close()
        logger.info("[RECV] FrameReceiver dihentikan.")

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
        buf = b''
        while len(buf) < n:
            try:
                chunk = sock.recv(n - len(buf))
            except Exception:
                return None
            if not chunk:
                return None
            buf += chunk
        return buf

    def stop(self):
        self._running = False
