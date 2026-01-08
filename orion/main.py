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
        self.running = True
        self.remote_control_request = None  # For backend control
    
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
        
        # Start web server and tunnel
        self.web_server.start()
        
        # Set stream URL in communicator
        public_url = self.web_server.get_public_url()
        if public_url:
            self.comms.set_stream_url(public_url)
        
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
    
    def enter_intruder_mode(self):
        """Enter active threat detection mode"""
        self.mode = config.MODE_INTRUDER
        
        # Initialize camera if not active
        if not self.camera.is_active:
            self.camera.initialize()
            logger.info("⏳ Camera warming up...")
            time.sleep(2)
        
        # Load AI
        self.ai.load_model()
        
        # Reset alert timer
        self.last_alert_time = time.time()
        
        # Update backend status
        self.comms.update_status("alert", self.gps.get_location())
        logger.warning("🚨 INTRUDER MODE: Active threat detection!")
    
    def sentry_loop(self):
        """Main loop for sentry mode"""
        # Check for remote control request
        if self.remote_control_request == config.MODE_INTRUDER:
            logger.info("📡 Processing remote activation request")
            self.remote_control_request = None
            self.enter_intruder_mode()
            return
        
        # Check if camera should be stopped to save battery
        if self.camera.is_active and self.web_server.last_stream_access > 0:
            idle_time = time.time() - self.web_server.last_stream_access
            if idle_time > config.STREAM_TIMEOUT:
                logger.info(f"💤 Stream idle for {int(idle_time)}s - stopping camera to save battery")
                self.camera.release()
        
        # Check GPIO sensors
        if self.sensors.any_trigger():
            logger.warning("⚡ GPIO SENSOR TRIGGERED!")
            self.enter_intruder_mode()
            return
        
        # Check microphone sound level
        if self.microphone.is_active and self.microphone.is_loud():
            mic_stats = self.microphone.get_stats()
            logger.warning(f"🎤 LOUD SOUND DETECTED! Level: {mic_stats['current']} (Threshold: {mic_stats['threshold']})")
            self.enter_intruder_mode()
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
        
        # Capture and analyze frame
        ret, frame = self.camera.capture_frame()
        
        if ret and frame is not None:
            threat, confidence = self.ai.analyze_frame(frame)
            
            if threat and confidence >= config.CONFIDENCE_THRESHOLD:
                # Check alert cooldown
                if time.time() - self.last_alert_time >= config.ALERT_COOLDOWN:
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
                    
                    self.last_alert_time = time.time()
        
        # Check timeout to return to sentry mode
        if time.time() - self.last_alert_time > config.STREAM_DURATION:
            logger.info("⏱️  Timeout - returning to sentry mode")
            self.enter_sentry_mode()
        
        time.sleep(0.1)
    
    def _send_alert_async(self, frame, threat, confidence):
        """Send alert in background thread (non-blocking)"""
        try:
            # Encode frame as JPEG and convert to base64
            _, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(jpeg_buffer).decode('utf-8')
            
            # Send alert to backend
            self.comms.send_alert(threat, confidence, self.gps.get_location(), frame_base64)
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
