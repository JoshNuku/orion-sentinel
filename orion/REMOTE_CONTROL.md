# Backend Remote Control API

The backend can now control the sentinel remotely via HTTP requests to the ngrok URL or local IP.

## Endpoints

### 1. Activate Intruder Mode (Start AI Detection)
**Request:**
```bash
POST https://your-ngrok-url.ngrok-free.app/control/activate
# or
POST http://192.168.x.x:8080/control/activate
```

**Response:**
```json
{
  "status": "success",
  "mode": "INTRUDER"
}
```

**What it does:**
- Activates AI threat detection
- Keeps camera streaming
- Extends monitoring duration
- Sentinel starts analyzing frames for threats

---

### 2. Deactivate Intruder Mode (Return to Sentry)
**Request:**
```bash
POST https://your-ngrok-url.ngrok-free.app/control/deactivate
# or
POST http://192.168.x.x:8080/control/deactivate
```

**Response:**
```json
{
  "status": "success",
  "mode": "SENTRY"
}
```

**What it does:**
- Unloads AI model (saves resources)
- Continues camera streaming
- Returns to low-power sensor monitoring
- No more threat alerts sent

---

### 3. Get Sentinel Status
**Request:**
```bash
GET https://your-ngrok-url.ngrok-free.app/status
# or
GET http://192.168.x.x:8080/status
```

**Response:**
```json
{
  "mode": "SENTRY",
  "camera_active": true,
  "ai_loaded": false
}
```

---

### 4. Video Stream (Always Available)
**Request:**
```bash
GET https://your-ngrok-url.ngrok-free.app/stream
# or
GET http://192.168.x.x:8080/stream
```

**Response:** MJPEG stream

**Note:** Stream is always available regardless of mode (SENTRY or INTRUDER)

---

### 5. Health Check
**Request:**
```bash
GET https://your-ngrok-url.ngrok-free.app/health
# or
GET http://192.168.x.x:8080/health
```

**Response:**
```json
{
  "status": "ok",
  "camera": true
}
```

---

## Usage Examples

### Backend Implementation (Node.js/Express)

```javascript
// User clicks "View Live Feed" button
app.post('/api/sentinel/:id/activate', async (req, res) => {
  const sentinel = await Sentinel.findById(req.params.id);
  
  // Trigger intruder mode on sentinel
  const response = await fetch(`${sentinel.streamUrl.replace('/stream', '')}/control/activate`, {
    method: 'POST'
  });
  
  if (response.ok) {
    // Redirect user to live stream
    res.json({ streamUrl: sentinel.streamUrl });
  }
});

// User closes feed
app.post('/api/sentinel/:id/deactivate', async (req, res) => {
  const sentinel = await Sentinel.findById(req.params.id);
  
  await fetch(`${sentinel.streamUrl.replace('/stream', '')}/control/deactivate`, {
    method: 'POST'
  });
  
  res.json({ status: 'deactivated' });
});
```

### Backend Implementation (Python/Flask)

```python
import requests

@app.route('/api/sentinel/<device_id>/activate', methods=['POST'])
def activate_sentinel(device_id):
    sentinel = db.sentinels.find_one({'deviceId': device_id})
    
    # Extract base URL from stream URL
    base_url = sentinel['streamUrl'].replace('/stream', '')
    
    # Activate intruder mode
    response = requests.post(f"{base_url}/control/activate")
    
    if response.ok:
        return jsonify({'streamUrl': sentinel['streamUrl']})
    
    return jsonify({'error': 'Failed to activate'}), 500

@app.route('/api/sentinel/<device_id>/deactivate', methods=['POST'])
def deactivate_sentinel(device_id):
    sentinel = db.sentinels.find_one({'deviceId': device_id})
    base_url = sentinel['streamUrl'].replace('/stream', '')
    
    requests.post(f"{base_url}/control/deactivate")
    return jsonify({'status': 'deactivated'})
```

---

## Frontend Integration

### React Example

```jsx
function SentinelFeed({ sentinel }) {
  const [isActive, setIsActive] = useState(false);
  
  const activateFeed = async () => {
    // Tell backend to activate sentinel
    await fetch(`/api/sentinel/${sentinel.id}/activate`, { method: 'POST' });
    setIsActive(true);
  };
  
  const deactivateFeed = async () => {
    await fetch(`/api/sentinel/${sentinel.id}/deactivate`, { method: 'POST' });
    setIsActive(false);
  };
  
  return (
    <div>
      <img src={sentinel.streamUrl} alt="Live feed" />
      <button onClick={activateFeed}>Start AI Detection</button>
      <button onClick={deactivateFeed}>Stop AI Detection</button>
    </div>
  );
}
```

---

## Use Cases

### 1. On-Demand Monitoring
User opens your webapp → Backend activates sentinel → User sees live feed with AI detection

### 2. Manual Investigation
Alert received → Security views feed → Backend keeps intruder mode active → User closes → Backend deactivates

### 3. Scheduled Patrol
Backend activates sentinel at specific times → AI monitors for X minutes → Auto-deactivate

### 4. Multi-Sentinel Dashboard
Users select which sentinels to monitor → Backend activates only selected ones → Saves resources

---

## Benefits

✅ **Stream Always Available** - Camera never stops, even in SENTRY mode
✅ **AI On Demand** - Only run detection when needed (saves CPU/battery)
✅ **Remote Control** - Backend decides when to activate threat detection
✅ **Resource Efficient** - Unload AI when not actively monitoring
✅ **User Experience** - Instant stream access without reconnection delays

---

## Testing

```bash
# Get ngrok URL from sentinel logs
# Example: https://2f6c1c0b9d65.ngrok-free.app

# Test activation
curl -X POST https://2f6c1c0b9d65.ngrok-free.app/control/activate

# Check status
curl https://2f6c1c0b9d65.ngrok-free.app/status

# View stream in browser
open https://2f6c1c0b9d65.ngrok-free.app/stream

# Test deactivation
curl -X POST https://2f6c1c0b9d65.ngrok-free.app/control/deactivate
```
