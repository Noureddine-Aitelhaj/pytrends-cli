# -*- coding: utf-8 -*-
"""
Python HTTP Server for Google Search, Autocomplete, and Trends APIs.
Provides various endpoints to interact with Google services.
"""

import http.server
import socketserver
import json
import os
import traceback
import urllib.parse
from datetime import datetime
import logging
import signal
import sys
import time
import requests

# --- Configuration ---

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)] # Ensure logs go to stdout for container environments
)
logger = logging.getLogger(__name__)

# Server Port
PORT = int(os.environ.get('PORT', 8080))

# Rate Limiter Configuration
MAX_CALLS_PER_MINUTE = 100
RATE_LIMIT_TIMEFRAME = 60  # seconds

# Disable SSL verification warnings for pytrends if needed (use with caution)
# import warnings
# from requests.packages.urllib3.exceptions import InsecureRequestWarning
# warnings.simplefilter('ignore', InsecureRequestWarning)

# --- Rate Limiter ---

class RateLimiter:
    """Simple in-memory rate limiter."""
    def __init__(self, max_calls, time_frame):
        self.max_calls = max_calls
        self.time_frame = time_frame
        self.calls = []
        logger.info(f"Rate limiter initialized: Max {max_calls} calls per {time_frame} seconds.")

    def add_call(self):
        """Record a call timestamp."""
        now = time.time()
        # Remove calls older than the time frame
        self.calls = [call for call in self.calls if call > now - self.time_frame]
        self.calls.append(now)

    def is_allowed(self):
        """Check if a call is allowed."""
        now = time.time()
        # Clean up old calls first
        self.calls = [call for call in self.calls if call > now - self.time_frame]
        # Check if current number of calls is below the maximum
        allowed = len(self.calls) < self.max_calls
        if not allowed:
            logger.warning(f"Rate limit exceeded. Current calls: {len(self.calls)} >= Max: {self.max_calls}")
        return allowed

# Initialize the rate limiter
rate_limiter = RateLimiter(max_calls=MAX_CALLS_PER_MINUTE, time_frame=RATE_LIMIT_TIMEFRAME)

# --- Core Functionality (External API Wrappers) ---

def get_google_suggestions(keyword, num_suggestions=10, language="en", region="us"):
    """Get autocomplete suggestions from Google Suggest API."""
    logger.info(f"Fetching Google suggestions for keyword: '{keyword}', lang: {language}, region: {region}")
    url = "https://suggestqueries.google.com/complete/search"
    params = {
        "client": "firefox",  # Provides JSON response
        "q": keyword,
        "hl": language,
        "gl": region,
        "ie": "UTF-8",
        "oe": "UTF-8"
    }

    try:
        response = requests.get(url, params=params, timeout=5) # Added timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        data = response.json() # Use response.json() for automatic decoding
        if len(data) > 1 and isinstance(data[1], list):
            suggestions = data[1][:num_suggestions] # Limit results if needed
            logger.info(f"Successfully fetched {len(suggestions)} suggestions.")
            return suggestions
        else:
            logger.warning(f"Unexpected response format from Google Suggest: {data}")
            return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Google suggestions: {str(e)}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response from Google Suggest: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting Google suggestions: {str(e)}", exc_info=True)
        return []

def get_trending_searches(pn='united_states', hl='en-US', tz=360):
    """Get daily trending searches for a given country using pytrends."""
    logger.info(f"Getting daily trending searches for country: {pn}, lang: {hl}")

    # Import dependencies only when needed
    try:
        from pytrends.request import TrendReq
        import pandas as pd
    except ImportError as e:
        logger.error(f"Missing dependency for trending searches: {e}")
        raise ImportError(f"pytrends or pandas not installed. Cannot get trending searches.")

    # Known working country formats for pytrends daily trends
    known_countries = {
        'united_states': 'united_states', 'us': 'united_states',
        'united_kingdom': 'united_kingdom', 'uk': 'united_kingdom', 'gb': 'united_kingdom',
        'japan': 'japan', 'jp': 'japan',
        'canada': 'canada', 'ca': 'canada',
        'germany': 'germany', 'de': 'germany',
        'india': 'india', 'in': 'india',
        'australia': 'australia', 'au': 'australia',
        'brazil': 'brazil', 'br': 'brazil',
        'france': 'france', 'fr': 'france',
        'mexico': 'mexico', 'mx': 'mexico',
        'italy': 'italy', 'it': 'italy',
        # Add more mappings as needed
    }

    # Normalize country input using the mapping
    normalized_pn = known_countries.get(pn.lower().replace('_', ' '), pn) # Default to original if not found

    try:
        # Initialize PyTrends with backoff factor to handle rate limiting
        pytrends = TrendReq(hl=hl, tz=tz, timeout=(10, 25), retries=2, backoff_factor=0.5)

        logger.debug(f"Requesting trending_searches with pn='{normalized_pn}'")
        df = pytrends.trending_searches(pn=normalized_pn)

        # Process the result (can be Series or DataFrame)
        if isinstance(df, pd.Series):
            result = df.tolist()
        elif isinstance(df, pd.DataFrame) and not df.empty:
            # Assuming the first column contains the trends if it's a DataFrame
            result = df.iloc[:, 0].tolist()
        elif isinstance(df, pd.DataFrame) and df.empty:
            logger.warning(f"Received empty DataFrame for trending searches for '{normalized_pn}'.")
            result = []
        else:
            logger.warning(f"Unexpected data type received from trending_searches: {type(df)}")
            result = []

        logger.info(f"Found {len(result)} trending searches for '{normalized_pn}'.")
        return {
            "pn_requested": pn,
            "pn_used": normalized_pn,
            "hl": hl,
            "data": [{"query": item} for item in result]
        }

    except Exception as e:
        logger.error(f"Failed to get trending searches for '{pn}' (used '{normalized_pn}'): {str(e)}", exc_info=True)
        # Re-raise as a ValueError to be caught by the handler
        raise ValueError(f"Failed to get trending searches for {pn}: {str(e)}")

