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
    country = known_countries.get(pn.lower(), pn.lower())
    
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
