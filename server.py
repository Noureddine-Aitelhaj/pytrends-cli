python
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

def get_trending_searches(pn='united_states', hl='en-US', tz=360):
    """Get trending searches for a given country"""
    logger.info(f"Getting trending searches for country: {pn}")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Known working country formats
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
    country = known_countries.get(pn.lower(), pn).upper()
    
    # Initialize PyTrends with backoff factor to handle rate limiting
    pytrends = TrendReq(hl=hl, tz=tz, timeout=(10,25), retries=2, backoff_factor=0.5)
    
    # Try getting data with the primary format
    try:
        df = pytrends.trending_searches(pn=country)
        
        # Handle different result formats
        if isinstance(df, pd.Series):
            result = df.tolist()
            return {
                "pn": pn,
                "data": [{"query": item} for item in result]
            }
        elif isinstance(df, pd.DataFrame):
            if len(df.columns) == 1 and not df.empty:
                result = df[df.columns[0]].tolist()
                return {
                    "pn": pn,
                    "data": [{"query": item} for item in result]
                }
            else:
                return {
                    "pn": pn,
                    "data": df.to_dict('records')
                }
        else:
            return {
                "pn": pn,
                "data": [{"query": str(df)}]
            }
            
    except Exception as e:
        # Try alternate format for certain countries
        if country.lower() in ['us', 'uk', 'jp', 'ca', 'de', 'in', 'au']:
            try:
                df = pytrends.trending_searches(pn=country.upper())
                
                if isinstance(df, pd.Series):
                    result = df.tolist()
                    return {
                        "pn": pn,
                        "data": [{"query": item} for item in result]
                    }
                else:
                    return {
                        "pn": pn,
                        "data": df.to_dict('records')
                    }
            except Exception as e2:
                logger.error(f"Both formats failed: {str(e)} and {str(e2)}")
                raise ValueError(f"Failed to get trending searches for {pn}: {str(e)}")
        else:
            raise ValueError(f"Failed to get trending searches for {pn}: {str(e)}")

def get_realtime_trending_searches(pn='US', hl='en-US', tz=360, cat="all", count=300):
    """Get realtime trending searches for a given country"""
    logger.info(f"Getting realtime trending searches for country: {pn}, count={count}")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    from datetime import datetime
    
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
        raise ValueError(f"Invalid country code: {pn}. Supported countries: {', '.join(supported_countries)}")
    
    # Initialize PyTrends with basic parameters and SSL verification disabled
    # This improves reliability for some connections
    pytrends = TrendReq(
        hl=hl,
        tz=tz,
        timeout=(10,25),
        retries=3,
        backoff_factor=0.5,
        requests_args={'verify': False}
    )
    
    try:
        # Call the realtime_trending_searches method with all parameters
        df = pytrends.realtime_trending_searches(pn=pn, cat=cat, count=count)
        
        if df is None or df.empty:
            return {"pn": pn, "cat": cat, "data": []}
            
        # Process the data
        result = []
        for item in df.to_dict("records"):
            result.append({
                "title": item.get("title", ""),
                "entities": item.get("entityNames", [])
            })
            
        return {
            "pn": pn,
            "cat": cat,
            "data": result
        }
    except Exception as e:
        logger.warning(f"Realtime failed: {str(e)}, trying today's searches")
        try:
            df = pytrends.today_searches(pn=pn)
            result = [{"title": title} for title in df]
            return {
                "pn": pn,
                "cat": cat,
                "data": result,
                "note": "Used daily trends as fallback"
            }
        except Exception as inner_e:
            logger.error(f"Daily trends also failed: {str(inner_e)}")
            return {
                "pn": pn,
                "cat": cat,
                "data": [{"note": "Could not retrieve trending searches"}],
                "error": str(e)
            }

def process_realtime_data(df):
    """Clean and format realtime data"""
    if df is None or df.empty:
        return []
    return [
        {
            "title": item.get("title", ""),
            "entities": item.get("entityNames", [])
        }
        for item in df.to_dict("records")
    ]

def process_daily_data(df):
    """Clean and format daily trends data"""
    if df is None or df.empty:
        return []
    return [{"title": title} for title in df]

