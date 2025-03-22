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
    
    # Known working country codes
    supported_countries = [
        'AR', 'AU', 'AT', 'BE', 'BR', 'CA', 'CL', 'CO', 'CZ', 'DK',
        'EG', 'FI', 'FR', 'DE', 'GR', 'HK', 'HU', 'IN', 'ID', 'IE',
        'IL', 'IT', 'JP', 'KE', 'MY', 'MX', 'NL', 'NZ', 'NG', 'NO',
        'PL', 'PT', 'PH', 'RO', 'RU', 'SA', 'SG', 'ZA', 'KR', 'ES',
        'SE', 'CH', 'TW', 'TH', 'TR', 'UA', 'GB', 'US', 'VN'
    ]
    
    # Format pn correctly (uppercase 2-letter country code is most reliable)
    if len(pn) == 2:
        pn = pn.upper()
    else:
        # Map some common country names to codes
        country_map = {
            'united_states': 'US',
            'united_kingdom': 'GB',
            'japan': 'JP',
            'canada': 'CA',
            'germany': 'DE',
            'india': 'IN',
            'australia': 'AU',
        }
        pn = country_map.get(pn.lower(), pn.upper())
    
    # Validate country code
    if pn not in supported_countries:
        raise ValueError(f"Country code {pn} not supported. Use one of: {', '.join(supported_countries)}")
    
    # Import dependencies
    from pytrends.request import TrendReq
    import pandas as pd
    
    # Initialize PyTrends with backoff factor to handle rate limiting
    pytrends = TrendReq(hl=hl, tz=tz, timeout=(10,25), retries=2, backoff_factor=0.5)
    
    # Get data
    try:
        df = pytrends.realtime_trending_searches(pn=pn)
    except Exception as e:
        raise ValueError(f"Failed to get realtime trending searches for {pn}: {str(e)}")
    
    if df.empty:
        return {"error": "No data found", "pn": pn}
    
    # Process the result
    try:
        result = df.to_dict('records')
        
        # Clean up and format results
        clean_result = []
        for item in result:
            clean_item = {}
            for k, v in item.items():
                if isinstance(v, pd.Timestamp):
                    clean_item[k] = v.isoformat()
                elif isinstance(v, list) and len(v) == 1:
                    clean_item[k] = v[0]
                else:
                    clean_item[k] = v
            clean_result.append(clean_item)
        
        return {
            "pn": pn,
            "cat": cat,
            "data": clean_result
        }
    except Exception as e:
        # Fallback if standard conversion fails
        logger.warning(f"Standard conversion failed, using fallback: {str(e)}")
        return {
            "pn": pn,
            "cat": cat,
            "data": {"raw_data": str(df)}
        }
