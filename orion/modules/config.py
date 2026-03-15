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

# Note: This is a "sound-first" architecture. Audio (MAX9814 + ADS1115) is 
# the primary trigger source. No external GPIO pins are used for triggers.

# ============================================================================
# MICROPHONE CONFIGURATION (ADS1115)
# ============================================================================

MIC_CHANNEL = 1               # ADS1115 channel (A1)
# Sound capture settings
MIC_SAMPLE_RATE = 16000       # Samples per second (for FFT/analysis)
MIC_BUFFER_DURATION = 3       # Seconds to keep in rolling buffer for analysis
MIC_BASELINE_SAMPLES = 50     # Samples to calculate baseline noise (short warmup)

# Simple level threshold (raw ADC units) used as a low-cost trigger fallback
MIC_THRESHOLD = 5000

# Audio analysis parameters
AUDIO_FFT_WINDOW = 1024       # FFT window size
AUDIO_FFT_HOP = 512           # Hop size for STFT (not used for simple FFT)
AUDIO_BANDS_HZ = {            # Frequency bands used for rule-based detection
    'low': (20, 300),         # Heavy machinery (excavator) energy band
    'mid': (300, 2000),       # Speech and mid-frequency machinery
    'high': (2000, 6000)      # Chainsaw and high-frequency noise
}

# Detection thresholds (tunable on-device)
AUDIO_DETECTION = {
    'excavator': {
        'low_energy_ratio': 0.55,  # fraction of total energy in low band
        'min_confidence': 0.5
    },
    'chainsaw': {
        'mid_high_energy_ratio': 0.45,
        'spectral_flatness': 0.02,
        'min_confidence': 0.5
    },
    'speech': {
        'centroid_max': 3000,
        'zcr_max': 0.15,
        'min_confidence': 0.5
    }
}

# Debounce / dwell times
AUDIO_DEBOUNCE_SECONDS = 2    # Seconds of sustained detection to confirm

# ADC sampling (ADS1115 over I2C is relatively slow in Python). Use a
# conservative ADC poll rate and resample in software for analysis.
MIC_ADC_SAMPLE_RATE = 200     # Samples/sec to read from ADS1115 (practical over I2C)

# ============================================================================

# AI MODEL CONFIGURATION (YOLOv10 ONNX)
YOLO_ONNX_PATH = "../model/yolov10.onnx"
YOLO_CLASSES = "../model/coco.names"  # Update if using custom classes
CONFIDENCE_THRESHOLD = 0.35
NMS_THRESHOLD = 0.4  # Non-maximum suppression
INPUT_SIZE = 640  # YOLOv10 input size
DEBUG_SHOW_ALL_DETECTIONS = True
DEBUG_SAVE_FRAMES = False

# AUDIO AI CONFIGURATION
AUDIO_MODEL_PATH = "../model/audio_classifier.onnx"
AUDIO_CLASSES_PATH = "../model/audio_classes.txt"
AUDIO_CONFIDENCE_THRESHOLD = 0.5  # Lowered to match rule-based detector confidence scaling

# Utility to load audio classes
def load_audio_classes():
    try:
        with open(AUDIO_CLASSES_PATH, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return ["SILENCE"]

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
STREAM_TIMEOUT = 300         # Seconds of inactivity before stopping camera (5 min)
HEARTBEAT_INTERVAL = 60      # Seconds between status updates
SENSOR_DEBOUNCE_SECONDS = 5  # Seconds to debounce repeated sensor triggers

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

# ============================================================================
# GPS / SERIAL
# ============================================================================
# Default serial port for NEO-7M (change to match your Pi: '/dev/ttyAMA0' or '/dev/ttyS0')
GPS_SERIAL_PORT = '/dev/ttyAMA0'
GPS_BAUD = 9600
GPS_READ_TIMEOUT = 1
