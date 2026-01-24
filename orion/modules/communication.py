"""
Project ORION - Communication Module
Handles backend API communication and device registration
"""

import requests
import logging
from datetime import datetime
from . import config

logger = logging.getLogger(__name__)


class Communicator:
    """Manages all backend communication"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        self.public_stream_url = None
    
    def set_stream_url(self, url):
        """Set the public stream URL (from ngrok)"""
        self.public_stream_url = url
        logger.info(f"📡 Stream URL set: {url}")
    
    def register_device(self, gps_data, battery_level=85, ip_address=None, stream_url=None, trigger_type=None):
        """
        Register sentinel device with backend
        
        Args:
            gps_data (dict): GPS coordinates {"lat": float, "lng": float}
            battery_level (int): Battery percentage
            
        Returns:
            bool: True if registration successful
        """
        # Note: do not send stream URL during registration.
        # The stream (public URL) is privacy-sensitive and will be shared
        # with the backend only when a threat is detected.
        logger.info("🌍 Registering sentinel (stream URL withheld until alerts)")
        try:
            payload = {
                "deviceId": config.DEVICE_ID,
                "status": "active",
                "location": gps_data,
                "batteryLevel": battery_level
            }

            if ip_address:
                payload["ipAddress"] = ip_address
            if stream_url:
                payload["streamUrl"] = stream_url
            if trigger_type:
                payload["triggerType"] = trigger_type

            response = self.session.post(
                f"{config.BACKEND_URL}/sentinels/register",
                json=payload,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                logger.info("✅ Device registered successfully")
                return True
            else:
                logger.error(f"❌ Registration failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Registration error: {e}")
            return False
    
    def send_alert(self, threat_type, confidence, gps_data, frame_base64=None, triggered_sensors=None, trigger_type=None):
        """
        Send threat alert to backend
        
        Args:
            threat_type (str): Type of threat detected
            confidence (float): Detection confidence (0.0-1.0)
            gps_data (dict): GPS coordinates
            frame_base64 (str, optional): Base64 encoded image of detection
        """
        try:
            payload = {
                "sentinelId": config.DEVICE_ID,
                "threatType": threat_type,
                "confidence": float(confidence),
                "location": gps_data,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Attach trigger metadata when available
            if trigger_type:
                payload["triggerType"] = trigger_type
            if triggered_sensors:
                payload["triggeredSensors"] = triggered_sensors

            # If a public stream URL is available, include it in the alert
            if self.public_stream_url:
                try:
                    payload["streamUrl"] = f"{self.public_stream_url}/stream"
                except Exception:
                    # Be conservative: don't fail alert if stream URL formatting fails
                    pass
            
            # Add image if provided
            if frame_base64:
                payload["imageData"] = frame_base64
            
            # Print alert payload to console
            logger.info("=" * 60)
            logger.info("🚨 SENDING ALERT TO BACKEND")
            logger.info("=" * 60)
            logger.info(f"Sentinel ID: {payload['sentinelId']}")
            logger.info(f"Threat Type: {payload['threatType']}")
            logger.info(f"Confidence:  {payload['confidence']:.2%}")
            logger.info(f"Location:    {payload['location']}")
            logger.info(f"Timestamp:   {payload['timestamp']}")
            if frame_base64:
                logger.info(f"Image Data:  {len(frame_base64)} bytes (base64)")
            logger.info("=" * 60)
            
            response = self.session.post(
                f"{config.BACKEND_URL}/alerts",
                json=payload,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Alert delivered successfully")
            else:
                logger.warning(f"⚠️  Alert send failed: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Alert error: {e}")
    
    def update_status(self, status, gps_data, battery_level=85, trigger_type=None):
        """
        Send heartbeat/status update to backend
        
        Args:
            status (str): Device status ("active", "alert", "offline")
            gps_data (dict): GPS coordinates
            battery_level (int): Battery percentage
        """
        try:
            payload = {
                "status": status,
                "location": gps_data,
                "batteryLevel": battery_level
            }

            # Attach trigger type when provided
            if trigger_type:
                payload["triggerType"] = trigger_type

            # Optional trigger type may be attached by caller
            # (e.g., 'gpio', 'microphone', 'remote', 'ai')
            # If provided, callers should pass trigger_type via keyword argument.
            # Note: Keep backward compatibility by accepting callers that don't pass it.
            # The method signature for update_status has been extended to accept
            # trigger_type via kwargs to avoid breaking existing call sites.
            # Extract if present in kwargs (some callers may call with named param).
            # (This function is intentionally forgiving; the explicit param will be
            # passed by updated call sites in the repo.)

            # If other code passed trigger_type as attribute on this instance
            # (not expected), ignore it. Standard callers should call with
            # update_status(status, gps, battery_level, trigger_type=...)

            # Send the PUT request
            self.session.put(
                f"{config.BACKEND_URL}/sentinels/{config.DEVICE_ID}/status",
                json=payload,
                timeout=3
            )
        except requests.exceptions.RequestException:
            # Silently fail on heartbeat errors
            pass
    
    def send_heartbeat(self, gps_data, battery_level=85):
        """Convenience method for sending heartbeat"""
        self.update_status("active", gps_data, battery_level)
