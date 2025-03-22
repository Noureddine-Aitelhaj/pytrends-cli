#!/usr/bin/env python
import sys
import json
import os
import argparse
import re
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Validation patterns
YOUTUBE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{11}$')
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

def validate_youtube_id(video_id):
    """Validate YouTube video ID format"""
    return bool(YOUTUBE_ID_PATTERN.match(video_id))

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
    pytrends.build_payload(keywords, cat=cat, timeframe=timeframes, geo=geo)
    
    # Get the data
    df = pytrends.multirange_interest_over_time()
    
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
    
    # Convert DataFrame to dictionary
    result = df.to_dict(orient='records')
    return {
        "pn": pn,
        "data": result
    }

def get_realtime_trending_searches(pn='US', hl='en-US', tz=360):
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
        df = pytrends.realtime_trending_searches(pn=pn)
    except Exception as e:
        raise ValueError(f"Failed to get realtime trending searches for {pn}: {str(e)}")
    
    if df.empty:
        return {"error": "No data found", "pn": pn}
    
    # Convert DataFrame to dictionary
    result = df.to_dict(orient='records')
    return {
        "pn": pn,
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

# =============== YOUTUBE TRANSCRIPT FUNCTIONS ===============

def extract_video_id(url_or_id):
    """Extract video ID from YouTube URL"""
    if "youtu.be" in url_or_id:
        return url_or_id.split("/")[-1].split("?")[0]
    elif "youtube.com" in url_or_id:
        if "v=" in url_or_id:
            video_id = url_or_id.split("v=")[1].split("&")[0]
            return video_id
    return url_or_id  # If it's already the ID

def get_transcript(video_id_or_url, languages=None, preserve_formatting=False, proxy_url=None, cookie_file=None):
    """Get transcript for a YouTube video"""
    logger.info(f"Getting transcript for video: {video_id_or_url}")
    
    # Extract video ID
    video_id = extract_video_id(video_id_or_url)
    
    # Validate video ID
    if not validate_youtube_id(video_id):
        raise ValueError(f"Invalid YouTube video ID format: {video_id}")
    
    # Import dependencies
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
        import requests
    except ImportError:
        raise ImportError("youtube-transcript-api is required. Install with: pip install youtube-transcript-api")
    
    # Setup custom request session if needed
    session = None
    if proxy_url or cookie_file:
        session = requests.Session()
        
        if proxy_url:
            logger.info(f"Using proxy URL: {proxy_url}")
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        
        if cookie_file and os.path.exists(cookie_file):
            logger.info(f"Using cookie file: {cookie_file}")
            # In a real implementation, we'd load cookies here
    
    try:
        # Get transcript
        if languages:
            # Convert comma-separated languages to list
            if isinstance(languages, str):
                lang_list = [lang.strip() for lang in languages.split(',')]
            else:
                lang_list = languages
                
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to get transcript in specified languages
            for lang in lang_list:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    transcript_data = transcript.fetch()
                    return {
                        "video_id": video_id,
                        "language": lang,
                        "transcript": transcript_data
                    }
                except NoTranscriptFound:
                    continue
                
            # If no specified language is found, use the default one
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id, preserve_formatting=preserve_formatting)
            return {
                "video_id": video_id,
                "language": "default",
                "transcript": transcript_data
            }
        else:
            # Get the default transcript
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id, preserve_formatting=preserve_formatting)
            return {
                "video_id": video_id,
                "language": "default", 
                "transcript": transcript_data
            }
            
    except TranscriptsDisabled:
        return {
            "video_id": video_id,
            "error": "Transcripts are disabled for this video"
        }
    except NoTranscriptFound:
        return {
            "video_id": video_id,
            "error": "No transcript found for this video"
        }
    except VideoUnavailable:
        return {
            "video_id": video_id,
            "error": "The video is unavailable"
        }
    except Exception as e:
        return {
            "video_id": video_id,
            "error": str(e)
        }

