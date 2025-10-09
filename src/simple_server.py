#!/usr/bin/env python3
"""
Simple HTTP server for the Knowledge Repository UI
"""

import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

PORT = 7860
DIRECTORY = Path(__file__).parent.parent  # Serve from project root, not src/

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

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
                print(f"🚀 Simple UI Server running at http://localhost:{PORT}")
                print(f"📁 Serving directory: {DIRECTORY}")
                print(f"🌐 Open http://localhost:{PORT}/simple_ui.html in your browser")
                print("Press Ctrl+C to stop the server")

                # Try to open browser automatically (optional)
                try:
                    webbrowser.open(f'http://localhost:{PORT}/simple_ui.html')
                except:
                    pass

                httpd.serve_forever()
        except OSError as e:
            if "Address already in use" in str(e):
                available_port = find_available_port(PORT + 1)
                print(f"⚠️ Port {PORT} is busy, using port {available_port} instead")
                with socketserver.TCPServer(("", available_port), CustomHandler) as httpd:
                    print(f"🚀 Simple UI Server running at http://localhost:{available_port}")
                    print(f"📁 Serving directory: {DIRECTORY}")
                    print(f"🌐 Open http://localhost:{available_port}/simple_ui.html in your browser")
                    print("Press Ctrl+C to stop the server")

                    # Try to open browser automatically (optional)
                    try:
                        webbrowser.open(f'http://localhost:{available_port}/simple_ui.html')
                    except:
                        pass

                    httpd.serve_forever()
            else:
                raise
    except KeyboardInterrupt:
        print("\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

if __name__ == "__main__":
    start_server()