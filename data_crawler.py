from datetime import datetime, timedelta
import pandas as pd
import sys
from models import Database
from config import TIMEFRAME
from logger import setup_logger
from utils import parse_datetime

logger = setup_logger()

# Check if MetaTrader5 is available (Windows only)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
    logger.info("MetaTrader5 library loaded successfully")
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 library not available - this will only work on Windows")

class DataCrawler:
    def __init__(self, timeframe='15m'):
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 library is required for data crawling")
            logger.error("This script must be run on Windows with MetaTrader5 installed")
            logger.error("Install with: pip install MetaTrader5")
            raise ImportError("MetaTrader5 library not available")
        
        self.db = Database()
        self.symbol = None
        self.mt5_initialized = False
        self.timeframe = timeframe
        logger.info(f"Data crawler initialized for {timeframe} timeframe")

    def _get_mt5_timeframe(self, timeframe_str):
        """Convert timeframe string to MT5 timeframe constant"""
        timeframe_mapping = {
            '1m': mt5.TIMEFRAME_M1,
            '5m': mt5.TIMEFRAME_M5,
            '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30,
            '1h': mt5.TIMEFRAME_H1,
            '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1
        }
        
        mt5_timeframe = timeframe_mapping.get(timeframe_str.lower())
        if mt5_timeframe is None:
            logger.warning(f"Unsupported timeframe {timeframe_str}, using 15m")
            return mt5.TIMEFRAME_M15
        
        return mt5_timeframe

    def _get_timeframe_minutes(self, timeframe_str):
        """Convert timeframe string to minutes"""
        timeframe_minutes = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440
        }
        
        minutes = timeframe_minutes.get(timeframe_str.lower())
        if minutes is None:
            logger.warning(f"Unknown timeframe {timeframe_str}, using 15 minutes")
            return 15
        
        return minutes

    def _initialize_mt5(self):
        """Initialize MT5 connection and find gold symbol"""
        if self.mt5_initialized:
            return True
            
        try:
            # Initialize MT5
            if not mt5.initialize():
                logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
                return False
            
            logger.info("✓ Connected to MetaTrader5")
            
            # Find gold symbol
            gold_symbols = ["XAUUSD", "GOLD", "XAUUSD.m", "Gold", "XAU/USD"]
            
            for gold_symbol in gold_symbols:
                if mt5.symbol_select(gold_symbol, True):
                    self.symbol = gold_symbol
                    logger.info(f"✓ Found gold symbol: {self.symbol}")
                    self.mt5_initialized = True
                    return True
            
            # If no symbol found, list available symbols
            logger.error("✗ No gold symbol found. Available symbols:")
            symbols = mt5.symbols_get()
            if symbols:
                for s in symbols[:20]:  # Show first 20 symbols
                    logger.info(f"  {s.name}")
            
            mt5.shutdown()
            return False
            
        except Exception as e:
            logger.error(f"Error initializing MT5: {e}")
            return False

    def _shutdown_mt5(self):
        """Shutdown MT5 connection"""
        if self.mt5_initialized:
            mt5.shutdown()
            self.mt5_initialized = False
            logger.info("✓ Disconnected from MT5")

    def _get_mt5_data(self, start_date, end_date):
        """Get data from MT5"""
        try:
            # Convert to timezone-aware datetime if needed
            if isinstance(start_date, str):
                start_dt = parse_datetime(start_date)
            else:
                start_dt = start_date
                
            if isinstance(end_date, str):
                end_dt = parse_datetime(end_date)
            else:
                end_dt = end_date
            
            # Ensure timezone info
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
            
            logger.info(f"✓ Getting {self.symbol} data from {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')} ({self.timeframe})")
            
            # Get MT5 timeframe constant
            mt5_timeframe = self._get_mt5_timeframe(self.timeframe)
            
            # Get data from MT5
            rates = mt5.copy_rates_range(self.symbol, mt5_timeframe, start_dt, end_dt)
            
            if rates is None or len(rates) == 0:
                logger.error("✗ No data retrieved from MT5")
                return None
            
            logger.info(f"✓ Retrieved {len(rates)} {self.timeframe} bars from MT5")
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['timestamp'] = pd.to_datetime(df['time'], unit='s')
            
            # Rename columns to match our database schema
            df = df.rename(columns={
                'open': 'open',
                'high': 'high', 
                'low': 'low',
                'close': 'close',
                'tick_volume': 'volume'
            })
            
            # Select only the columns we need
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # Remove timezone info to match database format
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)
            
            logger.info(f"✓ Converted MT5 data to DataFrame format")
            return df
            
        except Exception as e:
            logger.error(f"Error getting MT5 data: {e}")
            return None

    def crawl_historical_data(self, start_date, end_date):
        """
        Crawl historical OHLCV data for XAU/USD using MetaTrader5
        
        Args:
            start_date: str or datetime - Start date for data crawling
            end_date: str or datetime - End date for data crawling
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Initialize MT5 connection
            if not self._initialize_mt5():
                return False
            
            start_dt = parse_datetime(start_date) if isinstance(start_date, str) else start_date
            end_dt = parse_datetime(end_date) if isinstance(end_date, str) else end_date
            
            logger.info(f"Starting MT5 historical data crawl from {start_dt} to {end_dt}")
            
            # Get data from MT5
            df = self._get_mt5_data(start_dt, end_dt)
            
            if df is None or df.empty:
                logger.error("Failed to fetch any data from MT5")
                self._shutdown_mt5()
                return False
            
            # Save to database
            try:
                self.db.save_candles(df, self.timeframe)
                logger.info(f"Saved {len(df)} {self.timeframe} candles to database")
            except Exception as e:
                logger.error(f"Failed to save candles to database: {e}")
                self._shutdown_mt5()
                return False
            
            logger.info(f"MT5 historical data crawl completed. Total candles saved: {len(df)}")
            self._shutdown_mt5()
            return True
            
        except Exception as e:
            logger.error(f"Error during MT5 historical data crawl: {e}")
            self._shutdown_mt5()
            return False

    def crawl_incremental_data(self):
        """
        Crawl only new data since the last candle in database using MetaTrader5
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Initialize MT5 connection
            if not self._initialize_mt5():
                return False
                
            # Get the latest candle timestamp from database for this timeframe
            latest_time = self.db.get_latest_candle_time(self.timeframe)
            
            if latest_time is None:
                logger.warning(f"No existing {self.timeframe} data found. Use crawl_historical_data() instead.")
                self._shutdown_mt5()
                return False
            
            # Calculate start time for incremental crawl (add one timeframe to avoid duplicate)
            timeframe_minutes = self._get_timeframe_minutes(self.timeframe)
            start_time = latest_time + timedelta(minutes=timeframe_minutes)
            end_time = datetime.now()
            
            logger.info(f"Starting MT5 incremental data crawl from {start_time} to {end_time}")
            
            # Get new data from MT5
            df = self._get_mt5_data(start_time, end_time)
            
            if df is None:
                logger.error("Failed to fetch incremental data from MT5")
                self._shutdown_mt5()
                return False
            
            if df.empty:
                logger.info("No new data to crawl")
                self._shutdown_mt5()
                return True
            
            # Save new data to database
            self.db.save_candles(df, self.timeframe)
            logger.info(f"MT5 incremental crawl completed. Saved {len(df)} new {self.timeframe} candles")
            self._shutdown_mt5()
            return True
            
        except Exception as e:
            logger.error(f"Error during MT5 incremental data crawl: {e}")
            self._shutdown_mt5()
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
        Fill identified data gaps by fetching missing data from MetaTrader5
        
        Args:
            gaps: list - List of gaps from validate_data_integrity()
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not gaps:
            logger.info("No gaps to fill")
            return True
        
        try:
            # Initialize MT5 connection
            if not self._initialize_mt5():
                return False
                
            total_filled = 0
            
            for gap in gaps:
                logger.info(f"Filling gap from {gap['start']} to {gap['end']}")
                
                df = self._get_mt5_data(gap['start'], gap['end'])
                
                if df is not None and not df.empty:
                    self.db.save_candles(df)
                    total_filled += len(df)
                    logger.info(f"Filled gap with {len(df)} candles")
                else:
                    logger.warning(f"Could not fill gap from {gap['start']} to {gap['end']}")
            
            logger.info(f"MT5 gap filling completed. Total {total_filled} candles added")
            self._shutdown_mt5()
            return True
            
        except Exception as e:
            logger.error(f"Error during MT5 gap filling: {e}")
            self._shutdown_mt5()
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
        """Close MT5 and database connections"""
        self._shutdown_mt5()
        self.db.close()
        logger.info("Data crawler closed")