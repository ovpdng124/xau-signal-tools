from datetime import datetime, timedelta
import pandas as pd
from api_client import TwelveDataClient
from models import Database
from config import TIMEFRAME
from logger import setup_logger
from utils import parse_datetime

logger = setup_logger()

class DataCrawler:
    def __init__(self):
        self.api_client = TwelveDataClient()
        self.db = Database()
        logger.info("Data crawler initialized")

    def crawl_historical_data(self, start_date, end_date):
        """
        Crawl historical OHLCV data for XAU/USD
        
        Args:
            start_date: str or datetime - Start date for data crawling
            end_date: str or datetime - End date for data crawling
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            start_dt = parse_datetime(start_date) if isinstance(start_date, str) else start_date
            end_dt = parse_datetime(end_date) if isinstance(end_date, str) else end_date
            
            logger.info(f"Starting historical data crawl from {start_dt} to {end_dt}")
            
            # Estimate requests needed
            estimation = self.api_client.estimate_requests_needed(start_dt, end_dt, f"{TIMEFRAME}min")
            logger.info(f"Estimated requests needed: {estimation['estimated_requests']}")
            logger.info(f"Estimated time: {estimation['estimated_time_minutes']:.1f} minutes")
            
            if estimation['estimated_requests'] > 100:
                logger.warning(f"This will require {estimation['estimated_requests']} requests. Consider splitting into smaller date ranges.")
            
            # Fetch candle data (API client handles chunking automatically)
            df = self.api_client.get_candles(
                start_time=start_dt,
                end_time=end_dt,
                resolution=f"{TIMEFRAME}min"
            )
            
            if df is None or df.empty:
                logger.error("Failed to fetch any data")
                return False
            
            # Save to database
            try:
                self.db.save_candles(df)
                logger.info(f"Saved {len(df)} candles to database")
            except Exception as e:
                logger.error(f"Failed to save candles to database: {e}")
                return False
            
            # Check rate limit status
            rate_status = self.api_client.get_rate_limit_status()
            logger.info(f"Rate limit status: {rate_status['remaining_calls']} calls remaining")
            
            logger.info(f"Historical data crawl completed. Total candles saved: {len(df)}")
            return True
            
        except Exception as e:
            logger.error(f"Error during historical data crawl: {e}")
            return False

    def crawl_incremental_data(self):
        """
        Crawl only new data since the last candle in database
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the latest candle timestamp from database
            latest_time = self.db.get_latest_candle_time()
            
            if latest_time is None:
                logger.warning("No existing data found. Use crawl_historical_data() instead.")
                return False
            
            # Calculate start time for incremental crawl (add one timeframe to avoid duplicate)
            start_time = latest_time + timedelta(minutes=TIMEFRAME)
            end_time = datetime.now()
            
            logger.info(f"Starting incremental data crawl from {start_time} to {end_time}")
            
            # Fetch new data
            df = self.api_client.get_candles(
                start_time=start_time,
                end_time=end_time,
                resolution=f"{TIMEFRAME}min"
            )
            
            if df is None:
                logger.error("Failed to fetch incremental data")
                return False
            
            if df.empty:
                logger.info("No new data to crawl")
                return True
            
            # Save new data to database
            self.db.save_candles(df)
            logger.info(f"Incremental crawl completed. Saved {len(df)} new candles")
            return True
            
        except Exception as e:
            logger.error(f"Error during incremental data crawl: {e}")
            return False

    def validate_data_integrity(self, start_date=None, end_date=None):
        """
        Validate data integrity by checking for gaps in the database
        
        Args:
            start_date: str or datetime - Start date for validation
            end_date: str or datetime - End date for validation
        
        Returns:
            dict: Validation results with gaps and statistics
        """
        try:
            logger.info("Starting data integrity validation")
            
            # Load data from database
            df = self.db.load_candles(start_date, end_date)
            
            if df.empty:
                return {
                    'status': 'error',
                    'message': 'No data found in database',
                    'gaps': [],
                    'total_candles': 0
                }
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Find gaps (missing candles)
            gaps = []
            expected_interval = timedelta(minutes=TIMEFRAME)
            
            for i in range(1, len(df)):
                current_time = df.iloc[i]['timestamp']
                prev_time = df.iloc[i-1]['timestamp']
                expected_time = prev_time + expected_interval
                
                if current_time > expected_time:
                    # Found a gap
                    gap_start = expected_time
                    gap_end = current_time - expected_interval
                    gaps.append({
                        'start': gap_start,
                        'end': gap_end,
                        'duration_minutes': int((current_time - prev_time).total_seconds() / 60) - TIMEFRAME
                    })
            
            total_expected = int((df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).total_seconds() / (TIMEFRAME * 60)) + 1
            missing_candles = total_expected - len(df)
            completeness = (len(df) / total_expected) * 100 if total_expected > 0 else 0
            
            result = {
                'status': 'success',
                'total_candles': len(df),
                'expected_candles': total_expected,
                'missing_candles': missing_candles,
                'completeness_percent': completeness,
                'gaps': gaps,
                'start_time': df.iloc[0]['timestamp'],
                'end_time': df.iloc[-1]['timestamp']
            }
            
            logger.info(f"Data validation completed: {completeness:.2f}% complete, {len(gaps)} gaps found")
            return result
            
        except Exception as e:
            logger.error(f"Error during data validation: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'gaps': [],
                'total_candles': 0
            }

    def fill_data_gaps(self, gaps):
        """
        Fill identified data gaps by fetching missing data from API
        
        Args:
            gaps: list - List of gaps from validate_data_integrity()
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not gaps:
            logger.info("No gaps to fill")
            return True
        
        try:
            total_filled = 0
            
            for gap in gaps:
                logger.info(f"Filling gap from {gap['start']} to {gap['end']}")
                
                df = self.api_client.get_candles(
                    start_time=gap['start'],
                    end_time=gap['end'],
                    resolution=f"{TIMEFRAME}min"
                )
                
                if df is not None and not df.empty:
                    self.db.save_candles(df)
                    total_filled += len(df)
                    logger.info(f"Filled gap with {len(df)} candles")
                else:
                    logger.warning(f"Could not fill gap from {gap['start']} to {gap['end']}")
            
            logger.info(f"Gap filling completed. Total {total_filled} candles added")
            return True
            
        except Exception as e:
            logger.error(f"Error during gap filling: {e}")
            return False

    def get_data_summary(self):
        """
        Get summary of data in database
        
        Returns:
            dict: Data summary statistics
        """
        try:
            df = self.db.load_candles()
            
            if df.empty:
                return {
                    'total_candles': 0,
                    'start_date': None,
                    'end_date': None,
                    'date_range_days': 0
                }
            
            start_date = df['timestamp'].min()
            end_date = df['timestamp'].max()
            date_range_days = (end_date - start_date).days
            
            return {
                'total_candles': len(df),
                'start_date': start_date,
                'end_date': end_date,
                'date_range_days': date_range_days
            }
            
        except Exception as e:
            logger.error(f"Error getting data summary: {e}")
            return {
                'total_candles': 0,
                'start_date': None,
                'end_date': None,
                'date_range_days': 0
            }

    def close(self):
        """Close database connection"""
        self.db.close()
        logger.info("Data crawler closed")