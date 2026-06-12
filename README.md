          # 🥚 EggApp — Panduan Lengkap Setup & Menjalankan

Sistem deteksi telur retak dua-node:  
**Raspberry Pi 5** (kamera + servo) ↔ **Laptop RTX 4060** (YOLOv8 inference + GUI)

---

## 📂 Struktur File

```
eggapp/
├── raspi/
│   ├── raspi_app.py          ← Entry point Raspi
│   ├── camera_streamer.py
│   ├── stream_sender.py
│   ├── result_receiver.py
│   ├── servo_controller.py
│   ├── config.py
│   ├── .env
│   ├── requirements_raspi.txt
│   └── logs/
│
└── pc/
    ├── pc_app.py             ← Entry point Laptop
    ├── frame_receiver.py
    ├── result_sender.py
    ├── yolo_engine.py
    ├── config.py
    ├── .env
    ├── requirements_pc.txt
    ├── models/
    │   └── best.pt           ← Letakkan model YOLO di sini
    └── logs/
```

---

## 🌐 Topologi Jaringan (USB OTG Ethernet Tethering)

```
Raspberry Pi 5  ←──USB-C──→  Laptop Windows/Linux
192.168.137.2                  192.168.137.1

Port 9999 : Laptop LISTEN ← Raspi kirim stream JPEG
Port 9998 : Raspi LISTEN  ← Laptop kirim JSON hasil
```

### Setup IP Statis (Windows — ICS)

1. Hubungkan USB-C Raspi ke laptop.
2. Di Windows: **Settings → Network → USB Ethernet → Properties → IPv4**  
   Set IP `192.168.137.1` / Mask `255.255.255.0`
3. Di Raspi: edit `/etc/dhcpcd.conf`
   ```
   interface usb0
   static ip_address=192.168.137.2/24
   static routers=192.168.137.1
   static domain_name_servers=8.8.8.8
   ```
4. Restart: `sudo systemctl restart dhcpcd`
5. Test: `ping 192.168.137.1` dari Raspi → harus reply

---

## 🍓 BAGIAN 1 — Setup Raspberry Pi 5

### 1.1 Update & Install sistem

```bash
sudo apt update && sudo apt upgrade -y

# Picamera2 (WAJIB via apt, bukan pip)
sudo apt install -y python3-picamera2

# pigpio daemon untuk servo hardware PWM
sudo apt install -y pigpio python3-pigpio

# Qt6 dependencies
sudo apt install -y python3-pyqt6 libqt6widgets6

# pip & venv
sudo apt install -y python3-pip python3-venv
```

### 1.2 Buat virtual environment

```bash
cd ~/eggapp/raspi
python3 -m venv venv --system-site-packages
# PENTING: --system-site-packages agar picamera2 (apt) bisa diakses

source venv/bin/activate
```

### 1.3 Install Python dependencies

```bash
pip install -r requirements_raspi.txt
```

### 1.4 Enable Interface kamera

```bash
sudo raspi-config
# Pilih: Interface Options → Camera → Enable
# Reboot setelah enable
sudo reboot
```

### 1.5 Verifikasi servo + kamera

```bash
# Test pigpiod
sudo usermod -aG gpio admin


# Test kamera
python3 -c "from picamera2 import Picamera2; c=Picamera2(); print('Kamera OK:', c.sensor_modes[0]); c.close()"

# Test servo cepat (pin 14)
python3 -c "
import lgpio, time
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, 14)
print('IDLE...')
lgpio.tx_pwm(h, 14, 50, 7.5)   # 1500µs = 90°
time.sleep(1)
print('TERIMA...')
lgpio.tx_pwm(h, 14, 50, 12.5)  # 2500µs = 180°
time.sleep(1)
print('TOLAK...')
lgpio.tx_pwm(h, 14, 50, 2.5)   # 500µs = 0°
time.sleep(1)
lgpio.tx_pwm(h, 14, 50, 0)
lgpio.gpiochip_close(h)
print('OK')
"
```


