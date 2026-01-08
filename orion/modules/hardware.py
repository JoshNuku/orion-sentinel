"""
Project ORION - Hardware Interface Module
Handles GPIO sensors, GPS, and camera operations
"""

import time
import cv2
import threading
import logging
import RPi.GPIO as GPIO
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from . import config

logger = logging.getLogger(__name__)


class GPIOSensors:
    """Manages PIR and vibration sensors"""
    
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config.PIR_PIN, GPIO.IN)
        GPIO.setup(config.VIBRATION_PIN, GPIO.IN)
        logger.info("✅ GPIO sensors initialized")
    
    def motion_detected(self):
        """Check if PIR sensor detects motion"""
        return GPIO.input(config.PIR_PIN)
    
    def vibration_detected(self):
        """Check if vibration sensor triggered"""
        return GPIO.input(config.VIBRATION_PIN)
    
    def any_trigger(self):
        """Check if any sensor is triggered"""
        return self.motion_detected() or self.vibration_detected()
    
    def cleanup(self):
        """Clean up GPIO resources"""
        GPIO.cleanup()
        logger.info("GPIO cleaned up")


class GPSTracker:
    """GPS location tracking (mock implementation)"""
    
    def __init__(self):
        # TODO: Integrate with actual GPS module (e.g., via serial)
        self.mock_location = {"lat": 6.6745, "lng": -1.5716}
        logger.info("✅ GPS tracker initialized (mock mode)")
    
    def get_location(self):
        """Get current GPS coordinates"""
        # Replace with actual GPS serial reading when available
        return self.mock_location.copy()
    
    def update_location(self):
        """Update GPS data from hardware"""
        # TODO: Read from serial GPS module
        pass


class CameraManager:
    """Manages camera capture and streaming"""
    
    def __init__(self):
        self.camera = None
        self.lock = threading.Lock()
        self.is_active = False
    
    def initialize(self):
        """Initialize camera"""
        with self.lock:
            if not self.camera:
                self.camera = cv2.VideoCapture(config.CAMERA_INDEX)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
                time.sleep(1)  # Warmup
                self.is_active = True
                logger.info("📷 Camera initialized")
    
    def capture_frame(self):
        """Capture a single frame"""
        with self.lock:
            if self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                return ret, frame
        return False, None
    
    def get_jpeg_frame(self):
        """Get frame encoded as JPEG"""
        ret, frame = self.capture_frame()
        if ret:
            ret, buffer = cv2.imencode('.jpg', frame, 
                                      [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY])
            if ret:
                return buffer.tobytes()
        return None
    
    def release(self):
        """Release camera resources"""
        with self.lock:
            if self.camera:
                self.camera.release()
                self.camera = None
                self.is_active = False
                logger.info("📷 Camera released")
    
    def is_opened(self):
        """Check if camera is open"""
        with self.lock:
            return self.camera is not None and self.camera.isOpened()


class MicrophoneMonitor:
    """Monitors microphone (ADS1115) for sound level detection"""
    
    def __init__(self):
        self.ads = None
        self.mic_channel = None
        self.baseline = 0
        self.is_active = False
        self._monitoring = False
        self._thread = None
        self._lock = threading.Lock()
        self.current_level = 0
        self.peak_level = 0
    
    def initialize(self):
        """Initialize ADS1115 and microphone channel"""
        try:
            # Create I2C bus
            i2c = busio.I2C(board.SCL, board.SDA)
            
            # Create ADC object
            self.ads = ADS.ADS1115(i2c)
            
            # Create analog input on channel 1 (A1)
            self.mic_channel = AnalogIn(self.ads, config.MIC_CHANNEL)
            
            # Calculate baseline noise level
            self._calibrate_baseline()
            
            self.is_active = True
            logger.info(f"🎤 Microphone initialized (Baseline: {self.baseline})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Microphone initialization failed: {e}")
            return False
    
    def _calibrate_baseline(self):
        """Calibrate baseline noise level"""
        if not self.mic_channel:
            return
        
        logger.info("🎤 Calibrating microphone baseline...")
        samples = []
        
        for _ in range(config.MIC_BASELINE_SAMPLES):
            samples.append(self.mic_channel.value)
            time.sleep(0.01)
        
        # Use average as baseline
        self.baseline = sum(samples) // len(samples)
    
    def get_sound_level(self):
        """Get current sound level (deviation from baseline)"""
        if not self.mic_channel:
            return 0
        
        try:
            raw_value = self.mic_channel.value
            # Calculate absolute deviation from baseline
            level = abs(raw_value - self.baseline)
            return level
        except Exception as e:
            logger.error(f"Microphone read error: {e}")
            return 0
    
    def is_loud(self):
        """Check if current sound level exceeds threshold"""
        level = self.get_sound_level()
        return level > config.MIC_THRESHOLD
    
    def start_monitoring(self):
        """Start continuous monitoring in background thread"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("🎤 Microphone monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("🎤 Microphone monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            level = self.get_sound_level()
            
            with self._lock:
                self.current_level = level
                if level > self.peak_level:
                    self.peak_level = level
            
            time.sleep(1.0 / config.MIC_SAMPLE_RATE)
    
    def get_stats(self):
        """Get current microphone statistics"""
        with self._lock:
            return {
                "current": self.current_level,
                "peak": self.peak_level,
                "baseline": self.baseline,
                "threshold": config.MIC_THRESHOLD,
                "is_loud": self.current_level > config.MIC_THRESHOLD
            }
    
    def reset_peak(self):
        """Reset peak level"""
        with self._lock:
            self.peak_level = 0
    
    def release(self):
        """Release microphone resources"""
        self.stop_monitoring()
        self.ads = None
        self.mic_channel = None
        self.is_active = False
        logger.info("🎤 Microphone released")