def get_realtime_trending_searches(pn='US', hl='en-US', tz=360, cat="all"):
    """Get realtime trending searches for a given country using pytrends."""
    logger.info(f"Getting realtime trending searches for country: {pn}, category: {cat}, lang: {hl}")

    # Import dependencies only when needed
    try:
        from pytrends.request import TrendReq
        import pandas as pd
    except ImportError as e:
        logger.error(f"Missing dependency for realtime trending searches: {e}")
        raise ImportError(f"pytrends or pandas not installed. Cannot get realtime trends.")

    # Realtime trends use 2-letter country codes primarily. Map common names.
    country_map = {
        'united states': 'US', 'usa': 'US',
        'united kingdom': 'GB', 'uk': 'GB',
        'india': 'IN', 'brazil': 'BR', 'mexico': 'MX', 'france': 'FR',
        'germany': 'DE', 'italy': 'IT', 'spain': 'ES', 'canada': 'CA',
        'australia': 'AU', 'japan': 'JP',
        # Add more as needed
    }

    # Normalize country input to uppercase 2-letter code if possible
    normalized_pn = country_map.get(pn.lower(), pn).upper()
    logger.debug(f"Normalized country code for realtime trends: {normalized_pn}")

    # Initialize PyTrends - consider disabling SSL verification if network issues persist
    # requests_args={'verify': False} can sometimes help behind proxies/firewalls
    try:
        pytrends = TrendReq(
            hl=hl,
            tz=tz,
            timeout=(10, 25),
            retries=3,
            backoff_factor=0.5,
            # requests_args={'verify': False} # Uncomment if needed
        )
    except Exception as e:
         logger.error(f"Failed to initialize PyTrends: {str(e)}", exc_info=True)
         raise RuntimeError(f"PyTrends initialization failed: {str(e)}")

    result = []
    try:
        # Attempt realtime API
        logger.debug(f"Requesting realtime_trending_searches with pn='{normalized_pn}', cat='{cat}'")
        df = pytrends.realtime_trending_searches(pn=normalized_pn, cat=cat)
        result = process_realtime_data(df)

        if not result:
            logger.warning(f"Realtime trending searches returned empty for {normalized_pn}. Trying fallback.")
            raise ValueError("Empty realtime data, attempting fallback.") # Trigger fallback

    except Exception as e:
        logger.warning(f"Realtime trends API failed or returned empty for '{normalized_pn}': {str(e)}. Falling back to today's searches.")
        # Fallback to today's searches (different endpoint, might have different data)
        try:
            logger.debug(f"Attempting fallback: today_searches with pn='{normalized_pn}'")
            # Today's searches might use full country name or code, try normalized code first
            df_today = pytrends.today_searches(pn=normalized_pn)
            result = process_daily_data(df_today) # Use a different processor if format differs
            if not result:
                 logger.warning(f"Fallback today_searches also returned empty for {normalized_pn}.")
                 result = [{"note": f"Could not retrieve trending searches for {normalized_pn}. Both realtime and daily APIs returned no data."}]
            else:
                 logger.info(f"Successfully retrieved data using fallback today_searches for {normalized_pn}.")
                 # Add a note indicating this is fallback data
                 if isinstance(result, list) and result:
                     result[0]['note'] = "Data retrieved using fallback (today_searches)"

        except Exception as inner_e:
            logger.error(f"Fallback today_searches also failed for '{normalized_pn}': {str(inner_e)}", exc_info=True)
            result = [{"note": f"Could not retrieve trending searches for {normalized_pn}. Realtime API failed with '{str(e)}', and fallback failed with '{str(inner_e)}'."}]

    return {
        "pn_requested": pn,
        "pn_used": normalized_pn,
        "cat": cat,
        "hl": hl,
        "data": result
    }