### 1.7 Edit konfigurasi `.env`

```bash
nano ~/eggapp/raspi/.env
```

```env
LAPTOP_IP=192.168.137.1    # ← IP laptop
VIDEO_PORT=9999
RESULT_PORT=9998
SERVO_PIN=14               # ← GPIO BCM pin servo
CAM_WIDTH=640
CAM_HEIGHT=480
CAM_FPS=30
JPEG_QUALITY=80
LOG_LEVEL=INFO
```

---

## 💻 BAGIAN 2 — Setup Laptop (Windows/Linux + RTX 4060)

### 2.1 Install Python 3.11+

Download dari [python.org](https://python.org) — centang **Add to PATH**.

### 2.2 Buat virtual environment

```bash
# Windows (PowerShell)
cd C:\eggapp\pc
python -m venv venv
.\venv\Scripts\activate

# Linux
cd ~/eggapp/pc
python3 -m venv venv
source venv/bin/activate
```

### 2.3 Install PyTorch CUDA 12.1

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Verifikasi CUDA:

```python
python -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0))"
# Output: CUDA: True | GPU: NVIDIA GeForce RTX 4060
```

### 2.4 Install dependencies lainnya

```bash
pip install -r requirements_pc.txt
```

### 2.5 Letakkan model YOLO

```bash
# Salin file best.pt ke folder models/
cp /path/to/best.pt C:\eggapp\pc\models\best.pt

# Cek nama kelas model:
python -c "from ultralytics import YOLO; m=YOLO('models/best.pt'); print(m.names)"
```

> **Penting:** Sesuaikan `CLASS_DECISION` di `config.py` dengan nama kelas yang muncul.  
> Contoh output: `{0: 'telur_baik', 1: 'telur_retak'}` → sudah sesuai default.

### 2.6 Edit konfigurasi `.env`

```env
RASPI_IP=192.168.137.2    # ← IP Raspi
VIDEO_PORT=9999
RESULT_PORT=9998
MODEL_PATH=models/best.pt
CONF_THRESH=0.6
LOG_LEVEL=INFO
```

---

## ▶️ BAGIAN 3 — Menjalankan Sistem

### ⚠️ Urutan Start (PENTING)

```
1. Laptop terlebih dahulu → 2. Raspberry Pi
```

Laptop harus listen di port 9999 sebelum Raspi mulai connect.

---

### 3.1 Jalankan Laptop (pc_app.py)

```bash
# Windows
cd C:\eggapp\pc
.\venv\Scripts\activate
python pc_app.py

# Linux
cd ~/eggapp/pc
source venv/bin/activate
python pc_app.py
```

GUI akan terbuka dan langsung listen di port 9999.  
Log: `[RECV] Menunggu koneksi Raspi di port 9999`

---

### 3.2 Jalankan Raspberry Pi (raspi_app.py)

```bash
# Di Raspi (via SSH atau terminal langsung)
cd ~/eggapp/raspi
sudo pigpiod          # ← pastikan pigpiod running
source venv/bin/activate
python raspi_app.py
```

GUI Raspi terbuka. Klik tombol **▶ Start Stream**.

---

### 3.3 Mulai Inferensi di Laptop

Di GUI laptop, klik tombol **▶ Running**.

Model YOLO dimuat (pertama kali ~5-10 detik), lalu inferensi berjalan otomatis.

---

## 🖥️ Panduan GUI

### GUI Raspberry Pi

| Elemen | Fungsi |
|--------|--------|
| **▶ Start Stream** | Aktifkan kamera + mulai stream ke laptop |
| **■ Stop Stream** | Hentikan semua thread |
| **↺ Reset Servo** | Kembalikan servo ke posisi IDLE (90°) |
| Preview kamera | Tampilan live Pi Camera V2 |
| Status Servo | IDLE / DITERIMA / DITOLAK (warna berbeda) |
| Koneksi Laptop | ● TERHUBUNG (hijau) / ● TIDAK TERHUBUNG (merah) |
| Counter | Total diterima & ditolak |

### GUI Laptop

| Elemen | Fungsi |
|--------|--------|
| **▶ Running** | Mulai/stop inferensi YOLO |
| **Show** | Tampilkan info koneksi & model |
| **📷 Capture** | Simpan screenshot frame terakhir |
| Video Utama | Frame live + bounding box YOLO |
| RGB Feed | Thumbnail frame mentah dari Raspi |
| Depth/False Color | Colormap JET untuk visualisasi |
| Mask/Edge | Hasil Canny edge detection |
| Info bar | FPS, Confidence, Center Coordinate, Status |

---

## 🔌 Wiring Servo SG90

```
SG90          Raspberry Pi 5
─────         ────────────────
Merah  ──────→ Pin 4  (5V)
Coklat ──────→ Pin 6  (GND)
Oranye ──────→ Pin 23 (GPIO 14, BCM)
```

> Jika servo butuh arus lebih besar, gunakan power supply 5V eksternal.  
> Sambungkan GND eksternal ke GND Raspi.

---

## 🐛 Troubleshooting

### Servo tidak bergerak
```bash
# Pastikan pigpiod running
sudo pigpiod
pigs r 14   # baca status pin 14
```

### Kamera tidak terdeteksi
```bash
vcgencmd get_camera   # supported=1 detected=1
libcamera-hello --list-cameras
```

### "pigpiod tidak berjalan"
```bash
sudo systemctl start pigpiod
sudo systemctl enable pigpiod   # agar otomatis saat boot
```

### CUDA tidak terdeteksi di laptop
```bash
nvidia-smi   # cek versi driver
python -c "import torch; print(torch.version.cuda)"
# Pastikan versi CUDA torch sesuai driver
```

### Port sudah digunakan
```bash
# Linux
sudo lsof -i :9999
sudo kill -9 <PID>

# Windows
netstat -ano | findstr :9999
taskkill /PID <PID> /F
```

### Frame terputus / FPS rendah
- Kurangi resolusi kamera: set `CAM_WIDTH=320`, `CAM_HEIGHT=240` di `.env` Raspi
- Kurangi kualitas JPEG: set `JPEG_QUALITY=60`
- Cek kabel USB-C (gunakan USB 3.0)

### JSON tidak diterima Raspi
- Pastikan firewall laptop mengizinkan port 9998 inbound
- Windows: `netsh advfirewall firewall add rule name="EggApp" dir=in action=allow protocol=TCP localport=9998,9999`

---

## 🔁 Alur Data Lengkap

```
Pi Camera V2
     │ frame RGB
     ▼
CameraStreamer (QThread)
     │ JPEG bytes → queue
     ▼
StreamSenderThread ──TCP:9999──→ FrameReceiverThread (Laptop)
                                       │ np.ndarray BGR
                                       ▼
                               YoloInferenceThread
                                       │ (YoloEngine: infer + panels)
                                       ▼
                               pc_app MainWindow (GUI update)
                                       │ result dict
                                       ▼
                               ResultSenderThread ──TCP:9998──→ ResultReceiverThread (Raspi)
                                                                       │ JSON dict
                                                                       ▼
                                                               raspi_app MainWindow
                                                                       │
                                                               ServoWorker (QThread)
                                                                       │
                                                               ServoController (pigpio)
                                                                       │
                                                               SG90 Servo Motor
```

---

## ⚡ Tips Performa

| Setting | Default | Untuk Raspi lama / jaringan lambat |
|---------|---------|-------------------------------------|
| CAM_WIDTH | 640 | 320 |
| CAM_HEIGHT | 480 | 240 |
| CAM_FPS | 30 | 15 |
| JPEG_QUALITY | 80 | 60 |
| CONF_THRESH | 0.6 | 0.5 (lebih sensitif) |

---

*EggApp v1.0 — Raspberry Pi 5 + RTX 4060 + YOLOv8*
