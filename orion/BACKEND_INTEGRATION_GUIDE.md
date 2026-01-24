# ORION Sentinel - Complete Backend Integration Guide

**Version:** 1.0  
**Date:** January 8, 2026  
**Device ID:** ORN-001

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Operation Logic](#operation-logic)
3. [Backend API Endpoints](#backend-api-endpoints)
4. [Sentinel Control Endpoints](#sentinel-control-endpoints)
5. [Data Flow & Architecture](#data-flow--architecture)
6. [Implementation Examples](#implementation-examples)
7. [Battery Optimization](#battery-optimization)
8. [Error Handling](#error-handling)
9. [Security Considerations](#security-considerations)

---

## System Overview

### What is ORION Sentinel?

ORION is an AI-powered surveillance device running on Raspberry Pi 4 that:

- Detects threats using YOLOv4-Tiny (person, car, truck, motorcycle, bus)
- Streams live video via ngrok tunnel
- Operates in two modes: SENTRY (low-power monitoring) and INTRUDER (active AI detection)
- Automatically sends alerts to your backend when threats are detected
- Supports remote control from backend for on-demand monitoring

### System Modes

**SENTRY Mode (Default)**

- Low power consumption
- Camera OFF (battery saving)
- Monitors GPIO sensors (PIR, vibration) and microphone
- No AI detection running
- Automatically enters INTRUDER mode when sensors trigger

**INTRUDER Mode**

- Camera ON
- AI actively analyzing frames for threats
- Sends alerts to backend when threats detected
- Returns to SENTRY after timeout or manual deactivation

### Hardware Components

- **Camera:** USB/CSI camera (640x480 @ 15 FPS)
- **GPS:** Serial GPS module (4800 baud, currently mocked to Ghana coordinates)
- **Microphone:** ADS1115 ADC (channel A1, threshold 5000)
- **Sensors:** PIR motion sensor (GPIO 17), Vibration sensor (GPIO 27)
- **Connectivity:** WiFi + ngrok tunnel for public access

---

## Operation Logic

### State Machine Overview

The sentinel operates as a **state machine** with two primary modes:

```
┌─────────────────────────────────────────┐
│         SYSTEM STARTUP                  │
│  - Initialize hardware (GPIO, GPS, Mic) │
│  - Start Flask server + ngrok tunnel    │
│  - Register with backend                │
└──────────────┬──────────────────────────┘
               ↓
┌──────────────────────────────────────────┐
│         SENTRY MODE (Default)            │
│  • Camera: OFF                           │
│  • AI: Unloaded                          │
│  • Sensors: Active                       │
│  • Waiting for triggers...               │
└─────┬────────────────────────────────┬───┘
      │                                │
      │  Triggers:                     │
      │  - PIR sensor detects motion   │
      │  - Vibration sensor triggered  │
      │  - Microphone exceeds threshold│
      │  - Backend sends /control/activate
      │                                │
      ↓                                │
┌──────────────────────────────────────┐  │
│      INTRUDER MODE (Active)          │  │
│  • Camera: ON                        │  │
│  • AI: Loaded & analyzing            │  │
│  • Detecting threats every 0.1s      │  │
│  • Sending alerts when found         │  │
└─────┬────────────────────────────────┘  │
      │                                   │
      │  Exit conditions:                 │
      │  - 60s timeout (no threats)       │
      │  - Backend sends /control/deactivate
      │                                   │
      └───────────────────────────────────┘
```

### SENTRY Mode Operation

**What's Active:**

- ✅ GPIO sensors (PIR motion, vibration)
- ✅ Microphone (sound level monitoring)
- ✅ Web server (Flask + ngrok tunnel)
- ❌ Camera OFF (battery saving)
- ❌ AI model unloaded (memory saving)

**Main Loop (runs every 0.5s):**

```python
while mode == SENTRY:
    # Check remote control requests
    if backend_requested_intruder_mode:
        enter_intruder_mode()

    # Battery optimization: stop camera if idle
    if camera.is_active and stream_idle > 5_minutes:
        camera.release()  # Turn OFF

    # Check sensors
    if PIR_triggered or VIBRATION_triggered:
        enter_intruder_mode()

    # Check microphone
    if microphone.is_loud():  # Sound > threshold
        enter_intruder_mode()

    sleep(0.5)
```

### INTRUDER Mode Operation

**What's Active:**

- ✅ Camera ON
- ✅ AI model loaded (YOLOv4-Tiny)
- ✅ Frame analysis every 0.1 seconds
- ✅ All sensors still monitoring

**Main Loop (runs every 0.1s):**

```python
while mode == INTRUDER:
    # Check remote control requests
    if backend_requested_sentry_mode:
        enter_sentry_mode()

    # Capture and analyze frame
    frame = camera.capture_frame()
    threat, confidence = ai.analyze_frame(frame)

    # If threat found
    if threat and confidence >= 0.35:
        # Check cooldown (prevent spam)
        if time_since_last_alert >= 30_seconds:
            # Send alert in background thread
            send_alert_async(threat, confidence, frame)
            last_alert_time = now

    # Auto-return to SENTRY after timeout
    if time_since_last_alert > 60_seconds:
        enter_sentry_mode()

    sleep(0.1)  # 10 FPS detection rate
```

### AI Detection Process

**Frame Analysis Pipeline:**

```
1. Capture frame from camera (640x480)
   ↓
2. Preprocess: normalize, resize to 416x416
   ↓
3. Run YOLOv4-Tiny inference (~100-150ms)
   ↓
4. Parse detections (bounding boxes, confidence)
   ↓
5. Filter: confidence > 0.35
   ↓
6. Apply Non-Maximum Suppression (remove duplicates)
   ↓
7. Log ALL detections (debug mode)
   ↓
8. Filter for threat classes only
   - person, car, truck, motorcycle, bus
   ↓
9. Return highest confidence threat
```

**Example Detection Output:**

```
🔍 Detected 3 object(s):
   • chair: 72.5% at [120, 200, 80, 100]
   • bottle: 65.3% at [300, 150, 40, 90]
   • person: 87.5% at [180, 100, 120, 250]
⚠️ THREAT: person (87.5%)
```

### Alert Sending Process

**Non-Blocking Alert System:**

```
Main Thread              Alert Thread
     │                        │
     ├─ Detect threat         │
     ├─ Start alert thread ───┤
     ├─ Continue capturing    │
     │                        ├─ Encode frame (JPEG)
     ├─ Capture next frame    │
     │                        ├─ Convert to Base64
     ├─ Analyze frame         │
     │                        ├─ Build payload
     ├─ Detect threat         │
     │   (cooldown: skip)     ├─ POST /api/alerts
     ├─ Capture next frame    │
     │                        ├─ Wait for response
     ├─ Analyze frame         │
     │                        └─ Log result & exit
     └─ Continue...
```

**Why Async?** Network I/O takes 100-500ms. Async ensures camera never stops capturing frames.

### Camera Management Logic

**Smart On-Demand System:**

```
State 1: STARTUP
├─ Camera: OFF (battery saving)
└─ Waiting for trigger or stream request

State 2: STREAM REQUESTED
├─ GET /stream endpoint called
├─ Camera: Initializes automatically
├─ last_stream_access = now
└─ Serving video frames

State 3: KEEP-ALIVE ACTIVE
├─ Backend sends POST /stream/keepalive every 60s
├─ Resets last_stream_access timestamp
└─ Camera stays ON

State 4: IDLE TIMEOUT
├─ No stream access for 5+ minutes
├─ Camera: Releases automatically
├─ Returns to State 1
└─ Battery saved

State 5: SENSOR TRIGGER
├─ PIR/vibration/mic triggered
├─ Camera: Initializes for AI detection
└─ Enters INTRUDER mode
```

**Battery Impact:**

- Camera ON: ~2-5W power draw
- Camera OFF: ~0W power draw
- **Result:** 5-10x longer battery life

### Thread Architecture

The sentinel uses **4 concurrent threads:**

**1. Main Thread (Orchestrator)**

- Runs state machine (SENTRY ↔ INTRUDER)
- Polls sensors every 0.5s
- Controls mode transitions
- Captures and analyzes frames in INTRUDER mode

**2. Flask Thread (Web Server)**

- Serves video stream (`/stream`)
- Handles control endpoints (`/control/activate`, `/control/deactivate`)
- Always running in background
- Non-blocking, daemon thread

**3. Microphone Thread (Audio Monitor)**

- Continuously samples ADS1115 ADC
- Calculates baseline noise level
- Updates current sound level
- Main thread checks `is_loud()` method
- Daemon thread

**4. Alert Threads (Dynamic)**

- Created when threat detected
- Encodes frame to JPEG → Base64
- Sends POST request to backend
- Dies after completion
- Prevents blocking camera capture

### Timing Reference

```python
# Key intervals:

SENSOR_POLL_INTERVAL = 0.5s      # SENTRY mode loop
INTRUDER_LOOP = 0.1s             # Frame analysis rate (10 FPS)
AI_INFERENCE = 100-150ms         # Per frame on Pi 4
FRAME_CAPTURE = 20-50ms          # Camera read time
ALERT_SENDING = 100-500ms        # HTTP POST (async)

ALERT_COOLDOWN = 30s             # Min time between alerts
STREAM_DURATION = 60s            # Auto-timeout in INTRUDER
STREAM_TIMEOUT = 300s            # Camera auto-sleep (5 min)
HEARTBEAT_INTERVAL = 60s         # Status update frequency
```

### Example Timeline

**Scenario:** Motion detected → Person found → Alert sent → Timeout

```
T+0.0s:  [SENTRY] Polling sensors every 0.5s
T+0.5s:  [SENTRY] PIR sensor HIGH - motion detected!
T+0.6s:  [TRANSITION] Entering INTRUDER mode...
T+0.7s:  [INTRUDER] Camera initializing...
T+2.7s:  [INTRUDER] Camera warmup complete (2s delay)
T+2.8s:  [INTRUDER] Loading YOLOv4-Tiny model...
T+3.0s:  [INTRUDER] AI model loaded (23MB)
T+3.1s:  [INTRUDER] Backend status update: "alert"
T+3.2s:  [INTRUDER] Frame analysis loop started

T+3.3s:  Frame 1: chair (72%), bottle (65%) → No threats
T+3.4s:  Frame 2: person (87%), bottle (68%) → THREAT!
         └─ Start alert thread (async)
         └─ Continue capturing...
T+3.5s:  Frame 3: person (89%) → Cooldown active (29s left)
T+3.6s:  Frame 4: person (91%) → Cooldown active (28s left)
T+3.7s:  [ALERT THREAD] ✅ Backend received alert
         └─ Thread exits

... Continue detecting for 60 more seconds ...

T+63.4s: [INTRUDER] Timeout reached (60s since last threat)
T+63.5s: [TRANSITION] Returning to SENTRY mode...
T+63.6s: [SENTRY] AI model unloaded
T+63.7s: [SENTRY] Backend status update: "active"
T+63.8s: [SENTRY] Polling sensors every 0.5s
```

### Remote Control Override

Backend can bypass sensor triggers and directly control mode:

```
User Action: Opens webapp to view live feed

Frontend → Backend: "User wants to view Sentinel ORN-001"
    ↓
Backend → Sentinel: POST {streamUrl}/control/activate
    ↓
Sentinel: Sets remote_control_request = INTRUDER
    ↓
Next loop iteration: Checks request, enters INTRUDER mode
    ↓
Sentinel: Camera ON, AI loaded, detection active
    ↓
Frontend: Shows stream + AI detections
    ↓
Backend: Sends POST /stream/keepalive every 60s
    ↓
User closes webapp
    ↓
Backend → Sentinel: POST {streamUrl}/control/deactivate
    ↓
Sentinel: Sets remote_control_request = SENTRY
    ↓
Next loop iteration: Returns to SENTRY mode
    ↓
Sentinel: AI unloaded, camera auto-stops after 5 min idle
```

### Key Design Principles

**1. Battery Conservation**

- Camera OFF by default in SENTRY mode
- Only activate when needed (triggers or stream requests)
- Auto-sleep after 5 min idle

**2. Spam Prevention**

- 30-second cooldown between alerts
- One alert per threat event (not per frame)

**3. Non-Blocking I/O**

- Alert sending in background threads
- Camera never waits for network

**4. Fail-Safe Operation**

- Continue running even if backend unreachable
- Log errors, don't crash

**5. Resource Efficiency**

- Unload AI when not needed (saves 23MB RAM)
- Lightweight SENTRY loop (0.5s intervals)
- On-demand model loading

---

## Backend API Endpoints

These are the endpoints YOUR BACKEND must implement to receive data from the sentinel.

### 1. Device Registration

**Endpoint:** `POST http://192.168.1.100:5000/api/sentinels/register`

**When Called:**

- Once on sentinel startup
- Contains device ID, location, battery level, and public stream URL

**Request Payload:**

```json
{
  "deviceId": "ORN-001",
  "status": "active",
  "location": {
    "lat": 5.6,
    "lng": -0.19
  },
  "batteryLevel": 85,
  "streamUrl": "https://xxxx-xx-xx-xx-xx.ngrok-free.app/stream"
}
```

**Field Details:**

- `deviceId` (string): Unique sentinel identifier
- `status` (string): Always "active" on registration
- `location.lat` (float): Latitude coordinate
- `location.lng` (float): Longitude coordinate
- `batteryLevel` (integer): Battery percentage (0-100), currently fixed at 85
- `streamUrl` (string): Public ngrok URL for accessing video stream

**Expected Response:**

- Status: `200 OK` or `201 Created`
- The sentinel considers registration successful on these status codes

**Backend Actions:**

- Store sentinel info in database (update if already exists)
- Initialize sentinel status tracking
- Store stream URL for later use

**Example Implementation (Node.js/Express):**

```javascript
app.post("/api/sentinels/register", async (req, res) => {
  const { deviceId, status, location, batteryLevel, streamUrl } = req.body;

  // Upsert sentinel in database
  await Sentinel.findOneAndUpdate(
    { deviceId },
    {
      deviceId,
      status,
      location,
      batteryLevel,
      streamUrl,
      lastSeen: new Date(),
      isOnline: true,
    },
    { upsert: true, new: true }
  );

  console.log(`✅ Sentinel ${deviceId} registered with stream: ${streamUrl}`);

  res.status(201).json({
    message: "Sentinel registered successfully",
    deviceId,
  });
});
```

**Example Implementation (Python/Flask):**

```python
@app.route('/api/sentinels/register', methods=['POST'])
def register_sentinel():
    data = request.json

    # Upsert in database
    sentinel = db.sentinels.find_one_and_update(
        {'deviceId': data['deviceId']},
        {'$set': {
            'deviceId': data['deviceId'],
            'status': data['status'],
            'location': data['location'],
            'batteryLevel': data['batteryLevel'],
            'streamUrl': data['streamUrl'],
            'lastSeen': datetime.utcnow(),
            'isOnline': True
        }},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    print(f"✅ Sentinel {data['deviceId']} registered")

    return jsonify({
        'message': 'Sentinel registered successfully',
        'deviceId': data['deviceId']
    }), 201
```

---

### 2. Threat Alerts

**Endpoint:** `POST http://192.168.1.100:5000/api/alerts`

**When Called:**

- Whenever AI detects a threat (person, car, truck, motorcycle, bus)
- Cooldown: 30 seconds between alerts for same sentinel
- Only sent in INTRUDER mode

**Request Payload:**

```json
{
  "sentinelId": "ORN-001",
  "threatType": "person",
  "confidence": 0.87,
  "location": {
    "lat": 5.6,
    "lng": -0.19
  },
  "timestamp": "2026-01-08T12:34:56.789000",
  "imageData": "/9j/4AAQSkZJRgABAQEA...base64_string..."
}
```

**Field Details:**

- `sentinelId` (string): Device that detected the threat
- `threatType` (string): Lowercase object class (person, car, truck, motorcycle, bus)
- `confidence` (float): Detection confidence (0.0 to 1.0, typically 0.35-0.95)
- `location` (object): GPS coordinates at time of detection
- `timestamp` (string): ISO 8601 UTC timestamp
- `imageData` (string): Base64-encoded JPEG image of detection (typically 30-80KB)

**Expected Response:**

- Status: `200 OK` or `201 Created`
- Response body is ignored by sentinel

**Backend Actions:**

- Store alert in database
- Update sentinel status to "alert"
- Send notifications (SMS, push, email, etc.)
- Decode and save image
- Trigger webhooks or real-time updates to frontend

**Example Implementation (Node.js/Express):**

```javascript
app.post("/api/alerts", async (req, res) => {
  const { sentinelId, threatType, confidence, location, timestamp, imageData } =
    req.body;

  // Save alert to database
  const alert = await Alert.create({
    sentinelId,
    threatType,
    confidence,
    location,
    timestamp: new Date(timestamp),
    imageUrl: null, // Will be set after saving image
    status: "new",
  });

  // Decode and save image
  if (imageData) {
    const imageBuffer = Buffer.from(imageData, "base64");
    const imagePath = `alerts/${alert._id}.jpg`;

    // Save to S3, local disk, etc.
    await saveImage(imagePath, imageBuffer);
    alert.imageUrl = imagePath;
    await alert.save();
  }

  // Update sentinel status
  await Sentinel.findOneAndUpdate(
    { deviceId: sentinelId },
    {
      status: "alert",
      lastAlert: new Date(),
      lastSeen: new Date(),
    }
  );

  // Send notifications
  await sendPushNotification({
    title: `⚠️ Threat Detected: ${threatType}`,
    body: `Sentinel ${sentinelId} detected ${threatType} with ${(
      confidence * 100
    ).toFixed(0)}% confidence`,
    data: { alertId: alert._id },
  });

  // Emit real-time event to frontend
  io.emit("alert", {
    alertId: alert._id,
    sentinelId,
    threatType,
    confidence,
    timestamp,
  });

  console.log(`🚨 Alert: ${threatType} detected by ${sentinelId}`);

  res.status(201).json({
    message: "Alert received",
    alertId: alert._id,
  });
});
```

**Image Decoding Example:**

```javascript
// Node.js
const imageBuffer = Buffer.from(imageData, 'base64');
fs.writeFileSync(`alert_${alertId}.jpg`, imageBuffer);

// Python
import base64
img_bytes = base64.b64decode(imageData)
with open(f'alert_{alert_id}.jpg', 'wb') as f:
    f.write(img_bytes)
```

---

### 3. Status Updates (Heartbeat)

**Endpoint:** `PUT http://192.168.1.100:5000/api/sentinels/{deviceId}/status`

**Example URL:** `PUT http://192.168.1.100:5000/api/sentinels/ORN-001/status`

**When Called:**

- Periodically (every 60 seconds) while sentinel is running
- After mode changes (SENTRY ↔ INTRUDER)
- Fails silently if backend is unreachable

**Request Payload:**

```json
{
  "status": "active",
  "location": {
    "lat": 5.6,
    "lng": -0.19
  },
  "batteryLevel": 85
}
```

**Field Details:**

- `status` (string): Current sentinel status
  - `"active"` - SENTRY mode, normal operation
  - `"alert"` - INTRUDER mode, actively detecting threats
  - `"offline"` - Device disconnected (not sent by sentinel, inferred by backend)
- `location` (object): Current GPS coordinates
- `batteryLevel` (integer): Battery percentage

**Expected Response:**

- Status: `200 OK`
- Response is ignored by sentinel

**Backend Actions:**

- Update sentinel lastSeen timestamp
- Update current status and location
- Mark sentinel as offline if no update received for 90+ seconds

**Example Implementation (Node.js/Express):**

```javascript
app.put("/api/sentinels/:deviceId/status", async (req, res) => {
  const { deviceId } = req.params;
  const { status, location, batteryLevel } = req.body;

  await Sentinel.findOneAndUpdate(
    { deviceId },
    {
      status,
      location,
      batteryLevel,
      lastSeen: new Date(),
      isOnline: true,
    }
  );

  res.json({ message: "Status updated" });
});

// Background job: Mark sentinels offline if no heartbeat
setInterval(async () => {
  const threshold = new Date(Date.now() - 90000); // 90 seconds

  await Sentinel.updateMany(
    { lastSeen: { $lt: threshold }, isOnline: true },
    { isOnline: false, status: "offline" }
  );
}, 30000); // Check every 30 seconds
```

---

## Sentinel Control Endpoints

These are endpoints ON THE SENTINEL that your backend can call to control the device remotely.

**Base URLs:**

- Public: `https://xxxx-xx-xx-xx-xx.ngrok-free.app` (from registration payload)
- Local: `http://192.168.x.x:8080` (for same-network testing)

### 1. Activate Intruder Mode

**Endpoint:** `POST {streamUrl}/control/activate` (remove `/stream` from streamUrl)

**Purpose:** Backend requests sentinel to start AI detection

**Request:** Empty body (POST with no payload)

**Response:**

```json
{
  "status": "success",
  "mode": "INTRUDER"
}
```

**What Happens:**

1. Sentinel enters INTRUDER mode
2. Camera initializes if not active
3. AI model loads
4. Starts analyzing frames for threats
5. Will send alerts if threats detected
6. Continues until timeout or manual deactivation

**Use Case:** User clicks "View Live Feed" → Backend activates sentinel → User gets live feed with AI detection

**Example:**

```javascript
// Extract base URL from stream URL
const baseUrl = sentinel.streamUrl.replace("/stream", "");

// Activate sentinel
const response = await fetch(`${baseUrl}/control/activate`, {
  method: "POST",
});

if (response.ok) {
  console.log("Sentinel activated for AI detection");
}
```

---

### 2. Deactivate Intruder Mode

**Endpoint:** `POST {streamUrl}/control/deactivate`

**Purpose:** Backend requests sentinel to stop AI detection and return to SENTRY mode

**Request:** Empty body

**Response:**

```json
{
  "status": "success",
  "mode": "SENTRY"
}
```

**What Happens:**

1. Sentinel returns to SENTRY mode
2. AI model unloads (frees memory)
3. Camera may turn off after idle timeout (5 min)
4. No more alerts sent
5. Resumes sensor monitoring only

**Use Case:** User closes live feed → Backend deactivates sentinel → Saves battery/CPU

**Example:**

```javascript
const baseUrl = sentinel.streamUrl.replace("/stream", "");

await fetch(`${baseUrl}/control/deactivate`, {
  method: "POST",
});

console.log("Sentinel deactivated");
```

---

### 3. Get Sentinel Status

**Endpoint:** `GET {streamUrl}/status`

**Purpose:** Check current sentinel mode and camera state

**Response:**

```json
{
  "mode": "SENTRY",
  "camera_active": false,
  "ai_loaded": false,
  "stream_idle_seconds": 320
}
```

**Field Details:**

- `mode` (string): Current mode ("SENTRY" or "INTRUDER")
- `camera_active` (boolean): Whether camera is currently running
- `ai_loaded` (boolean): Whether AI model is loaded in memory
- `stream_idle_seconds` (integer): Seconds since last stream access (0 if never accessed)

**Use Case:** Check if sentinel needs to be activated before showing stream to user

---

### 4. Video Stream

**Endpoint:** `GET {streamUrl}` (use streamUrl directly from registration)

**Purpose:** Access live MJPEG video stream

**Response:** MJPEG stream (multipart/x-mixed-replace)

**Behavior:**

- First access automatically initializes camera if off
- Stream is always available (works in both SENTRY and INTRUDER modes)
- In SENTRY mode: Just video, no AI detection
- In INTRUDER mode: Video + AI analyzing frames

**Frontend Usage:**

```html
<img src="https://xxxx.ngrok-free.app/stream" alt="Live Feed" />
```

**Important:** Camera will auto-stop after 5 minutes of no stream access (battery saving)

---

### 5. Stream Keep-Alive

**Endpoint:** `POST {streamUrl}/stream/keepalive`

**Purpose:** Prevent camera from shutting down due to idle timeout

**Request:** Empty body

**Response:**

```json
{
  "status": "ok",
  "message": "Stream kept alive"
}
```

**When to Use:**

- Send every 60 seconds while user is viewing stream
- Prevents camera from auto-stopping after 5 min idle
- Stop sending when user closes stream

**Example:**

```javascript
let keepAliveInterval;

function startStreamViewing(sentinel) {
  // Show stream
  document.getElementById("feed").src = sentinel.streamUrl;

  // Send keep-alive every 60 seconds
  const baseUrl = sentinel.streamUrl.replace("/stream", "");
  keepAliveInterval = setInterval(() => {
    fetch(`${baseUrl}/stream/keepalive`, { method: "POST" });
  }, 60000);
}

function stopStreamViewing() {
  // Clear interval
  clearInterval(keepAliveInterval);
  // Camera will auto-stop after 5 min
}
```

---

### 6. Health Check

**Endpoint:** `GET {streamUrl}/health`

**Purpose:** Basic health check

**Response:**

```json
{
  "status": "ok",
  "camera": true
}
```

---

## Data Flow & Architecture

### 1. Registration Flow

```
Sentinel Startup
    ↓
Initialize Hardware (GPS, Sensors, Mic)
    ↓
Start Flask + Ngrok Tunnel
    ↓
POST /api/sentinels/register → Backend
    ↓
Backend stores sentinel info + stream URL
    ↓
Enter SENTRY Mode (camera OFF)
```

### 2. Threat Detection Flow

```
Sensor Triggered (PIR/Vibration/Mic)
    ↓
Enter INTRUDER Mode
    ↓
Camera ON + AI loads
    ↓
Analyze frames every 0.1s
    ↓
Threat detected (confidence > 35%)
    ↓
Encode frame to JPEG → Base64
    ↓
POST /api/alerts → Backend (in background thread)
    ↓
Backend saves alert + image
    ↓
Backend sends notifications
    ↓
Continue monitoring for 60s or until manual deactivation
```

### 3. On-Demand Viewing Flow

```
User opens webapp
    ↓
Frontend requests stream access
    ↓
Backend: POST {sentinel}/control/activate
    ↓
Sentinel enters INTRUDER mode
    ↓
Camera ON (if not already)
    ↓
Frontend shows stream: <img src="{streamUrl}">
    ↓
Backend sends /stream/keepalive every 60s
    ↓
User closes webapp
    ↓
Backend: POST {sentinel}/control/deactivate
    ↓
Sentinel returns to SENTRY mode
    ↓
Camera auto-stops after 5 min idle
```

### 4. Heartbeat Flow

```
Every 60 seconds:
    Sentinel → PUT /api/sentinels/{id}/status → Backend
    Backend updates lastSeen timestamp

Backend background job (every 30s):
    Find sentinels with lastSeen > 90s ago
    Mark as offline
```

---

## Implementation Examples

### Complete Backend (Node.js/Express + MongoDB)

```javascript
const express = require("express");
const mongoose = require("mongoose");
const app = express();

app.use(express.json({ limit: "10mb" })); // For base64 images

// Sentinel Schema
const sentinelSchema = new mongoose.Schema({
  deviceId: { type: String, required: true, unique: true },
  status: {
    type: String,
    enum: ["active", "alert", "offline"],
    default: "active",
  },
  location: {
    lat: Number,
    lng: Number,
  },
  batteryLevel: Number,
  streamUrl: String,
  lastSeen: Date,
  isOnline: { type: Boolean, default: true },
  lastAlert: Date,
});

const Sentinel = mongoose.model("Sentinel", sentinelSchema);

// Alert Schema
const alertSchema = new mongoose.Schema({
  sentinelId: { type: String, required: true },
  threatType: { type: String, required: true },
  confidence: { type: Number, required: true },
  location: {
    lat: Number,
    lng: Number,
  },
  timestamp: { type: Date, required: true },
  imageUrl: String,
  status: {
    type: String,
    enum: ["new", "reviewed", "dismissed"],
    default: "new",
  },
});

const Alert = mongoose.model("Alert", alertSchema);

// 1. Registration
app.post("/api/sentinels/register", async (req, res) => {
  try {
    const { deviceId, status, location, batteryLevel, streamUrl } = req.body;

    const sentinel = await Sentinel.findOneAndUpdate(
      { deviceId },
      {
        deviceId,
        status,
        location,
        batteryLevel,
        streamUrl,
        lastSeen: new Date(),
        isOnline: true,
      },
      { upsert: true, new: true }
    );

    console.log(`✅ Sentinel ${deviceId} registered`);
    res.status(201).json({ message: "Registered", sentinelId: sentinel._id });
  } catch (error) {
    console.error("Registration error:", error);
    res.status(500).json({ error: "Registration failed" });
  }
});

// 2. Alerts
app.post("/api/alerts", async (req, res) => {
  try {
    const {
      sentinelId,
      threatType,
      confidence,
      location,
      timestamp,
      imageData,
    } = req.body;

    // Create alert
    const alert = await Alert.create({
      sentinelId,
      threatType,
      confidence,
      location,
      timestamp: new Date(timestamp),
      imageUrl: null,
    });

    // Save image
    if (imageData) {
      const fs = require("fs");
      const path = `./uploads/alerts/${alert._id}.jpg`;

      // Ensure directory exists
      require("fs").mkdirSync("./uploads/alerts", { recursive: true });

      const imageBuffer = Buffer.from(imageData, "base64");
      fs.writeFileSync(path, imageBuffer);

      alert.imageUrl = `/alerts/${alert._id}.jpg`;
      await alert.save();
    }

    // Update sentinel
    await Sentinel.findOneAndUpdate(
      { deviceId: sentinelId },
      { status: "alert", lastAlert: new Date(), lastSeen: new Date() }
    );

    // Send notification (implement your notification service)
    // await sendPushNotification(...);

    console.log(
      `🚨 Alert: ${threatType} (${(confidence * 100).toFixed(
        0
      )}%) from ${sentinelId}`
    );
    res.status(201).json({ message: "Alert received", alertId: alert._id });
  } catch (error) {
    console.error("Alert error:", error);
    res.status(500).json({ error: "Failed to process alert" });
  }
});

// 3. Status Updates
app.put("/api/sentinels/:deviceId/status", async (req, res) => {
  try {
    const { deviceId } = req.params;
    const { status, location, batteryLevel } = req.body;

    await Sentinel.findOneAndUpdate(
      { deviceId },
      {
        status,
        location,
        batteryLevel,
        lastSeen: new Date(),
        isOnline: true,
      }
    );

    res.json({ message: "Status updated" });
  } catch (error) {
    console.error("Status update error:", error);
    res.status(500).json({ error: "Failed to update status" });
  }
});

// Background job: Mark offline sentinels
setInterval(async () => {
  const threshold = new Date(Date.now() - 90000); // 90 seconds

  await Sentinel.updateMany(
    { lastSeen: { $lt: threshold }, isOnline: true },
    { isOnline: false, status: "offline" }
  );
}, 30000);

// Frontend endpoints
app.get("/api/sentinels", async (req, res) => {
  const sentinels = await Sentinel.find({});
  res.json(sentinels);
});

app.get("/api/sentinels/:id", async (req, res) => {
  const sentinel = await Sentinel.findById(req.params.id);
  res.json(sentinel);
});

app.get("/api/alerts", async (req, res) => {
  const alerts = await Alert.find({}).sort({ timestamp: -1 }).limit(50);
  res.json(alerts);
});

// Remote control
app.post("/api/sentinels/:id/activate", async (req, res) => {
  try {
    const sentinel = await Sentinel.findById(req.params.id);
    const baseUrl = sentinel.streamUrl.replace("/stream", "");

    const response = await fetch(`${baseUrl}/control/activate`, {
      method: "POST",
    });

    if (response.ok) {
      res.json({ status: "activated", streamUrl: sentinel.streamUrl });
    } else {
      res.status(500).json({ error: "Failed to activate" });
    }
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/api/sentinels/:id/deactivate", async (req, res) => {
  try {
    const sentinel = await Sentinel.findById(req.params.id);
    const baseUrl = sentinel.streamUrl.replace("/stream", "");

    await fetch(`${baseUrl}/control/deactivate`, { method: "POST" });
    res.json({ status: "deactivated" });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

mongoose.connect("mongodb://localhost/orion").then(() => {
  app.listen(5000, "0.0.0.0", () => {
    console.log("Backend running on port 5000");
  });
});
```

### Frontend Example (React)

```jsx
import React, { useState, useEffect, useRef } from "react";

function SentinelDashboard() {
  const [sentinels, setSentinels] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedSentinel, setSelectedSentinel] = useState(null);
  const keepAliveInterval = useRef(null);

  // Fetch sentinels
  useEffect(() => {
    fetchSentinels();
    fetchAlerts();

    const interval = setInterval(() => {
      fetchSentinels();
      fetchAlerts();
    }, 10000); // Refresh every 10s

    return () => clearInterval(interval);
  }, []);

  const fetchSentinels = async () => {
    const res = await fetch("/api/sentinels");
    const data = await res.json();
    setSentinels(data);
  };

  const fetchAlerts = async () => {
    const res = await fetch("/api/alerts");
    const data = await res.json();
    setAlerts(data);
  };

  const viewStream = async (sentinel) => {
    // Activate sentinel
    await fetch(`/api/sentinels/${sentinel._id}/activate`, { method: "POST" });

    setSelectedSentinel(sentinel);

    // Start keep-alive
    const baseUrl = sentinel.streamUrl.replace("/stream", "");
    keepAliveInterval.current = setInterval(() => {
      fetch(`${baseUrl}/stream/keepalive`, { method: "POST" });
    }, 60000);
  };

  const closeStream = async () => {
    if (selectedSentinel) {
      // Deactivate sentinel
      await fetch(`/api/sentinels/${selectedSentinel._id}/deactivate`, {
        method: "POST",
      });

      // Stop keep-alive
      clearInterval(keepAliveInterval.current);

      setSelectedSentinel(null);
    }
  };

  return (
    <div className="dashboard">
      <h1>ORION Sentinels</h1>

      {/* Sentinel Grid */}
      <div className="sentinels-grid">
        {sentinels.map((sentinel) => (
          <div
            key={sentinel._id}
            className={`sentinel-card ${sentinel.status}`}
          >
            <h3>{sentinel.deviceId}</h3>
            <p>Status: {sentinel.status}</p>
            <p>Battery: {sentinel.batteryLevel}%</p>
            <p>Online: {sentinel.isOnline ? "🟢" : "🔴"}</p>
            <button onClick={() => viewStream(sentinel)}>View Stream</button>
          </div>
        ))}
      </div>

      {/* Stream Modal */}
      {selectedSentinel && (
        <div className="stream-modal">
          <div className="modal-content">
            <h2>{selectedSentinel.deviceId} - Live Feed</h2>
            <img
              src={selectedSentinel.streamUrl}
              alt="Live stream"
              style={{ width: "100%", maxWidth: "800px" }}
            />
            <button onClick={closeStream}>Close</button>
          </div>
        </div>
      )}

      {/* Recent Alerts */}
      <div className="alerts-section">
        <h2>Recent Alerts</h2>
        {alerts.map((alert) => (
          <div key={alert._id} className="alert-card">
            <img src={alert.imageUrl} alt="Alert" width="200" />
            <div>
              <h4>{alert.threatType} detected</h4>
              <p>Sentinel: {alert.sentinelId}</p>
              <p>Confidence: {(alert.confidence * 100).toFixed(0)}%</p>
              <p>Time: {new Date(alert.timestamp).toLocaleString()}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SentinelDashboard;
```

---

## Battery Optimization

### Camera Auto-Sleep System

**Problem:** Camera consumes significant power (2-5W on Pi 4)

**Solution:** Camera only runs when needed

**Behavior:**

1. **Startup:** Camera OFF
2. **Stream Request:** Camera turns ON automatically
3. **Idle for 5 min:** Camera turns OFF (saves battery)
4. **Threat Detected:** Camera turns ON for detection
5. **Keep-Alive:** Backend pings every 60s to keep camera alive

### Configuration

In `modules/config.py`:

```python
STREAM_TIMEOUT = 300  # Seconds before camera auto-stops (default: 5 min)
```

Adjust based on your needs:

- `60` = 1 minute (aggressive battery saving)
- `300` = 5 minutes (balanced, recommended)
- `600` = 10 minutes (less battery conscious)

### Keep-Alive Implementation

**When user is viewing stream:**

```javascript
// Send keep-alive every 60 seconds
const baseUrl = sentinel.streamUrl.replace("/stream", "");
const keepAliveInterval = setInterval(() => {
  fetch(`${baseUrl}/stream/keepalive`, { method: "POST" });
}, 60000);

// Clear when user closes stream
clearInterval(keepAliveInterval);
```

**Battery Impact:**

- Without auto-sleep: 100% camera uptime = ~48 hours battery life
- With auto-sleep: ~10% camera uptime = ~200+ hours battery life
- **5x-10x battery improvement** depending on usage patterns

---

## Error Handling

### Sentinel Connection Lost

**Detection:** No heartbeat received for 90 seconds

**Backend Action:**

```javascript
// Background job
setInterval(async () => {
  const threshold = new Date(Date.now() - 90000);

  await Sentinel.updateMany(
    { lastSeen: { $lt: threshold }, isOnline: true },
    { isOnline: false, status: "offline" }
  );

  // Optional: Send notification
  const offlineSentinels = await Sentinel.find({ isOnline: false });
  for (const sentinel of offlineSentinels) {
    await sendAlert(`Sentinel ${sentinel.deviceId} is offline`);
  }
}, 30000);
```

### Alert Delivery Failures

**Sentinel Behavior:** Alerts sent in background thread, failures logged but don't crash system

**Backend Should:**

- Always return 200/201 even if processing fails
- Queue failed alerts for retry
- Log all alert receipts

### Ngrok Tunnel Failures

**Sentinel Behavior:**

- Logs error but continues running
- Falls back to local IP in registration
- Retries ngrok on next startup

**Backend Should:**

- Accept both ngrok URLs and local IPs
- Validate stream URL before showing to users
- Handle unreachable streams gracefully

### Stream Access Errors

**Frontend Should:**

```javascript
<img
  src={sentinel.streamUrl}
  alt="Live feed"
  onError={(e) => {
    e.target.src = "/placeholder-offline.png";
    showError("Stream unavailable");
  }}
/>
```

---

## Security Considerations

### 1. Ngrok URLs are Public

**Risk:** Anyone with ngrok URL can access stream

**Mitigations:**

- Ngrok URLs change on restart (not permanent)
- Only backend stores URLs (don't expose in frontend)
- Add authentication to Flask endpoints (future enhancement)

**Recommended Implementation:**

```python
# In web_server.py
from functools import wraps

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Auth-Token')
        if token != config.API_TOKEN:
            return {'error': 'Unauthorized'}, 401
        return f(*args, **kwargs)
    return decorated

@app.route('/stream')
@require_token
def video_stream():
    # ...
```

### 2. Image Data Size

**Risk:** Base64 images can be 50-100KB, may impact database size

**Mitigations:**

- Store images in S3/cloud storage, not database
- Implement image cleanup policy (delete after 30 days)
- Use JPEG quality setting to control size

**Storage Calculation:**

- 1 alert = ~60KB image
- 100 alerts/day = ~6MB/day
- 30 days = ~180MB/month

### 3. Backend IP Exposure

**Risk:** Backend IP hardcoded in sentinel config

**Current:** `http://192.168.1.100:5000/api`

**Production:**

- Use domain name instead: `https://api.yourdomain.com`
- Enable HTTPS with SSL certificate
- Use API gateway for rate limiting

### 4. Alert Flooding

**Risk:** Malicious or malfunctioning sentinel sends too many alerts

**Mitigation Already Implemented:**

- 30-second cooldown between alerts
- Sentinel-side rate limiting

**Additional Backend Protection:**

```javascript
// Rate limit per sentinel
const rateLimit = new Map();

app.post("/api/alerts", async (req, res) => {
  const { sentinelId } = req.body;
  const now = Date.now();
  const lastAlert = rateLimit.get(sentinelId) || 0;

  if (now - lastAlert < 20000) {
    // 20 second backend limit
    return res.status(429).json({ error: "Too many alerts" });
  }

  rateLimit.set(sentinelId, now);

  // Process alert...
});
```

---

## Testing Checklist

### Initial Setup

- [ ] Sentinel registers successfully
- [ ] Backend receives registration with correct stream URL
- [ ] Sentinel shows up as "online" in backend

### Alert Flow

- [ ] Trigger sensor (PIR/vibration/microphone)
- [ ] Sentinel enters INTRUDER mode
- [ ] Backend receives alert with threat type
- [ ] Image data is properly decoded
- [ ] Notification sent (if implemented)
- [ ] Sentinel returns to SENTRY after timeout

### Stream Access

- [ ] Open stream URL in browser, camera activates
- [ ] Stream displays video feed
- [ ] Keep-alive prevents camera from stopping
- [ ] Camera stops 5 min after closing stream

### Remote Control

- [ ] Backend activates sentinel via `/control/activate`
- [ ] Sentinel enters INTRUDER mode
- [ ] Backend deactivates via `/control/deactivate`
- [ ] Sentinel returns to SENTRY mode

### Error Scenarios

- [ ] Backend offline during alert → Sentinel logs error, continues running
- [ ] Ngrok tunnel fails → Sentinel uses local IP fallback
- [ ] Network drops → Sentinel marked offline after 90s
- [ ] Stream accessed when camera off → Camera auto-initializes

### Battery Testing

- [ ] Camera turns off after 5 min idle
- [ ] Keep-alive prevents auto-stop
- [ ] Camera initializes on stream request
- [ ] Camera initializes on sensor trigger

---

## Configuration Reference

### Backend Configuration

**Required Environment Variables:**

```bash
MONGODB_URI=mongodb://localhost/orion
PORT=5000
HOST=0.0.0.0
UPLOAD_DIR=./uploads/alerts
```

**Optional:**

```bash
NOTIFICATION_SERVICE_KEY=xxx
PUSH_NOTIFICATION_URL=https://...
SENTRY_DSN=https://...
```

### Sentinel Configuration

File: `/home/josh/Documents/terra-sentry/orion/modules/config.py`

**Key Settings:**

```python
# Your Backend
BACKEND_URL = "http://192.168.1.100:5000/api"  # Change to your production URL

# Device Identity
DEVICE_ID = "ORN-001"  # Unique per device

# AI Detection
CONFIDENCE_THRESHOLD = 0.35  # Lower = more detections (0.25-0.5 recommended)
THREAT_CLASSES = ["person", "car", "truck", "motorcycle", "bus"]

# Battery Optimization
STREAM_TIMEOUT = 300  # Camera auto-stop after 5 min idle
ALERT_COOLDOWN = 30   # Minimum seconds between alerts

# Ngrok
NGROK_ENABLED = True  # Set False to use local IP only
```

---

## Support & Troubleshooting

### Common Issues

**1. Sentinel not registering**

- Check backend is running on correct IP/port
- Verify firewall allows port 5000
- Test: `curl http://192.168.1.100:5000/api/sentinels/register`

**2. Alerts not received**

- Check backend `/api/alerts` endpoint accepts POST
- Verify backend can parse JSON with base64 strings
- Check backend logs for errors

**3. Stream won't load**

- Verify ngrok tunnel is active (check sentinel logs)
- Test stream URL directly in browser
- Check if camera is initialized (`GET /status`)

**4. High battery drain**

- Verify STREAM_TIMEOUT is set (default 300s)
- Ensure keep-alive stops when user closes stream
- Check camera turns off after idle period

**5. Ngrok authentication error**

- Run: `ngrok config add-authtoken YOUR_TOKEN`
- Or set `NGROK_ENABLED = False` in config.py

### Debug Endpoints

**Check Sentinel Status:**

```bash
curl https://your-ngrok-url.ngrok-free.app/status
```

**Check Camera State:**

```bash
curl https://your-ngrok-url.ngrok-free.app/health
```

**Manual Activation:**

```bash
curl -X POST https://your-ngrok-url.ngrok-free.app/control/activate
```

### Logs

**Sentinel Logs:** Console output when running `python main.py`

**Key Log Messages:**

- `✅ Device registered successfully` - Registration worked
- `🚨 INTRUDER MODE: Active threat detection!` - AI activated
- `💤 SENTRY MODE: Monitoring sensors` - Low power mode
- `🔍 Detected X object(s):` - AI found something
- `⚠️ THREAT: person (87%)` - Threat detected, alert sent
- `📷 Camera initialized` - Camera turned on
- `💤 Stream idle for Xs - stopping camera` - Battery save activated

---

## Version History

**v1.0 (January 8, 2026)**

- Initial release
- YOLOv4-Tiny AI detection
- Dual mode operation (SENTRY/INTRUDER)
- Remote control via backend
- Battery optimization with camera auto-sleep
- Base64 image transmission in alerts
- Ngrok tunnel support

**Planned Features:**

- Authentication tokens for stream access
- Video recording on alert
- Multi-sentinel coordination
- Mobile app integration
- Advanced GPS tracking with actual hardware

---

## Contact & Credits

**Project:** ORION Sentinel  
**Device ID:** ORN-001  
**Hardware:** Raspberry Pi 4  
**AI Model:** YOLOv4-Tiny  
**Repository:** github.com/JoshNuku/orion-sentinel

---

**End of Documentation**
