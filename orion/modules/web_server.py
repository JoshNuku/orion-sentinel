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
    
    def __init__(self, camera_manager):
        self.camera = camera_manager
        self.app = Flask(__name__)
        self.public_url = None
        self.server_thread = None
        
        # Register routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/stream')
        def video_stream():
            """Video stream endpoint"""
            return Response(
                self._generate_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
        
        @self.app.route('/health')
        def health():
            """Health check endpoint"""
            return {"status": "ok", "camera": self.camera.is_opened()}
    
    def _generate_stream(self):
        """Generate video stream frames"""
        while True:
            frame_bytes = self.camera.get_jpeg_frame()
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       frame_bytes + 
                       b'\r\n')
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
