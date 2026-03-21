# Raspberry Pi (Sentinel) — Integration Guide for Project ORION

Purpose: document exactly what the backend/web needs from a Raspberry Pi (Sentinel) implementation so you can rebuild the Pi code and remain fully compatible with the web/dashboard.

-- Summary of what the web (backend) expects
- HTTP endpoints the Pi must call (outbound to backend)
- HTTP control endpoints the Pi should expose (so backend can call the Pi)
- Real-time events the backend emits (for dashboards)
- Payload formats, size limits, and examples
- Quick setup, dependencies and test commands

---

## 1) Key backend endpoints (Pi → Backend)
Base backend API prefix: `https://<BACKEND_HOST>/api`

- Register / update sentinel (call on startup and when stream created)
  - POST /api/sentinels/register
  - Body JSON:

```json
{
  "deviceId": "ORN-001",
  "location": { "lat": -12.3456, "lng": 45.6789 },
  "batteryLevel": 92,
  "ipAddress": "10.0.0.5",
  "status": "ACTIVE",
  "streamUrl": "https://<ngrok>.ngrok.io/stream",
  "triggerType": "ai"
}
```

- Heartbeat (called every ~60s)
  - PUT /api/sentinels/:deviceId/status
  - Body JSON (send what changed):

```json
{
  "status": "ACTIVE",
  "location": { "lat": -12.3456, "lng": 45.6789 },
  "batteryLevel": 91,
  "triggerType": "ai"
}
```

- Create alert (detection event)
  - POST /api/alerts
  - Important: backend accepts JSON bodies up to 10MB. If sending images as base64, keep them reasonably small (recommended < 3–4MB).
  - Body JSON:

```json
{
  "sentinelId": "ORN-001",
  "threatType": "person",        
  "confidence": 0.87,            
  "location": { "lat": -12.3456, "lng": 45.6789 },
  "timestamp": "2026-03-21T12:34:56.000Z",
  "imageData": "<base64-jpeg>",      
  "triggerType": "ai",
  "triggeredSensors": ["mic", "gpio4"]
}
```

- Optional: When the dashboard requests keep-alive, the backend will POST to the Pi at `/stream/keepalive`. Implement a handler for that.

---

## 2) Control endpoints the Pi should expose (Backend → Pi)
The backend expects to be able to call the Pi directly (using the sentinel.streamUrl base). Implement these simple endpoints on the Pi HTTP server:

- GET /status
  - Response JSON example:

```json
{
  "mode": "SENTRY",               
  "camera_active": true,
  "ai_loaded": true,
  "stream_idle_seconds": 5
}
```

- POST /control/activate
  - Switch camera/AI to active intruder-detection mode. Return JSON {"mode": "INTRUDER"}

- POST /control/deactivate
  - Return to low-power / SENTRY mode. Return JSON {"mode": "SENTRY"}

- POST /control/request_stream
  - Trigger creation of a public tunnel/stream (e.g., start ngrok and publish a URL). When a stream URL is available, the Pi should call backend POST /api/sentinels/register (update) with the `streamUrl` field.

- POST /stream/keepalive
  - Called by backend when a dashboard is viewing stream. Should reset any stream idle timer to prevent auto-stop.

- GET /stream
  - Provide MJPEG / multipart streaming at this path if using ngrok or direct proxying. The backend stream proxy expects the `streamUrl` to end with `/stream` for ngrok URLs.

Notes:
- The backend uses the stream base (streamUrl.replace('/stream', '')) to call the control endpoints. For example, if streamUrl is https://abc.ngrok.io/stream, backend will call https://abc.ngrok.io/control/activate.
- When responding to backend fetches, include header `ngrok-skip-browser-warning: true` handling is not required by the Pi but backend sets it when calling ngrok tunnels.

---

## 3) Real-time events the backend emits (for dashboards)
The Pi does not need to implement WebSocket for dashboard—this is just for your awareness so you can align behaviours.

