#!/usr/bin/env python3
"""Orchestrator module moved from top-level main.py

Full orchestrator implementation copied from the previous top-level
`main.py`. This module exposes `OrionSentinel` which is importable and
runnable by a small top-level runner.
"""

import time
import logging
import base64
import cv2
import threading
from . import config
from .hardware import GPSTracker, CameraManager, MicrophoneMonitor
from .ai_engine import IntelligenceUnit, AudioIntelligenceUnit
from .communication import Communicator
from .web_server import VideoServer

# Try to import ADS1115Driver for automatic attachment; optional.
try:
    from .hardware_components.mic_driver import ADS1115Driver
except Exception:
    ADS1115Driver = None

logger = logging.getLogger(__name__)


class OrionSentinel:
    """Main sentinel orchestrator"""

    def __init__(self):
        # Initialize components
        self.gps = GPSTracker()
        self.camera = CameraManager()
        self.microphone = MicrophoneMonitor()

        # Attach ADS1115Driver automatically when available
        if ADS1115Driver is not None:
            try:
                driver = ADS1115Driver(channel=config.MIC_CHANNEL)
                self.microphone.set_driver(driver)
                logger.info("🎚️ ADS1115Driver attached to MicrophoneMonitor")
            except Exception as e:
                logger.warning(f"Could not attach ADS1115Driver: {e}")

        self.audio_ai = AudioIntelligenceUnit()
        self.ai = IntelligenceUnit()
        self.comms = Communicator()
        self.web_server = VideoServer(self.camera, sentinel=self)

        try:
            audio_class_names = config.load_audio_classes()
        except Exception:
            audio_class_names = None
        self.audio_ai.load_model(None, audio_class_names)

        # System state
        self.mode = config.MODE_SENTRY
        self.last_alert_time = 0
        self.last_sensor_event_time = 0
        self.intruder_start_time = 0
        self.current_triggered_sensors = []
        self.running = True
        self.remote_control_request = None
        self.no_threat_frame_count = 0
        self.NO_THREAT_FRAME_LIMIT = 20
        self.last_alert_threat = None
        self.same_threat_count = 0

    def initialize(self):
        """Initialize all systems"""
        logger.info("=" * 60)
        logger.info("PROJECT ORION - SENTINEL DEVICE")
        logger.info(f"Device ID: {config.DEVICE_ID}")
        logger.info("=" * 60)

        logger.info("📹 Camera standby (will activate on demand)")

        if self.microphone.initialize():
            self.microphone.start_monitoring()

        self.web_server.start()

        location = self.gps.get_location()
        self.comms.register_device(location)

        logger.info("✅ SYSTEM ONLINE - ENTERING SENTRY MODE")

    def enter_sentry_mode(self):
        """Enter low-power sentry mode"""
        self.mode = config.MODE_SENTRY
        if self.ai.is_loaded():
            self.ai.unload_model()
        if self.microphone.is_active:
            self.microphone.reset_peak()
        self.comms.update_status("active", self.gps.get_location())
        logger.info("💤 SENTRY MODE: Monitoring sensors + microphone...")

    def request_intruder_mode(self):
        logger.info("📡 Backend requested INTRUDER mode")
        self.remote_control_request = config.MODE_INTRUDER

    def request_sentry_mode(self):
        logger.info("📡 Backend requested SENTRY mode")
        self.remote_control_request = config.MODE_SENTRY

    def enter_intruder_mode(self, trigger_type=None, triggered_sensors=None):
        self.mode = config.MODE_INTRUDER
        if not self.camera.is_active:
            self.camera.initialize()
            logger.info("⏳ Camera warming up...")
            time.sleep(2)
        self.no_threat_frame_count = 0
        trigger_type_map = {
            'microphone': 'microphone',
            'remote': 'remote',
            'ai': 'ai',
            'camera': 'camera',
            'manual': 'manual',
            'sound': 'sound',
        }
        mapped_trigger_type = trigger_type_map.get(trigger_type, trigger_type)
        self.ai.load_model()
        self.current_triggered_sensors = triggered_sensors or []
        self.intruder_start_time = time.time()
        self.comms.update_status("alert", self.gps.get_location(), trigger_type=mapped_trigger_type)
        logger.warning("🚨 INTRUDER MODE: Active threat detection!")

    def sentry_loop(self):
        if self.remote_control_request == config.MODE_INTRUDER:
            logger.info("📡 Processing remote activation request")
            self.remote_control_request = None
            self.enter_intruder_mode(trigger_type='remote')
            return

        if self.camera.is_active:
            self.camera.release()

        if self.microphone.is_active:
            audio_clip = self.microphone.get_audio_clip()
            class_name, confidence = self.audio_ai.infer(audio_clip)
            logger.info(f"🎤 Audio AI: {class_name} ({confidence:.2%})")
            if class_name in ["Chainsaw", "Excavator"] and confidence >= config.AUDIO_CONFIDENCE_THRESHOLD:
                logger.warning(f"🎤 THREAT AUDIO DETECTED: {class_name} ({confidence:.2%})")
                self.last_sensor_event_time = time.time()
                self.confirmation_mode(class_name)
                return

        time.sleep(config.SENSOR_POLL_INTERVAL)

    def confirmation_mode(self, audio_class):
        logger.info(f"🔔 Entering Confirmation Mode for {audio_class}")
        if not self.camera.is_active:
            self.camera.initialize()
            logger.info("⏳ Camera warming up...")
            time.sleep(2)
        self.ai.load_model()
        start_time = time.time()
        visual_match = False
        matched_class = None
        while time.time() - start_time < config.STREAM_DURATION:
            ret, frame = self.camera.capture_frame()
            if ret and frame is not None:
                threat, confidence = self.ai.analyze_frame(frame)
                logger.info(f"🖼️ Vision AI: {threat} ({confidence:.2%})")
                if audio_class == "Chainsaw" and threat == "person" and confidence >= 0.5:
                    visual_match = True
                    matched_class = threat
                    break
                if audio_class == "Excavator" and threat == "excavator" and confidence >= 0.5:
                    visual_match = True
                    matched_class = threat
                    break
            time.sleep(0.2)

        if visual_match:
            logger.warning(f"✅ Verified threat: {audio_class} + {matched_class}")
            self.send_priority_alert(audio_class, matched_class, high_priority=True)
        else:
            logger.warning(f"⚠️ Audio-only threat: {audio_class}")
            self.send_priority_alert(audio_class, None, high_priority=False)

        self.camera.release()
        self.ai.unload_model()
        logger.info("🔄 Returning to Listening Mode")

    def send_priority_alert(self, audio_class, visual_class, high_priority):
        if visual_class:
            threat_type = visual_class
            confidence = 0.95 if high_priority else 0.75
        else:
            threat_type = audio_class or 'unknown'
            confidence = 0.65 if high_priority else 0.55

        frame_base64 = None
        if visual_class:
            ret, frame = self.camera.capture_frame()
            if ret and frame is not None:
                _, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frame_base64 = base64.b64encode(jpeg_buffer).decode('utf-8')

        try:
            self.comms.send_alert(
                threat_type,
                confidence,
                self.gps.get_location(),
                frame_base64,
                triggered_sensors=self.current_triggered_sensors,
                trigger_type='microphone' if not visual_class else 'ai'
            )
        except Exception as e:
            logger.error(f"❌ Failed to send priority alert: {e}")

    def intruder_loop(self):
        if self.remote_control_request == config.MODE_SENTRY:
            logger.info("📡 Processing remote deactivation request")
            self.remote_control_request = None
            self.enter_sentry_mode()
            return

        if self.mode != config.MODE_INTRUDER:
            time.sleep(0.1)
            return

        ret, frame = self.camera.capture_frame()

        if ret and frame is not None:
            threat, confidence = self.ai.analyze_frame(frame)

            if threat and threat != 'unknown' and confidence >= 0.5:
                self.no_threat_frame_count = 0
                now = time.time()
                send_alert = False
                if self.last_alert_threat == threat and (now - self.last_alert_time) < config.ALERT_COOLDOWN:
                    self.same_threat_count += 1
                    if self.same_threat_count <= 2:
                        send_alert = True
                    else:
                        logger.info("Skipping alert - cooldown active for same threat")
                else:
                    self.same_threat_count = 1
                    send_alert = True

                if send_alert:
                    logger.warning(f"⚠️  THREAT DETECTED: {threat} ({confidence:.2%})")
                    if self.microphone.is_active:
                        mic_stats = self.microphone.get_stats()
                        logger.info(f"🎤 Sound: {mic_stats['current']} (Peak: {mic_stats['peak']})")

                    alert_thread = threading.Thread(target=self._send_alert_async, args=(frame.copy(), threat, confidence), daemon=True)
                    alert_thread.start()
                    self.last_alert_time = now
                    self.last_alert_threat = threat
                
            else:
                self.no_threat_frame_count += 1
                if confidence < 0.5:
                    logger.info(f"Skipping alert - low confidence ({confidence})")
                elif threat == 'unknown':
                    logger.info("Skipping alert - unknown threat type")

            if self.no_threat_frame_count >= self.NO_THREAT_FRAME_LIMIT:
                logger.info(f"No threat detected for {self.NO_THREAT_FRAME_LIMIT} frames, stopping camera to save battery.")
                self.camera.release()
                self.no_threat_frame_count = 0
                self.enter_sentry_mode()
                return

        if self.intruder_start_time and (time.time() - self.intruder_start_time > config.STREAM_DURATION):
            logger.info("⏱️  Timeout - returning to sentry mode")
            self.enter_sentry_mode()

        time.sleep(0.1)

    def _send_alert_async(self, frame, threat, confidence, trigger_type='ai'):
        try:
            threat_type_map = {
                'person': 'person',
                'car': 'car',
                'truck': 'truck',
                'motorcycle': 'motorcycle',
                'bus': 'bus',
                'animal': 'animal',
                'unknown': 'unknown',
            }
            mapped_threat = threat_type_map.get(threat, 'unknown')

            trigger_type_map = {
                'microphone': 'microphone',
                'remote': 'remote',
                'ai': 'ai',
                'camera': 'camera',
                'manual': 'manual',
                'sound': 'sound',
            }
            mapped_trigger_type = trigger_type_map.get(trigger_type, trigger_type)

            public_url = self.web_server.get_public_url()
            if not public_url:
                try:
                    public_url = self.web_server.start_tunnel()
                except Exception:
                    public_url = None

            if public_url:
                self.comms.set_stream_url(public_url)
            else:
                try:
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        s.connect(('8.8.8.8', 80))
                        local_ip = s.getsockname()[0]
                    finally:
                        s.close()
                    local_base = f"http://{local_ip}:{config.VIDEO_PORT}"
                    self.comms.set_stream_url(local_base)
                except Exception:
                    pass

            _, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(jpeg_buffer).decode('utf-8')

            self.comms.send_alert(
                mapped_threat,
                confidence,
                self.gps.get_location(),
                frame_base64,
                triggered_sensors=self.current_triggered_sensors,
                trigger_type=mapped_trigger_type
            )
            try:
                self.last_alert_time = time.time()
                self.intruder_start_time = time.time()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"❌ Failed to send alert: {e}")

    def run(self):
        try:
            self.initialize()
            while self.running:
                if self.mode == config.MODE_SENTRY:
                    self.sentry_loop()
                elif self.mode == config.MODE_INTRUDER:
                    self.intruder_loop()
        except KeyboardInterrupt:
            logger.info("\n⏹️  Shutdown requested")
            self.shutdown()

    def shutdown(self):
        logger.info("Shutting down...")
        self.web_server.stop()
        self.camera.release()
        if self.microphone.is_active:
            self.microphone.release()
        logger.info("✅ Shutdown complete")
