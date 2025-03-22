# server.py - Simplified version with backward compatibility
import http.server
import socketserver
import json
import os
import traceback
import urllib.parse
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Parse the URL
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_string = parsed_url.query
        query = urllib.parse.parse_qs(query_string)
        
        logger.info(f"Received request for path: {path}")
        
        # Health check endpoint
        if path == '/health' or path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "time": str(datetime.now())}
            self.wfile.write(json.dumps(response).encode())
            return
        
        # BACKWARD COMPATIBILITY: Original trends endpoint
        elif path == '/trends':
            self.handle_trends(query)
            return
        
        # New trending endpoints
        elif path.startswith('/trends/'):
            endpoint = path[8:]  # Remove '/trends/' prefix
            if endpoint == 'interest-over-time':
                self.handle_interest_over_time(query)
            elif endpoint == 'related-queries':
                self.handle_related_queries(query)
            elif endpoint == 'interest-by-region':
                self.handle_interest_by_region(query)
            else:
                self.handle_not_implemented()
            return
        
        # YouTube transcript endpoints
        elif path == '/youtube/transcript':
            self.handle_youtube_transcript(query)
            return
        elif path == '/youtube/transcript/list':
            self.handle_youtube_transcript_list(query)
            return
        
        # Default response for unimplemented endpoints
        else:
            self.handle_not_implemented()
            return
    
    def handle_not_implemented(self):
        """Handle not implemented endpoints"""
        self.send_response(200)  # Return 200 for all paths to avoid health check issues
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "message": "Endpoint not implemented yet",
            "available_endpoints": [
                "/health", 
                "/trends?keywords=keyword1,keyword2", 
                "/trends/interest-over-time?keywords=keyword1,keyword2",
                "/trends/related-queries?keywords=keyword1,keyword2",
                "/trends/interest-by-region?keywords=keyword1,keyword2",
                "/youtube/transcript?video_id=VIDEO_ID",
                "/youtube/transcript/list?video_id=VIDEO_ID"
            ]
        }).encode())
    
    def handle_trends(self, query):
        """Handle legacy trends endpoint - BACKWARD COMPATIBILITY"""
        try:
            # Get parameters
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            query_type = query.get('query_type', ['interest_over_time'])[0]
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = int(query.get('cat', ['0'])[0])
            
            logger.info(f"Trends request: keywords={keywords}, timeframe={timeframe}, type={query_type}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            
            # Get data based on query type
            if query_type == 'interest_over_time':
                data = pytrends.interest_over_time()
                result = data.reset_index().to_dict('records') if not data.empty else []
            elif query_type == 'related_queries':
                data = pytrends.related_queries()
                result = {}
                for kw in keywords:
                    if kw in data and data[kw]:
                        result[kw] = {
                            "top": data[kw]["top"].to_dict('records') if data[kw]["top"] is not None else [],
                            "rising": data[kw]["rising"].to_dict('records') if data[kw]["rising"] is not None else []
                        }
            elif query_type == 'interest_by_region':
                resolution = query.get('resolution', ['COUNTRY'])[0]
                data = pytrends.interest_by_region(resolution=resolution)
                result = data.reset_index().to_dict('records') if not data.empty else []
            else:
                result = {"message": "Unsupported query type"}
            
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
            logger.error(f"Error processing trends request: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Send error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            error_response = {
                "status": "error",
                "message": str(e),
                "sample": True,
                "data": [{"date": "2025-03-21", "value": 100}]
            }
            
            self.wfile.write(json.dumps(error_response).encode())
    
    def handle_interest_over_time(self, query):
        """Handle interest over time endpoint"""
        try:
            # Get parameters
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = int(query.get('cat', ['0'])[0])
            
            logger.info(f"Interest over time request: keywords={keywords}, timeframe={timeframe}, geo={geo}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            
            # Get data
            data = pytrends.interest_over_time()
            result = data.reset_index().to_dict('records') if not data.empty else []
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "keywords": keywords,
                "timeframe": timeframe,
                "geo": geo,
                "data": result
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing interest over time request: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Send error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            error_response = {
                "status": "error",
                "message": str(e)
            }
            
            self.wfile.write(json.dumps(error_response).encode())
    
    def handle_related_queries(self, query):
        """Handle related queries endpoint"""
        try:
            # Get parameters
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = int(query.get('cat', ['0'])[0])
            
            logger.info(f"Related queries request: keywords={keywords}, timeframe={timeframe}, geo={geo}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            
            # Get data
            data = pytrends.related_queries()
            result = {}
            
            for kw in keywords:
                if kw in data and data[kw]:
                    result[kw] = {
                        "top": data[kw]["top"].to_dict('records') if data[kw]["top"] is not None else [],
                        "rising": data[kw]["rising"].to_dict('records') if data[kw]["rising"] is not None else []
                    }
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "keywords": keywords,
                "timeframe": timeframe,
                "geo": geo,
                "data": result
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing related queries request: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Send error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            error_response = {
                "status": "error",
                "message": str(e)
            }
            
            self.wfile.write(json.dumps(error_response).encode())
    
    def handle_interest_by_region(self, query):
        """Handle interest by region endpoint"""
        try:
            # Get parameters
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            resolution = query.get('resolution', ['COUNTRY'])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = int(query.get('cat', ['0'])[0])
            
            logger.info(f"Interest by region request: keywords={keywords}, timeframe={timeframe}, geo={geo}, resolution={resolution}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            
            # Get data
            data = pytrends.interest_by_region(resolution=resolution)
            result = data.reset_index().to_dict('records') if not data.empty else []
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "keywords": keywords,
                "timeframe": timeframe,
                "geo": geo,
                "resolution": resolution,
                "data": result
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing interest by region request: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Send error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            error_response = {
                "status": "error",
                "message": str(e)
            }
            
            self.wfile.write(json.dumps(error_response).encode())
    
    def handle_youtube_transcript(self, query):
        """Handle YouTube transcript endpoint"""
        try:
            # Get parameters
            video_id = query.get('video_id', [''])[0]
            languages = query.get('languages', [None])[0]
            format_type = query.get('format', ['json'])[0]
            preserve_formatting = query.get('preserve_formatting', ['false'])[0].lower() == 'true'
            
            if not video_id:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "Missing video_id parameter"}
                self.wfile.write(json.dumps(error_response).encode())
                return
            
            logger.info(f"YouTube transcript request: video_id={video_id}, languages={languages}")
            
            # Import here so if it fails, it doesn't affect health checks
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
            
            # Extract video ID from URL if needed
            if "youtube.com" in video_id or "youtu.be" in video_id:
                if "youtu.be" in video_id:
                    video_id = video_id.split("/")[-1].split("?")[0]
                elif "v=" in video_id:
                    video_id = video_id.split("v=")[1].split("&")[0]
            
            # Get transcript
            try:
                if languages:
                    lang_list = [lang.strip() for lang in languages.split(',')]
                    transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_list)
                else:
                    transcript_data = YouTubeTranscriptApi.get_transcript(video_id, preserve_formatting=preserve_formatting)
                
                # Format transcript if requested
                if format_type == 'text':
                    full_text = " ".join([item["text"] for item in transcript_data])
                    result = {"video_id": video_id, "full_text": full_text, "transcript": transcript_data}
                else:
                    result = {"video_id": video_id, "transcript": transcript_data}
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result, default=str).encode())
                
            except TranscriptsDisabled:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "Transcripts are disabled for this video"}
                self.wfile.write(json.dumps(error_response).encode())
                
            except NoTranscriptFound:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "No transcript found for this video"}
                self.wfile.write(json.dumps(error_response).encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                error_response = {
                    "status": "error",
                    "message": str(e),
                    "video_id": video_id
                }
                
                self.wfile.write(json.dumps(error_response).encode())
                
        except Exception as e:
            logger.error(f"Error processing YouTube transcript request: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Send error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            error_response = {
                "status": "error",
                "message": str(e)
            }
            
            self.wfile.write(json.dumps(error_response).encode())
    
    def handle_youtube_transcript_list(self, query):
        """Handle YouTube transcript list endpoint"""
        try:
            # Get parameters
            video_id = query.get('video_id', [''])[0]
            
            if not video_id:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "Missing video_id parameter"}
                self.wfile.write(json.dumps(error_response).encode())
                return
            
            logger.info(f"YouTube transcript list request: video_id={video_id}")
            
            # Import here so if it fails, it doesn't affect health checks
            from youtube_transcript_api import YouTubeTranscriptApi
            
            # Extract video ID from URL if needed
            if "youtube.com" in video_id or "youtu.be" in video_id:
                if "youtu.be" in video_id:
                    video_id = video_id.split("/")[-1].split("?")[0]
                elif "v=" in video_id:
                    video_id = video_id.split("v=")[1].split("&")[0]
            
            try:
                # List all available transcripts
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # Get transcript metadata
                available_transcripts = []
                for transcript in transcript_list:
                    available_transcripts.append({
                        "language": transcript.language,
                        "language_code": transcript.language_code,
                        "is_generated": transcript.is_generated,
                        "is_translatable": transcript.is_translatable,
                        "translation_languages": [
                            {"language": lang["name"], "language_code": lang["language_code"]}
                            for lang in transcript.translation_languages
                        ] if transcript.is_translatable else []
                    })
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                result = {
                    "video_id": video_id,
                    "available_transcripts": available_transcripts
                }
                
                self.wfile.write(json.dumps(result, default=str).encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                error_response = {
                    "status": "error",
                    "message": str(e),
                    "video_id": video_id
                }
                
                self.wfile.write(json.dumps(error_response).encode())
                
        except Exception as e:
            logger.error(f"Error in transcript list: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Send error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            error_response = {
                "status": "error",
                "message": str(e)
            }
            
            self.wfile.write(json.dumps(error_response).encode())

# =============== SERVER STARTUP ===============

PORT = int(os.environ.get('PORT', 8080))
logger.info(f"Starting server on 0.0.0.0:{PORT}")

try:
    httpd = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
    logger.info(f"Server started on 0.0.0.0:{PORT}")
    httpd.serve_forever()
except Exception as e:
    logger.error(f"Error in server: {e}")
    logger.error(traceback.format_exc())
