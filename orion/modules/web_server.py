"""
Project ORION - Web Server Module
Flask video streaming with automatic Ngrok tunneling
"""

import time
import logging
import threading
from flask import Flask, Response
from pyngrok import ngrok
from . import config

logger = logging.getLogger(__name__)


class VideoServer:
    """Manages Flask web server and video streaming"""
    
    def __init__(self, camera_manager, sentinel=None):
        self.camera = camera_manager
        self.sentinel = sentinel  # Reference to OrionSentinel for remote control
        self.app = Flask(__name__)
        self.public_url = None
        self.server_thread = None
        self.active_viewers = 0  # Track number of stream viewers
        self.last_stream_access = 0  # Timestamp of last stream request
        
        # Register routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/stream')
        def video_stream():
            """Video stream endpoint"""
            import time
            self.last_stream_access = time.time()

            # Always ensure ngrok tunnel is running for manual/remote requests
            if config.NGROK_ENABLED and not self.public_url:
                logger.info("🔄 (Re)starting ngrok tunnel for stream request")
                self.start_tunnel()

            # Ensure camera is active
            if self.sentinel and not self.camera.is_active:
                logger.info("📹 Stream requested - initializing camera")
                self.camera.initialize()

            return Response(
                self._generate_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
        
        @self.app.route('/health')
        def health():
            """Health check endpoint"""
            return {"status": "ok", "camera": self.camera.is_opened()}
        
        @self.app.route('/control/activate', methods=['POST'])
        def activate_intruder():
            """Backend can activate intruder mode on demand"""
            if self.sentinel:
                # Handle optional ngrok header (some clients send this)
                ngrok_header = None
                try:
                    ngrok_header = self.app.request.headers.get('ngrok-skip-browser-warning')
                except Exception:
                    # Flask may not expose request in this closure in some contexts; ignore
                    ngrok_header = None

                if ngrok_header:
                    logger.info(f"Received ngrok header for activate: {ngrok_header}")

                self.sentinel.request_intruder_mode()
                return {"status": "success", "mode": "INTRUDER"}, 200
            return {"status": "error", "message": "Sentinel not configured"}, 500
        
        @self.app.route('/control/deactivate', methods=['POST'])
        def deactivate_intruder():
            """Backend can deactivate intruder mode"""
            if self.sentinel:
                try:
                    ngrok_header = self.app.request.headers.get('ngrok-skip-browser-warning')
                except Exception:
                    ngrok_header = None

                if ngrok_header:
                    logger.info(f"Received ngrok header for deactivate: {ngrok_header}")

                self.sentinel.request_sentry_mode()
                return {"status": "success", "mode": "SENTRY"}, 200
            return {"status": "error", "message": "Sentinel not configured"}, 500
        
        @self.app.route('/status')
        def get_status():
            """Get current sentinel status"""
            if self.sentinel:
                import time
                return {
                    "mode": self.sentinel.mode,
                    "camera_active": self.camera.is_active,
                    "ai_loaded": self.sentinel.ai.is_loaded(),
                    "stream_idle_seconds": int(time.time() - self.last_stream_access) if self.last_stream_access else 0
                }, 200
            return {"status": "error"}, 500
        
        @self.app.route('/stream/keepalive', methods=['POST'])
        def stream_keepalive():
            """Backend sends this periodically to keep stream alive"""
            import time
            self.last_stream_access = time.time()
            return {"status": "ok", "message": "Stream kept alive"}, 200

        @self.app.route('/control/request_stream', methods=['POST'])
        def request_stream():
            """Backend can request the sentinel to provide/start the public stream URL.

            This endpoint returns quickly (200 accepted). The tunnel startup runs
            in the background. When a public URL becomes available the sentinel
            will update the backend registration with `streamUrl` and `ipAddress`.
            """
            if not self.sentinel:
                return {"status": "error", "message": "Sentinel not configured"}, 500

            # Always (re)start ngrok tunnel for manual/remote requests
            def _start_and_register():
                try:
                    public = self.start_tunnel()
                    if public:
                        # Update communicator and register with backend including ipAddress
                        if hasattr(self.sentinel, 'comms') and self.sentinel.comms:
                            try:
                                self.sentinel.comms.set_stream_url(public)

                                # Attempt to discover local IP for backend record
                                ip_addr = None
                                try:
                                    import socket
                                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                                    try:
                                        s.connect(('8.8.8.8', 80))
                                        ip_addr = s.getsockname()[0]
                                    finally:
                                        s.close()
                                except Exception:
                                    ip_addr = None

                                # Register device with backend including streamUrl and ipAddress
                                try:
                                    self.sentinel.comms.register_device(self.sentinel.gps.get_location(), battery_level=85, ip_address=ip_addr, stream_url=f"{public}/stream")
                                except Exception as e:
                                    logger.error(f"Failed to register device with stream URL: {e}")
                            except Exception as e:
                                logger.error(f"Failed to update communicator with public URL: {e}")
                except Exception as e:
                    logger.error(f"Failed to start tunnel in background: {e}")

            bg = threading.Thread(target=_start_and_register, daemon=True)
            bg.start()

            # Return accepted quickly; backend may poll registration or status endpoint
            return {"status": "accepted", "message": "Stream is being prepared"}, 200
    
    def _generate_stream(self):
        """Generate video stream frames"""
        while True:
            try:
                frame_bytes = self.camera.get_jpeg_frame()
                if frame_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           frame_bytes + 
                           b'\r\n')
                else:
                    # No frame available, wait and retry
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"❌ Stream error: {e}")
                time.sleep(0.5)
            
            time.sleep(0.05)  # ~20 FPS
    
    def start_tunnel(self):
        """
        Start Ngrok tunnel
        
        Returns:
            str: Public URL or None if failed
        """
        if not config.NGROK_ENABLED:
            logger.info("⚠️  Ngrok disabled - using local IP only")
            return None
            
        try:
            tunnel = ngrok.connect(config.VIDEO_PORT)
            self.public_url = tunnel.public_url
            logger.info(f"🚇 NGROK TUNNEL: {self.public_url}")
            return self.public_url
        except Exception as e:
            logger.error(f"❌ Ngrok failed: {e}")
            logger.warning("⚠️  Continuing with local IP only")
            return None
    
    def start(self):
        """Start Flask server and Ngrok tunnel in background"""
        
        # Start tunnel first
        self.start_tunnel()
        
        # Start Flask in background thread
        self.server_thread = threading.Thread(
            target=self._run_flask,
            daemon=True
        )
        self.server_thread.start()
        
        # Give server time to start
        time.sleep(2)
        logger.info(f"🌐 Video server started on port {config.VIDEO_PORT}")
    
    def _run_flask(self):
        """Run Flask server (called in background thread)"""
        self.app.run(
            host='0.0.0.0',
            port=config.VIDEO_PORT,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    
    def stop(self):
        """Stop server and close tunnel"""
        if config.NGROK_ENABLED:
            try:
                ngrok.kill()
                logger.info("🚇 Ngrok tunnel closed")
            except Exception as e:
                logger.error(f"Error closing tunnel: {e}")
    
    def get_public_url(self):
        """Get the public stream URL"""
        return self.public_url
