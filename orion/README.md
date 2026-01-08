# Project ORION - Sentinel Device

**AI-Powered Surveillance System with Automatic Cloud Tunneling**

## 🎯 Features

- **Dual-Mode Operation**: Low-power sentry mode + active intruder detection
- **AI Threat Detection**: MindSpore/ONNX model for heavy machinery detection
- **Automatic Ngrok Tunneling**: Public video streaming without manual setup
- **Multi-Sensor Fusion**: PIR motion, vibration, GPS tracking
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
PIR_PIN = 17                        # Motion sensor GPIO
VIBRATION_PIN = 27                  # Vibration sensor GPIO
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

### Access Video Stream

- **Local**: `http://localhost:8080/stream`
- **Public**: Check logs for ngrok URL (e.g., `https://abc123.ngrok.io/stream`)

## 🔧 Hardware Wiring

### GPIO Sensors (BCM Numbering)

| Component            | Pi Pin | GPIO    | Notes             |
| -------------------- | ------ | ------- | ----------------- |
| PIR Sensor OUT       | 11     | GPIO 17 | Motion detection  |
| Vibration Sensor OUT | 13     | GPIO 27 | Vibration trigger |
| PIR/Vibration VCC    | 1      | 3.3V    | Power             |
| PIR/Vibration GND    | 6      | GND     | Ground            |

### GPS Module

| GPS | Pi Pin | GPIO           | Notes                       |
| --- | ------ | -------------- | --------------------------- |
| VCC | 1      | 3.3V           | Or 5V if module requires    |
| GND | 6      | GND            | Ground                      |
| TX  | 10     | GPIO 15 (RXD0) | GPS transmits → Pi receives |
| RX  | 8      | GPIO 14 (TXD0) | Pi transmits → GPS receives |

### Camera

- Use Raspberry Pi Camera Module (CSI) or USB webcam

## 🧠 AI Model

The system expects a YOLO-style object detection model trained on:

- **Classes**: JCB, Excavator (update in `config.py`)
- **Input Size**: 320x320 (update `INPUT_SIZE` if different)
- **Format**: MindSpore `.ms` or ONNX `.onnx`

### Model Output Expected

```python
# Should return list of detections:
[
    (class_name, confidence, bbox),
    ...
]
```

Update parsing logic in `ai_engine.py` if your model uses a different format.

## 🌐 Backend API

The sentinel expects the following endpoints:

### POST `/api/sentinels/register`

```json
{
  "deviceId": "ORN-001",
  "status": "active",
  "location": { "lat": 6.6745, "lng": -1.5716 },
  "batteryLevel": 85,
  "streamUrl": "https://abc123.ngrok.io/stream"
}
```

### POST `/api/alerts`

```json
{
  "sentinelId": "ORN-001",
  "threatType": "Excavator",
  "confidence": 0.95,
  "location": { "lat": 6.6745, "lng": -1.5716 },
  "timestamp": "2026-01-07T12:34:56.789Z"
}
```

### PUT `/api/sentinels/{deviceId}/status`

```json
{
  "status": "active",
  "location": { "lat": 6.6745, "lng": -1.5716 },
  "batteryLevel": 85
}
```

## 🐛 Troubleshooting

### No Video Stream

```bash
# Check camera
vcgencmd get_camera

# Test camera manually
raspistill -o test.jpg

# Check if port is in use
sudo lsof -i :8080
```

### Ngrok Fails

```bash
# Install ngrok separately if needed
pip install pyngrok

# Or use manual tunnel
ngrok http 8080
```

### GPIO Errors

```bash
# Check GPIO status
gpio readall

# Ensure user is in gpio group
sudo usermod -a -G gpio $USER
```

### AI Model Not Loading

- Check model file path in `config.py`
- Verify model format matches library (MindSpore vs ONNX)
- Check model input shape matches `INPUT_SIZE`

## 📝 Customization

### Add New Sensors

Edit `modules/hardware.py`:

```python
class GPIOSensors:
    def __init__(self):
        # Add your sensor pin
        GPIO.setup(NEW_SENSOR_PIN, GPIO.IN)

    def new_sensor_check(self):
        return GPIO.input(NEW_SENSOR_PIN)
```

### Change Detection Classes

Edit `modules/config.py`:

```python
CLASS_NAMES = ["JCB", "Excavator", "Bulldozer", "Crane"]
```

### Adjust Timing

Edit `modules/config.py`:

```python
ALERT_COOLDOWN = 60      # Alert every 60 seconds
STREAM_DURATION = 120    # Stay in intruder mode for 2 minutes
```

## 📄 License

MIT License - Feel free to use and modify

## 🆘 Support

For issues or questions:

1. Check logs for error messages
2. Verify hardware connections
3. Test components individually (GPS, camera, sensors)
4. Check backend connectivity

---

**Project ORION** - Securing sites with AI 🛡️