def google_search(query, num_results=10, lang="en", proxy=None, advanced=False, sleep_interval=0, timeout=5):
    """
    Perform a Google search and return the results
    
    Parameters:
    -----------
    query : str
        The search query
    num_results : int
        The number of results to return (default 10)
    lang : str
        The language code (default "en")
    proxy : str
        Optional proxy server (default None)
    advanced : bool
        Whether to return advanced search results with additional metadata (default False)
    sleep_interval : int
        Time to sleep between requests (default 0)
    timeout : int
        Timeout for requests in seconds (default 5)
        
    Returns:
    --------
    dict : Search results with metadata
    """
    logger.info(f"Performing Google search for query: {query}")
    
    # Import dependencies
    from googlesearch import search
    
    try:
        # Execute the search
        results = []
        
        if advanced:
            # For advanced search, we get full result objects
            search_results = search(
                query,
                num_results=num_results,
                lang=lang, 
                proxy=proxy,
                advanced=True,
                sleep_interval=sleep_interval,
                timeout=timeout
            )
            
            # Process advanced results
            for result in search_results:
                results.append({
                    "title": result.title,
                    "url": result.url,
                    "description": result.description,
                    "rank": result.rank
                })
        else:
            # For simple search, we just get URLs
            search_results = search(
                query,
                num_results=num_results,
                lang=lang,
                proxy=proxy,
                advanced=False,
                sleep_interval=sleep_interval,
                timeout=timeout
            )
            
            # Convert to list if it's a generator
            results = list(search_results)
        
        return {
            "query": query,
            "num_results": len(results),
            "lang": lang,
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Error performing Google search: {str(e)}")
        raise ValueError(f"Failed to perform Google search for '{query}': {str(e)}")
        
def search_and_analyze(query, num_results=10, include_trends=False, lang="en"):
    """
    Perform a Google search and optionally get trend data for the query
    
    Parameters:
    -----------
    query : str
        The search query
    num_results : int
        The number of results to return (default 10)
    include_trends : bool
        Whether to include trend data for the query (default False)
    lang : str
        The language code (default "en")
    
    Returns:
    --------
    dict : Combined search results and trend data
    """
    logger.info(f"Performing combined search and analysis for: {query}")
    
    # Get search results
    search_results = google_search(
        query=query,
        num_results=num_results,
        lang=lang,
        advanced=True
    )
    
    response = {
        "query": query,
        "search_results": search_results["results"]
    }
    
    # Optionally get trend data
    if include_trends:
        try:
            # Import dependencies
            from pytrends.request import TrendReq
            import pandas as pd
            
            # Initialize PyTrends
            pytrends = TrendReq(hl=f"{lang}-{lang.upper()}", tz=360)
            
            # Build payload
            pytrends.build_payload([query], timeframe='today 3-m')
            
            # Get interest over time
            interest_df = pytrends.interest_over_time()
            if not interest_df.empty:
                trend_data = interest_df.reset_index().to_dict('records')
            else:
                trend_data = []
                
            # Get related queries
            related = pytrends.related_queries()
            related_data = {}
            
            if query in related and related[query]:
                if related[query]['top'] is not None:
                    related_data["top"] = related[query]['top'].to_dict('records')
                else:
                    related_data["top"] = []
                    
                if related[query]['rising'] is not None:
                    related_data["rising"] = related[query]['rising'].to_dict('records')
                else:
                    related_data["rising"] = []
            
            response["trend_data"] = {
                "interest_over_time": trend_data,
                "related_queries": related_data
            }
            
        except Exception as e:
            logger.warning(f"Could not get trend data: {str(e)}")
            response["trend_data"] = {"error": str(e)}
    
    return response

def get_keyword_suggestions(keyword, num_results=10, lang="en", country="us"):
    """
    Get keyword suggestions from Google Autocomplete
    
    Parameters:
    -----------
    keyword : str
        The base keyword to get suggestions for
    num_results : int
        Maximum number of suggestions to return (default 10)
    lang : str
        Language code (default "en")
    country : str
        Country code (default "us")
    
    Returns:
    --------
    dict : Suggestion results
    """
    logger.info(f"Getting keyword suggestions for: {keyword}")
    
    try:
        # Import dependencies
        import requests
        import json
        
        # Use the Google Suggest API
        url = "https://suggestqueries.google.com/complete/search"
        params = {
            "client": "firefox",  # Using firefox client for JSON response
            "q": keyword,
            "hl": lang,
            "gl": country,
            "ie": "UTF-8",
            "oe": "UTF-8"
        }
        
        # Make the request
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            # Parse suggestions from the response
            data = json.loads(response.content.decode('utf-8'))
            suggestions = data[1][:num_results]
            
            return {
                "keyword": keyword,
                "lang": lang,
                "country": country,
                "suggestions": suggestions
            }
        else:
            logger.error(f"Error getting suggestions: {response.status_code}")
            raise ValueError(f"Failed to get suggestions: HTTP {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error getting keyword suggestions: {str(e)}")
        raise ValueError(f"Failed to get suggestions for '{keyword}': {str(e)}")

def get_niche_topics(seed_keyword, depth=2, results_per_level=5, lang="en"):
    """
    Generate a hierarchical list of niche topics related to a seed keyword
    using search and suggestions
    
    Parameters:
    -----------
    seed_keyword : str
        The main topic to explore
    depth : int
        How many levels deep to explore (default 2)
    results_per_level : int
        How many results to include per level (default 5)
    lang : str
        Language code (default "en")
    
    Returns:
    --------
    dict : Hierarchical topic tree
    """
    logger.info(f"Generating niche topics for: {seed_keyword}, depth={depth}")
    
    # Import dependencies
    import time
    
    # Start with the seed keyword as the root topic
    topic_tree = {
        "keyword": seed_keyword,
        "subtopics": []
    }
    
    # Queue to process, with (keyword, current_depth, parent) tuples
    processing_queue = [(seed_keyword, 0, topic_tree["subtopics"])]
    
    # Process the queue
    while processing_queue:
        current_keyword, current_depth, parent_list = processing_queue.pop(0)
        
        # Skip if we've reached max depth
        if current_depth >= depth:
            continue
            
        try:
            # Get suggestions for the current keyword
            suggestions_result = get_keyword_suggestions(
                current_keyword, 
                num_results=results_per_level,
                lang=lang
            )
            
            # Create a node for each suggestion
            for suggestion in suggestions_result["suggestions"]:
                subtopic = {
                    "keyword": suggestion,
                    "subtopics": []
                }
                parent_list.append(subtopic)
                
                # Add to queue for next level processing
                if current_depth < depth - 1:
                    processing_queue.append((suggestion, current_depth + 1, subtopic["subtopics"]))
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
                
        except Exception as e:
            logger.warning(f"Error exploring '{current_keyword}': {str(e)}")
            continue
    
    return topic_tree

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
                "endpoints": [
                    "/health",
                    "/search",
                    "/search/combined",
                    "/autocomplete",
                    "/trends",
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
                    "/niche-topics"
                ]
            }
            self.wfile.write(json.dumps(response).encode())
            return

        # Google Search endpoints
        elif path == '/search':
            self.handle_google_search(query)
            return
        elif path == '/search/combined':
            self.handle_combined_search(query)
            return
        elif path == '/niche-topics':
            self.handle_niche_topics(query)
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

    def handle_google_search(self, query):
        """Handle Google search endpoint"""
        try:
            # Get parameters
            search_query = query.get('q', [''])[0]
            num_results = int(query.get('num', ['10'])[0])
            lang = query.get('lang', ['en'])[0]
            advanced = query.get('advanced', ['false'])[0].lower() == 'true'
            sleep_interval = int(query.get('sleep', ['0'])[0])
            timeout = int(query.get('timeout', ['5'])[0])

            if not search_query:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "Search query (q) parameter is required"}
                self.wfile.write(json.dumps(error_response).encode())
                return

            logger.info(f"Google search request: q={search_query}, num={num_results}, lang={lang}")

            # Use the google_search function from CLI
            try:
                result = google_search(
                    query=search_query,
                    num_results=num_results,
                    lang=lang,
                    advanced=advanced,
                    sleep_interval=sleep_interval,
                    timeout=timeout
                )
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result, default=str).encode())

            except Exception as search_error:
                logger.error(f"Search execution error: {str(search_error)}")
                raise search_error

        except Exception as e:
            logger.error(f"Error processing Google search request: {str(e)}")
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

    def handle_combined_search(self, query):
        """Handle combined search and trends analysis endpoint"""
        try:
            # Get parameters
            search_query = query.get('q', [''])[0]
            num_results = int(query.get('num', ['10'])[0])
            include_trends = query.get('include_trends', ['false'])[0].lower() == 'true'
            lang = query.get('lang', ['en'])[0]

            if not search_query:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "Search query (q) parameter is required"}
                self.wfile.write(json.dumps(error_response).encode())
                return

            logger.info(f"Combined search request: q={search_query}, include_trends={include_trends}")

            # Use the search_and_analyze function from CLI
            result = search_and_analyze(
                query=search_query,
                num_results=num_results,
                include_trends=include_trends,
                lang=lang
            )

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, default=str).encode())

        except Exception as e:
            logger.error(f"Error processing combined search request: {str(e)}")
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

    def handle_niche_topics(self, query):
        """Handle niche topics discovery endpoint"""
        try:
            # Get parameters
            seed_keyword = query.get('keyword', [''])[0]
            depth = int(query.get('depth', ['2'])[0])
            results_per_level = int(query.get('results_per_level', ['5'])[0])
            lang = query.get('lang', ['en'])[0]

            if not seed_keyword:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = {"error": "Keyword parameter is required"}
                self.wfile.write(json.dumps(error_response).encode())
                return

            # Validate parameters
            if depth > 3:
                depth = 3  # Limit depth to avoid excessive requests
            if results_per_level > 10:
                results_per_level = 10  # Limit results to avoid excessive requests

            logger.info(f"Niche topics request: keyword={seed_keyword}, depth={depth}, results_per_level={results_per_level}")

            # Use the get_niche_topics function from CLI
            topic_tree = get_niche_topics(
                seed_keyword=seed_keyword,
                depth=depth,
                results_per_level=results_per_level,
                lang=lang
            )

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "seed_keyword": seed_keyword,
                "depth": depth,
                "results_per_level": results_per_level,
                "lang": lang,
                "topic_tree": topic_tree
            }
            self.wfile.write(json.dumps(response, default=str).encode())

        except Exception as e:
            logger.error(f"Error processing niche topics request: {str(e)}")
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
                "/search?q=bitcoin&num=10&advanced=true",
                "/search/combined?q=bitcoin&include_trends=true",
                "/autocomplete?keyword=bitcoin&language=en&region=us",
                "/niche-topics?keyword=bitcoin&depth=2&results_per_level=5",
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

            # Build payload
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframes, geo=geo)

            # Get data
            data = pytrends.multirange_interest_over_time()
            result = data.reset_index().to_dict('records') if not data.empty else []

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
            from pytrends import dailydata
            # This functionality is handled by the dailydata module now
            data = dailydata.get_daily_data(
                keyword=keywords[0] if keywords else "bitcoin",
                start_year=year_start,
                start_mon=month_start,
                start_day=day_start,
                stop_year=year_end,
                stop_mon=month_end,
                stop_day=day_end,
                geo=geo,
                verbose=False
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
                logger.info(f"Processing data for keyword '{kw}'")  # Debugging log
                if kw in data:
                    result[kw] = {}
                    # Check for top topics
                    if data[kw]['top'] is not None:
                        result[kw]['top'] = data[kw]['top'].to_dict('records')
                    else:
                        result[kw]['top'] = []
                    # Check for rising topics
                    if data[kw]['rising'] is not None:
                        result[kw]['rising'] = data[kw]['rising'].to_dict('records')
                    else:
                        result[kw]['rising'] = []
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

            # Use the get_trending_searches function from CLI
            result = get_trending_searches(pn=pn, hl=hl, tz=tz)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, default=str).encode())

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
            pn = query.get('pn', ['US'])[0]  # Can be uppercase or lowercase
            hl = query.get('hl', ['en-US'])[0]
            tz = int(query.get('tz', ['360'])[0])
            cat = query.get('cat', ['all'])[0]
            count = int(query.get('count', ['300'])[0])

            logger.info(f"Realtime trending searches request: pn={pn}, count={count}")

            # Use the get_realtime_trending_searches function from CLI
            result = get_realtime_trending_searches(pn=pn, hl=hl, tz=tz, cat=cat, count=count)

            # Send successful response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, default=str).encode())

        except Exception as e:
            logger.error(f"Error processing realtime trending searches request: {str(e)}")
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
