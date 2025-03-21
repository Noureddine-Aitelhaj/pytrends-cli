# server.py - Update the trends endpoint implementation
import http.server
import socketserver
import os
import json
import time
from datetime import datetime
import urllib.parse
from pytrends.request import TrendReq
import pandas as pd

# Track when the server started
start_time = time.time()

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Parse the path and query
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        
        # Health check endpoint
        if path == '/health' or path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            health_data = {
                "status": "healthy",
                "message": "Health check passed",
                "path": path,
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": time.time() - start_time
            }
            
            self.wfile.write(json.dumps(health_data).encode())
            return
        
        # Google Trends endpoint
        elif path == '/trends':
            try:
                # Extract parameters
                keywords = query.get('keywords', ['bitcoin'])[0].split(',')
                timeframe = query.get('timeframe', ['today 3-m'])[0]
                query_type = query.get('query_type', ['interest_over_time'])[0]
                geo = query.get('geo', [''])[0]
                
                print(f"Processing trends request: keywords={keywords}, timeframe={timeframe}, query_type={query_type}, geo={geo}")
                
                # Initialize PyTrends
                pytrends = TrendReq(hl='en-US', tz=360)
                
                # Build payload
                pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo)
                
                # Get data based on query type
                if query_type == 'interest_over_time':
                    data = pytrends.interest_over_time()
                    result = data.reset_index().to_dict('records')
                elif query_type == 'interest_by_region':
                    data = pytrends.interest_by_region()
                    result = data.reset_index().to_dict('records')
                elif query_type == 'related_topics':
                    data = pytrends.related_topics()
                    # Format the nested dictionary structure
                    result = {k: {inner_k: str(inner_v) for inner_k, inner_v in v.items()} for k, v in data.items()}
                elif query_type == 'related_queries':
                    data = pytrends.related_queries()
                    # Format the nested dictionary structure
                    result = {k: {inner_k: inner_v.to_dict() if isinstance(inner_v, pd.DataFrame) else None 
                                  for inner_k, inner_v in v.items()} for k, v in data.items()}
                else:
                    result = {"error": "Invalid query_type"}
                
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
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                error_response = {
                    "error": "Internal server error",
                    "message": str(e)
                }
                
                self.wfile.write(json.dumps(error_response).encode())
            return
        
        # YouTube transcript endpoint
        elif path == '/youtube':
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                
                # Extract video ID from parameter
                video_param = query.get('video', [''])[0]
                format_type = query.get('format', ['json'])[0]
                
                # Extract video ID if full URL was provided
                if 'youtube.com' in video_param or 'youtu.be' in video_param:
                    if 'v=' in video_param:
                        video_id = video_param.split('v=')[1].split('&')[0]
                    else:
                        video_id = video_param.split('/')[-1].split('?')[0]
                else:
                    video_id = video_param
                
                print(f"Processing YouTube transcript request: video_id={video_id}, format={format_type}")
                
                # Get transcript
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                
                # Format based on request
                if format_type.lower() == 'text':
                    # Join all text pieces
                    full_text = ' '.join([item['text'] for item in transcript_list])
                    result = {"video_id": video_id, "full_text": full_text}
                else:
                    # Return the full transcript data
                    result = {"video_id": video_id, "transcript": transcript_list}
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                print(f"Error processing YouTube request: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                error_response = {
                    "error": "Internal server error",
                    "message": str(e)
                }
                
                self.wfile.write(json.dumps(error_response).encode())
            return
        
        # File access endpoint
        elif path.startswith('/file/'):
            file_name = path.split('/file/')[1]
            file_path = os.path.join('/app/data', file_name)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                self.send_response(200)
                if file_name.endswith('.json'):
                    self.send_header('Content-Type', 'application/json')
                elif file_name.endswith('.txt'):
                    self.send_header('Content-Type', 'text/plain')
                else:
                    self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{file_name}"')
                self.end_headers()
                self.wfile.write(file_content)
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "File not found"}).encode())
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
    httpd = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
    print(f"Server started on 0.0.0.0:{PORT}")
    print("Server is ready to accept connections")
    httpd.serve_forever()
except Exception as e:
    print(f"Error in server: {e}")
