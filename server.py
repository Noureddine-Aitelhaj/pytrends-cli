import http.server
import socketserver
import os
import json

class BasicHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            "status": "healthy",
            "message": "Health check passed",
            "path": self.path
        }
        
        self.wfile.write(json.dumps(response).encode())

PORT = int(os.environ.get('PORT', 8080))
print(f"Starting server on 0.0.0.0:{PORT}")
httpd = socketserver.TCPServer(("0.0.0.0", PORT), BasicHandler)
print(f"Server started on 0.0.0.0:{PORT}")

try:
    print("Server is ready to accept connections")
    httpd.serve_forever()
except Exception as e:
    print(f"Error in server: {e}")