def get_transcript_as_text(video_id_or_url, languages=None, preserve_formatting=False):
    """Get transcript for a YouTube video as plain text"""
    logger.info(f"Getting transcript as text for video: {video_id_or_url}")
    
    result = get_transcript(video_id_or_url, languages, preserve_formatting)
    
    if "error" in result:
        return result
    
    # Import formatter
    try:
        from youtube_transcript_api.formatters import TextFormatter
    except ImportError:
        # Fall back to manual joining if formatter not available
        full_text = " ".join([item["text"] for item in result["transcript"]])
        result["full_text"] = full_text
        return result
    
    # Use formatter to get plaintext
    formatter = TextFormatter()
    full_text = formatter.format_transcript(result["transcript"])
    
    result["full_text"] = full_text
    return result

def get_transcript_as_json(video_id_or_url, languages=None, preserve_formatting=False):
    """Get transcript for a YouTube video as formatted JSON"""
    logger.info(f"Getting transcript as JSON for video: {video_id_or_url}")
    
    result = get_transcript(video_id_or_url, languages, preserve_formatting)
    
    if "error" in result:
        return result
    
    # Import formatter
    try:
        from youtube_transcript_api.formatters import JSONFormatter
    except ImportError:
        # Return raw transcript if formatter not available
        return result
    
    # Use formatter to get JSON
    formatter = JSONFormatter()
    json_formatted = formatter.format_transcript(result["transcript"])
    
    result["json_formatted"] = json_formatted
    return result

def list_available_transcripts(video_id_or_url):
    """List available transcripts for a YouTube video"""
    logger.info(f"Listing available transcripts for video: {video_id_or_url}")
    
    # Extract video ID
    video_id = extract_video_id(video_id_or_url)
    
    # Validate video ID
    if not validate_youtube_id(video_id):
        raise ValueError(f"Invalid YouTube video ID format: {video_id}")
    
    # Import dependencies
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, VideoUnavailable
    except ImportError:
        raise ImportError("youtube-transcript-api is required. Install with: pip install youtube-transcript-api")
    
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
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
        
        return {
            "video_id": video_id,
            "available_transcripts": available_transcripts
        }
        
    except TranscriptsDisabled:
        return {
            "video_id": video_id,
            "error": "Transcripts are disabled for this video"
        }
    except VideoUnavailable:
        return {
            "video_id": video_id,
            "error": "The video is unavailable"
        }
    except Exception as e:
        return {
            "video_id": video_id,
            "error": str(e)
        }

def translate_transcript(video_id_or_url, source_lang, target_lang):
    """Translate a transcript from one language to another"""
    logger.info(f"Translating transcript for video: {video_id_or_url} from {source_lang} to {target_lang}")
    
    # Extract video ID
    video_id = extract_video_id(video_id_or_url)
    
    # Validate video ID
    if not validate_youtube_id(video_id):
        raise ValueError(f"Invalid YouTube video ID format: {video_id}")
    
    if not target_lang:
        raise ValueError("Target language is required")
    
    # Import dependencies
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled, 
            NoTranscriptFound, 
            VideoUnavailable,
            TranslationLanguageNotAvailable
        )
    except ImportError:
        raise ImportError("youtube-transcript-api is required. Install with: pip install youtube-transcript-api")
    
    try:
        # List all available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Get transcript in source language
        transcript = transcript_list.find_transcript([source_lang])
        
        # Translate the transcript
        translated_transcript = transcript.translate(target_lang)
        transcript_data = translated_transcript.fetch()
        
        return {
            "video_id": video_id,
            "source_language": source_lang,
            "target_language": target_lang,
            "transcript": transcript_data
        }
        
    except TranscriptsDisabled:
        return {
            "video_id": video_id,
            "error": "Transcripts are disabled for this video"
        }
    except NoTranscriptFound:
        return {
            "video_id": video_id,
            "error": f"No transcript found in language: {source_lang}"
        }
    except VideoUnavailable:
        return {
            "video_id": video_id,
            "error": "The video is unavailable"
        }
    except TranslationLanguageNotAvailable:
        return {
            "video_id": video_id,
            "error": f"Translation to {target_lang} is not available"
        }
    except Exception as e:
        return {
            "video_id": video_id,
            "error": str(e)
        }

# =============== MAIN FUNCTION ===============

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

