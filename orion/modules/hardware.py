"""
Project ORION - Hardware Interface Module
Handles GPIO sensors, GPS, and camera operations
"""

import time
import cv2
import threading
import logging
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from . import config

logger = logging.getLogger(__name__)

import numpy as _np
import wave as _wave




class GPSTracker:
    """GPS location tracking wrapper.

    By default this will attempt to use the `SerialGPSDriver` from
    `modules.hardware_components.gps_driver`. If the driver or required
    dependencies are not present, the tracker falls back to a mock
    location so the system can run without blocking.
    """

    def __init__(self):
        self._driver = None
        self._mock_location = {"lat": 6.6745, "lng": -1.5716}
        try:
            from .hardware_components.gps_driver import SerialGPSDriver
        except Exception:
            # Silently fall back to mock mode
            SerialGPSDriver = None

        if 'SerialGPSDriver' in locals() and SerialGPSDriver is not None:
            try:
                # Initialize concrete driver with config defaults
                from . import config as _cfg
                self._driver = SerialGPSDriver(port=_cfg.GPS_SERIAL_PORT, baud=_cfg.GPS_BAUD)
                try:
                    self._driver.initialize()
                    logger.info("✅ GPS tracker initialized (SerialGPSDriver)")
                except Exception as e:
                    logger.warning(f"⚠️ GPS driver failed to initialize, using mock: {e}")
                    self._driver = None
            except Exception:
                self._driver = None
        else:
            logger.info("✅ GPS tracker initialized (mock mode)")

    def get_location(self):
        """Get current GPS coordinates from driver or mock copy."""
        if self._driver is not None:
            try:
                return self._driver.get_location()
            except Exception:
                logger.exception("GPS driver error; returning mock location")
                return self._mock_location.copy()
        return self._mock_location.copy()

    def update_location(self):
        """No-op helper for compatibility with previous API."""
        # The driver is read-on-demand by `get_location()`; keep this for API
        # compatibility and potential background updates in future.
        return


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
        # Audio buffer for inference (2-3s) - buffer holds ADC samples at ADC poll rate
        self.audio_buffer = []
        self.buffer_duration = getattr(config, 'MIC_BUFFER_DURATION', 3)
        # ADC poll/sample rate (practical over I2C)
        self.adc_rate = getattr(config, 'MIC_ADC_SAMPLE_RATE', 200)
        # Analysis/sample rate (target for FFT) - used when resampling
        self.sample_rate = getattr(config, 'MIC_SAMPLE_RATE', 16000)
        self.buffer_size = int(self.buffer_duration * self.adc_rate)
        # Simulation support (WAV file playback into ADC buffer)
        self.simulate_wav = None
        self._sim_wav_data = None
        self._sim_index = 0
        # Optional external driver implementing `initialize()`, `read()`, `close()`
        # Attach with `set_driver(driver)` to override ADS1115 reads.
        self.driver = None
    
    def initialize(self):
        """Initialize ADS1115 and microphone channel"""
        try:
            # If an external driver is provided, initialize it and skip ADS setup
            if self.driver is not None:
                try:
                    self.driver.initialize()
                except Exception:
                    logger.exception("Microphone driver initialization failed")
            else:
                # Create I2C bus and ADC object
                i2c = busio.I2C(board.SCL, board.SDA)
                self.ads = ADS.ADS1115(i2c)
                # Create analog input on configured channel
                self.mic_channel = AnalogIn(self.ads, config.MIC_CHANNEL)

            # Calculate baseline noise level
            self._calibrate_baseline()

            # If simulation path was set before initialize, ensure wav loaded
            if self.simulate_wav:
                try:
                    self._load_simulation(self.simulate_wav)
                except Exception:
                    logger.exception("Failed to load simulation WAV")

            self.is_active = True
            logger.info(f"🎤 Microphone initialized (Baseline: {self.baseline})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Microphone initialization failed: {e}")
            return False
    
    def _calibrate_baseline(self):
        """Calibrate baseline noise level"""
        # If no ADC channel, driver or simulation data available, nothing to calibrate
        if not self.mic_channel and self.driver is None and self._sim_wav_data is None:
            return
        
        logger.info("🎤 Calibrating microphone baseline...")
        samples = []
        
        for _ in range(config.MIC_BASELINE_SAMPLES):
            try:
                if self._sim_wav_data is not None:
                    samples.append(float(self._sim_wav_data[self._sim_index]))
                    self._sim_index = (self._sim_index + 1) % len(self._sim_wav_data)
                elif self.driver is not None:
                    samples.append(float(self.driver.read()))
                else:
                    samples.append(self.mic_channel.value)
            except Exception:
                samples.append(0)
            time.sleep(1.0 / max(10, self.adc_rate))
        
        # Use average as baseline
        self.baseline = sum(samples) // len(samples)
    
    def get_sound_level(self):
        """Get current sound level (deviation from baseline)"""
        # Prefer simulation data, then external driver, then ADC channel
        try:
            if self._sim_wav_data is not None:
                raw_value = float(self._sim_wav_data[self._sim_index])
            elif self.driver is not None:
                raw_value = float(self.driver.read())
            elif self.mic_channel:
                raw_value = self.mic_channel.value
            else:
                return 0

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
        """Background monitoring loop with audio buffering"""
        while self._monitoring:
            level = self.get_sound_level()
            # Read raw value for audio buffer
            try:
                if self._sim_wav_data is not None:
                    raw_value = float(self._sim_wav_data[self._sim_index])
                    self._sim_index = (self._sim_index + 1) % len(self._sim_wav_data)
                elif self.driver is not None:
                    raw_value = float(self.driver.read())
                else:
                    raw_value = self.mic_channel.value
            except Exception:
                raw_value = 0
            with self._lock:
                self.current_level = level
                if level > self.peak_level:
                    self.peak_level = level
                # Buffer audio samples
                self.audio_buffer.append(raw_value)
                if len(self.audio_buffer) > self.buffer_size:
                    # keep only the most recent samples
                    self.audio_buffer = self.audio_buffer[-self.buffer_size:]
            # Sleep based on ADC poll rate (practical over I2C)
            time.sleep(1.0 / self.adc_rate)

    def load_simulation(self, wav_path):
        """Public API: set a WAV file to simulate ADC input.

        Call before `initialize()` or while stopped. The file will be resampled
        to the ADC poll rate and played in a loop into the audio buffer.
        """
        self.simulate_wav = wav_path
        # If already initialized, load immediately
        try:
            self._load_simulation(wav_path)
            logger.info(f"🎧 Simulation WAV loaded: {wav_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load simulation WAV: {e}")
            return False

    def set_driver(self, driver):
        """Attach an external driver implementing `initialize()`, `read()`, `close()`.

        The driver should provide:
            - initialize(): prepare hardware
            - read(): return a numeric ADC-like sample (int/float)
            - close(): cleanup

        Attaching a driver lets you swap the ADS1115 for any microhone input
        (USB mic reader, Pi HAT, a different ADC) without changing higher-level
        orchestration code.
        """
        self.driver = driver
        logger.info("🎚️ Microphone external driver attached")

    def _load_simulation(self, wav_path):
        """Internal: read WAV and resample to ADC poll rate."""
        with _wave.open(wav_path, 'rb') as wf:
            sr = wf.getframerate()
            frames = wf.getnframes()
            sampwidth = wf.getsampwidth()
            nch = wf.getnchannels()
            data = wf.readframes(frames)

        # Convert bytes to numpy
        if sampwidth == 2:
            dtype = _np.int16
        elif sampwidth == 4:
            dtype = _np.int32
        else:
            dtype = _np.int16

        audio = _np.frombuffer(data, dtype=dtype).astype(_np.float32)
        if nch > 1:
            audio = audio.reshape(-1, nch).mean(axis=1)

        # Normalize then scale to ADC-like range
        audio = audio - _np.mean(audio)
        maxv = _np.max(_np.abs(audio)) if _np.max(_np.abs(audio)) > 0 else 1.0
        audio = audio / maxv
        # scale to roughly same amplitude as ADC readings
        audio = audio * 10000.0

        # Resample to adc_rate
        target_len = int(len(audio) * (float(self.adc_rate) / float(sr)))
        if target_len <= 0:
            target_len = len(audio)
        t_old = _np.linspace(0.0, float(len(audio)) / sr, num=len(audio), endpoint=False)
        t_new = _np.linspace(0.0, float(len(audio)) / sr, num=target_len, endpoint=False)
        resampled = _np.interp(t_new, t_old, audio)

        self._sim_wav_data = resampled.astype(_np.float32)
        self._sim_index = 0

    def get_audio_clip(self):
        """Return latest buffered audio clip (2-3s) as numpy array"""
        import numpy as np
        with self._lock:
            buf = list(self.audio_buffer[-self.buffer_size:])

        if len(buf) == 0:
            return np.zeros(int(self.sample_rate * self.buffer_duration), dtype=np.float32)

        # Convert to float array
        arr = np.array(buf, dtype=np.float32)

        # Resample from adc_rate -> sample_rate using linear interpolation
        try:
            adc_rate = float(self.adc_rate)
            target_rate = float(self.sample_rate)
            duration = len(arr) / adc_rate
            target_len = int(duration * target_rate)
            if target_len <= 0:
                return np.zeros(int(self.sample_rate * self.buffer_duration), dtype=np.float32)

            # Original time axis
            t_old = np.linspace(0.0, duration, num=len(arr), endpoint=False)
            t_new = np.linspace(0.0, duration, num=target_len, endpoint=False)
            resampled = np.interp(t_new, t_old, arr)
            return resampled.astype(np.float32)
        except Exception:
            # Fallback - simple repeat/trim
            if len(arr) >= int(self.sample_rate * self.buffer_duration):
                return arr[:int(self.sample_rate * self.buffer_duration)]
            else:
                # pad
                needed = int(self.sample_rate * self.buffer_duration) - len(arr)
                return np.pad(arr, (0, needed), mode='constant').astype(np.float32)
    
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
