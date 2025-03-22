# server.py - Updated with parameter validation and proper status codes
import http.server
import socketserver
import json
import os
import traceback
import urllib.parse
from datetime import datetime
import time
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Handler(http.server.SimpleHTTPRequestHandler):
    # Validation patterns
    YOUTUBE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{11}$')
    COUNTRY_CODE_PATTERN = re.compile(r'^[A-Z]{2}(-[A-Z]{2,3})?$')
    DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    TIMEFRAME_PATTERN = re.compile(r'^(today \d+-[ydm]|\d{4}-\d{2}-\d{2} \d{4}-\d{2}-\d{2}|all)$')
    
    def do_GET(self):
        try:
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
                response = {"status": "healthy", "time": str(datetime.now())}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Google Trends endpoint
            elif path.startswith('/trends'):
                # Handle different trend endpoints
                if path == '/trends/interest-over-time':
                    self.handle_interest_over_time(query)
                elif path == '/trends/multirange-interest-over-time':
                    self.handle_multirange_interest_over_time(query)
                elif path == '/trends/historical-hourly-interest':
                    self.handle_historical_hourly_interest(query)
                elif path == '/trends/interest-by-region':
                    self.handle_interest_by_region(query)
                elif path == '/trends/related-topics':
                    self.handle_related_topics(query)
                elif path == '/trends/related-queries':
                    self.handle_related_queries(query)
                elif path == '/trends/trending-searches':
                    self.handle_trending_searches(query)
                elif path == '/trends/realtime-trending-searches':
                    self.handle_realtime_trending_searches(query)
                elif path == '/trends/top-charts':
                    self.handle_top_charts(query)
                elif path == '/trends/suggestions':
                    self.handle_suggestions(query)
                elif path == '/trends/categories':
                    self.handle_categories(query)
                else:
                    # Default trends endpoint for backward compatibility
                    self.send_error_response(404, "Not Found", "Endpoint not found. Available trend endpoints: /trends/interest-over-time, /trends/multirange-interest-over-time, etc.")
                return
            
            # YouTube Transcript endpoint
            elif path.startswith('/youtube'):
                if path == '/youtube/transcript':
                    self.handle_transcript(query)
                elif path == '/youtube/transcript/list':
                    self.handle_transcript_list(query)
                elif path == '/youtube/transcript/translate':
                    self.handle_transcript_translate(query)
                else:
                    self.send_error_response(404, "Not Found", "Endpoint not found. Available YouTube endpoints: /youtube/transcript, /youtube/transcript/list, /youtube/transcript/translate")
                return
            
            # Default response for unimplemented endpoints
            else:
                self.send_error_response(404, "Not Found", "Endpoint not found", {
                    "available_endpoints": [
                        "/health",
                        "/trends/interest-over-time",
                        "/trends/multirange-interest-over-time",
                        "/trends/historical-hourly-interest",
                        "/trends/interest-by-region",
                        "/trends/related-topics",
                        "/trends/related-queries",
                        "/trends/trending-searches",
                        "/trends/realtime-trending-searches",
                        "/trends/top-charts",
                        "/trends/suggestions",
                        "/trends/categories",
                        "/youtube/transcript",
                        "/youtube/transcript/list",
                        "/youtube/transcript/translate"
                    ]
                })
                return
        except Exception as e:
            logger.error(f"Uncaught exception in do_GET: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", str(e))
    
    def send_success_response(self, data, status_code=200):
        """Send a successful response with the given data"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def send_error_response(self, status_code, title, message, additional_data=None):
        """Send an error response with the given status code and message"""
        # For /health endpoint always return 200 to avoid triggering alerts
        if self.path.startswith('/health'):
            status_code = 200
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        error_response = {
            "error": title,
            "message": message,
            "timestamp": str(datetime.now())
        }
        
        if additional_data:
            error_response.update(additional_data)
        
        self.wfile.write(json.dumps(error_response).encode())
    
    def validate_geo(self, geo):
        """Validate the geo parameter"""
        if not geo:  # Empty is valid (global)
            return True
        
        return bool(self.COUNTRY_CODE_PATTERN.match(geo))
    
    def validate_timeframe(self, timeframe):
        """Validate the timeframe parameter"""
        # Check for common formats like 'today 3-m', '2022-01-01 2022-02-01', etc.
        if self.TIMEFRAME_PATTERN.match(timeframe):
            return True
        
        # Check for date ranges
        if ' ' in timeframe:
            start_date, end_date = timeframe.split(' ')
            return bool(self.DATE_PATTERN.match(start_date) and self.DATE_PATTERN.match(end_date))
        
        return False
    
    def validate_youtube_id(self, video_id):
        """Validate YouTube video ID format"""
        return bool(self.YOUTUBE_ID_PATTERN.match(video_id))

    # =============== PYTRENDS HANDLERS ===============

    def handle_interest_over_time(self, query):
        """Handle Google Trends interest over time request"""
        try:
            # Get parameters
            if 'keywords' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: keywords")
                
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            cat = query.get('cat', ['0'])[0]
            
            # Validate parameters
            if not keywords:
                return self.send_error_response(400, "Bad Request", "At least one keyword is required")
            
            if len(keywords) > 5:
                return self.send_error_response(400, "Bad Request", "Maximum 5 keywords are allowed")
            
            if not self.validate_timeframe(timeframe):
                return self.send_error_response(400, "Bad Request", "Invalid timeframe format. Use formats like 'today 3-m' or 'YYYY-MM-DD YYYY-MM-DD'")
            
            if geo and not self.validate_geo(geo):
                return self.send_error_response(400, "Bad Request", "Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
            
            try:
                tz = int(tz)
                cat = int(cat)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameters tz and cat must be integers")
                
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
            if data.empty:
                return self.send_success_response({
                    "keywords": keywords,
                    "timeframe": timeframe,
                    "geo": geo,
                    "data": []
                })
                
            result = data.reset_index().to_dict('records')
            
            # Send response
            self.send_success_response({
                "keywords": keywords,
                "timeframe": timeframe,
                "geo": geo,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in interest_over_time: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch interest over time data: {str(e)}")
    
    def handle_multirange_interest_over_time(self, query):
        """Handle Google Trends multirange interest over time request"""
        try:
            # Get parameters
            if 'keywords' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: keywords")
                
            if 'timeframes' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: timeframes")
                
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframes = query.get('timeframes', ['2022-01-01 2022-01-31'])[0].split('|')
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            cat = query.get('cat', ['0'])[0]
            
            # Validate parameters
            if not keywords:
                return self.send_error_response(400, "Bad Request", "At least one keyword is required")
            
            if len(keywords) > 5:
                return self.send_error_response(400, "Bad Request", "Maximum 5 keywords are allowed")
            
            for tf in timeframes:
                if not self.validate_timeframe(tf):
                    return self.send_error_response(400, "Bad Request", f"Invalid timeframe format: {tf}. Use formats like 'YYYY-MM-DD YYYY-MM-DD'")
            
            if geo and not self.validate_geo(geo):
                return self.send_error_response(400, "Bad Request", "Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
            
            try:
                tz = int(tz)
                cat = int(cat)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameters tz and cat must be integers")
                
            logger.info(f"Multirange interest over time request: keywords={keywords}, timeframes={timeframes}, geo={geo}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframes, geo=geo)
            
            # Get data
            data = pytrends.multirange_interest_over_time()
            if data.empty:
                return self.send_success_response({
                    "keywords": keywords,
                    "timeframes": timeframes,
                    "geo": geo,
                    "data": []
                })
                
            result = data.reset_index().to_dict('records')
            
            # Send response
            self.send_success_response({
                "keywords": keywords,
                "timeframes": timeframes,
                "geo": geo,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in multirange_interest_over_time: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch multirange interest over time data: {str(e)}")
    
    def handle_historical_hourly_interest(self, query):
        """Handle Google Trends historical hourly interest request"""
        try:
            # Get parameters
            if 'keywords' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: keywords")
                
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            
            # Parse dates
            try:
                year_start = int(query.get('year_start', ['2022'])[0])
                month_start = int(query.get('month_start', ['1'])[0])
                day_start = int(query.get('day_start', ['1'])[0])
                hour_start = int(query.get('hour_start', ['0'])[0])
                year_end = int(query.get('year_end', ['2022'])[0])
                month_end = int(query.get('month_end', ['1'])[0])
                day_end = int(query.get('day_end', ['7'])[0])
                hour_end = int(query.get('hour_end', ['0'])[0])
                sleep = int(query.get('sleep', ['0'])[0])
                cat = int(query.get('cat', ['0'])[0])
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Date parameters must be integers")
                
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            
            # Validate parameters
            if not keywords:
                return self.send_error_response(400, "Bad Request", "At least one keyword is required")
                
            if len(keywords) > 5:
                return self.send_error_response(400, "Bad Request", "Maximum 5 keywords are allowed")
                
            if geo and not self.validate_geo(geo):
                return self.send_error_response(400, "Bad Request", "Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
                
            # Basic date validation
            if not (1 <= month_start <= 12 and 1 <= month_end <= 12 and 1 <= day_start <= 31 and 1 <= day_end <= 31):
                return self.send_error_response(400, "Bad Request", "Invalid date parameters")
                
            # Validate date range
            start_date = datetime(year_start, month_start, day_start, hour_start)
            end_date = datetime(year_end, month_end, day_end, hour_end)
            
            if end_date <= start_date:
                return self.send_error_response(400, "Bad Request", "End date must be after start date")
                
            if (end_date - start_date).days > 7:
                return self.send_error_response(400, "Bad Request", "Date range is limited to 7 days for hourly data")
            
            try:
                tz = int(tz)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameter tz must be an integer")
                
            logger.info(f"Historical hourly interest request: keywords={keywords}, start={year_start}-{month_start}-{day_start}, end={year_end}-{month_end}-{day_end}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Get data
            data = pytrends.get_historical_interest(
                keywords, 
                year_start=year_start, month_start=month_start, day_start=day_start, hour_start=hour_start,
                year_end=year_end, month_end=month_end, day_end=day_end, hour_end=hour_end,
                cat=cat, geo=geo, gprop='', sleep=sleep
            )
            
            if data.empty:
                return self.send_success_response({
                    "keywords": keywords,
                    "start_date": f"{year_start}-{month_start}-{day_start} {hour_start}:00",
                    "end_date": f"{year_end}-{month_end}-{day_end} {hour_end}:00",
                    "geo": geo,
                    "data": []
                })
                
            result = data.reset_index().to_dict('records')
            
            # Send response
            self.send_success_response({
                "keywords": keywords,
                "start_date": f"{year_start}-{month_start}-{day_start} {hour_start}:00",
                "end_date": f"{year_end}-{month_end}-{day_end} {hour_end}:00",
                "geo": geo,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in historical_hourly_interest: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch historical hourly interest data: {str(e)}")
    
    def handle_interest_by_region(self, query):
        """Handle Google Trends interest by region request"""
        try:
            # Get parameters
            if 'keywords' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: keywords")
                
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            resolution = query.get('resolution', ['COUNTRY'])[0]
            inc_low_vol = query.get('inc_low_vol', ['true'])[0].lower() == 'true'
            inc_geo_code = query.get('inc_geo_code', ['false'])[0].lower() == 'true'
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            cat = query.get('cat', ['0'])[0]
            
            # Validate parameters
            if not keywords:
                return self.send_error_response(400, "Bad Request", "At least one keyword is required")
                
            if len(keywords) > 5:
                return self.send_error_response(400, "Bad Request", "Maximum 5 keywords are allowed")
                
            if not self.validate_timeframe(timeframe):
                return self.send_error_response(400, "Bad Request", "Invalid timeframe format. Use formats like 'today 3-m' or 'YYYY-MM-DD YYYY-MM-DD'")
                
            if geo and not self.validate_geo(geo):
                return self.send_error_response(400, "Bad Request", "Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
                
            valid_resolutions = ['COUNTRY', 'REGION', 'CITY', 'DMA']
            if resolution not in valid_resolutions:
                return self.send_error_response(400, "Bad Request", f"Invalid resolution. Must be one of: {', '.join(valid_resolutions)}")
            
            try:
                tz = int(tz)
                cat = int(cat)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameters tz and cat must be integers")
                
            logger.info(f"Interest by region request: keywords={keywords}, timeframe={timeframe}, geo={geo}, resolution={resolution}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            
            # Get data
            data = pytrends.interest_by_region(resolution=resolution, inc_low_vol=inc_low_vol, inc_geo_code=inc_geo_code)
            if data.empty:
                return self.send_success_response({
                    "keywords": keywords,
                    "timeframe": timeframe,
                    "geo": geo,
                    "resolution": resolution,
                    "data": []
                })
                
            result = data.reset_index().to_dict('records')
            
            # Send response
            self.send_success_response({
                "keywords": keywords,
                "timeframe": timeframe,
                "geo": geo,
                "resolution": resolution,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in interest_by_region: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch interest by region data: {str(e)}")
    
    def handle_related_topics(self, query):
        """Handle Google Trends related topics request"""
        try:
            # Get parameters
            if 'keywords' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: keywords")
                
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            cat = query.get('cat', ['0'])[0]
            
            # Validate parameters
            if not keywords:
                return self.send_error_response(400, "Bad Request", "At least one keyword is required")
                
            if len(keywords) > 5:
                return self.send_error_response(400, "Bad Request", "Maximum 5 keywords are allowed")
                
            if not self.validate_timeframe(timeframe):
                return self.send_error_response(400, "Bad Request", "Invalid timeframe format. Use formats like 'today 3-m' or 'YYYY-MM-DD YYYY-MM-DD'")
                
            if geo and not self.validate_geo(geo):
                return self.send_error_response(400, "Bad Request", "Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
            
            try:
                tz = int(tz)
                cat = int(cat)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameters tz and cat must be integers")
                
            logger.info(f"Related topics request: keywords={keywords}, timeframe={timeframe}, geo={geo}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            
            # Get data
            data = pytrends.related_topics()
            result = {}
            
            for kw in keywords:
                if kw in data and data[kw]:
                    result[kw] = {
                        "top": data[kw]["top"].to_dict('records') if data[kw]["top"] is not None else [],
                        "rising": data[kw]["rising"].to_dict('records') if data[kw]["rising"] is not None else []
                    }
            
            # Send response
            self.send_success_response({
                "keywords": keywords,
                "timeframe": timeframe,
                "geo": geo,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in related_topics: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch related topics data: {str(e)}")
    
    def handle_related_queries(self, query):
        """Handle Google Trends related queries request"""
        try:
            # Get parameters
            if 'keywords' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: keywords")
                
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            cat = query.get('cat', ['0'])[0]
            
            # Validate parameters
            if not keywords:
                return self.send_error_response(400, "Bad Request", "At least one keyword is required")
                
            if len(keywords) > 5:
                return self.send_error_response(400, "Bad Request", "Maximum 5 keywords are allowed")
                
            if not self.validate_timeframe(timeframe):
                return self.send_error_response(400, "Bad Request", "Invalid timeframe format. Use formats like 'today 3-m' or 'YYYY-MM-DD YYYY-MM-DD'")
                
            if geo and not self.validate_geo(geo):
                return self.send_error_response(400, "Bad Request", "Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
            
            try:
                tz = int(tz)
                cat = int(cat)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameters tz and cat must be integers")
                
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
            self.send_success_response({
                "keywords": keywords,
                "timeframe": timeframe,
                "geo": geo,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in related_queries: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch related queries data: {str(e)}")
    
    def handle_trending_searches(self, query):
        """Handle Google Trends trending searches request"""
        try:
            # Get parameters
            pn = query.get('pn', ['united_states'])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            
            # Very minimal validation since this endpoint needs few parameters
            try:
                tz = int(tz)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameter tz must be an integer")
                
            logger.info(f"Trending searches request: pn={pn}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Get data
            try:
                data = pytrends.trending_searches(pn=pn)
                result = data.to_dict('records') if not data.empty else []
            except Exception as e:
                return self.send_error_response(400, "Bad Request", f"Invalid country parameter (pn): {pn}. Error: {str(e)}")
            
            # Send response
            self.send_success_response({
                "pn": pn,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in trending_searches: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch trending searches data: {str(e)}")
    
    def handle_realtime_trending_searches(self, query):
        """Handle Google Trends realtime trending searches request"""
        try:
            # Get parameters
            pn = query.get('pn', ['US'])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            
            # Validate parameters
            if not self.validate_geo(pn):
                return self.send_error_response(400, "Bad Request", "Invalid country code format for pn. Use ISO country codes like 'US'")
            
            try:
                tz = int(tz)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameter tz must be an integer")
                
            logger.info(f"Realtime trending searches request: pn={pn}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Get data
            try:
                data = pytrends.realtime_trending_searches(pn=pn)
                result = data.to_dict('records') if not data.empty else []
            except Exception as e:
                return self.send_error_response(400, "Bad Request", f"Invalid country code (pn): {pn}. Error: {str(e)}")
            
            # Send response
            self.send_success_response({
                "pn": pn,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in realtime_trending_searches: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch realtime trending searches data: {str(e)}")
    
    def handle_top_charts(self, query):
        """Handle Google Trends top charts request"""
        try:
            # Get parameters
            if 'date' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: date (as year, e.g. 2021)")
                
            try:
                date = int(query.get('date', ['2021'])[0])
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Date parameter must be an integer year, e.g. 2021")
                
            geo = query.get('geo', ['GLOBAL'])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            
            # Validate parameters
            current_year = datetime.now().year
            if date < 2001 or date >= current_year:  # Google Trends data starts around 2001
                return self.send_error_response(400, "Bad Request", f"Date must be between 2001 and {current_year-1}")
                
            try:
                tz = int(tz)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameter tz must be an integer")
                
            logger.info(f"Top charts request: date={date}, geo={geo}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Get data
            try:
                data = pytrends.top_charts(date, geo=geo)
                result = data.to_dict('records') if not data.empty else []
            except Exception as e:
                return self.send_error_response(400, "Bad Request", f"Error fetching top charts: {str(e)}")
            
            # Send response
            self.send_success_response({
                "date": date,
                "geo": geo,
                "data": result
            })
            
        except Exception as e:
            logger.error(f"Error in top_charts: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch top charts data: {str(e)}")
    
    def handle_suggestions(self, query):
        """Handle Google Trends keyword suggestions request"""
        try:
            # Get parameters
            if 'keyword' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: keyword")
                
            keyword = query.get('keyword', ['bitcoin'])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            
            # Minimal validation
            if not keyword:
                return self.send_error_response(400, "Bad Request", "Keyword cannot be empty")
                
            try:
                tz = int(tz)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameter tz must be an integer")
                
            logger.info(f"Suggestions request: keyword={keyword}")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Get data
            try:
                suggestions = pytrends.suggestions(keyword=keyword)
            except Exception as e:
                return self.send_error_response(400, "Bad Request", f"Error fetching suggestions: {str(e)}")
            
            # Send response
            self.send_success_response({
                "keyword": keyword,
                "suggestions": suggestions
            })
            
        except Exception as e:
            logger.error(f"Error in suggestions: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch suggestions data: {str(e)}")
    
    def handle_categories(self, query):
        """Handle Google Trends categories request"""
        try:
            # Get parameters
            hl = query.get('hl', ['en-US'])[0]
            tz = query.get('tz', ['360'])[0]
            
            # Minimal validation
            try:
                tz = int(tz)
            except ValueError:
                return self.send_error_response(400, "Bad Request", "Parameter tz must be an integer")
                
            logger.info(f"Categories request")
            
            # Import here so if it fails, it doesn't affect health checks
            from pytrends.request import TrendReq
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=hl, tz=tz)
            
            # Get data
            try:
                categories = pytrends.categories()
            except Exception as e:
                return self.send_error_response(400, "Bad Request", f"Error fetching categories: {str(e)}")
            
            # Send response
            self.send_success_response({
                "categories": categories
            })
            
        except Exception as e:
            logger.error(f"Error in categories: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch categories data: {str(e)}")

    # =============== YOUTUBE TRANSCRIPT HANDLERS ===============
    
    def extract_video_id(self, url_or_id):
        """Extract video ID from YouTube URL"""
        if "youtu.be" in url_or_id:
            return url_or_id.split("/")[-1].split("?")[0]
        elif "youtube.com" in url_or_id:
            if "v=" in url_or_id:
                return url_or_id.split("v=")[1].split("&")[0]
        return url_or_id  # If it's already the ID
    
    def handle_transcript(self, query):
        """Handle YouTube transcript request"""
        try:
            # Get parameters
            if 'video_id' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: video_id")
                
            video_id_or_url = query.get('video_id', [''])[0]
            languages = query.get('languages', [None])[0]
            format_type = query.get('format', ['json'])[0]
            preserve_formatting = query.get('preserve_formatting', ['false'])[0].lower() == 'true'
            
            # Get proxy and cookie parameters
            proxy_url = query.get('proxy_url', [None])[0]
            cookie_file = query.get('cookie_file', [None])[0]
            
            if not video_id_or_url:
                return self.send_error_response(400, "Bad Request", "Empty video_id parameter")
            
            # Extract video ID from URL if needed
            video_id = self.extract_video_id(video_id_or_url)
            
            # Validate video_id format
            if not self.validate_youtube_id(video_id):
                return self.send_error_response(400, "Bad Request", f"Invalid YouTube video ID format: {video_id}")
                
            if format_type not in ['json', 'text']:
                return self.send_error_response(400, "Bad Request", "Format must be 'json' or 'text'")
                
            logger.info(f"YouTube transcript request: video_id={video_id}, languages={languages}")
            
            # Import here so if it fails, it doesn't affect health checks
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import TranscriptsDisabled, VideoUnavailable
            from youtube_transcript_api.formatters import TextFormatter, JSONFormatter
            import requests
            
            # Setup session with proxy and/or cookies if provided
            session = None
            if proxy_url or cookie_file:
                session = requests.Session()
                
                if proxy_url:
                    session.proxies = {
                        'http': proxy_url,
                        'https': proxy_url
                    }
                
                if cookie_file and os.path.exists(cookie_file):
                    # Load cookies from file
                    logger.info(f"Using cookie file: {cookie_file}")
                    # Actual cookie loading would need to be implemented
            
            # Get transcript
            try:
                transcript_data = None
                if languages:
                    lang_list = [lang.strip() for lang in languages.split(',')]
                    
                    # List all available transcripts
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    
                    # Try to get transcript in specified languages
                    transcript = transcript_list.find_transcript(lang_list)
                    transcript_data = transcript.fetch()
                else:
                    transcript_data = YouTubeTranscriptApi.get_transcript(video_id, preserve_formatting=preserve_formatting)
                
                # Apply formatter if requested
                if format_type == 'text':
                    text_formatter = TextFormatter()
                    formatted_transcript = text_formatter.format_transcript(transcript_data)
                    result = {
                        "video_id": video_id,
                        "formatted_text": formatted_transcript,
                        "transcript": transcript_data
                    }
                else:
                    json_formatter = JSONFormatter()
                    formatted_transcript = json_formatter.format_transcript(transcript_data)
                    result = {
                        "video_id": video_id,
                        "transcript": transcript_data
                    }
                
                # Send response
                self.send_success_response(result)
                
            except TranscriptsDisabled:
                self.send_error_response(404, "Not Found", "Transcripts are disabled for this video")
            except NoTranscriptFound:
                self.send_error_response(404, "Not Found", "No transcript found for this video")
            except VideoUnavailable:
                self.send_error_response(404, "Not Found", "The video is unavailable")
            except NoTranscriptAvailable:
                self.send_error_response(404, "Not Found", "No transcript available for this video")
                
        except Exception as e:
            logger.error(f"Error in transcript: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to fetch transcript: {str(e)}")
    
    def handle_transcript_list(self, query):
        """Handle YouTube transcript list request"""
        try:
            # Get parameters
            if 'video_id' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: video_id")
                
            video_id_or_url = query.get('video_id', [''])[0]
            
            if not video_id_or_url:
                return self.send_error_response(400, "Bad Request", "Empty video_id parameter")
            
            # Extract video ID from URL if needed
            video_id = self.extract_video_id(video_id_or_url)
            
            # Validate video_id format
            if not self.validate_youtube_id(video_id):
                return self.send_error_response(400, "Bad Request", f"Invalid YouTube video ID format: {video_id}")
                
            logger.info(f"YouTube transcript list request: video_id={video_id}")
            
            # Import here so if it fails, it doesn't affect health checks
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptAvailable, VideoUnavailable
            
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
                self.send_success_response({
                    "video_id": video_id,
                    "available_transcripts": available_transcripts
                })
                
            except TranscriptsDisabled:
                self.send_error_response(404, "Not Found", "Transcripts are disabled for this video")
            except VideoUnavailable:
                self.send_error_response(404, "Not Found", "The video is unavailable")
            except NoTranscriptAvailable:
                self.send_error_response(404, "Not Found", "No transcript available for this video")
                
        except Exception as e:
            logger.error(f"Error in transcript list: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to list transcripts: {str(e)}")
    
    def handle_transcript_translate(self, query):
        """Handle YouTube transcript translation request"""
        try:
            # Get parameters
            if 'video_id' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: video_id")
                
            if 'target_lang' not in query:
                return self.send_error_response(400, "Bad Request", "Missing required parameter: target_lang")
                
            video_id_or_url = query.get('video_id', [''])[0]
            source_lang = query.get('source_lang', ['en'])[0]
            target_lang = query.get('target_lang', ['fr'])[0]
            
            if not video_id_or_url:
                return self.send_error_response(400, "Bad Request", "Empty video_id parameter")
                
            if not target_lang:
                return self.send_error_response(400, "Bad Request", "Empty target_lang parameter")
            
            # Extract video ID from URL if needed
            video_id = self.extract_video_id(video_id_or_url)
            
            # Validate video_id format
            if not self.validate_youtube_id(video_id):
                return self.send_error_response(400, "Bad Request", f"Invalid YouTube video ID format: {video_id}")
                
            logger.info(f"YouTube transcript translate request: video_id={video_id}, source_lang={source_lang}, target_lang={target_lang}")
            
            # Import here so if it fails, it doesn't affect health checks
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptAvailable, VideoUnavailable, NoTranscriptFound, TranslationLanguageNotAvailable
            
            try:
                # List all available transcripts
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # Get transcript in source language
                transcript = transcript_list.find_transcript([source_lang])
                
                # Translate the transcript
                translated_transcript = transcript.translate(target_lang)
                transcript_data = translated_transcript.fetch()
                
                # Send response
                self.send_success_response({
                    "video_id": video_id,
                    "source_language": source_lang,
                    "target_language": target_lang,
                    "transcript": transcript_data
                })
                
            except TranscriptsDisabled:
                self.send_error_response(404, "Not Found", "Transcripts are disabled for this video")
            except NoTranscriptFound:
                self.send_error_response(404, "Not Found", f"No transcript found in language: {source_lang}")
            except VideoUnavailable:
                self.send_error_response(404, "Not Found", "The video is unavailable")
            except NoTranscriptAvailable:
                self.send_error_response(404, "Not Found", "No transcript available for this video")
            except TranslationLanguageNotAvailable:
                self.send_error_response(400, "Bad Request", f"Translation to {target_lang} is not available")
                
        except Exception as e:
            logger.error(f"Error in transcript translate: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_error_response(500, "Internal Server Error", f"Failed to translate transcript: {str(e)}")

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
