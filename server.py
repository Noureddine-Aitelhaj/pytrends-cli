def handle_realtime_trending_searches(self, query):
    """Handle realtime trending searches endpoint"""
    try:
        # Get parameters
        pn = query.get('pn', ['US'])[0]
        hl = query.get('hl', ['en-US'])[0]
        tz = int(query.get('tz', ['360'])[0])
        cat = query.get('cat', ['all'])[0]
        
        logger.info(f"Realtime trending searches request: pn={pn}, cat={cat}")
        
        # Import here to avoid impacting health checks
        from pytrends.request import TrendReq
        import pandas as pd
        
        # Initialize PyTrends with basic parameters
        pytrends = TrendReq(
            hl=hl,
            tz=tz,
            timeout=(10,25),
            retries=2,
            backoff_factor=0.5
        )
        
        # Removed the _get_google_cookies() call

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
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {
                "status": "error", 
                "message": f"Country code {pn} not supported. Use a 2-letter ISO country code from the supported list.",
                "supported_countries": supported_countries
            }
            self.wfile.write(json.dumps(error_response).encode())
            return
        
        # Get data
        try:
            df = pytrends.realtime_trending_searches(pn=pn)
            
            if df.empty:
                result = []
            else:
                # The realtime trending searches dataframe has a specific structure
                # Make it more user-friendly
                result = df.to_dict('records')
                
                # Clean up the result to make it more readable
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
                
                result = clean_result
                
        except Exception as e:
            logger.error(f"Error getting realtime trending searches: {str(e)}")
            result = {"error": f"Failed to get realtime trending searches: {str(e)}"}
        
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            "pn": pn,
            "cat": cat,
            "data": result
        }
        
        self.wfile.write(json.dumps(response, default=str).encode())
        
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