def process_realtime_data(df):
    """Clean and format realtime trending data from DataFrame."""
    if df is None or df.empty:
        logger.debug("process_realtime_data received empty or None DataFrame.")
        return []
    try:
        # Expected columns: 'title', 'entityNames'
        required_cols = ['title', 'entityNames']
        if not all(col in df.columns for col in required_cols):
             logger.warning(f"Realtime data DataFrame missing expected columns. Found: {list(df.columns)}. Expected: {required_cols}")
             # Adapt if structure is different, e.g., maybe just use first column if ['title', 'entityNames'] are missing
             if 'title' in df.columns:
                 return df[['title']].to_dict("records")
             elif not df.empty: # Fallback to using the first column as title
                 return df[[df.columns[0]]].rename(columns={df.columns[0]: 'title'}).to_dict("records")
             return []

        # Convert DataFrame rows to a list of dictionaries
        records = df.to_dict("records")
        processed = [
            {
                "title": item.get("title", ""),
                "entities": item.get("entityNames", [])
            }
            for item in records
        ]
        logger.debug(f"Processed {len(processed)} realtime data records.")
        return processed
    except Exception as e:
        logger.error(f"Error processing realtime DataFrame: {str(e)}", exc_info=True)
        return []


def process_daily_data(df):
    """Clean and format daily trends data (often just a Series or single-column DataFrame)."""
    if df is None:
        logger.debug("process_daily_data received None input.")
        return []
    try:
        if isinstance(df, pd.Series):
            result_list = df.tolist()
        elif isinstance(df, pd.DataFrame):
            if df.empty:
                logger.debug("process_daily_data received empty DataFrame.")
                return []
            # Assume the first column holds the trending query
            result_list = df.iloc[:, 0].tolist()
        elif isinstance(df, list): # Already a list
            result_list = df
        else:
            logger.warning(f"Unexpected data type in process_daily_data: {type(df)}")
            return [] # Or try converting to string: [{"title": str(df)}]

        processed = [{"title": title} for title in result_list if title] # Ensure title is not empty
        logger.debug(f"Processed {len(processed)} daily data records.")
        return processed
    except Exception as e:
        logger.error(f"Error processing daily data: {str(e)}", exc_info=True)
        return []


def google_search(query, num_results=10, lang="en", proxy=None, advanced=False, sleep_interval=0, timeout=5):
    """Perform a Google search using the googlesearch-python library."""
    logger.info(f"Performing Google search for query: '{query}', num_results={num_results}, lang={lang}, advanced={advanced}")

    # Import dependency only when needed
    try:
        # NOTE: googlesearch-python can be unreliable due to Google blocking scrapers.
        # Consider using official APIs (like Google Custom Search JSON API) for production.
        from googlesearch import search
    except ImportError as e:
        logger.error(f"Missing dependency for Google search: {e}")
        raise ImportError(f"googlesearch-python not installed. Cannot perform search.")

    try:
        # Execute the search
        search_results_generator = search(
            query=query,
            num_results=num_results,
            lang=lang,
            proxy=proxy,
            advanced=advanced, # Returns dicts with title, url, description if True
            sleep_interval=sleep_interval, # Be respectful of Google's servers
            timeout=timeout
        )

        # Process results
        results_list = []
        count = 0
        for result in search_results_generator:
            if advanced:
                # Result is expected to be an object with attributes
                results_list.append({
                    "title": getattr(result, 'title', 'N/A'),
                    "url": getattr(result, 'url', 'N/A'),
                    "description": getattr(result, 'description', 'N/A'),
                    # 'rank' might not be consistently available depending on library version/Google's output
                    # "rank": getattr(result, 'rank', None)
                })
            else:
                # Result is expected to be just the URL string
                results_list.append({"url": result}) # Wrap in dict for consistency
            count += 1
            # Optional: Break if we somehow get more results than requested (though library usually handles num_results)
            # if count >= num_results:
            #     break

        logger.info(f"Google search returned {len(results_list)} results for '{query}'.")
        return {
            "query": query,
            "num_results_requested": num_results,
            "num_results_returned": len(results_list),
            "lang": lang,
            "advanced": advanced,
            "results": results_list
        }

    except Exception as e:
        # Specific handling for common googlesearch issues might be needed
        # e.g., if it raises exceptions related to HTTP errors or parsing failures
        logger.error(f"Error performing Google search for '{query}': {str(e)}", exc_info=True)
        # Re-raise as ValueError for the handler
        raise ValueError(f"Failed to perform Google search for '{query}': {str(e)}")

