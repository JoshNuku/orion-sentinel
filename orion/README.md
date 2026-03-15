# Project ORION — Sentinel Device

Audio-first, lightweight edge sentinel that listens for suspicious sounds
(Excavator, Chainsaw, Speech), confirms with a camera, and posts alerts
to a backend.

## Key features

- Audio-first trigger pipeline (MAX9814 analog mic + ADS1115 ADC)
- Lightweight rule-based audio detector (FFT heuristics) with optional
  visual confirmation via YOLO (OpenCV DNN)
- Modular drivers for ADS1115 and NEO‑7M GPS
- Flask-based local server + optional ngrok tunnel for remote streaming

---

## Repository layout (important files)

```text
orion/
├── main.py                         # Thin runner -> modules.orchestrator.OrionSentinel
├── requirements.txt                # Python dependencies
├── README.md                       # This file (cleaned)
└── modules/
    ├── __init__.py
    ├── config.py                   # Single-source config (MODEL paths, audio thresholds)
    ├── hardware.py                 # CameraManager, MicrophoneMonitor, GPSTracker wrapper
    ├── ai/                         # AI package
    │   ├── audio.py                # AudioIntelligenceUnit (FFT heuristics)
    │   └── vision.py               # IntelligenceUnit (YOLO wrapper)
    ├── ai_engine.py                # Compatibility wrapper (old import paths)
    ├── communication.py            # Communicator (backend API calls)
    ├── web_server.py               # Flask video server + optional ngrok tunnel
    └── hardware_components/        # Driver interfaces and examples (ADS1115, GPS)
```

---

## Quick start — Developer / Pi

### Step 1 — Create a virtualenv and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r orion/requirements.txt
```

Note: hardware-related packages (`adafruit-blinka`, `adafruit-circuitpython-ads1x15`,
`pyserial`, `pynmea2`) are listed in `requirements.txt`. Install them only on
the Pi or when you intend to attach the real hardware.

### Step 2 — Enable Pi interfaces (if running on Raspberry Pi)

```bash
sudo raspi-config nonint do_serial 2   # enable serial
sudo raspi-config nonint do_i2c 0      # enable i2c
sudo raspi-config nonint do_camera 0   # enable camera
sudo reboot
```

### Step 3 — Configure basic settings

Edit `modules/config.py` and set your backend URL and device id. Important
keys (examples):

```py
DEVICE_ID = "ORN-001"
BACKEND_URL = "https://your-backend/api"
# Model paths (relative to project root)
YOLO_WEIGHTS = "model/yolov3-tiny.weights"
YOLO_CONFIG = "model/yolov3-tiny.cfg"
YOLO_CLASSES = "model/coco.names"

# Audio sampling & detection
MIC_ADC_SAMPLE_RATE = 200          # ADS1115 poll rate (Hz)
MIC_SAMPLE_RATE = 16000            # analysis sample rate (resampled)
MIC_BUFFER_DURATION = 1.5          # seconds of audio buffered for inference
```

### Step 4 — Place vision model files (if using vision)

- `model/yolov3-tiny.weights`
- `model/yolov3-tiny.cfg`
- `model/coco.names`

The audio detector is model-free (rule-based) so it works without any
ONNX/MindSpore models; however the vision confirmation requires the above
YOLO files or an equivalent model referenced in `modules/config.py`.

### Step 5 — Start the sentinel (dev)

```bash
cd /home/josh/Documents/terra-sentry/orion
python3 main.py
```

---

## Driver integration examples

Attach an ADS1115 driver to `MicrophoneMonitor`:

```py
from modules import config
from modules.hardware import MicrophoneMonitor
from modules.hardware_components.mic_driver import ADS1115Driver

mic = MicrophoneMonitor()
driver = ADS1115Driver(channel=config.MIC_CHANNEL)
mic.set_driver(driver)
mic.initialize()
mic.start_monitoring()
```

Attach the serial GPS driver (NEO‑7M):

```py
from modules.hardware_components.gps_driver import SerialGPSDriver
gps = SerialGPSDriver(port="/dev/ttyAMA0", baudrate=9600)
gps.initialize()
loc = gps.get_location()
```

---

## Alert payload (example)

The communicator posts alerts to `{BACKEND_URL}/alerts` with JSON like:

```json
{
  "sentinelId": "ORN-001",
  "threatType": "chainsaw",
  "confidence": 0.87,
  "location": {"lat": 5.6037, "lon": -0.1870},
  "timestamp": "2026-03-15T12:34:56Z",
  "streamUrl": "https://your-ngrok-url.ngrok.io/stream",
  "imageData": "<base64-jpeg>",
  "triggerType": "microphone",
  "triggeredSensors": ["microphone"]
}
```

Backend implementers should accept optional `streamUrl` and `imageData`.

---

## Model & config notes

- The audio detector uses FFT-based heuristics and is configured from
  `modules/config.py` (band cutoffs and `AUDIO_DETECTION` thresholds).
- The vision pipeline uses the YOLO files referenced in config—set the
  correct file paths in `YOLO_WEIGHTS`, `YOLO_CONFIG`, and `YOLO_CLASSES`.
- If you prefer to deploy with ONNX models, point config to your ONNX file
  and ensure `modules/ai/vision.py` can load it (OpenCV DNN supports ONNX).

---

## Calibration & tuning (audio)

Use the replay harness to tune thresholds on your workstation or Pi:

1. Generate or collect a WAV that contains the target sound (chainsaw, excavator).
1. Resample/prepare a WAV and run the harness:

```bash
# Example: replay a test WAV through the audio detector
python3 orion/test_audio.py path/to/test_sound.wav
```

1. Tune values in `modules/config.py` under `AUDIO_DETECTION` and
   `MIC_*` constants until detection sensitivity/false-positive rate are
   acceptable on real hardware.

Calibration tips:

- Record real device ADC outputs (use short WAVs and convert to ADC-like range)
- Adjust `MIC_ADC_SAMPLE_RATE` (ADS1115 poll) for reliable sampling without
  saturating I2C; buffer at ADC rate and resample to `MIC_SAMPLE_RATE`.
- Use `MIC_BUFFER_DURATION` to control temporal context used by the FFT.

---

## ngrok & security

- To enable ngrok public tunnels set the `NGROK_TOKEN` environment variable
  and enable `NGROK_ENABLED` in `modules/config.py`.
- Be aware that exposing a camera stream publicly has privacy/security
  implications. If you deploy to production, prefer a secure VPN or
  configure your backend to pull the stream via a secure channel.

---

## Troubleshooting

- Camera not opening: ensure the camera is enabled (`raspi-config`) and
  that the user has camera permissions. Test with `ffmpeg`/`libcamera`.
- I2C/ADS1115 errors: verify I2C is enabled and `i2cdetect -y 1` shows
  a device (0x48 typical). Ensure correct wiring and 3.3V power.
- Serial GPS: ensure the serial port is enabled and not used by console.
- ai_engine / model load failures: check file paths in `modules/config.py`
  and that model files exist and are readable.
- Increase logging by setting Python logging to `DEBUG` (see `main.py`)

---

## Running tests / simulation

- Use `orion/test_audio.py` to replay WAVs for offline tuning. Mock the
  `Communicator` when writing unit tests to verify payloads without network.

---

## Contributing & license

If you'd like me to add a `CONTRIBUTING.md` or apply a license header,
tell me which license you prefer (MIT/Apache-2.0/etc.) and I'll add it.

---

If you'd like, I can also:

- Split hardware dependencies into an `extras` group or separate
  `requirements-hw.txt` so non-hardware developers can install minimal deps.
- Add wiring diagrams or a small image for physical connections.
