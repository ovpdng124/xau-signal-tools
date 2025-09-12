import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import math
from config import (
    TWELVE_DATA_API_KEY, 
    TWELVE_DATA_BASE_URL, 
    SYMBOL, 
    API_RATE_LIMIT_PER_MINUTE,
    MAX_POINTS_PER_REQUEST
)
from RateLimiter import RateLimiter
from logger import setup_logger

logger = setup_logger()

class TwelveDataClient:
    def __init__(self):
        self.api_key = TWELVE_DATA_API_KEY
        self.base_url = TWELVE_DATA_BASE_URL
        self.symbol = SYMBOL
        
        # Rate limiting: 8 requests/minute = ~7.5 seconds between requests
        self.rate_limiter = RateLimiter(max_calls=API_RATE_LIMIT_PER_MINUTE, period=60.0)
        
        if not self.api_key:
            raise ValueError("TWELVE_DATA_API_KEY is required")
        
        logger.info("Twelve Data API client initialized")

    def _make_request(self, endpoint, params=None):
        """
        Make API request with rate limiting and error handling
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            API response data or None if failed
        """
        if params is None:
            params = {}
        
        params['apikey'] = self.api_key
        
        # Apply rate limiting
        self.rate_limiter.wait()
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if 'status' in data and data['status'] == 'error':
                logger.error(f"Twelve Data API error: {data.get('message', 'Unknown error')}")
                return None
            
            return data
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                logger.warning("Rate limit exceeded, waiting longer...")
                time.sleep(10)  # Wait 10 seconds and retry once
                try:
                    response = requests.get(url, params=params, timeout=30)
                    response.raise_for_status()
                    return response.json()
                except:
                    logger.error("Retry failed after rate limit")
                    return None
            else:
                logger.error(f"HTTP error: {e}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def _calculate_max_days_for_interval(self, interval_minutes):
        """
        Calculate maximum days that can be fetched in one request
        based on the 5000 points limit
        
        Args:
            interval_minutes: Interval in minutes
            
        Returns:
            Maximum number of days
        """
        points_per_day = (24 * 60) / interval_minutes
        max_days = int(MAX_POINTS_PER_REQUEST / points_per_day)
        return max(1, max_days)  # At least 1 day

    def _split_date_range(self, start_time, end_time, interval_minutes):
        """
        Split date range into smaller chunks to respect 5000 points limit
        
        Args:
            start_time: Start datetime
            end_time: End datetime
            interval_minutes: Interval in minutes
            
        Returns:
            List of (start, end) datetime tuples
        """
        max_days = self._calculate_max_days_for_interval(interval_minutes)
        chunks = []
        
        current_start = start_time
        
        while current_start < end_time:
            current_end = min(current_start + timedelta(days=max_days), end_time)
            chunks.append((current_start, current_end))
            current_start = current_end
        
        logger.info(f"Split date range into {len(chunks)} chunks (max {max_days} days per chunk)")
        return chunks

    def get_candles(self, start_time, end_time, resolution='15min'):
        """
        Fetch candle data for XAU/USD from Twelve Data API
        
        Args:
            start_time: datetime object
            end_time: datetime object  
            resolution: string ('1min', '5min', '15min', '30min', '1h', '1day')
        
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        # Convert resolution to minutes for calculation
        resolution_mapping = {
            '1min': 1, '5min': 5, '15min': 15, '30min': 30, 
            '1h': 60, '2h': 120, '4h': 240, '1day': 1440
        }
        interval_minutes = resolution_mapping.get(resolution, 15)
        
        logger.info(f"Fetching candles for {self.symbol} from {start_time} to {end_time} (resolution: {resolution})")
        
        # Split date range into chunks
        chunks = self._split_date_range(start_time, end_time, interval_minutes)
        
        all_candles = []
        
        for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
            logger.info(f"Processing chunk {i}/{len(chunks)}: {chunk_start} to {chunk_end}")
            
            # Use the symbol from config (XAU/USD format for time_series)
            symbol_to_use = self.symbol
            
            params = {
                'symbol': symbol_to_use,
                'interval': resolution,
                'start_date': chunk_start.strftime('%Y-%m-%d'),
                'end_date': chunk_end.strftime('%Y-%m-%d'),
                'timezone': 'UTC',
                'dp': 2  # 5 decimal places
            }
            
            data = self._make_request('time_series', params)
            
            if not data:
                logger.error(f"Failed to fetch chunk {i}: {chunk_start} to {chunk_end}")
                continue
            
            # Check if we have values
            values = data.get('values')
            if not values:
                logger.warning(f"No data returned for chunk {i}")
                continue
            
            # Convert to DataFrame
            chunk_df = pd.DataFrame(values)
            
            # Rename columns to match our schema
            if 'datetime' in chunk_df.columns:
                chunk_df = chunk_df.rename(columns={
                    'datetime': 'timestamp',
                    'open': 'open',
                    'high': 'high', 
                    'low': 'low',
                    'close': 'close',
                    'volume': 'volume'
                })
            
            # Convert timestamp to datetime
            chunk_df['timestamp'] = pd.to_datetime(chunk_df['timestamp'])
            
            # Convert OHLCV to numeric
            for col in ['open', 'high', 'low', 'close']:
                chunk_df[col] = pd.to_numeric(chunk_df[col], errors='coerce')
            
            # Handle volume (might be missing for forex)
            if 'volume' in chunk_df.columns:
                chunk_df['volume'] = pd.to_numeric(chunk_df['volume'], errors='coerce').fillna(0)
            else:
                chunk_df['volume'] = 0
            
            all_candles.append(chunk_df)
            
            logger.info(f"Chunk {i} completed: {len(chunk_df)} candles")
            
            # Add delay between chunks to respect rate limits
            if i < len(chunks):
                logger.debug("Waiting 8 seconds between chunks...")
                time.sleep(8)  # ~8 seconds to stay under 8 requests/minute
        
        if not all_candles:
            logger.error("No data retrieved from any chunks")
            return pd.DataFrame()
        
        # Combine all chunks
        df = pd.concat(all_candles, ignore_index=True)
        
        # Sort by timestamp and remove duplicates
        df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp']).reset_index(drop=True)
        
        # Filter to exact date range
        df = df[(df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)]
        
        logger.info(f"Successfully fetched {len(df)} total candles")
        return df

    def get_api_usage(self):
        """Get API usage information"""
        # Don't pass any extra params for api_usage endpoint
        data = self._make_request('api_usage')
        
        if not data:
            return None
            
        return data

    def test_connection(self):
        """Test API connection using api_usage endpoint"""
        try:
            usage_info = self.get_api_usage()
            if usage_info:
                current_usage = usage_info.get('current_usage', 0)
                plan_limit = usage_info.get('plan_limit', 'Unknown')
                logger.info(f"API connection test successful. Usage: {current_usage}/{plan_limit}")
                return True
            else:
                logger.error("API connection test failed")
                return False
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False

    def get_rate_limit_status(self):
        """Get current rate limit status"""
        return {
            'remaining_calls': self.rate_limiter.get_remaining_calls(),
            'reset_time': self.rate_limiter.get_reset_time(),
            'limit_per_minute': API_RATE_LIMIT_PER_MINUTE
        }

    def estimate_requests_needed(self, start_time, end_time, resolution='15min'):
        """
        Estimate number of API requests needed for date range
        
        Args:
            start_time: Start datetime
            end_time: End datetime
            resolution: Time resolution
            
        Returns:
            Estimated number of requests
        """
        resolution_mapping = {
            '1min': 1, '5min': 5, '15min': 15, '30min': 30, 
            '1h': 60, '2h': 120, '4h': 240, '1day': 1440
        }
        interval_minutes = resolution_mapping.get(resolution, 15)
        
        total_days = (end_time - start_time).days + 1
        max_days_per_request = self._calculate_max_days_for_interval(interval_minutes)
        
        estimated_requests = math.ceil(total_days / max_days_per_request)
        
        return {
            'estimated_requests': estimated_requests,
            'total_days': total_days,
            'max_days_per_request': max_days_per_request,
            'estimated_time_minutes': estimated_requests * 0.13  # ~8 seconds per request
        }