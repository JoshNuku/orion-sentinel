"""
Project ORION - Configuration Module
All system settings and constants
"""

# ============================================================================
# DEVICE CONFIGURATION
# ============================================================================

DEVICE_ID = "ORN-001"
BACKEND_URL = "http://192.168.137.1:5000/api"  # Your Backend IP
VIDEO_PORT = 8080
NGROK_ENABLED = True  # Set to True if you have ngrok authtoken configured

# ============================================================================
# GPIO PINS (BCM Mode)
# ============================================================================

PIR_PIN = 17        # Motion sensor
VIBRATION_PIN = 27  # Vibration sensor

# ============================================================================
# MICROPHONE CONFIGURATION (ADS1115)
# ============================================================================

MIC_CHANNEL = 1              # ADS1115 channel (A1)
MIC_THRESHOLD = 5000         # Sound level threshold for alert
MIC_SAMPLE_RATE = 100        # Samples per second
MIC_BASELINE_SAMPLES = 50    # Samples to calculate baseline noise

# ============================================================================
# AI MODEL CONFIGURATION (YOLOv3-Tiny)
# ============================================================================

YOLO_WEIGHTS = "../model/yolov4-tiny.weights"
YOLO_CONFIG = "../model/yolov4-tiny.cfg"
CONFIDENCE_THRESHOLD = 0.35
YOLO_CLASSES = "../model/coco.names"
NMS_THRESHOLD = 0.4  # Non-maximum suppression
INPUT_SIZE = 416  # YOLOv3 input size
DEBUG_SHOW_ALL_DETECTIONS = True  # Show all objects detected, not just threats
DEBUG_SAVE_FRAMES = False  # Save frames to disk for debugging

# Target classes for threat detection (COCO dataset)
THREAT_CLASSES = [
    "truck", "car", "motorcycle", "bus",  # Vehicles
    "person"  # People (for trespassing)
]

# ============================================================================
# TIMING CONFIGURATION
# ============================================================================

SENSOR_POLL_INTERVAL = 0.5   # Seconds between sensor checks
ALERT_COOLDOWN = 30          # Seconds between consecutive alerts
STREAM_DURATION = 60         # Seconds to stay in INTRUDER mode
HEARTBEAT_INTERVAL = 60      # Seconds between status updates

# ============================================================================
# CAMERA SETTINGS
# ============================================================================

CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 15
JPEG_QUALITY = 60

# ============================================================================
# SYSTEM MODES
# ============================================================================

MODE_SENTRY = "SENTRY"
MODE_INTRUDER = "INTRUDER"
