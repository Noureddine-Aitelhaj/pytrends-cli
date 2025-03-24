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

def get_realtime_trending_searches(pn='US', hl='en-US', tz=360, cat="all"):
    """Get realtime trending searches for a given country"""
    logger.info(f"Getting realtime trending searches for country: {pn}")
    
    # Import dependencies
    import logging
    from pytrends.request import TrendReq
    from pytrends import dailydata
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
    
    result = []
    try:
        # Attempt realtime API first
        df = pytrends.realtime_trending_searches(pn=pn)
        result = process_realtime_data(df)
        
        if not result:  # Fallback if empty response
            raise ValueError("Empty realtime data")
            
    except Exception as e:
        logger.warning(f"Realtime failed: {str(e)}, trying daily trends")
        # Fallback to daily trends
        try:
            df = dailydata.get_daily_trends(
                geo=pn,
                date=datetime.now().strftime('%Y%m%d'),
                hl=hl
            )
            result = process_daily_data(df)
        except Exception as inner_e:
            logger.error(f"Daily trends also failed: {str(inner_e)}")
            result = [{"note": "Could not retrieve trending searches"}]

    return {
        "pn": pn,
        "cat": cat,
        "data": result
    }

def process_realtime_data(df):
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

def process_daily_data(df):
    """Clean and format daily trends data"""
    if df is None or df.empty:
        return []
    try:
        return df[['title', 'traffic', 'related_queries']].to_dict('records')
    except:
        # Fallback if columns are different
        return df.to_dict('records')

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
