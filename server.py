import http.server
import socketserver
import json
import os
import traceback
import urllib.parse
from datetime import datetime
import logging
import signal
import time
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_calls, time_frame):
        self.max_calls = max_calls
        self.time_frame = time_frame
        self.calls = []

    def add_call(self):
        now = time.time()
        self.calls = [call for call in self.calls if call > now - self.time_frame]
        self.calls.append(now)

    def is_allowed(self):
        return len(self.calls) < self.max_calls

# Create a rate limiter: 100 calls per minute
rate_limiter = RateLimiter(max_calls=100, time_frame=60)

def get_google_suggestions(keyword, num_suggestions=10, language="en", region="us"):
    """Get autocomplete suggestions from Google"""
    url = "https://suggestqueries.google.com/complete/search"
    params = {
        "client": "firefox",
        "q": keyword,
        "hl": language,
        "gl": region,
        "ie": "UTF-8",
        "oe": "UTF-8"
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = json.loads(response.content.decode("utf-8"))
            suggestions = data[1]
            return suggestions
        else:
            logger.error(f"Error fetching suggestions: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error getting Google suggestions: {str(e)}")
        return []

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if not rate_limiter.is_allowed():
            self.send_error(429, "Too Many Requests")
            return

        rate_limiter.add_call()

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
            response = {
                "status": "healthy",
                "time": str(datetime.now()),
                "version": "1.0",
                "endpoints": ["/health", "/trends", "/trends/interest-over-time", "/trends/multirange-interest-over-time",
                              "/trends/historical-hourly-interest", "/trends/interest-by-region", "/trends/related-topics",
                              "/trends/related-queries", "/trends/trending-searches", "/trends/realtime-trending-searches",
                              "/trends/top-charts", "/trends/suggestions", "/trends/categories", "/autocomplete"]
            }
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Google Autocomplete endpoint
        elif path == '/autocomplete':
            self.handle_autocomplete(query)
            return
        
        # Original trends endpoint (backward compatibility)
        elif path == '/trends':
            self.handle_trends(query)
            return
        
        # New trend endpoints
        elif path.startswith('/trends/'):
            endpoint = path[8:]  # Remove '/trends/' prefix
            if endpoint == 'interest-over-time':
                self.handle_interest_over_time(query)
            elif endpoint == 'multirange-interest-over-time':
                self.handle_multirange_interest_over_time(query)
            elif endpoint == 'historical-hourly-interest':
                self.handle_historical_hourly_interest(query)
            elif endpoint == 'interest-by-region':
                self.handle_interest_by_region(query)
            elif endpoint == 'related-topics':
                self.handle_related_topics(query)
            elif endpoint == 'related-queries':
                self.handle_related_queries(query)
            elif endpoint == 'trending-searches':
                self.handle_trending_searches(query)
            elif endpoint == 'realtime-trending-searches':
                self.handle_realtime_trending_searches(query)
            elif endpoint == 'top-charts':
                self.handle_top_charts(query)
            elif endpoint == 'suggestions':
                self.handle_suggestions(query)
            elif endpoint == 'categories':
                self.handle_categories(query)
            else:
                self.handle_not_implemented()
            return
        
        # Default response for unimplemented endpoints
        else:
            self.handle_not_implemented()
            return
    
    def handle_autocomplete(self, query):
        """Handle Google autocomplete request"""
        try:
            # Get parameters
            keyword = query.get('keyword', [''])[0]
            num = int(query.get('num', ['10'])[0])
            language = query.get('language', ['en'])[0]
            region = query.get('region', ['us'])[0]
            
            if not keyword:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Keyword parameter is required"}).encode())
                return

            logger.info(f"Autocomplete request for keyword: {keyword}, language: {language}, region: {region}")
            
            # Get the suggestions
            suggestions = get_google_suggestions(keyword, num, language, region)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "keyword": keyword,
                "language": language,
                "region": region,
                "suggestions": suggestions
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            logger.error(f"Error processing autocomplete request: {str(e)}")
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
    
    def handle_not_implemented(self):
        """Handle not implemented endpoints"""
        self.send_response(501)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "error",
            "message": "Endpoint not implemented yet",
            "available_endpoints": [
                "/health", 
                "/autocomplete?keyword=bitcoin&language=en&region=us",
                "/trends?keywords=keyword1,keyword2", 
                "/trends/interest-over-time?keywords=keyword1,keyword2",
                "/trends/multirange-interest-over-time?keywords=keyword1,keyword2&timeframes=2022-01-01 2022-01-31|2022-03-01 2022-03-31",
                "/trends/historical-hourly-interest?keywords=keyword1,keyword2&year_start=2022&month_start=1&day_start=1&year_end=2022&month_end=1&day_end=7",
                "/trends/interest-by-region?keywords=keyword1,keyword2&resolution=COUNTRY",
                "/trends/related-topics?keywords=keyword1,keyword2",
                "/trends/related-queries?keywords=keyword1,keyword2",
                "/trends/trending-searches?pn=united_states",
                "/trends/realtime-trending-searches?pn=US",
                "/trends/top-charts?date=2022&geo=GLOBAL",
                "/trends/suggestions?keyword=bitcoin",
                "/trends/categories"
            ]
        }).encode())
    
    def handle_trends(self, query):
        """Handle legacy trends endpoint - for backward compatibility"""
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
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
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
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
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
    
    def handle_multirange_interest_over_time(self, query):
        """Handle multirange interest over time endpoint"""
        try:
            # Get parameters
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframes = query.get('timeframes', ['2022-01-01 2022-01-31'])[0].split('|')
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = int(query.get('cat', ['0'])[0])
            
            logger.info(f"Multirange interest over time request: keywords={keywords}, timeframes={timeframes}, geo={geo}")
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
            # Collect data for each timeframe
            all_data = []
            
            for timeframe in timeframes:
                try:
                    # Build payload for this timeframe
                    pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
                    
                    # Get data
                    data = pytrends.interest_over_time()
                    if not data.empty:
                        # Add a timeframe column to identify the source
                        data['timeframe'] = timeframe
                        all_data.append(data)
                except Exception as inner_e:
                    logger.warning(f"Error with timeframe {timeframe}: {str(inner_e)}")
            
            # Combine all data frames
            if all_data:
                combined_data = pd.concat(all_data)
                result = combined_data.reset_index().to_dict('records')
            else:
                result = []
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "keywords": keywords,
                "timeframes": timeframes,
                "geo": geo,
                "data": result
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing multirange interest over time request: {str(e)}")
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
    
    def handle_historical_hourly_interest(self, query):
        """Handle historical hourly interest endpoint"""
        try:
            # Get parameters
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
            except ValueError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "Date parameters must be integers"}
                self.wfile.write(json.dumps(error_response).encode())
                return
                
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = int(query.get('cat', ['0'])[0])
            
            logger.info(f"Historical hourly interest request: keywords={keywords}, start={year_start}-{month_start}-{day_start}, end={year_end}-{month_end}-{day_end}")
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
            # Get data
            data = pytrends.get_historical_interest(
                keywords, 
                year_start=year_start, month_start=month_start, day_start=day_start, hour_start=hour_start,
                year_end=year_end, month_end=month_end, day_end=day_end, hour_end=hour_end,
                cat=cat, geo=geo, gprop='', sleep=sleep
            )
            
            result = data.reset_index().to_dict('records') if not data.empty else []
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "keywords": keywords,
                "start_date": f"{year_start}-{month_start}-{day_start} {hour_start}:00",
                "end_date": f"{year_end}-{month_end}-{day_end} {hour_end}:00",
                "geo": geo,
                "data": result
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing historical hourly interest request: {str(e)}")
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
            inc_low_vol = query.get('inc_low_vol', ['true'])[0].lower() == 'true'
            inc_geo_code = query.get('inc_geo_code', ['false'])[0].lower() == 'true'
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = int(query.get('cat', ['0'])[0])
            
            logger.info(f"Interest by region request: keywords={keywords}, timeframe={timeframe}, geo={geo}, resolution={resolution}")
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            
            # Get data
            data = pytrends.interest_by_region(resolution=resolution, inc_low_vol=inc_low_vol, inc_geo_code=inc_geo_code)
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
    
    def handle_related_topics(self, query):
        """Handle related topics endpoint"""
        try:
            # Get parameters
            keywords = query.get('keywords', ['bitcoin'])[0].split(',')
            timeframe = query.get('timeframe', ['today 3-m'])[0]
            geo = query.get('geo', [''])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = int(query.get('cat', ['0'])[0])
            logger.info(f"Related topics request: keywords={keywords}, timeframe={timeframe}, geo={geo}")
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl,
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            # Get data
            data = pytrends.related_topics()
            result = {}
            for kw in keywords:
                logger.info(f"Data for keyword '{kw}': {data.get(kw)}")  # Debugging log
                if kw in data:
                    result[kw] = {}
                    # Simplify:  Just get the whole data object and include it
                    result[kw] = data[kw] # Include the full dataset, hopefully it will be enough
                else:
                    result[kw] = {"note": "No related topics found for this keyword."} # Handle keywords with no results
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
            logger.error(f"Error processing related topics request: {str(e)}")
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
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
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
                else:
                    result[kw] = {"top": [], "rising": []}
            
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
    
    def handle_trending_searches(self, query):
        """Handle trending searches endpoint"""
        try:
            # Get parameters
            pn = query.get('pn', ['united_states'])[0].lower()  # Ensure lowercase
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            
            logger.info(f"Trending searches request: pn={pn}")
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz, 
                timeout=(10,25), 
                retries=2, 
                backoff_factor=0.5,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
            # Get data with correct country codes
            # These are the known working formats for different countries
            known_countries = {
                'united_states': 'united_states',
                'us': 'united_states',
                'uk': 'united_kingdom',
                'united_kingdom': 'united_kingdom', 
                'japan': 'japan',
                'canada': 'canada',
                'germany': 'germany',
                'india': 'india',
                'australia': 'australia',
                'brazil': 'brazil',
                'france': 'france',
                'mexico': 'mexico',
                'italy': 'italy'
            }
            
            # Use known country format if available
            country = known_countries.get(pn.lower(), pn.lower())
            
            # Get data
            try:
                df = pytrends.trending_searches(pn=country)
                
                # Handle different formats of results
                if isinstance(df, pd.Series):
                    result = df.tolist()
                    result = [{"query": item} for item in result]
                elif isinstance(df, pd.DataFrame):
                    if len(df.columns) == 1 and not df.empty:
                        result = df[df.columns[0]].tolist()
                        result = [{"query": item} for item in result]
                    else:
                        result = df.to_dict('records')
                else:
                    result = [{"query": str(df)}]
                    
            except Exception as e:
                # Try alternate format with uppercase for certain countries
                if country.lower() in ['us', 'uk', 'jp', 'ca', 'de', 'in', 'au']:
                    try:
                        df = pytrends.trending_searches(pn=country.upper())
                        if isinstance(df, pd.Series):
                            result = df.tolist()
                            result = [{"query": item} for item in result]
                        else:
                            result = df.to_dict('records')
                    except Exception as e2:
                        logger.error(f"Both formats failed: {str(e)} and {str(e2)}")
                        raise ValueError(f"Failed to get trending searches for {pn}: {str(e)}")
                else:
                    raise ValueError(f"Failed to get trending searches for {pn}: {str(e)}")
                    
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "pn": pn,
                "data": result
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing trending searches request: {str(e)}")
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
    
    def handle_realtime_trending_searches(self, query):
        """Handle realtime trending searches endpoint"""
        try:
            # Get parameters
            pn = query.get('pn', ['US'])[0].upper()  # Force uppercase for realtime
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = query.get('cat', ['all'])[0]
            
            logger.info(f"Realtime trending searches request: pn={pn}")
            
            # Import here to avoid impacting health checks
            import logging
            from pytrends.request import TrendReq
            from pytrends import dailydata
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl,
                tz=tz,
                timeout=(10,25),
                retries=3,
                backoff_factor=0.5,
                requests_args={
                    'verify': False,
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
            # Known working country codes
            supported_countries = [
                'AR', 'AU', 'AT', 'BE', 'BR', 'CA', 'CL', 'CO', 'CZ', 'DK',
                'EG', 'FI', 'FR', 'DE', 'GR', 'HK', 'HU', 'IN', 'ID', 'IE',
                'IL', 'IT', 'JP', 'KE', 'MY', 'MX', 'NL', 'NZ', 'NG', 'NO',
                'PL', 'PT', 'PH', 'RO', 'RU', 'SA', 'SG', 'ZA', 'KR', 'ES',
                'SE', 'CH', 'TW', 'TH', 'TR', 'UA', 'GB', 'US', 'VN'
            ]
            
            # Convert country names to codes
            country_map = {
                'united_states': 'US',
                'india': 'IN',
                'brazil': 'BR',
                'mexico': 'MX',
                'united_kingdom': 'GB',
                'france': 'FR',
                'germany': 'DE',
                'italy': 'IT',
                'spain': 'ES',
                'canada': 'CA',
                'australia': 'AU',
                'japan': 'JP'
            }

            # Normalize country input
            pn = country_map.get(pn.lower(), pn[:2].upper())

            # Validate country code
            if pn not in supported_countries:
                return self._send_validation_error(
                    f"Invalid country code: {pn}",
                    list(supported_countries)
                )
            
            result = []
            try:
                # Attempt realtime API first
                df = pytrends.realtime_trending_searches(pn=pn)
                result = self._process_realtime_data(df)
                
                if not result:  # Fallback if empty response
                    raise ValueError("Empty realtime data")
                    
            except Exception as e:
                logger.warning(f"Realtime failed: {str(e)}, trying daily trends")
                # Fallback to daily trends api 
                try:
                    # Try to use daily data API if available
                    today = datetime.now().strftime('%Y-%m-%d')
                    df = pytrends.trending_searches(pn=pn)
                    result = []
                    if isinstance(df, pd.Series):
                        for item in df.tolist():
                            result.append({
                                "title": item,
                                "traffic": "Daily trend",
                                "date": today
                            })
                    elif isinstance(df, pd.DataFrame) and len(df.columns) > 0:
                        column = df.columns[0]
                        for item in df[column].tolist():
                            result.append({
                                "title": item,
                                "traffic": "Daily trend",
                                "date": today
                            })
                except Exception as inner_e:
                    logger.error(f"Daily trends also failed: {str(inner_e)}")
                    result = [{"note": "Could not retrieve trending searches"}]

            # Send successful response
            self._send_success_response({
                "pn": pn,
                "cat": cat,
                "data": result
            })

        except Exception as e:
            logger.error(f"Critical failure: {str(e)}")
            logger.error(traceback.format_exc())
            self._send_error_response(str(e))

    def _process_realtime_data(self, df):
        """Clean and format realtime data"""
        if df is None or df.empty:
            return []
            
        clean_result = []
        for item in df.to_dict('records'):
            clean_item = {
                "title": item.get('title', ''),
                "traffic": item.get('formattedTraffic', ''),
                "image": item.get('image', {}).get('newsUrl', ''),
                "articles": [
                    {"title": art.get('title', ''), "url": art.get('url', '')}
                    for art in item.get('articles', [])
                ]
            }
            clean_result.append(clean_item)
        return clean_result

    def _process_daily_data(self, df):
        """Clean and format daily trends data"""
        if df is None or df.empty:
            return []
        try:
            return df[['title', 'traffic', 'related_queries']].to_dict('records')
        except:
            # Fallback if columns are different
            return df.to_dict('records')

    def _send_success_response(self, data):
        """Send a successful response"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _send_validation_error(self, message, supported):
        """Send a validation error response"""
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_response = {
            "status": "error",
            "message": message,
            "supported_countries": supported
        }
        self.wfile.write(json.dumps(error_response).encode())

    def _send_error_response(self, message):
        """Send an error response"""
        self.send_response(500)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_response = {"status": "error", "message": message}
        self.wfile.write(json.dumps(error_response).encode())
    
    def handle_top_charts(self, query):
        """Handle top charts endpoint"""
        try:
            # Get parameters
            date = int(query.get('date', ['2021'])[0])
            geo = query.get('geo', ['GLOBAL'])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            
            logger.info(f"Top charts request: date={date}, geo={geo}")
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
            # Get data
            data = pytrends.top_charts(date, geo=geo)
            result = data.to_dict('records') if not data.empty else []
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "date": date,
                "geo": geo,
                "data": result
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing top charts request: {str(e)}")
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
    
    def handle_suggestions(self, query):
        """Handle keyword suggestions endpoint"""
        try:
            # Get parameters
            keyword = query.get('keyword', ['bitcoin'])[0]
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            
            logger.info(f"Suggestions request: keyword={keyword}")
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
            # Get data
            suggestions = pytrends.suggestions(keyword=keyword)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "keyword": keyword,
                "suggestions": suggestions
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing suggestions request: {str(e)}")
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
    
    def handle_categories(self, query):
        """Handle categories endpoint"""
        try:
            # Get parameters
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            
            logger.info(f"Categories request")
            
            # Import here to avoid impacting health checks
            from pytrends.request import TrendReq
            
            # Initialize PyTrends with custom headers
            pytrends = TrendReq(
                hl=hl, 
                tz=tz,
                requests_args={
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
            )
            
            # Get data
            categories = pytrends.categories()
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                "categories": categories
            }
            
            self.wfile.write(json.dumps(response, default=str).encode())
            
        except Exception as e:
            logger.error(f"Error processing categories request: {str(e)}")
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