def main():
    # Create main parser
    parser = argparse.ArgumentParser(
        description='Google Trends and YouTube Transcript CLI Tool',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--output', '-o', type=str, default='./output', 
                        help='Output directory for saving results')
    
    # Create subparsers for main commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # =============== TRENDS COMMANDS ===============
    
    # Trends parser
    trends_parser = subparsers.add_parser('trends', help='Google Trends commands')
    trends_subparsers = trends_parser.add_subparsers(dest='trends_command', help='Trends command type')
    
    # Interest over time
    iot_parser = trends_subparsers.add_parser('interest-over-time', 
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
    miot_parser = trends_subparsers.add_parser('multirange-interest-over-time',
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
    hhi_parser = trends_subparsers.add_parser('historical-hourly-interest',
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
    ibr_parser = trends_subparsers.add_parser('interest-by-region',
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
    rt_parser = trends_subparsers.add_parser('related-topics',
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
    rq_parser = trends_subparsers.add_parser('related-queries',
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
    ts_parser = trends_subparsers.add_parser('trending-searches',
                                           help='Get trending searches for a country')
    ts_parser.add_argument('--pn', type=str, default='united_states', 
                         help='Country name (e.g., "united_states", "japan")')
    ts_parser.add_argument('--hl', type=str, default='en-US', 
                         help='Host language for accessing Google Trends')
    ts_parser.add_argument('--tz', type=int, default=360, 
                         help='Timezone offset (in minutes)')
    
    # Realtime trending searches
    rts_parser = trends_subparsers.add_parser('realtime-trending-searches',
                                            help='Get realtime trending searches for a country')
    rts_parser.add_argument('--pn', type=str, default='US', 
                          help='Country code (e.g., "US", "JP")')
    rts_parser.add_argument('--hl', type=str, default='en-US', 
                          help='Host language for accessing Google Trends')
    rts_parser.add_argument('--tz', type=int, default=360, 
                          help='Timezone offset (in minutes)')
    
    # Top charts
    tc_parser = trends_subparsers.add_parser('top-charts',
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
    sg_parser = trends_subparsers.add_parser('suggestions',
                                           help='Get keyword suggestions')
    sg_parser.add_argument('--keyword', '-k', type=str, required=True, 
                         help='Keyword to get suggestions for')
    sg_parser.add_argument('--hl', type=str, default='en-US', 
                         help='Host language for accessing Google Trends')
    sg_parser.add_argument('--tz', type=int, default=360, 
                         help='Timezone offset (in minutes)')
    
    # Categories
    cat_parser = trends_subparsers.add_parser('categories',
                                            help='Get available categories')
    cat_parser.add_argument('--hl', type=str, default='en-US', 
                          help='Host language for accessing Google Trends')
    cat_parser.add_argument('--tz', type=int, default=360, 
                          help='Timezone offset (in minutes)')
    
    # =============== YOUTUBE COMMANDS ===============
    
    # YouTube parser
    yt_parser = subparsers.add_parser('youtube', help='YouTube transcript commands')
    yt_subparsers = yt_parser.add_subparsers(dest='youtube_command', help='YouTube command type')
    
    # Get transcript
    transcript_parser = yt_subparsers.add_parser('transcript',
                                               help='Get video transcript')
    transcript_parser.add_argument('--video', '-v', type=str, required=True, 
                                 help='YouTube Video ID or URL')
    transcript_parser.add_argument('--languages', '-l', type=str, 
                                 help='Preferred languages (comma separated)')
    transcript_parser.add_argument('--format', '-f', type=str, default='json', 
                                 choices=['json', 'text'], 
                                 help='Output format')
    transcript_parser.add_argument('--preserve-formatting', action='store_true', 
                                 help='Preserve HTML formatting in transcript')
    transcript_parser.add_argument('--proxy-url', type=str, 
                                 help='Proxy URL to use for requests')
    transcript_parser.add_argument('--cookie-file', type=str, 
                                 help='Path to cookies.txt file for authentication')
    
    # List available transcripts
    list_parser = yt_subparsers.add_parser('list',
                                         help='List available transcripts')
    list_parser.add_argument('--video', '-v', type=str, required=True, 
                           help='YouTube Video ID or URL')
    
    # Translate transcript
    translate_parser = yt_subparsers.add_parser('translate',
                                              help='Translate a transcript')
    translate_parser.add_argument('--video', '-v', type=str, required=True, 
                                help='YouTube Video ID or URL')
    translate_parser.add_argument('--source-lang', '-s', type=str, default='en', 
                                help='Source language code')
    translate_parser.add_argument('--target-lang', '-t', type=str, required=True, 
                                help='Target language code')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # Handle commands
        if args.command == 'trends':
            if not args.trends_command:
                parser.error("Please specify a trends command (e.g., interest-over-time, related-queries)")
                
            if args.trends_command == 'interest-over-time':
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
                
            elif args.trends_command == 'multirange-interest-over-time':
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
                
            elif args.trends_command == 'historical-hourly-interest':
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
                
            elif args.trends_command == 'interest-by-region':
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
                
            elif args.trends_command == 'related-topics':
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
                
            elif args.trends_command == 'related-queries':
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
                
            elif args.trends_command == 'trending-searches':
                # Execute trending searches query
                result = get_trending_searches(
                    pn=args.pn, 
                    hl=args.hl, 
                    tz=args.tz
                )
                file_path = f"{args.output}/trending_searches_{args.pn}_{timestamp}.json"
                
            elif args.trends_command == 'realtime-trending-searches':
                # Execute realtime trending searches query
                result = get_realtime_trending_searches(
                    pn=args.pn, 
                    hl=args.hl, 
                    tz=args.tz
                )
                file_path = f"{args.output}/realtime_trending_searches_{args.pn}_{timestamp}.json"
                
            elif args.trends_command == 'top-charts':
                # Execute top charts query
                result = get_top_charts(
                    date=args.date, 
                    geo=args.geo, 
                    hl=args.hl, 
                    tz=args.tz
                )
                file_path = f"{args.output}/top_charts_{args.date}_{args.geo}_{timestamp}.json"
                
            elif args.trends_command == 'suggestions':
                # Execute suggestions query
                result = get_suggestions(
                    keyword=args.keyword, 
                    hl=args.hl, 
                    tz=args.tz
                )
                file_path = f"{args.output}/suggestions_{args.keyword}_{timestamp}.json"
                
            elif args.trends_command == 'categories':
                # Execute categories query
                result = get_categories(
                    hl=args.hl, 
                    tz=args.tz
                )
                file_path = f"{args.output}/categories_{timestamp}.json"
                
            else:
                parser.error(f"Unknown trends command: {args.trends_command}")
                
        elif args.command == 'youtube':
            if not args.youtube_command:
                parser.error("Please specify a YouTube command (e.g., transcript, list, translate)")
                
            if args.youtube_command == 'transcript':
                # Extract video ID
                video_id = extract_video_id(args.video)
                
                if args.format == 'text':
                    # Get transcript as text
                    result = get_transcript_as_text(
                        video_id_or_url=args.video, 
                        languages=args.languages, 
                        preserve_formatting=args.preserve_formatting
                    )
                else:
                    # Get transcript as JSON
                    result = get_transcript(
                        video_id_or_url=args.video, 
                        languages=args.languages, 
                        preserve_formatting=args.preserve_formatting,
                        proxy_url=args.proxy_url,
                        cookie_file=args.cookie_file
                    )
                    
                file_path = f"{args.output}/transcript_{video_id}_{timestamp}.json"
                
            elif args.youtube_command == 'list':
                # Extract video ID
                video_id = extract_video_id(args.video)
                
                # List available transcripts
                result = list_available_transcripts(args.video)
                file_path = f"{args.output}/transcript_list_{video_id}_{timestamp}.json"
                
            elif args.youtube_command == 'translate':
                # Extract video ID
                video_id = extract_video_id(args.video)
                
                # Translate transcript
                result = translate_transcript(
                    video_id_or_url=args.video, 
                    source_lang=args.source_lang, 
                    target_lang=args.target_lang
                )
                file_path = f"{args.output}/transcript_translate_{video_id}_{args.source_lang}_to_{args.target_lang}_{timestamp}.json"
                
            else:
                parser.error(f"Unknown YouTube command: {args.youtube_command}")
                
        else:
            parser.error("Please specify a command (trends or youtube)")
            
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
