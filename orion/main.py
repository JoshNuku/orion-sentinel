#!/usr/bin/env python3
"""
Project ORION - Main Orchestrator
Sentinel Device with AI Detection, Power Management, and Automatic Tunneling
"""

import time
import logging
import base64
import cv2
import threading
from modules import config
from modules.hardware import GPIOSensors, GPSTracker, CameraManager, MicrophoneMonitor
from modules.ai_engine import IntelligenceUnit
from modules.communication import Communicator
from modules.web_server import VideoServer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class OrionSentinel:
    """Main sentinel orchestrator"""
    
    def __init__(self):
        # Initialize all modules
        self.sensors = GPIOSensors()
        self.gps = GPSTracker()
        self.camera = CameraManager()
        self.microphone = MicrophoneMonitor()
        self.ai = IntelligenceUnit()
        self.comms = Communicator()
        self.web_server = VideoServer(self.camera, sentinel=self)
        
        # System state
        self.mode = config.MODE_SENTRY
        self.last_alert_time = 0
        self.last_sensor_event_time = 0
        self.intruder_start_time = 0
        self.current_triggered_sensors = []
        self.running = True
        self.remote_control_request = None  # For backend control
        # For battery saving: count consecutive no-threat frames
        self.no_threat_frame_count = 0
        self.NO_THREAT_FRAME_LIMIT = 20  # Stop camera after 20 no-threat frames (tune as needed)
        # For smarter cooldown
        self.last_alert_threat = None
        self.same_threat_count = 0
    
    def initialize(self):
        """Initialize all systems"""
        logger.info("="*60)
        logger.info("PROJECT ORION - SENTINEL DEVICE")
        logger.info(f"Device ID: {config.DEVICE_ID}")
        logger.info("="*60)
        
        # Don't initialize camera yet - wait for stream request or trigger
        # This saves battery in sentry mode
        logger.info("📹 Camera standby (will activate on demand)")
        
        # Initialize microphone for sentry monitoring
        if self.microphone.initialize():
            self.microphone.start_monitoring()
        
        # Start web server (local Flask) but do not necessarily start the public tunnel.
        # The public ngrok tunnel (and public stream URL) will be started only when needed
        # (i.e., when a threat is detected) to avoid exposing the stream unnecessarily.
        self.web_server.start()
        
        # Register with backend
        location = self.gps.get_location()
        self.comms.register_device(location)
        
        logger.info("✅ SYSTEM ONLINE - ENTERING SENTRY MODE")
    
    def enter_sentry_mode(self):
        """Enter low-power sentry mode"""
        self.mode = config.MODE_SENTRY
        
        # Unload AI but KEEP camera running for stream
        if self.ai.is_loaded():
            self.ai.unload_model()
        # Don't release camera - keep it for continuous streaming
        
        # Reset microphone peak for new monitoring period
        if self.microphone.is_active:
            self.microphone.reset_peak()
        
        # Update backend status
        self.comms.update_status("active", self.gps.get_location())
        logger.info("💤 SENTRY MODE: Monitoring sensors + microphone...")
    
    def request_intruder_mode(self):
        """Backend request to enter intruder mode"""
        logger.info("📡 Backend requested INTRUDER mode")
        self.remote_control_request = config.MODE_INTRUDER
    
    def request_sentry_mode(self):
        """Backend request to return to sentry mode"""
        logger.info("📡 Backend requested SENTRY mode")
        self.remote_control_request = config.MODE_SENTRY
    
    def enter_intruder_mode(self, trigger_type=None, triggered_sensors=None):
        """Enter active threat detection mode"""
        self.mode = config.MODE_INTRUDER

        # Ensure camera is initialized when entering intruder mode
        if not self.camera.is_active:
            self.camera.initialize()
            logger.info("⏳ Camera warming up...")
            time.sleep(2)

        # Reset no-threat frame counter when entering intruder mode
        self.no_threat_frame_count = 0

        # Map trigger_type to backend spec
        trigger_type_map = {
            'gpio': 'pir',
            'microphone': 'microphone',
            'remote': 'remote',
            'ai': 'ai',
            'camera': 'camera',
            'manual': 'manual',
            'sound': 'sound',
            'vibration': 'vibration',
        }
        mapped_trigger_type = trigger_type_map.get(trigger_type, trigger_type)

        # Load AI
        self.ai.load_model()

        # Record triggered sensors for later alert payloads
        self.current_triggered_sensors = triggered_sensors or []

        # Record when intruder mode started (used for timeout)
        self.intruder_start_time = time.time()

        # Update backend status (include mapped trigger type)
        self.comms.update_status("alert", self.gps.get_location(), trigger_type=mapped_trigger_type)
        logger.warning("🚨 INTRUDER MODE: Active threat detection!")
        # No alert is sent here! Only AI detection will send alerts.
    
    def sentry_loop(self):
        """Main loop for sentry mode"""
        # Check for remote control request
        if self.remote_control_request == config.MODE_INTRUDER:
            logger.info("📡 Processing remote activation request")
            self.remote_control_request = None
            # Ensure camera is initialized before entering intruder mode
            if not self.camera.is_active:
                self.camera.initialize()
                logger.info("⏳ Camera warming up...")
                time.sleep(2)
            self.enter_intruder_mode(trigger_type='remote')
            return
        
        # Check if camera should be stopped to save battery
        if self.camera.is_active and self.web_server.last_stream_access > 0:
            idle_time = time.time() - self.web_server.last_stream_access
            if idle_time > config.STREAM_TIMEOUT:
                logger.info(f"💤 Stream idle for {int(idle_time)}s - stopping camera to save battery")
                self.camera.release()
        
        # Check GPIO sensors
        sensor_triggered = False
        triggered_list = []
        try:
            triggered_list = self.sensors.get_triggered_sensors()
            sensor_triggered = len(triggered_list) > 0
        except Exception:
            sensor_triggered = self.sensors.any_trigger()

        if sensor_triggered:
            now = time.time()
            # Debounce repeated sensor triggers
            if now - self.last_sensor_event_time < config.SENSOR_DEBOUNCE_SECONDS:
                logger.info("⚡ Sensor triggered but debounced (recent event)")
            else:
                logger.warning(f"⚡ GPIO SENSOR TRIGGERED! Sensors: {triggered_list}")
                self.last_sensor_event_time = now
                # Ensure camera is initialized before entering intruder mode
                if not self.camera.is_active:
                    self.camera.initialize()
                    logger.info("⏳ Camera warming up...")
                    time.sleep(2)
                self.enter_intruder_mode(trigger_type='gpio', triggered_sensors=triggered_list)
                return
        
        # Check microphone sound level
        if self.microphone.is_active and self.microphone.is_loud():
            mic_stats = self.microphone.get_stats()
            now = time.time()
            if now - self.last_sensor_event_time < config.SENSOR_DEBOUNCE_SECONDS:
                logger.info("🎤 Loud sound detected but debounced (recent event)")
            else:
                logger.warning(f"🎤 LOUD SOUND DETECTED! Level: {mic_stats['current']} (Threshold: {mic_stats['threshold']})")
                self.last_sensor_event_time = now
                # Ensure camera is initialized before entering intruder mode
                if not self.camera.is_active:
                    self.camera.initialize()
                    logger.info("⏳ Camera warming up...")
                    time.sleep(2)
                self.enter_intruder_mode(trigger_type='microphone', triggered_sensors=['SOUND'])
                return
        
        time.sleep(config.SENSOR_POLL_INTERVAL)
    
    def intruder_loop(self):
        """Main loop for intruder mode"""
        # Check for remote control request to deactivate
        if self.remote_control_request == config.MODE_SENTRY:
            logger.info("📡 Processing remote deactivation request")
            self.remote_control_request = None
            self.enter_sentry_mode()
            return

        # Only send alerts in INTRUDER mode
        if self.mode != config.MODE_INTRUDER:
            time.sleep(0.1)
            return

        # Capture and analyze frame
        ret, frame = self.camera.capture_frame()

        if ret and frame is not None:
            threat, confidence = self.ai.analyze_frame(frame)

            # Only send alert if threat is real, not 'unknown', and confidence >= 0.5
            if threat and threat != 'unknown' and confidence >= 0.5:
                self.no_threat_frame_count = 0  # Reset counter on real threat

                now = time.time()
                send_alert = False

                # Smarter cooldown: allow up to 2 alerts for the same threat within cooldown
                if self.last_alert_threat == threat and (now - self.last_alert_time) < config.ALERT_COOLDOWN:
                    self.same_threat_count += 1
                    if self.same_threat_count <= 2:
                        send_alert = True
                    else:
                        logger.info("Skipping alert - cooldown active for same threat")
                else:
                    # New threat or cooldown expired
                    self.same_threat_count = 1
                    send_alert = True

                if send_alert:
                    logger.warning(f"⚠️  THREAT DETECTED: {threat} ({confidence:.2%})")

                    # Log microphone stats if available
                    if self.microphone.is_active:
                        mic_stats = self.microphone.get_stats()
                        logger.info(f"🎤 Sound: {mic_stats['current']} (Peak: {mic_stats['peak']})")

                    # Send alert in background thread to avoid blocking camera stream
                    alert_thread = threading.Thread(
                        target=self._send_alert_async,
                        args=(frame.copy(), threat, confidence),
                        daemon=True
                    )
                    alert_thread.start()
                    self.last_alert_time = now
                    self.last_alert_threat = threat
                # else: already logged skip above
            else:
                self.no_threat_frame_count += 1
                if confidence < 0.5:
                    logger.info(f"Skipping alert - low confidence ({confidence})")
                elif threat == 'unknown':
                    logger.info("Skipping alert - unknown threat type")

            # If too many consecutive no-threat frames, stop camera to save battery
            if self.no_threat_frame_count >= self.NO_THREAT_FRAME_LIMIT:
                logger.info(f"No threat detected for {self.NO_THREAT_FRAME_LIMIT} frames, stopping camera to save battery.")
                self.camera.release()
                self.no_threat_frame_count = 0
                # Return to sentry mode
                self.enter_sentry_mode()
                return

        # Check timeout to return to sentry mode (based on intruder start)
        if self.intruder_start_time and (time.time() - self.intruder_start_time > config.STREAM_DURATION):
            logger.info("⏱️  Timeout - returning to sentry mode")
            self.enter_sentry_mode()

        time.sleep(0.1)
    
    def _send_alert_async(self, frame, threat, confidence, trigger_type='ai'):
        """Send alert in background thread (non-blocking)

        Now includes triggered sensor metadata when available.
        """
        try:
            # Map threatType to backend spec
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

            # Map triggerType to backend spec
            trigger_type_map = {
                'gpio': 'pir',
                'microphone': 'microphone',
                'remote': 'remote',
                'ai': 'ai',
                'camera': 'camera',
                'manual': 'manual',
                'sound': 'sound',
                'vibration': 'vibration',
            }
            mapped_trigger_type = trigger_type_map.get(trigger_type, trigger_type)

            # Ensure a stream URL is available to include in the alert.
            public_url = self.web_server.get_public_url()
            if not public_url:
                # Try to start the public tunnel now (may return None if ngrok not available)
                try:
                    public_url = self.web_server.start_tunnel()
                except Exception:
                    public_url = None

            if public_url:
                # Register the public URL (base) with communicator so send_alert will include it
                self.comms.set_stream_url(public_url)
            else:
                # Fallback: use local network IP so backend can reach the sentinel
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

            # Encode frame as JPEG and convert to base64
            _, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(jpeg_buffer).decode('utf-8')

            # Send alert to backend (includes streamUrl if communicator has it)
            self.comms.send_alert(
                mapped_threat,
                confidence,
                self.gps.get_location(),
                frame_base64,
                triggered_sensors=self.current_triggered_sensors,
                trigger_type=mapped_trigger_type
            )
            # Record when the last alert was sent (used for cooldown)
            try:
                self.last_alert_time = time.time()
                self.intruder_start_time = time.time()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"❌ Failed to send alert: {e}")
    
    def run(self):
        """Main execution loop"""
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
        """Clean shutdown"""
        logger.info("Shutting down...")
        
        # Stop web server
        self.web_server.stop()
        
        # Release hardware
        self.camera.release()
        if self.microphone.is_active:
            self.microphone.release()
        self.sensors.cleanup()
        
        logger.info("✅ Shutdown complete")


def main():
    """Entry point"""
    sentinel = OrionSentinel()
    sentinel.run()


if __name__ == "__main__":
    main()
