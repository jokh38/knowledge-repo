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
DIRECTORY = Path(__file__).parent

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
    except KeyboardInterrupt:
        print("\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

if __name__ == "__main__":
    start_server()