- WebSocket events (Socket.io) the backend emits:
  - `connected` — server connection confirmation
  - `new-alert` — when backend saves an alert (payload: { alert, sentinel })
  - `alert-verified` — when an operator verifies an alert ({ alertId, isVerified })
  - `sentinel-status-update` — when sentinel status or heartbeat changes ({ deviceId, status, batteryLevel?, location? })

The Pi should ensure it updates the DB via the heartbeat and register endpoints so the dashboard receives those `sentinel-status-update` broadcasts.

---

## 4) Important payload rules & validations
- `deviceId` format: uppercase string matching ORN-xxx (e.g., ORN-001). Backend models call `.toUpperCase()` internally.
- `confidence`: float between 0 and 1 inclusive.
- `location`: object with numeric `lat` and `lng` fields.
- Image handling: PUT base64 JPEG in `imageData` when creating an alert. Keep size under backend limit (10MB); recommended <4MB.
- Heartbeat frequency: call PUT /api/sentinels/:deviceId/status every ~60 seconds.

---

## 5) Minimal Pi server implementation suggestions (Python)

- Recommended Python packages (example requirements.txt):

```
flask>=2.0
flask-cors
requests
opencv-python
numpy
gunicorn
```

- Environment variables (example):
  - BACKEND_URL=https://your-backend.example.com
  - DEVICE_ID=ORN-001
  - LOCATION_LAT=-12.3456
  - LOCATION_LNG=45.6789

### Sample functions

Register / update (call on startup or when streamUrl becomes available):

```python
import os
import requests

BACKEND = os.environ['BACKEND_URL']
DEV = os.environ['DEVICE_ID']

def register(stream_url=None, battery=100):
    payload = {
        'deviceId': DEV,
        'location': {'lat': float(os.environ['LOCATION_LAT']), 'lng': float(os.environ['LOCATION_LNG'])},
        'batteryLevel': battery,
        'ipAddress': '192.168.1.5',
        'streamUrl': stream_url
    }
    r = requests.post(f"{BACKEND}/api/sentinels/register", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()

def heartbeat(status='ACTIVE', battery=95):
    payload = {'status': status, 'batteryLevel': battery}
    r = requests.put(f"{BACKEND}/api/sentinels/{DEV}/status", json=payload, timeout=10)
    return r.status_code == 200

def send_alert(threat, confidence, lat, lng, image_b64=None):
    payload = {
        'sentinelId': DEV,
        'threatType': threat,
        'confidence': confidence,
        'location': {'lat': lat, 'lng': lng},
        'imageData': image_b64
    }
    r = requests.post(f"{BACKEND}/api/alerts", json=payload, timeout=15)
    return r
```

---

## 6) Quick test commands

- Register test (curl):

```bash
curl -X POST "${BACKEND_URL}/api/sentinels/register" \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"ORN-001","location":{"lat":-12.34,"lng":45.67},"batteryLevel":100}'
```

- Send a sample alert (no image):

```bash
curl -X POST "${BACKEND_URL}/api/alerts" \
  -H "Content-Type: application/json" \
  -d '{"sentinelId":"ORN-001","threatType":"person","confidence":0.9,"location":{"lat":-12.34,"lng":45.67}}'
```

---

## 7) Troubleshooting & tips
- Backend body size: server accepts up to 10MB JSON. If you need larger images, upload to S3 or reduce resolution before encoding.
- Use ngrok for development public streams. Ensure the `streamUrl` uses the `/stream` path for backend compatibility (backend will `replace('/stream','')` when calling control endpoints).
- When backend calls your Pi endpoints, it may set header `ngrok-skip-browser-warning: true`. Support it if you implement middleware that checks headers.
- Keep heartbeats frequent enough (60s) so the backend doesn't mark device inactive (90s offline threshold).

---

## 8) Next steps I can help with
- Add a concrete Python example server (Flask) that exposes the required control endpoints and a simple MJPEG stream handler.
- Provide a ready-to-run `requirements.txt` and a minimal `app.py` with register/heartbeat/alert sample flows.

If you want that, tell me which language/framework you prefer (Flask, FastAPI, Node/Express) and I'll scaffold it.
