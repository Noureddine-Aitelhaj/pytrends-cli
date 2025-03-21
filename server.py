# server.py - Replace the entire content with this code
import http.server
import socketserver
import os
import json
import time
from datetime import datetime

# Track when the server started
start_time = time.time()

class BasicHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Basic health check endpoint
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            health_data = {
                "status": "healthy",
                "message": "Health check passed",
                "path": self.path,
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": time.time() - start_time
            }
            
            self.wfile.write(json.dumps(health_data).encode())
            return
        
        # Handle trends endpoint with minimal logic
        elif self.path.startswith('/trends'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            sample_data = {
                "status": "ok",
                "sample": True,
                "message": "This is sample data to test connectivity",
                "data": [{"date": "2025-03-21", "value": 100}]
            }
            
            self.wfile.write(json.dumps(sample_data).encode())
            return
        
        # Default response for other paths
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
            return

PORT = int(os.environ.get('PORT', 8080))
print(f"Starting server on 0.0.0.0:{PORT}")

try:
    httpd = socketserver.TCPServer(("0.0.0.0", PORT), BasicHandler)
    print(f"Server started on 0.0.0.0:{PORT}")
    print("Server is ready to accept connections")
    httpd.serve_forever()
except Exception as e:
    print(f"Error in server: {e}")