def search_and_analyze(query, num_results=10, include_trends=False, lang="en"):
    """Perform Google search and optionally fetch trend data for the query."""
    logger.info(f"Performing combined search and analysis for: '{query}', include_trends={include_trends}")

    # Get search results
    search_results_data = google_search(
        query=query,
        num_results=num_results,
        lang=lang,
        advanced=True # Use advanced for richer search result data
    )

    response = {
        "query": query,
        "search_metadata": {
            "num_results_requested": search_results_data["num_results_requested"],
            "num_results_returned": search_results_data["num_results_returned"],
            "lang": search_results_data["lang"]
        },
        "search_results": search_results_data["results"],
        "trend_data": None # Initialize trend data as None
    }

    # Optionally get trend data
    if include_trends:
        logger.info(f"Fetching trend data for '{query}'...")
        try:
            # Import dependencies only when needed
            from pytrends.request import TrendReq
            import pandas as pd

            # Initialize PyTrends (use lang for hl)
            # Map language code format if necessary, e.g., 'en' -> 'en-US'
            hl_trends = f"{lang.lower()}-{lang.upper()}" if len(lang) == 2 else lang
            pytrends = TrendReq(hl=hl_trends, tz=360, timeout=(10, 25), retries=2, backoff_factor=0.5)

            # Build payload for the single query
            pytrends.build_payload([query], timeframe='today 3-m') # Example timeframe

            # 1. Interest Over Time
            interest_df = pytrends.interest_over_time()
            if not interest_df.empty and query in interest_df.columns:
                # Keep only the query's column and reset index
                trend_interest = interest_df[[query]].reset_index().rename(columns={'date': 'date', query: 'interest'}).to_dict('records')
            else:
                trend_interest = []

            # 2. Related Queries
            related_data_raw = pytrends.related_queries()
            related_data = {"top": [], "rising": []}
            if query in related_data_raw and related_data_raw[query]:
                if related_data_raw[query].get('top') is not None:
                    related_data["top"] = related_data_raw[query]['top'].to_dict('records')
                if related_data_raw[query].get('rising') is not None:
                    related_data["rising"] = related_data_raw[query]['rising'].to_dict('records')

            response["trend_data"] = {
                "interest_over_time": trend_interest,
                "related_queries": related_data,
                "status": "success"
            }
            logger.info(f"Successfully fetched trend data for '{query}'.")

        except ImportError as e:
             logger.error(f"Missing dependency for trend analysis: {e}")
             response["trend_data"] = {"error": f"Missing dependency: {e}", "status": "error"}
        except Exception as e:
            logger.warning(f"Could not get trend data for '{query}': {str(e)}", exc_info=True)
            response["trend_data"] = {"error": str(e), "status": "error"}

    return response


def get_niche_topics(seed_keyword, depth=2, results_per_level=5, lang="en", country="us"):
    """Explore niche topics related to a seed keyword using suggestions."""
    logger.info(f"Generating niche topics for: '{seed_keyword}', depth={depth}, results={results_per_level}")

    # Basic validation
    depth = max(1, min(depth, 3)) # Limit depth to prevent excessive recursion/calls
    results_per_level = max(1, min(results_per_level, 10)) # Limit results per level

    # Use a dictionary to store the tree structure
    topic_tree = {"keyword": seed_keyword, "subtopics": []}
    # Use a queue for breadth-first exploration: (keyword, current_depth, parent_node_list)
    processing_queue = [(seed_keyword, 0, topic_tree["subtopics"])]
    # Keep track of processed keywords to avoid cycles (optional, but good practice)
    processed_keywords = {seed_keyword}

    while processing_queue:
        current_keyword, current_depth, parent_subtopic_list = processing_queue.pop(0)

        # Stop if max depth is reached
        if current_depth >= depth:
            continue

        logger.debug(f"Exploring depth {current_depth + 1} for keyword: '{current_keyword}'")

        try:
            # Get suggestions for the current keyword
            suggestions = get_google_suggestions(
                current_keyword,
                num_suggestions=results_per_level,
                language=lang,
                region=country
            )

            # Process valid suggestions
            for suggestion in suggestions:
                if suggestion and suggestion not in processed_keywords:
                    # Create a new node for the suggestion
                    subtopic_node = {
                        "keyword": suggestion,
                        "subtopics": []
                    }
                    parent_subtopic_list.append(subtopic_node)
                    processed_keywords.add(suggestion)

                    # Add this suggestion to the queue for the next level exploration
                    processing_queue.append((suggestion, current_depth + 1, subtopic_node["subtopics"]))

            # Add a small delay to be respectful to the suggestion API
            time.sleep(0.2) # Adjust as needed

        except Exception as e:
            # Log error for this specific keyword but continue exploring others
            logger.warning(f"Error getting suggestions for '{current_keyword}' at depth {current_depth}: {str(e)}")
            continue # Skip adding subtopics for this errored keyword

    logger.info(f"Finished generating niche topics for '{seed_keyword}'.")
    return topic_tree


