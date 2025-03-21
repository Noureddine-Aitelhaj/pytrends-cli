# server.py - Replace with this minimal version
import http.server
import socketserver
import json
import os

class MinimalHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Always respond to health checks
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"status": "healthy"}
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Simple trends endpoint
        elif self.path.startswith('/trends'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            sample_data = {
                "status": "ok",
                "sample": True,
                "message": "Sample data - health check is now working",
                "data": [{"date": "2025-03-21", "value": 100}]
            }
            self.wfile.write(json.dumps(sample_data).encode())
            return
        
        # Default response for other paths
        else:
            self.send_response(200)  # Return 200 for all paths during testing
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Endpoint not implemented yet"}).encode())
            return

PORT = int(os.environ.get('PORT', 8080))
print(f"Starting minimal server on 0.0.0.0:{PORT}")

try:
    httpd = socketserver.TCPServer(("0.0.0.0", PORT), MinimalHandler)
    print(f"Server started on 0.0.0.0:{PORT}")
    httpd.serve_forever()
except Exception as e:
    print(f"Error in server: {e}")
