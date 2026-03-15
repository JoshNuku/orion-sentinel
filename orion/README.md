# Project ORION - Sentinel Device

**AI-Powered Surveillance System with Automatic Cloud Tunneling**

## 🎯 Features

- **Dual-Mode Operation**: Low-power sentry mode + active intruder detection
- **AI Threat Detection**: MindSpore/ONNX model for heavy machinery detection
- **Automatic Ngrok Tunneling**: Public video streaming without manual setup
- **Audio-First Design**: Microphone (MAX9814 + ADS1115) and GPS tracking
- **Backend Integration**: Real-time alerts and device registration
- **Modular Architecture**: Clean separation of concerns

## 📁 Project Structure

```
orion/
├── main.py                    # Main orchestrator
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── modules/
    ├── __init__.py           # Package init
    ├── config.py             # Configuration settings
    ├── hardware.py           # GPIO, GPS, Camera
    ├── ai_engine.py          # AI inference
    ├── communication.py      # Backend API
    └── web_server.py         # Flask + Ngrok
```

## 🚀 Installation

### 1. Clone/Copy Project

```bash
cd /home/josh/Documents/terra-sentry/orion
```

### 2. Install Dependencies

```bash
# Activate virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure Settings

Edit `modules/config.py`:

```python
DEVICE_ID = "ORN-001"              # Your device ID
BACKEND_URL = "http://192.168.1.100:5000/api"  # Your backend URL
# Audio-first mode: microphone connected via ADS1115 ADC (see docs)
```

### 4. Place AI Model

Put your trained model in the project root:

- `orion_detector.ms` (MindSpore) OR
- `orion_detector.onnx` (ONNX)

### 5. Enable Hardware

```bash
# Enable serial for GPS
sudo raspi-config nonint do_serial 2

# Enable I2C for sensors (if needed)
sudo raspi-config nonint do_i2c 0

# Enable camera
sudo raspi-config nonint do_camera 0

# Reboot
sudo reboot
```

## ▶️ Usage

### Run the Sentinel

```bash
cd /home/josh/Documents/terra-sentry/orion
python3 main.py
```

### Expected Output

```
============================================================
PROJECT ORION - SENTINEL DEVICE
Device ID: ORN-001
============================================================
✅ GPIO sensors initialized
✅ GPS tracker initialized (mock mode)
🚇 NGROK TUNNEL: https://abc123.ngrok.io
🌐 Video server started on port 8080
🌍 Registering with Stream URL: https://abc123.ngrok.io/stream
✅ Device registered successfully
✅ SYSTEM ONLINE - ENTERING SENTRY MODE
💤 SENTRY MODE: Monitoring sensors...
```

# Project ORION — Consolidated Guide

This README consolidates device setup, hardware wiring, software structure,
and developer notes for the audio-first ORION sentinel.

Overview
- Audio-first edge sentinel using MAX9814 (mic amp) -> ADS1115 (I2C ADC) to
  detect Excavator/Chainsaw/Speech, trigger camera confirmation and send
  alerts to a backend.

Key components
- Microphone: MAX9814 (analog) -> ADS1115 AIN (or attach a driver for USB mic)
- ADC: ADS1115 (I2C) — sample at a practical ADC poll rate and resample for
  analysis
- GPS: u-blox NEO-7M (serial NMEA) — use the `SerialGPSDriver` provided
- Camera: Raspberry Pi CSI or USB webcam (OpenCV)
- Vision: YOLOv3-tiny (OpenCV DNN) for visual confirmation

Repository layout (important files)
- `main.py` — Orchestrator and state machine
- `modules/config.py` — Single source of configuration
- `modules/hardware.py` — Camera manager, `MicrophoneMonitor` (buffer + sim)
- `modules/ai_engine.py` — Compatibility wrapper for split AI modules
- `modules/ai_audio.py` — AudioIntelligenceUnit (rule-based FFT heuristics)
- `modules/ai_vision.py` — IntelligenceUnit (YOLOv3-Tiny wrapper)
- `modules/communication.py` — Backend requests
- `modules/hardware_components/` — Driver interfaces and examples

Quick start
1. Create and activate a venv, then install requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r orion/requirements.txt
```

2. Enable Pi interfaces (if using Raspberry Pi hardware):

```bash
sudo raspi-config nonint do_serial 2   # enable serial
sudo raspi-config nonint do_i2c 0      # enable i2c
sudo raspi-config nonint do_camera 0   # enable camera (if using CSI)
sudo reboot
```

3. Wire hardware:
- MAX9814 OUT -> ADS1115 A1
- ADS1115 VCC -> 3.3V, GND -> GND, SDA/SCL -> I2C pins
- NEO-7M TX -> Pi RX (GPIO15/ttyAMA0), RX -> Pi TX (GPIO14)

4. Start the sentinel:

```bash
cd /home/josh/Documents/terra-sentry/orion
python3 main.py
```

Driver integration
- `orion/modules/hardware_components/mic_driver.py` contains `MicDriverBase` and
  `ADS1115Driver` that can initialize ADS1115 for you. Attach with:

```py
from orion.modules.hardware import MicrophoneMonitor
from orion.modules.hardware_components.mic_driver import ADS1115Driver

mic = MicrophoneMonitor()
driver = ADS1115Driver(channel=config.MIC_CHANNEL)
mic.set_driver(driver)
mic.initialize()
mic.start_monitoring()
```

- GPS: `orion/modules/hardware_components/gps_driver.py` provides
  `SerialGPSDriver` that opens a serial port and parses NMEA via `pynmea2`.
  Attach/replace the `GPSTracker` with a wrapper that calls the driver's
  `get_location()`.

Notes on the NEO-7M (u-blox)
- The NEO-7M outputs NMEA sentences over UART. Typical settings:
  - Baud: 9600 (default)
  - Interface: TX->Pi RX0 (ttyAMA0) if using GPIO serial
- Use `pynmea2` to parse sentences and extract latitude/longitude. The
  provided `SerialGPSDriver` will attempt to read and return a valid fix.

AI and detection flow
- The system listens in SENTRY mode using `MicrophoneMonitor.get_audio_clip()`
  and runs `AudioIntelligenceUnit.infer()` to detect suspicious sounds.
- On detection (Excavator/Chainsaw), the sentinel enters confirmation mode:
  camera is started and `IntelligenceUnit` (YOLO) attempts visual verification.
- Alerts are sent via `Communicator.send_alert()` with payload containing
  `sentinelId`, `threatType`, `confidence`, `location`, `timestamp`, and
  optional `imageData`/`streamUrl`.

Testing without hardware
- Use `MicrophoneMonitor.load_simulation(wav_path)` to stream a WAV into the
  ADC buffer and exercise detection paths. See `orion/test_audio.py` for a
  replay harness.

Single README policy
- Auxiliary documentation in this repository has been consolidated here.
  If you have a specific section you'd like expanded (backend integration,
  or hardware wiring diagrams), tell me and I'll add it.

Next steps you may want
- Integrate ADS1115Driver into `main.py` startup (I can do this for you).
- Replace the mock `GPSTracker` with the `SerialGPSDriver` wrapper.
- Add a small test that replays labeled WAVs and asserts expected alerts.

---

For full developer details, see `orion/modules` code and the `hardware_components`
package for driver examples.