# --- HTTP Request Handler ---

class Handler(http.server.SimpleHTTPRequestHandler):
    """Handles incoming HTTP GET requests."""

    def _send_response(self, status_code, content_type, response_body):
        """Helper to send standardized JSON responses."""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        # Consider adding CORS headers if accessed from a different domain browser
        # self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        if isinstance(response_body, (dict, list)):
            response_bytes = json.dumps(response_body, default=str).encode('utf-8') # Use default=str for non-serializable types like datetime
        elif isinstance(response_body, str):
            response_bytes = response_body.encode('utf-8')
        else:
             response_bytes = str(response_body).encode('utf-8')
        self.wfile.write(response_bytes)

    def _send_error_response(self, status_code, message, error_details=None):
        """Helper to send standardized JSON error responses."""
        error_body = {"status": "error", "message": message}
        if error_details:
             if isinstance(error_details, Exception):
                 error_body["details"] = f"{type(error_details).__name__}: {str(error_details)}"
             else:
                 error_body["details"] = str(error_details)
        logger.error(f"Sending error response {status_code}: {message} {error_body.get('details', '')}")
        self._send_response(status_code, 'application/json', error_body)

    def do_GET(self):
        """Handle GET requests."""
        start_time = time.time()
        # Parse the URL
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_string = parsed_url.query
        query_params = urllib.parse.parse_qs(query_string) # Returns dict with list values

        logger.info(f"Received GET request for path: {path} with params: {query_params}")

        # --- Health Check Endpoint (BEFORE Rate Limiter) ---
        if path == '/health' or path == '/':
            logger.info("Handling health check request.")
            health_response = {
                "status": "healthy",
                "time": datetime.now().isoformat(),
                "version": "1.1", # Example version
                "rate_limit_status": {
                     "max_calls": rate_limiter.max_calls,
                     "time_frame_seconds": rate_limiter.time_frame,
                     "current_calls_in_window": len(rate_limiter.calls)
                }
                # List only key, stable endpoints here
                # "available_endpoints": [ "/health", "/search", "/autocomplete", "/trends/..." ]
            }
            self._send_response(200, 'application/json', health_response)
            duration = time.time() - start_time
            logger.info(f"Health check completed in {duration:.4f} seconds.")
            return # Exit early, do not apply rate limiting to health checks

        # --- Apply Rate Limiter for all other endpoints ---
        if not rate_limiter.is_allowed():
            self._send_error_response(429, "Too Many Requests")
            duration = time.time() - start_time
            logger.warning(f"Request denied due to rate limiting for {path}. Duration: {duration:.4f}s")
            return
        else:
            # Record the call only if it's allowed and not a health check
            rate_limiter.add_call()
            logger.debug(f"Rate limit check passed. Current calls: {len(rate_limiter.calls)}")


        # --- Route to specific handlers ---
        try:
            if path == '/search':
                self.handle_google_search(query_params)
            elif path == '/search/combined':
                self.handle_combined_search(query_params)
            elif path == '/niche-topics':
                self.handle_niche_topics(query_params)
            elif path == '/autocomplete':
                self.handle_autocomplete(query_params)
            elif path == '/trends': # Legacy/Simplified Trends Endpoint
                self.handle_trends_legacy(query_params) # Keep distinct from new ones
            elif path.startswith('/trends/'):
                self.handle_trends_endpoints(path, query_params)
            else:
                self._send_error_response(404, "Endpoint not found")

        except ImportError as e:
             # Handle missing dependencies specifically
             self._send_error_response(501, f"Feature unavailable due to missing dependency: {e}", e)
        except ValueError as e:
             # Handle bad requests / validation errors
             self._send_error_response(400, f"Bad Request: {e}", e)
        except Exception as e:
            # Catch-all for unexpected server errors
            logger.error(f"Unhandled exception processing request for {path}: {str(e)}", exc_info=True)
            self._send_error_response(500, "Internal Server Error", e)
        finally:
            duration = time.time() - start_time
            logger.info(f"Request for {path} processed in {duration:.4f} seconds.")


    # --- Endpoint Handlers ---

    def handle_autocomplete(self, query):
        """Handle /autocomplete endpoint."""
        logger.info("Handling autocomplete request...")
        keyword = query.get('keyword', [''])[0]
        num = int(query.get('num', ['10'])[0])
        language = query.get('language', ['en'])[0]
        region = query.get('region', ['us'])[0]

        if not keyword:
            raise ValueError("Required parameter 'keyword' is missing.")

        suggestions = get_google_suggestions(keyword, num, language, region)
        response_body = {
            "keyword": keyword, "language": language, "region": region,
            "num_requested": num, "num_returned": len(suggestions),
            "suggestions": suggestions
        }
        self._send_response(200, 'application/json', response_body)

    def handle_google_search(self, query):
        """Handle /search endpoint."""
        logger.info("Handling Google search request...")
        search_query = query.get('q', [''])[0]
        num_results = int(query.get('num', ['10'])[0])
        lang = query.get('lang', ['en'])[0]
        advanced = query.get('advanced', ['false'])[0].lower() == 'true'
        sleep_interval = int(query.get('sleep', ['0'])[0]) # Use with caution
        timeout = int(query.get('timeout', ['5'])[0])

        if not search_query:
            raise ValueError("Required parameter 'q' (search query) is missing.")

        # Call the core search function (handles its own errors/imports)
        result = google_search(
            query=search_query, num_results=num_results, lang=lang,
            advanced=advanced, sleep_interval=sleep_interval, timeout=timeout
        )
        self._send_response(200, 'application/json', result)


    def handle_combined_search(self, query):
        """Handle /search/combined endpoint."""
        logger.info("Handling combined search and analysis request...")
        search_query = query.get('q', [''])[0]
        num_results = int(query.get('num', ['10'])[0])
        include_trends = query.get('include_trends', ['false'])[0].lower() == 'true'
        lang = query.get('lang', ['en'])[0]

        if not search_query:
            raise ValueError("Required parameter 'q' (search query) is missing.")

        result = search_and_analyze(
            query=search_query, num_results=num_results,
            include_trends=include_trends, lang=lang
        )
        self._send_response(200, 'application/json', result)


    def handle_niche_topics(self, query):
        """Handle /niche-topics endpoint."""
        logger.info("Handling niche topics request...")
        seed_keyword = query.get('keyword', [''])[0]
        depth = int(query.get('depth', ['2'])[0])
        results_per_level = int(query.get('results_per_level', ['5'])[0])
        lang = query.get('lang', ['en'])[0]
        country = query.get('country', ['us'])[0]

        if not seed_keyword:
            raise ValueError("Required parameter 'keyword' is missing.")

        # Validate parameters (optional, function also does it)
        depth = max(1, min(depth, 3))
        results_per_level = max(1, min(results_per_level, 10))

        topic_tree = get_niche_topics(
            seed_keyword=seed_keyword, depth=depth,
            results_per_level=results_per_level, lang=lang, country=country
        )
        response = {
            "seed_keyword": seed_keyword, "depth": depth, "results_per_level": results_per_level,
            "lang": lang, "country": country, "topic_tree": topic_tree
        }
        self._send_response(200, 'application/json', response)


    def handle_trends_legacy(self, query):
        """Handle /trends (legacy) endpoint - maps to interest_over_time or related_queries."""
        logger.warning("Handling legacy /trends request. Consider using specific /trends/* endpoints.")
        keywords = query.get('keywords', ['bitcoin'])[0].split(',')
        timeframe = query.get('timeframe', ['today 3-m'])[0]
        query_type = query.get('query_type', ['interest_over_time'])[0].lower()
        geo = query.get('geo', [''])[0]
        hl = query.get('hl', ['en-US'])[0]
        tz = int(query.get('tz', ['360'])[0])
        cat = int(query.get('cat', ['0'])[0])

        if not keywords:
            raise ValueError("Required parameter 'keywords' is missing.")

        try:
            from pytrends.request import TrendReq
            import pandas as pd
        except ImportError as e:
            raise ImportError(f"pytrends or pandas not installed. Cannot use legacy /trends.")

        pytrends = TrendReq(hl=hl, tz=tz, timeout=(10, 25), retries=2, backoff_factor=0.5)
        pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)

        data = {}
        if query_type == 'interest_over_time':
            df = pytrends.interest_over_time()
            data = df.reset_index().to_dict('records') if not df.empty else []
        elif query_type == 'related_queries':
            raw_data = pytrends.related_queries()
            data = {}
            for kw in keywords:
                 if kw in raw_data and raw_data[kw]:
                     data[kw] = {
                         "top": raw_data[kw].get("top").to_dict('records') if raw_data[kw].get("top") is not None else [],
                         "rising": raw_data[kw].get("rising").to_dict('records') if raw_data[kw].get("rising") is not None else []
                     }
                 else:
                     data[kw] = {"top": [], "rising": []}
        elif query_type == 'interest_by_region':
             resolution = query.get('resolution', ['COUNTRY'])[0]
             df = pytrends.interest_by_region(resolution=resolution)
             data = df.reset_index().to_dict('records') if not df.empty else []
        else:
            raise ValueError(f"Unsupported legacy 'query_type': {query_type}. Supported: interest_over_time, related_queries, interest_by_region.")

        response_body = {
            "keywords": keywords, "timeframe": timeframe, "geo": geo,
            "query_type": query_type, "data": data, "note": "Legacy endpoint"
        }
        self._send_response(200, 'application/json', response_body)


    def handle_trends_endpoints(self, path, query):
        """Router for specific /trends/* endpoints."""
        endpoint = path[len('/trends/'):] # Get part after /trends/
        logger.info(f"Handling trends endpoint: {endpoint}")

        # Centralized parameter extraction
        keywords = query.get('keywords', [''])[0].split(',') if query.get('keywords') else []
        timeframe = query.get('timeframe', ['today 3-m'])[0]
        geo = query.get('geo', [''])[0]
        hl = query.get('hl', ['en-US'])[0]
        tz = int(query.get('tz', ['360'])[0])
        cat = int(query.get('cat', ['0'])[0])
        pn = query.get('pn', ['US'])[0]       # For country-specific trends
        date = query.get('date', [str(datetime.now().year - 1)])[0] # For top charts, default last year

         # Import dependencies here for all trends functions
        try:
            from pytrends.request import TrendReq
            import pandas as pd
        except ImportError as e:
            raise ImportError(f"pytrends or pandas not installed. Cannot use /trends/ endpoints.")

        # Initialize PyTrends (can be reused)
        # Add custom user agent header - sometimes helps avoid blocking
        custom_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        pytrends = TrendReq(hl=hl, tz=tz, timeout=(10, 25), retries=2, backoff_factor=0.5, requests_args={'headers': custom_headers})

        result = {}
        response_meta = {"hl": hl, "tz": tz} # Basic metadata for response


        # --- Route based on specific endpoint ---
        if endpoint == 'interest-over-time':
            if not keywords or keywords == ['']: raise ValueError("Parameter 'keywords' is required.")
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            df = pytrends.interest_over_time()
            result = df.reset_index().to_dict('records') if not df.empty else []
            response_meta.update({"keywords": keywords, "timeframe": timeframe, "geo": geo, "cat": cat})

        elif endpoint == 'interest-by-region':
             if not keywords or keywords == ['']: raise ValueError("Parameter 'keywords' is required.")
             resolution = query.get('resolution', ['COUNTRY'])[0].upper()
             if resolution not in ['COUNTRY', 'REGION', 'CITY', 'DMA']: raise ValueError("Invalid 'resolution'. Use COUNTRY, REGION, CITY, or DMA.")
             inc_low_vol = query.get('inc_low_vol', ['true'])[0].lower() == 'true'
             inc_geo_code = query.get('inc_geo_code', ['false'])[0].lower() == 'true'
             pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
             df = pytrends.interest_by_region(resolution=resolution, inc_low_vol=inc_low_vol, inc_geo_code=inc_geo_code)
             result = df.reset_index().to_dict('records') if not df.empty else []
             response_meta.update({"keywords": keywords, "timeframe": timeframe, "geo": geo, "cat": cat, "resolution": resolution})

        elif endpoint == 'related-topics':
            if not keywords or keywords == ['']: raise ValueError("Parameter 'keywords' is required.")
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            raw_data = pytrends.related_topics()
            result = {}
            for kw in keywords:
                 if kw in raw_data and raw_data[kw]:
                     result[kw] = {
                         "top": raw_data[kw].get("top").to_dict('records') if raw_data[kw].get("top") is not None else [],
                         "rising": raw_data[kw].get("rising").to_dict('records') if raw_data[kw].get("rising") is not None else []
                     }
                 else:
                     result[kw] = {"top": [], "rising": []}
            response_meta.update({"keywords": keywords, "timeframe": timeframe, "geo": geo, "cat": cat})

        elif endpoint == 'related-queries':
            if not keywords or keywords == ['']: raise ValueError("Parameter 'keywords' is required.")
            pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
            raw_data = pytrends.related_queries()
            result = {}
            for kw in keywords:
                 if kw in raw_data and raw_data[kw]:
                     result[kw] = {
                         "top": raw_data[kw].get("top").to_dict('records') if raw_data[kw].get("top") is not None else [],
                         "rising": raw_data[kw].get("rising").to_dict('records') if raw_data[kw].get("rising") is not None else []
                     }
                 else:
                     result[kw] = {"top": [], "rising": []}
            response_meta.update({"keywords": keywords, "timeframe": timeframe, "geo": geo, "cat": cat})

        elif endpoint == 'trending-searches':
            # Use the dedicated function which handles country normalization
            result_data = get_trending_searches(pn=pn, hl=hl, tz=tz) # Catches errors internally
            result = result_data['data']
            response_meta.update({"pn_requested": pn, "pn_used": result_data['pn_used']})

        elif endpoint == 'realtime-trending-searches':
            cat_realtime = query.get('cat', ['all'])[0]
            # Use the dedicated function which handles country normalization and fallback
            result_data = get_realtime_trending_searches(pn=pn, hl=hl, tz=tz, cat=cat_realtime) # Catches errors internally
            result = result_data['data']
            response_meta.update({"pn_requested": pn, "pn_used": result_data['pn_used'], "cat": cat_realtime})

        elif endpoint == 'top-charts':
            try:
                date_int = int(date)
            except ValueError:
                 raise ValueError("Parameter 'date' must be a valid year (integer).")
            df = pytrends.top_charts(date_int, hl=hl, tz=tz, geo=geo)
            result = df.to_dict('records') if not df.empty else []
            response_meta.update({"year": date_int, "geo": geo})

        elif endpoint == 'suggestions':
            keyword = query.get('keyword', [''])[0]
            if not keyword: raise ValueError("Parameter 'keyword' is required.")
            suggestions_list = pytrends.suggestions(keyword=keyword)
            # Format suggestions to be consistent with get_google_suggestions
            result = [{"title": sugg['title'], "type": sugg['type']} for sugg in suggestions_list]
            response_meta.update({"keyword": keyword})

        elif endpoint == 'categories':
            categories_dict = pytrends.categories()
            result = categories_dict # Already a dictionary
            response_meta.update({}) # No specific params other than hl/tz

        # elif endpoint == 'historical-hourly-interest': # Requires careful date handling
        #     # ... implementation needed, parsing year/month/day start/end ...
        #     raise NotImplementedError("Endpoint '/trends/historical-hourly-interest' not fully implemented yet.")

        # elif endpoint == 'multirange-interest-over-time': # Requires multiple calls
        #     # ... implementation needed, parsing timeframes ...
        #     raise NotImplementedError("Endpoint '/trends/multirange-interest-over-time' not fully implemented yet.")

        else:
            raise ValueError(f"Unknown /trends/ endpoint: {endpoint}")


        # Send successful response
        response_body = {
            "endpoint": f"/trends/{endpoint}",
            "metadata": response_meta,
            "data": result,
            "status": "success"
        }
        self._send_response(200, 'application/json', response_body)

