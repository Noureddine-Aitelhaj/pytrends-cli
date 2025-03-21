# server.py - After health check is working, update to add PyTrends
import http.server
import socketserver
import json
import os
import traceback
import urllib.parse

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Parse the URL
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_string = parsed_url.query
        query = urllib.parse.parse_qs(query_string)
        
        # Health check endpoint - keep this minimal and reliable
        if path == '/health' or path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"status": "healthy"}
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Google Trends endpoint
        elif path == '/trends':
            # Get parameters
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            query_type = query.get('query_type', ['interest_over_time'])[0]
            geo = query.get('geo', [''])[0]
            
            print(f"Trends request: keywords={keywords}, timeframe={timeframe}, type={query_type}")
            
            try:
                # Import here so if it fails, it doesn't affect health checks
                from pytrends.request import TrendReq
                import pandas as pd
                
                # Initialize PyTrends
                pytrends = TrendReq(hl='en-US', tz=360)
                
                # Build payload
                pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo)
                
                # Get data
                if query_type == 'interest_over_time':
                    data = pytrends.interest_over_time()
                    result = data.reset_index().to_dict('records')
                else:
                    result = {"message": "Only interest_over_time is supported currently"}
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response = {
                    "keywords": keywords,
                    "timeframe": timeframe,
                    "query_type": query_type,
                    "geo": geo,
                    "data": result
                }
                
                self.wfile.write(json.dumps(response, default=str).encode())
                
            except Exception as e:
                print(f"Error processing trends request: {str(e)}")
                print(traceback.format_exc())
                
                # Send error response
                self.send_response(200)  # Still send 200 to prevent healthcheck issues
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                error_response = {
                    "status": "error",
                    "message": str(e),
                    "sample": True,
                    "data": [{"date": "2025-03-21", "value": 100}]
                }
                
                self.wfile.write(json.dumps(error_response).encode())
            
            return
        
        # Default response
        else:
            self.send_response(200)  # Return 200 for all paths to avoid health check issues
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Endpoint not implemented yet"}).encode())
            return

PORT = int(os.environ.get('PORT', 8080))
print(f"Starting server on 0.0.0.0:{PORT}")

try:
    httpd = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
    print(f"Server started on 0.0.0.0:{PORT}")
    httpd.serve_forever()
except Exception as e:
    print(f"Error in server: {e}")
