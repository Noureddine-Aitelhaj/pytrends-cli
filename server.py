import os
import http.server
import socketserver
from http import HTTPStatus
import json
from urllib.parse import parse_qs, urlparse
import subprocess

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Parse URL and query parameters
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
        # List files or serve content
        if path == '/':
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            data_dir = '/app/data'
            files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
            self.wfile.write(json.dumps({'files': files}).encode())
            
        elif path == '/trends':
            self.handle_trends_request(query)
            
        elif path == '/youtube':
            self.handle_youtube_request(query)
            
        elif path.startswith('/file/'):
            filename = path[6:]  # Remove '/file/' prefix
            filepath = os.path.join('/app/data', filename)
            
            if os.path.exists(filepath):
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                with open(filepath, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                self.wfile.write(b'File not found')
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            self.wfile.write(b'Not found')
    
    def handle_trends_request(self, query):
        # Handle trends request
        try:
            keywords = query.get('keywords', [''])[0]
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            query_type = query.get('query_type', ['interest_over_time'])[0]
            
            if not keywords:
                self.send_error(400, 'Missing keywords parameter')
                return
                
            # Build command
            cmd = [
                'python', 'cli.py',
                '--output', '/app/data',
                'trends',
                '--keywords', keywords,
                '--timeframe', timeframe,
                '--geo', geo,
                '--query-type', query_type
            ]
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse the output to get the saved file path
            output_lines = result.stdout.strip().split('\n')
            file_path = None
            for line in output_lines:
                if line.startswith('Data saved to '):
                    file_path = line.replace('Data saved to ', '')
                    break
            
            # Read the file
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_error(500, f'Error processing request: {result.stderr}')
                
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')
    
    def handle_youtube_request(self, query):
        # Handle YouTube transcript request
        try:
            video = query.get('video', [''])[0]
            languages = query.get('languages', [''])[0]
            format_type = query.get('format', ['json'])[0]
            
            if not video:
                self.send_error(400, 'Missing video parameter')
                return
                
            # Build command
            cmd = [
                'python', 'cli.py',
                '--output', '/app/data',
                'youtube',
                '--video', video
            ]
            
            if languages:
                cmd.extend(['--languages', languages])
                
            cmd.extend(['--format', format_type])
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse the output to get the saved file path
            output_lines = result.stdout.strip().split('\n')
            file_path = None
            for line in output_lines:
                if line.startswith('Output saved to:'):
                    file_path = line.replace('Output saved to:', '').strip()
                    break
            
            # Read the file
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_error(500, f'Error processing request: {result.stderr}')
                
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

PORT = int(os.environ.get('PORT', 8080))
httpd = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
print(f"Serving at port {PORT}")
httpd.serve_forever()
