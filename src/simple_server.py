#!/usr/bin/env python3
"""
Simple HTTP server for the Knowledge Repository UI
"""

import http.server
import socketserver
import os
import sys
import logging
import webbrowser
from pathlib import Path

# Setup logging to capture all console output
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize standard logging first
from src.logging_config import setup_logging
setup_logging(log_file="simple_ui.log")

# Initialize console capture if not already initialized
from src.console_capture import setup_global_console_logging
try:
    console_capture = setup_global_console_logging()
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Console capture already initialized or failed: {e}")
    console_capture = None
logger = logging.getLogger(__name__)

PORT = 7860
DIRECTORY = Path(__file__).parent.parent  # Serve from project root, not src/

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_GET(self):
        # Handle favicon.ico requests specifically
        if self.path == '/favicon.ico':
            favicon_path = DIRECTORY / 'favicon.ico'
            if favicon_path.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'image/x-icon')
                self.send_header('Content-Length', str(favicon_path.stat().st_size))
                self.end_headers()
                with open(favicon_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "File Not Found")
                return

        # Handle all other GET requests normally
        super().do_GET()

    def log_message(self, format, *args):
        # Suppress logging for favicon requests to reduce noise
        if '/favicon.ico' not in args[0]:
            super().log_message(format, *args)

def start_server():
    """Start the simple HTTP server"""
    import socket

    def find_available_port(start_port):
        """Find an available port starting from start_port"""
        for port_num in range(start_port, start_port + 10):  # Try 10 ports
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex(("", port_num))
                    if result != 0:  # Port is available
                        return port_num
            except Exception:
                continue
        raise RuntimeError(f"No available ports found in range {start_port}-{start_port + 9}")

    try:
        # Try the default port first
        try:
            with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
                logger.info(f"🚀 Simple UI Server running at http://localhost:{PORT}")
                logger.info(f"📁 Serving directory: {DIRECTORY}")
                logger.info(f"🌐 Open http://localhost:{PORT}/simple_ui.html in your browser")
                logger.info("Press Ctrl+C to stop the server")

                # Try to open browser automatically (optional)
                try:
                    webbrowser.open(f'http://localhost:{PORT}/simple_ui.html')
                    logger.info(f"Browser automatically opened to http://localhost:{PORT}/simple_ui.html")
                except Exception as e:
                    logger.warning(f"Could not auto-open browser: {e}")

                logger.info("Simple UI Server started successfully")
                httpd.serve_forever()
        except OSError as e:
            if "Address already in use" in str(e):
                available_port = find_available_port(PORT + 1)
                logger.warning(f"⚠️ Port {PORT} is busy, using port {available_port} instead")
                with socketserver.TCPServer(("", available_port), CustomHandler) as httpd:
                    logger.info(f"🚀 Simple UI Server running at http://localhost:{available_port}")
                    logger.info(f"📁 Serving directory: {DIRECTORY}")
                    logger.info(f"🌐 Open http://localhost:{available_port}/simple_ui.html in your browser")
                    logger.info("Press Ctrl+C to stop the server")

                    # Try to open browser automatically (optional)
                    try:
                        webbrowser.open(f'http://localhost:{available_port}/simple_ui.html')
                        logger.info(f"Browser automatically opened to http://localhost:{available_port}/simple_ui.html")
                    except Exception as browser_e:
                        logger.warning(f"Could not auto-open browser: {browser_e}")

                    logger.info("Simple UI Server started successfully on alternate port")
                    httpd.serve_forever()
            else:
                logger.error(f"OSError starting server: {e}")
                raise
    except KeyboardInterrupt:
        logger.info("👋 Simple UI Server stopped by user. Goodbye!")
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}")

if __name__ == "__main__":
    start_server()