#!/usr/bin/env python
import sys
import json
import os
import argparse
from pytrends.request import TrendReq
import pandas as pd
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

# =============== PYTRENDS FUNCTIONS ===============

def get_interest_over_time(keywords, timeframe, geo):
    """Get interest over time for keywords"""
    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo)
    
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

def get_related_queries(keywords, timeframe, geo):
    """Get related queries for keywords"""
    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo)
    
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

def get_interest_by_region(keywords, timeframe, geo, resolution='COUNTRY'):
    """Get interest by region for keywords"""
    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo)
    
    df = pytrends.interest_by_region(resolution=resolution)
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

# =============== YOUTUBE TRANSCRIPT FUNCTIONS ===============

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    if "youtu.be" in url:
        # Handle youtu.be URLs
        return url.split("/")[-1].split("?")[0]
    elif "youtube.com" in url:
        # Handle youtube.com URLs
        if "v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
            return video_id
    # If it's already just the ID
    return url

def get_transcript(video_id_or_url, languages=None):
    """Get transcript for a YouTube video"""
    video_id = extract_video_id(video_id_or_url)
    
    try:
        if languages:
            # Convert comma-separated languages to list
            lang_list = [lang.strip() for lang in languages.split(',')]
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
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
            return {
                "video_id": video_id,
                "language": "default",
                "transcript": transcript_data
            }
        else:
            # Get the default transcript
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
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
    except Exception as e:
        return {
            "video_id": video_id,
            "error": str(e)
        }

def get_transcript_as_text(video_id_or_url, languages=None):
    """Get transcript for a YouTube video as plain text"""
    result = get_transcript(video_id_or_url, languages)
    
    if "error" in result:
        return result
    
    # Join all transcript segments into a single text
    full_text = " ".join([item["text"] for item in result["transcript"]])
    
    result["full_text"] = full_text
    return result

# =============== MAIN FUNCTION ===============

def save_to_file(data, file_path):
    """Save data to a file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Data saved to {file_path}")
    return file_path

def main():
    parser = argparse.ArgumentParser(description='Google Trends and YouTube Transcript CLI')
    parser.add_argument('--output', '-o', type=str, required=True, help='Output directory')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Trends parser
    trends_parser = subparsers.add_parser('trends', help='Google Trends commands')
    trends_parser.add_argument('--keywords', '-k', type=str, required=True, help='Keywords (comma separated)')
    trends_parser.add_argument('--timeframe', '-t', type=str, default='today 3-m', help='Timeframe (default: today 3-m)')
    trends_parser.add_argument('--geo', '-g', type=str, default='', help='Geography (default: global)')
    trends_parser.add_argument('--query-type', '-q', type=str, default='interest_over_time', 
                       choices=['interest_over_time', 'related_queries', 'interest_by_region'],
                       help='Query type')
    
    # YouTube parser
    yt_parser = subparsers.add_parser('youtube', help='YouTube Transcript commands')
    yt_parser.add_argument('--video', '-v', type=str, required=True, help='YouTube Video ID or URL')
    yt_parser.add_argument('--languages', '-l', type=str, help='Preferred languages (comma separated)')
    yt_parser.add_argument('--format', '-f', type=str, default='json', choices=['json', 'text'], help='Output format')
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if args.command == 'trends':
        # Parse keywords
        keywords = [k.strip() for k in args.keywords.split(',')]
        
        # Run the selected query type
        if args.query_type == 'interest_over_time':
            result = get_interest_over_time(keywords, args.timeframe, args.geo)
            file_path = f"{args.output}/interest_over_time_{timestamp}.json"
        elif args.query_type == 'related_queries':
            result = get_related_queries(keywords, args.timeframe, args.geo)
            file_path = f"{args.output}/related_queries_{timestamp}.json"
        elif args.query_type == 'interest_by_region':
            result = get_interest_by_region(keywords, args.timeframe, args.geo)
            file_path = f"{args.output}/interest_by_region_{timestamp}.json"
            
    elif args.command == 'youtube':
        if args.format == 'text':
            result = get_transcript_as_text(args.video, args.languages)
        else:
            result = get_transcript(args.video, args.languages)
            
        video_id = extract_video_id(args.video)
        file_path = f"{args.output}/transcript_{video_id}_{timestamp}.json"
    
    # Save the data to a file
    saved_file = save_to_file(result, file_path)
    print(f"Output saved to: {saved_file}")

if __name__ == "__main__":
    main()
