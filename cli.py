#!/usr/bin/env python
import sys
import json
import os
import argparse
import re
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Validation patterns
COUNTRY_CODE_PATTERN = re.compile(r'^[A-Z]{2}(-[A-Z]{2,3})?$')
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
TIMEFRAME_PATTERN = re.compile(r'^(today \d+-[ydm]|\d{4}-\d{2}-\d{2} \d{4}-\d{2}-\d{2}|all)$')

# =============== UTILITY FUNCTIONS ===============

def validate_geo(geo):
    """Validate the geo parameter"""
    if not geo:  # Empty is valid (global)
        return True
    
    return bool(COUNTRY_CODE_PATTERN.match(geo))

def validate_timeframe(timeframe):
    """Validate the timeframe parameter"""
    # Check for common formats like 'today 3-m', '2022-01-01 2022-02-01', etc.
    if TIMEFRAME_PATTERN.match(timeframe):
        return True
    
    # Check for date ranges
    if ' ' in timeframe:
        start_date, end_date = timeframe.split(' ')
        return bool(DATE_PATTERN.match(start_date) and DATE_PATTERN.match(end_date))
    
    return False

def validate_date(year, month, day):
    """Validate a date for correctness"""
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False

# =============== PYTRENDS FUNCTIONS ===============

def get_interest_over_time(keywords, timeframe, geo='', hl='en-US', tz=360, cat=0):
    """Get interest over time for keywords"""
    logger.info(f"Getting interest over time for: {keywords}")
    
    # Validate parameters
    if not keywords:
        raise ValueError("At least one keyword is required")
    
    if len(keywords) > 5:
        raise ValueError("Maximum 5 keywords are allowed")
    
    if not validate_timeframe(timeframe):
        raise ValueError("Invalid timeframe format. Use formats like 'today 3-m' or 'YYYY-MM-DD YYYY-MM-DD'")
    
    if geo and not validate_geo(geo):
        raise ValueError("Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
    
    # Get the data
    df = pytrends.interest_over_time()
    
    if df.empty:
        return {"error": "No data found", "keywords": keywords}
    
    # Convert DataFrame to dictionary
    result = df.reset_index().to_dict(orient='records')
    return {
        "keywords": keywords,
        "timeframe": timeframe,
        "geo": geo,
        "data": result
    }

def get_multirange_interest_over_time(keywords, timeframes, geo='', hl='en-US', tz=360, cat=0):
    """Get multirange interest over time for keywords"""
    logger.info(f"Getting multirange interest for: {keywords} across {len(timeframes)} timeframes")
    
    # Validate parameters
    if not keywords:
        raise ValueError("At least one keyword is required")
    
    if len(keywords) > 5:
        raise ValueError("Maximum 5 keywords are allowed")
    
    for tf in timeframes:
        if not validate_timeframe(tf):
            raise ValueError(f"Invalid timeframe format: {tf}. Use formats like 'YYYY-MM-DD YYYY-MM-DD'")
    
    if geo and not validate_geo(geo):
        raise ValueError("Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    
    # For multirange_interest_over_time we don't use build_payload
    # Get the data
    df = pytrends.multirange_interest_over_time(keywords, cat=cat, timeframe=timeframes, geo=geo)
    
    if df.empty:
        return {"error": "No data found", "keywords": keywords}
    
    # Convert DataFrame to dictionary
    result = df.reset_index().to_dict(orient='records')
    return {
        "keywords": keywords,
        "timeframes": timeframes,
        "geo": geo,
        "data": result
    }

def get_historical_hourly_interest(keywords, year_start, month_start, day_start, hour_start,
                                  year_end, month_end, day_end, hour_end, geo='', 
                                  hl='en-US', tz=360, cat=0, sleep=0):
    """Get historical hourly interest for keywords"""
    logger.info(f"Getting historical hourly interest for: {keywords}")
    
    # Validate parameters
    if not keywords:
        raise ValueError("At least one keyword is required")
    
    if len(keywords) > 5:
        raise ValueError("Maximum 5 keywords are allowed")
    
    # Basic date validation
    if not validate_date(year_start, month_start, day_start) or not validate_date(year_end, month_end, day_end):
        raise ValueError("Invalid date parameters")
    
    if hour_start < 0 or hour_start > 23 or hour_end < 0 or hour_end > 23:
        raise ValueError("Hours must be between 0 and 23")
    
    # Validate date range
    start_date = datetime(year_start, month_start, day_start, hour_start)
    end_date = datetime(year_end, month_end, day_end, hour_end)
    
    if end_date <= start_date:
        raise ValueError("End date must be after start date")
        
    if (end_date - start_date).days > 7:
        raise ValueError("Date range is limited to 7 days for hourly data")
    
    if geo and not validate_geo(geo):
        raise ValueError("Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    
    # Get the data
    df = pytrends.get_historical_interest(
        keywords, 
        year_start=year_start, month_start=month_start, day_start=day_start, hour_start=hour_start,
        year_end=year_end, month_end=month_end, day_end=day_end, hour_end=hour_end,
        cat=cat, geo=geo, gprop='', sleep=sleep
    )
    
    if df.empty:
        return {"error": "No data found", "keywords": keywords}
    
    # Convert DataFrame to dictionary
    result = df.reset_index().to_dict(orient='records')
    return {
        "keywords": keywords,
        "start_date": f"{year_start}-{month_start}-{day_start} {hour_start}:00",
        "end_date": f"{year_end}-{month_end}-{day_end} {hour_end}:00",
        "geo": geo,
        "data": result
    }

def get_interest_by_region(keywords, timeframe, geo='', resolution='COUNTRY', 
                          inc_low_vol=True, inc_geo_code=False, hl='en-US', tz=360, cat=0):
    """Get interest by region for keywords"""
    logger.info(f"Getting interest by region for: {keywords} with resolution: {resolution}")
    
    # Validate parameters
    if not keywords:
        raise ValueError("At least one keyword is required")
    
    if len(keywords) > 5:
        raise ValueError("Maximum 5 keywords are allowed")
    
    if not validate_timeframe(timeframe):
        raise ValueError("Invalid timeframe format. Use formats like 'today 3-m' or 'YYYY-MM-DD YYYY-MM-DD'")
    
    if geo and not validate_geo(geo):
        raise ValueError("Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
    
    valid_resolutions = ['COUNTRY', 'REGION', 'CITY', 'DMA']
    if resolution not in valid_resolutions:
        raise ValueError(f"Invalid resolution. Must be one of: {', '.join(valid_resolutions)}")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
    
    # Get the data
    df = pytrends.interest_by_region(resolution=resolution, inc_low_vol=inc_low_vol, inc_geo_code=inc_geo_code)
    
    if df.empty:
        return {"error": "No data found", "keywords": keywords}
    
    # Convert DataFrame to dictionary
    result = df.reset_index().to_dict(orient='records')
    return {
        "keywords": keywords,
        "timeframe": timeframe,
        "geo": geo,
        "resolution": resolution,
        "data": result
    }

def get_related_topics(keywords, timeframe, geo='', hl='en-US', tz=360, cat=0):
    """Get related topics for keywords"""
    logger.info(f"Getting related topics for: {keywords}")
    
    # Validate parameters
    if not keywords:
        raise ValueError("At least one keyword is required")
    
    if len(keywords) > 5:
        raise ValueError("Maximum 5 keywords are allowed")
    
    if not validate_timeframe(timeframe):
        raise ValueError("Invalid timeframe format. Use formats like 'today 3-m' or 'YYYY-MM-DD YYYY-MM-DD'")
    
    if geo and not validate_geo(geo):
        raise ValueError("Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
    
    # Get the data
    related = pytrends.related_topics()
    
    result = {}
    for kw in keywords:
        if kw in related and related[kw]:
            result[kw] = {
                "top": related[kw]["top"].to_dict(orient='records') if related[kw]["top"] is not None else [],
                "rising": related[kw]["rising"].to_dict(orient='records') if related[kw]["rising"] is not None else []
            }
    
    return {
        "keywords": keywords,
        "timeframe": timeframe,
        "geo": geo,
        "data": result
    }

def get_related_queries(keywords, timeframe, geo='', hl='en-US', tz=360, cat=0):
    """Get related queries for keywords"""
    logger.info(f"Getting related queries for: {keywords}")
    
    # Validate parameters
    if not keywords:
        raise ValueError("At least one keyword is required")
    
    if len(keywords) > 5:
        raise ValueError("Maximum 5 keywords are allowed")
    
    if not validate_timeframe(timeframe):
        raise ValueError("Invalid timeframe format. Use formats like 'today 3-m' or 'YYYY-MM-DD YYYY-MM-DD'")
    
    if geo and not validate_geo(geo):
        raise ValueError("Invalid geo format. Use ISO country codes like 'US' or 'US-NY'")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    pytrends.build_payload(keywords, cat=cat, timeframe=timeframe, geo=geo)
    
    # Get the data
    related = pytrends.related_queries()
    
    result = {}
    for kw in keywords:
        if kw in related and related[kw]:
            result[kw] = {
                "top": related[kw]["top"].to_dict(orient='records') if related[kw]["top"] is not None else [],
                "rising": related[kw]["rising"].to_dict(orient='records') if related[kw]["rising"] is not None else []
            }
    
    return {
        "keywords": keywords,
        "timeframe": timeframe,
        "geo": geo,
        "data": result
    }

def get_trending_searches(pn='united_states', hl='en-US', tz=360):
    """Get trending searches for a given country"""
    logger.info(f"Getting trending searches for country: {pn}")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    
    # Get the data
    try:
        df = pytrends.trending_searches(pn=pn)
    except Exception as e:
        raise ValueError(f"Failed to get trending searches for {pn}: {str(e)}")
    
    if df.empty:
        return {"error": "No data found", "pn": pn}
    
    # Convert results to a simpler format
    simple_results = []
    for item in df.to_dict(orient='records'):
        if not isinstance(item, dict):
            simple_results.append({"query": str(item)})
        else:
            simple_results.append(item)
    
    # If simple_results is empty but we have data, fall back to original format
    if not simple_results and not df.empty:
        try:
            # For pandas Series format
            result = df.to_list()
            return {
                "pn": pn,
                "data": [{"query": str(item)} for item in result]
            }
        except:
            # Last resort
            return {
                "pn": pn,
                "data": [{"query": str(item)} for item in df.values.tolist()[0]]
            }
    
    return {
        "pn": pn,
        "data": simple_results
    }

def get_realtime_trending_searches(pn='US', hl='en-US', tz=360, cat="all"):
    """Get realtime trending searches for a given country"""
    logger.info(f"Getting realtime trending searches for country: {pn}")
    
    # Validate parameters
    if not validate_geo(pn):
        raise ValueError("Invalid country code format for pn. Use ISO country codes like 'US'")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    
    # Get the data
    try:
        df = pytrends.realtime_trending_searches(pn=pn, cat=cat)
    except Exception as e:
        raise ValueError(f"Failed to get realtime trending searches for {pn}: {str(e)}")
    
    if df.empty:
        return {"error": "No data found", "pn": pn}
    
    # Convert DataFrame to dictionary
    try:
        result = df.to_dict(orient='records')
    except Exception as e:
        # Fallback if standard conversion fails
        logger.warning(f"Standard conversion failed, using fallback: {str(e)}")
        result = {"raw_data": str(df)}
    
    return {
        "pn": pn,
        "cat": cat,
        "data": result
    }

def get_top_charts(date, geo='GLOBAL', hl='en-US', tz=360):
    """Get top charts for a given date and region"""
    logger.info(f"Getting top charts for year: {date} and region: {geo}")
    
    # Validate parameters
    current_year = datetime.now().year
    if not isinstance(date, int) or date < 2001 or date >= current_year:
        raise ValueError(f"Date must be an integer year between 2001 and {current_year-1}")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    
    # Get the data
    try:
        df = pytrends.top_charts(date, geo=geo)
    except Exception as e:
        raise ValueError(f"Failed to get top charts for {date}: {str(e)}")
    
    if df.empty:
        return {"error": "No data found", "date": date, "geo": geo}
    
    # Convert DataFrame to dictionary
    result = df.to_dict(orient='records')
    return {
        "date": date,
        "geo": geo,
        "data": result
    }

def get_suggestions(keyword, hl='en-US', tz=360):
    """Get keyword suggestions"""
    logger.info(f"Getting suggestions for keyword: {keyword}")
    
    # Validate parameters
    if not keyword:
        raise ValueError("Keyword cannot be empty")
    
    # Import dependencies
    from pytrends.request import TrendReq
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    
    # Get the data
    try:
        suggestions = pytrends.suggestions(keyword=keyword)
    except Exception as e:
        raise ValueError(f"Failed to get suggestions for {keyword}: {str(e)}")
    
    return {
        "keyword": keyword,
        "suggestions": suggestions
    }

def get_categories(hl='en-US', tz=360):
    """Get available categories"""
    logger.info("Getting available categories")
    
    # Import dependencies
    from pytrends.request import TrendReq
    
    # Initialize PyTrends
    pytrends = TrendReq(hl=hl, tz=tz)
    
    # Get the data
    try:
        categories = pytrends.categories()
    except Exception as e:
        raise ValueError(f"Failed to get categories: {str(e)}")
    
    return {
        "categories": categories
    }

# =============== UTILITY FUNCTIONS ===============

def save_to_file(data, file_path):
    """Save data to a file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Data saved to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving to file: {str(e)}")
        raise

# =============== MAIN FUNCTION ===============

def main():
    # Create main parser
    parser = argparse.ArgumentParser(
        description='Google Trends CLI Tool',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--output', '-o', type=str, default='./output', 
                        help='Output directory for saving results')
    
    # Create subparsers for main commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Original Google Trends command (compatibility)
    trends_parser = subparsers.add_parser('trends', help='Google Trends command (legacy)')
    trends_parser.add_argument('--keywords', '-k', type=str, required=True, 
                              help='Keywords (comma separated, max 5)')
    trends_parser.add_argument('--timeframe', '-t', type=str, default='today 3-m', 
                              help='Timeframe (e.g., "today 3-m", "2022-01-01 2022-02-01", "all")')
    trends_parser.add_argument('--query_type', '-q', type=str, default='interest_over_time', 
                              choices=['interest_over_time', 'interest_by_region', 'related_queries'],
                              help='Query type to perform')
    trends_parser.add_argument('--geo', '-g', type=str, default='', 
                              help='Geography (ISO country code, e.g., "US", "US-NY")')
    trends_parser.add_argument('--resolution', '-r', type=str, default='COUNTRY', 
                              choices=['COUNTRY', 'REGION', 'CITY', 'DMA'], 
                              help='Resolution for interest_by_region')
    trends_parser.add_argument('--hl', type=str, default='en-US', 
                              help='Host language for accessing Google Trends')
    trends_parser.add_argument('--tz', type=int, default=360, 
                              help='Timezone offset (in minutes)')
    trends_parser.add_argument('--cat', type=int, default=0, 
                              help='Category to narrow results')
    
    # Interest over time
    iot_parser = subparsers.add_parser('interest-over-time', 
                                      help='Get interest over time data for keywords')
    iot_parser.add_argument('--keywords', '-k', type=str, required=True, 
                          help='Keywords (comma separated, max 5)')
    iot_parser.add_argument('--timeframe', '-t', type=str, default='today 3-m', 
                          help='Timeframe (e.g., "today 3-m", "2022-01-01 2022-02-01", "all")')
    iot_parser.add_argument('--geo', '-g', type=str, default='', 
                          help='Geography (ISO country code, e.g., "US", "US-NY")')
    iot_parser.add_argument('--hl', type=str, default='en-US', 
                          help='Host language for accessing Google Trends')
    iot_parser.add_argument('--tz', type=int, default=360, 
                          help='Timezone offset (in minutes)')
    iot_parser.add_argument('--cat', type=int, default=0, 
                          help='Category to narrow results')
    
    # Multirange interest over time
    miot_parser = subparsers.add_parser('multirange-interest-over-time',
                                      help='Get interest over time data across multiple timeframes')
    miot_parser.add_argument('--keywords', '-k', type=str, required=True, 
                           help='Keywords (comma separated, max 5)')
    miot_parser.add_argument('--timeframes', '-t', type=str, required=True, 
                           help='Timeframes (pipe separated, e.g., "2022-01-01 2022-01-31|2022-03-01 2022-03-31")')
    miot_parser.add_argument('--geo', '-g', type=str, default='', 
                           help='Geography (ISO country code, e.g., "US", "US-NY")')
    miot_parser.add_argument('--hl', type=str, default='en-US', 
                           help='Host language for accessing Google Trends')
    miot_parser.add_argument('--tz', type=int, default=360, 
                           help='Timezone offset (in minutes)')
    miot_parser.add_argument('--cat', type=int, default=0, 
                           help='Category to narrow results')
    
    # Historical hourly interest
    hhi_parser = subparsers.add_parser('historical-hourly-interest',
                                     help='Get historical hourly interest data for keywords')
    hhi_parser.add_argument('--keywords', '-k', type=str, required=True, 
                          help='Keywords (comma separated, max 5)')
    hhi_parser.add_argument('--year-start', type=int, required=True, 
                          help='Start year (e.g., 2022)')
    hhi_parser.add_argument('--month-start', type=int, required=True, 
                          help='Start month (1-12)')
    hhi_parser.add_argument('--day-start', type=int, required=True, 
                          help='Start day (1-31)')
    hhi_parser.add_argument('--hour-start', type=int, default=0, 
                          help='Start hour (0-23)')
    hhi_parser.add_argument('--year-end', type=int, required=True, 
                          help='End year (e.g., 2022)')
    hhi_parser.add_argument('--month-end', type=int, required=True, 
                          help='End month (1-12)')
    hhi_parser.add_argument('--day-end', type=int, required=True, 
                          help='End day (1-31)')
    hhi_parser.add_argument('--hour-end', type=int, default=0, 
                          help='End hour (0-23)')
    hhi_parser.add_argument('--geo', '-g', type=str, default='', 
                          help='Geography (ISO country code, e.g., "US", "US-NY")')
    hhi_parser.add_argument('--sleep', type=int, default=0, 
                          help='Sleep time between requests (in seconds)')
    hhi_parser.add_argument('--hl', type=str, default='en-US', 
                          help='Host language for accessing Google Trends')
    hhi_parser.add_argument('--tz', type=int, default=360, 
                          help='Timezone offset (in minutes)')
    hhi_parser.add_argument('--cat', type=int, default=0, 
                          help='Category to narrow results')
    
    # Interest by region
    ibr_parser = subparsers.add_parser('interest-by-region',
                                     help='Get interest by region data for keywords')
    ibr_parser.add_argument('--keywords', '-k', type=str, required=True, 
                          help='Keywords (comma separated, max 5)')
    ibr_parser.add_argument('--timeframe', '-t', type=str, default='today 3-m', 
                          help='Timeframe (e.g., "today 3-m", "2022-01-01 2022-02-01", "all")')
    ibr_parser.add_argument('--geo', '-g', type=str, default='', 
                          help='Geography (ISO country code, e.g., "US", "US-NY")')
    ibr_parser.add_argument('--resolution', '-r', type=str, default='COUNTRY', 
                          choices=['COUNTRY', 'REGION', 'CITY', 'DMA'], 
                          help='Resolution of the data')
    ibr_parser.add_argument('--inc-low-vol', type=bool, default=True, 
                          help='Include low search volume regions')
    ibr_parser.add_argument('--inc-geo-code', type=bool, default=False, 
                          help='Include geographic codes in response')
    ibr_parser.add_argument('--hl', type=str, default='en-US', 
                          help='Host language for accessing Google Trends')
    ibr_parser.add_argument('--tz', type=int, default=360, 
                          help='Timezone offset (in minutes)')
    ibr_parser.add_argument('--cat', type=int, default=0, 
                          help='Category to narrow results')
    
    # Related topics
    rt_parser = subparsers.add_parser('related-topics',
                                    help='Get related topics for keywords')
    rt_parser.add_argument('--keywords', '-k', type=str, required=True, 
                         help='Keywords (comma separated, max 5)')
    rt_parser.add_argument('--timeframe', '-t', type=str, default='today 3-m', 
                         help='Timeframe (e.g., "today 3-m", "2022-01-01 2022-02-01", "all")')
    rt_parser.add_argument('--geo', '-g', type=str, default='', 
                         help='Geography (ISO country code, e.g., "US", "US-NY")')
    rt_parser.add_argument('--hl', type=str, default='en-US', 
                         help='Host language for accessing Google Trends')
    rt_parser.add_argument('--tz', type=int, default=360, 
                         help='Timezone offset (in minutes)')
    rt_parser.add_argument('--cat', type=int, default=0, 
                         help='Category to narrow results')
    
    # Related queries
    rq_parser = subparsers.add_parser('related-queries',
                                    help='Get related queries for keywords')
    rq_parser.add_argument('--keywords', '-k', type=str, required=True, 
                         help='Keywords (comma separated, max 5)')
    rq_parser.add_argument('--timeframe', '-t', type=str, default='today 3-m', 
                         help='Timeframe (e.g., "today 3-m", "2022-01-01 2022-02-01", "all")')
    rq_parser.add_argument('--geo', '-g', type=str, default='', 
                         help='Geography (ISO country code, e.g., "US", "US-NY")')
    rq_parser.add_argument('--hl', type=str, default='en-US', 
                         help='Host language for accessing Google Trends')
    rq_parser.add_argument('--tz', type=int, default=360, 
                         help='Timezone offset (in minutes)')
    rq_parser.add_argument('--cat', type=int, default=0, 
                         help='Category to narrow results')
    
    # Trending searches
    ts_parser = subparsers.add_parser('trending-searches',
                                    help='Get trending searches for a country')
    ts_parser.add_argument('--pn', type=str, default='united_states', 
                         help='Country name (e.g., "united_states", "japan")')
    ts_parser.add_argument('--hl', type=str, default='en-US', 
                         help='Host language for accessing Google Trends')
    ts_parser.add_argument('--tz', type=int, default=360, 
                         help='Timezone offset (in minutes)')
    
    # Realtime trending searches
    rts_parser = subparsers.add_parser('realtime-trending-searches',
                                     help='Get realtime trending searches for a country')
    rts_parser.add_argument('--pn', type=str, default='US', 
                          help='Country code (e.g., "US", "JP")')
    rts_parser.add_argument('--cat', type=str, default='all', 
                          help='Category (default is "all")')
    rts_parser.add_argument('--hl', type=str, default='en-US', 
                          help='Host language for accessing Google Trends')
    rts_parser.add_argument('--tz', type=int, default=360, 
                          help='Timezone offset (in minutes)')
    
    # Top charts
    tc_parser = subparsers.add_parser('top-charts',
                                    help='Get top charts for a year')
    tc_parser.add_argument('--date', type=int, required=True, 
                         help='Year (e.g., 2021)')
    tc_parser.add_argument('--geo', type=str, default='GLOBAL', 
                         help='Geography (e.g., "GLOBAL", "US")')
    tc_parser.add_argument('--hl', type=str, default='en-US', 
                         help='Host language for accessing Google Trends')
    tc_parser.add_argument('--tz', type=int, default=360, 
                         help='Timezone offset (in minutes)')
    
    # Suggestions
    sg_parser = subparsers.add_parser('suggestions',
                                    help='Get keyword suggestions')
    sg_parser.add_argument('--keyword', '-k', type=str, required=True, 
                         help='Keyword to get suggestions for')
    sg_parser.add_argument('--hl', type=str, default='en-US', 
                         help='Host language for accessing Google Trends')
    sg_parser.add_argument('--tz', type=int, default=360, 
                         help='Timezone offset (in minutes)')
    
    # Categories
    cat_parser = subparsers.add_parser('categories',
                                     help='Get available categories')
    cat_parser.add_argument('--hl', type=str, default='en-US', 
                          help='Host language for accessing Google Trends')
    cat_parser.add_argument('--tz', type=int, default=360, 
                          help='Timezone offset (in minutes)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # Handle legacy 'trends' command
        if args.command == 'trends':
            # Process keywords
            keywords = [k.strip() for k in args.keywords.split(',')]
            
            if args.query_type == 'interest_over_time':
                # Execute interest over time query
                result = get_interest_over_time(
                    keywords=keywords, 
                    timeframe=args.timeframe, 
                    geo=args.geo, 
                    hl=args.hl, 
                    tz=args.tz, 
                    cat=args.cat
                )
                file_path = f"{args.output}/interest_over_time_{timestamp}.json"
            
            elif args.query_type == 'interest_by_region':
                # Execute interest by region query
                result = get_interest_by_region(
                    keywords=keywords, 
                    timeframe=args.timeframe, 
                    geo=args.geo, 
                    resolution=args.resolution, 
                    hl=args.hl, 
                    tz=args.tz, 
                    cat=args.cat
                )
                file_path = f"{args.output}/interest_by_region_{timestamp}.json"
                
            elif args.query_type == 'related_queries':
                # Execute related queries query
                result = get_related_queries(
                    keywords=keywords, 
                    timeframe=args.timeframe, 
                    geo=args.geo, 
                    hl=args.hl, 
                    tz=args.tz, 
                    cat=args.cat
                )
                file_path = f"{args.output}/related_queries_{timestamp}.json"
                
            else:
                parser.error(f"Unsupported query type: {args.query_type}")
                
        # Handle newer explicit commands
        elif args.command == 'interest-over-time':
            # Process keywords
            keywords = [k.strip() for k in args.keywords.split(',')]
            
            # Execute interest over time query
            result = get_interest_over_time(
                keywords=keywords, 
                timeframe=args.timeframe, 
                geo=args.geo, 
                hl=args.hl, 
                tz=args.tz, 
                cat=args.cat
            )
            file_path = f"{args.output}/interest_over_time_{timestamp}.json"
            
        elif args.command == 'multirange-interest-over-time':
            # Process keywords and timeframes
            keywords = [k.strip() for k in args.keywords.split(',')]
            timeframes = [t.strip() for t in args.timeframes.split('|')]
            
            # Execute multirange interest over time query
            result = get_multirange_interest_over_time(
                keywords=keywords, 
                timeframes=timeframes, 
                geo=args.geo, 
                hl=args.hl, 
                tz=args.tz, 
                cat=args.cat
            )
            file_path = f"{args.output}/multirange_interest_over_time_{timestamp}.json"
            
        elif args.command == 'historical-hourly-interest':
            # Process keywords
            keywords = [k.strip() for k in args.keywords.split(',')]
            
            # Execute historical hourly interest query
            result = get_historical_hourly_interest(
                keywords=keywords, 
                year_start=args.year_start, 
                month_start=args.month_start, 
                day_start=args.day_start, 
                hour_start=args.hour_start, 
                year_end=args.year_end, 
                month_end=args.month_end, 
                day_end=args.day_end, 
                hour_end=args.hour_end, 
                geo=args.geo, 
                hl=args.hl, 
                tz=args.tz, 
                cat=args.cat, 
                sleep=args.sleep
            )
            file_path = f"{args.output}/historical_hourly_interest_{timestamp}.json"
            
        elif args.command == 'interest-by-region':
            # Process keywords
            keywords = [k.strip() for k in args.keywords.split(',')]
            
            # Execute interest by region query
            result = get_interest_by_region(
                keywords=keywords, 
                timeframe=args.timeframe, 
                geo=args.geo, 
                resolution=args.resolution, 
                inc_low_vol=args.inc_low_vol, 
                inc_geo_code=args.inc_geo_code, 
                hl=args.hl, 
                tz=args.tz, 
                cat=args.cat
            )
            file_path = f"{args.output}/interest_by_region_{timestamp}.json"
            
        elif args.command == 'related-topics':
            # Process keywords
            keywords = [k.strip() for k in args.keywords.split(',')]
            
            # Execute related topics query
            result = get_related_topics(
                keywords=keywords, 
                timeframe=args.timeframe, 
                geo=args.geo, 
                hl=args.hl, 
                tz=args.tz, 
                cat=args.cat
            )
            file_path = f"{args.output}/related_topics_{timestamp}.json"
            
        elif args.command == 'related-queries':
            # Process keywords
            keywords = [k.strip() for k in args.keywords.split(',')]
            
            # Execute related queries query
            result = get_related_queries(
                keywords=keywords, 
                timeframe=args.timeframe, 
                geo=args.geo, 
                hl=args.hl, 
                tz=args.tz, 
                cat=args.cat
            )
            file_path = f"{args.output}/related_queries_{timestamp}.json"
            
        elif args.command == 'trending-searches':
            # Execute trending searches query
            result = get_trending_searches(
                pn=args.pn, 
                hl=args.hl, 
                tz=args.tz
            )
            file_path = f"{args.output}/trending_searches_{args.pn}_{timestamp}.json"
            
        elif args.command == 'realtime-trending-searches':
            # Execute realtime trending searches query
            result = get_realtime_trending_searches(
                pn=args.pn,
                cat=args.cat, 
                hl=args.hl, 
                tz=args.tz
            )
            file_path = f"{args.output}/realtime_trending_searches_{args.pn}_{timestamp}.json"
            
        elif args.command == 'top-charts':
            # Execute top charts query
            result = get_top_charts(
                date=args.date, 
                geo=args.geo, 
                hl=args.hl, 
                tz=args.tz
            )
            file_path = f"{args.output}/top_charts_{args.date}_{args.geo}_{timestamp}.json"
            
        elif args.command == 'suggestions':
            # Execute suggestions query
            result = get_suggestions(
                keyword=args.keyword, 
                hl=args.hl, 
                tz=args.tz
            )
            file_path = f"{args.output}/suggestions_{args.keyword}_{timestamp}.json"
            
        elif args.command == 'categories':
            # Execute categories query
            result = get_categories(
                hl=args.hl, 
                tz=args.tz
            )
            file_path = f"{args.output}/categories_{timestamp}.json"
            
        else:
            parser.print_help()
            sys.exit(1)
            
        # Save the data to a file if we have a result and file path
        if 'result' in locals() and 'file_path' in locals():
            saved_file = save_to_file(result, file_path)
            print(f"Output saved to: {saved_file}")
        else:
            print("Error: No result or file path generated.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