# --- Server Startup and Shutdown ---

# Global variable to hold the server instance for shutdown
httpd = None

def shutdown_server(signum, frame):
    """Gracefully shutdown the server."""
    logger.info(f"Received signal {signum}. Shutting down server...")
    if httpd:
        try:
            httpd.shutdown()  # Stop accepting new requests
            httpd.server_close() # Close the socket
            logger.info("Server successfully shut down.")
        except Exception as e:
             logger.error(f"Error during server shutdown: {e}", exc_info=True)
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_server)  # Handle Ctrl+C
    signal.signal(signal.SIGTERM, shutdown_server) # Handle kill/system shutdown

    logger.info(f"Starting HTTP server on 0.0.0.0:{PORT}")
    logger.info("Available core endpoints:")
    logger.info(f"  GET /health                       - Server status (bypasses rate limit)")
    logger.info(f"  GET /search?q=...               - Google Search results")
    logger.info(f"  GET /autocomplete?keyword=...     - Google Autocomplete suggestions")
    logger.info(f"  GET /search/combined?q=...      - Search + Trend Analysis")
    logger.info(f"  GET /niche-topics?keyword=...   - Explore related topics")
    logger.info("Available /trends/ endpoints (use pytrends):")
    logger.info(f"  GET /trends/interest-over-time?keywords=...")
    logger.info(f"  GET /trends/interest-by-region?keywords=...")
    logger.info(f"  GET /trends/related-topics?keywords=...")
    logger.info(f"  GET /trends/related-queries?keywords=...")
    logger.info(f"  GET /trends/trending-searches?pn=...")
    logger.info(f"  GET /trends/realtime-trending-searches?pn=...")
    logger.info(f"  GET /trends/top-charts?date=YYYY&geo=...")
    logger.info(f"  GET /trends/suggestions?keyword=...")
    logger.info(f"  GET /trends/categories")
    logger.info(f"Rate limit: {MAX_CALLS_PER_MINUTE} calls per {RATE_LIMIT_TIMEFRAME} seconds (excluding /health)")

    try:
        # Allow address reuse immediately after server stops
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
        logger.info(f"Server listening on 0.0.0.0:{PORT}. Press Ctrl+C to stop.")
        httpd.serve_forever()
    except OSError as e:
        logger.error(f"Could not bind to port {PORT}: {e}. Is the port already in use?")
    except Exception as e:
        logger.error(f"Critical error starting or running server: {e}", exc_info=True)
    finally:
        if httpd:
            httpd.server_close() # Ensure socket is closed on unexpected exit
            logger.info("Server socket closed.")
