#!/usr/bin/env python3

import argparse
import sys
from datetime import datetime
from data_crawler import DataCrawler
from signal_detector import SignalDetector
from backtester import Backtester
from models import Database
from config import CRAWL_START_DATE, CRAWL_END_DATE, BACKTEST_START_DATE, BACKTEST_END_DATE
from logger import setup_logger
from utils import create_directories, parse_datetime

logger = setup_logger()

def setup_parser():
    """Setup command line argument parser"""
    parser = argparse.ArgumentParser(
        description='XAU Signal Tools - Trading signal detection and backtesting for XAU/USD',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s migrate  # Initialize database schema
  %(prog)s reset --confirm  # Reset database (WARNING: deletes all data)
  %(prog)s crawl --start-date "2024-01-01 00:00:00" --end-date "2024-12-31 23:59:59"
  %(prog)s crawl --incremental
  %(prog)s detect --start-date "2024-06-01 00:00:00" --end-date "2024-06-30 23:59:59"
  %(prog)s backtest --start-date "2024-01-01 00:00:00" --end-date "2024-12-31 23:59:59"
  %(prog)s backtest  # Uses dates from .env file
  %(prog)s status  # Show system status
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Crawl command
    crawl_parser = subparsers.add_parser('crawl', help='Crawl historical OHLCV data from Finnhub API')
    crawl_parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD HH:MM:SS)')
    crawl_parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD HH:MM:SS)')
    crawl_parser.add_argument('--incremental', action='store_true', help='Crawl only new data since last update')
    crawl_parser.add_argument('--validate', action='store_true', help='Validate data integrity after crawling')
    crawl_parser.add_argument('--fill-gaps', action='store_true', help='Fill data gaps found during validation')
    
    # Detect command
    detect_parser = subparsers.add_parser('detect', help='Detect trading signals from historical data')
    detect_parser.add_argument('--start-date', type=str, help='Start date for signal detection')
    detect_parser.add_argument('--end-date', type=str, help='End date for signal detection')
    detect_parser.add_argument('--export', action='store_true', help='Export detected signals to CSV')
    
    # Backtest command
    backtest_parser = subparsers.add_parser('backtest', help='Run backtest with signal detection and trading simulation')
    backtest_parser.add_argument('--start-date', type=str, help='Backtest start date')
    backtest_parser.add_argument('--end-date', type=str, help='Backtest end date')
    backtest_parser.add_argument('--export', action='store_true', default=True, help='Export results to CSV (default: True)')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show database and system status')
    
    # Migration command
    migrate_parser = subparsers.add_parser('migrate', help='Initialize/migrate database schema')
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset database (drop all tables and recreate)')
    reset_parser.add_argument('--confirm', action='store_true', help='Confirm reset operation')
    
    return parser

def handle_crawl_command(args):
    """Handle crawl command"""
    try:
        crawler = DataCrawler()
        
        if args.incremental:
            logger.info("Starting incremental data crawl...")
            success = crawler.crawl_incremental_data()
        else:
            # Use provided dates or defaults from config
            start_date = args.start_date or CRAWL_START_DATE
            end_date = args.end_date or CRAWL_END_DATE
            
            logger.info(f"Starting full data crawl from {start_date} to {end_date}")
            success = crawler.crawl_historical_data(start_date, end_date)
        
        if not success:
            logger.error("Data crawl failed")
            return False
        
        # Validate data if requested
        if args.validate:
            logger.info("Validating data integrity...")
            validation_result = crawler.validate_data_integrity(start_date, end_date)
            
            if validation_result['status'] == 'success':
                print(f"\nDATA VALIDATION RESULTS:")
                print(f"Total candles: {validation_result['total_candles']}")
                print(f"Expected candles: {validation_result['expected_candles']}")
                print(f"Missing candles: {validation_result['missing_candles']}")
                print(f"Data completeness: {validation_result['completeness_percent']:.2f}%")
                print(f"Data gaps found: {len(validation_result['gaps'])}")
                
                # Fill gaps if requested and gaps exist
                if args.fill_gaps and validation_result['gaps']:
                    logger.info("Filling data gaps...")
                    crawler.fill_data_gaps(validation_result['gaps'])
            else:
                logger.error(f"Data validation failed: {validation_result['message']}")
        
        crawler.close()
        logger.info("Data crawl completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error in crawl command: {e}")
        return False

def handle_detect_command(args):
    """Handle detect command"""
    try:
        db = Database()
        detector = SignalDetector()
        
        # Use provided dates or default to None (all data)
        start_date = args.start_date
        end_date = args.end_date
        
        logger.info(f"Loading data for signal detection from {start_date or 'beginning'} to {end_date or 'end'}")
        
        # Load data from database
        df = db.load_candles(start_date, end_date)
        
        if df.empty:
            logger.error("No data found in database for the specified period")
            return False
        
        logger.info(f"Loaded {len(df)} candles for signal detection")
        
        # Sort data by timestamp DESC for scanning (latest first)
        df = df.sort_values('timestamp', ascending=False).reset_index(drop=True)
        
        # Detect signals
        signals = detector.scan_for_signals(df)
        
        if not signals:
            logger.info("No signals detected in the specified period")
            return True
        
        # Print signal summary
        print(f"\nDETECTED SIGNALS SUMMARY:")
        print(f"Total signals: {len(signals)}")
        
        long_signals = [s for s in signals if s['signal_type'] == 'LONG']
        short_signals = [s for s in signals if s['signal_type'] == 'SHORT']
        engulfing_signals = [s for s in signals if s['condition'] == 'ENGULFING']
        inside_bar_signals = [s for s in signals if s['condition'] == 'INSIDE_BAR']
        
        print(f"LONG signals: {len(long_signals)}")
        print(f"SHORT signals: {len(short_signals)}")
        print(f"Engulfing patterns: {len(engulfing_signals)}")
        print(f"Inside bar patterns: {len(inside_bar_signals)}")
        
        # Export to CSV if requested
        if args.export:
            # Convert signals to export format
            export_data = []
            for signal in signals:
                export_data.append({
                    'timestamp': signal['timestamp'],
                    'signal_type': signal['signal_type'],
                    'condition': signal['condition'],
                    'entry_price': signal['entry_price']
                })
            
            from utils import save_results_to_csv
            filepath = save_results_to_csv(export_data, "detected_signals")
            logger.info(f"Signals exported to {filepath}")
        
        db.close()
        logger.info("Signal detection completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error in detect command: {e}")
        return False

def handle_backtest_command(args):
    """Handle backtest command"""
    try:
        # Use provided dates or defaults from config
        start_date = args.start_date or BACKTEST_START_DATE
        end_date = args.end_date or BACKTEST_END_DATE
        
        logger.info(f"Starting backtest from {start_date} to {end_date}")
        
        backtester = Backtester()
        
        # Run backtest
        results = backtester.run_backtest(start_date, end_date)
        
        if not results:
            logger.warning("No trades were executed during backtest period")
            return True
        
        # Analyze results
        stats = backtester.analyze_results(results)
        
        # Export results if requested
        if args.export:
            filepath = backtester.export_results(results, "backtest_results")
            if filepath:
                print(f"\nResults exported to: {filepath}")
        
        backtester.close()
        logger.info("Backtest completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error in backtest command: {e}")
        return False

def handle_status_command(args):
    """Handle status command"""
    try:
        crawler = DataCrawler()
        
        # Get data summary
        summary = crawler.get_data_summary()
        
        print("\nXAU SIGNAL TOOLS STATUS")
        print("=" * 40)
        print(f"Database candles: {summary['total_candles']}")
        
        if summary['total_candles'] > 0:
            print(f"Data range: {summary['start_date']} to {summary['end_date']}")
            print(f"Coverage: {summary['date_range_days']} days")
        else:
            print("No data in database")
        
        # Test API connection
        print("\nAPI STATUS:")
        if crawler.api_client.test_connection():
            rate_status = crawler.api_client.get_rate_limit_status()
            usage_info = crawler.api_client.get_api_usage()
            print(f"Twelve Data API: Connected")
            print(f"Symbol: {crawler.api_client.symbol}")
            print(f"Rate limit: {rate_status['remaining_calls']}/{rate_status['limit_per_minute']} calls remaining")
            if usage_info:
                print(f"API Usage: {usage_info.get('current_usage', 0)}/{usage_info.get('plan_limit', 'Unknown')}")
        else:
            print("Twelve Data API: Connection failed")
        
        # Test database connection
        print("\nDATABASE STATUS:")
        try:
            db = Database()
            print("PostgreSQL: Connected")
            db.close()
        except Exception as e:
            print(f"PostgreSQL: Connection failed - {e}")
        
        crawler.close()
        return True
        
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        return False

def handle_migrate_command(args):
    """Handle migrate command"""
    try:
        logger.info("Starting database migration...")
        
        db = Database()
        logger.info("Database tables created/updated successfully")
        
        db.close()
        print("\nDatabase migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error in migrate command: {e}")
        return False

def handle_reset_command(args):
    """Handle reset command"""
    if not args.confirm:
        print("\nWARNING: This will permanently delete ALL data in the database!")
        print("To confirm, use: python main.py reset --confirm")
        return False
    
    try:
        logger.info("Starting database reset...")
        
        from sqlalchemy import create_engine, text
        from models import Base
        from config import DATABASE_URL
        
        engine = create_engine(DATABASE_URL)
        
        # Drop all tables
        logger.info("Dropping all tables...")
        with engine.connect() as conn:
            # Drop tables in correct order due to dependencies
            conn.execute(text("DROP TABLE IF EXISTS signals CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS candles CASCADE"))
            conn.commit()
        
        # Recreate all tables
        logger.info("Creating fresh database schema...")
        Base.metadata.create_all(bind=engine)
        
        engine.dispose()
        
        print("\nDatabase reset completed successfully!")
        print("All data has been permanently deleted and tables recreated.")
        return True
        
    except Exception as e:
        logger.error(f"Error in reset command: {e}")
        return False

def main():
    """Main entry point"""
    try:
        # Create necessary directories
        create_directories()
        
        # Setup argument parser
        parser = setup_parser()
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return 1
        
        logger.info(f"Starting XAU Signal Tools - Command: {args.command}")
        
        # Route to appropriate handler
        success = False
        
        if args.command == 'crawl':
            success = handle_crawl_command(args)
        elif args.command == 'detect':
            success = handle_detect_command(args)
        elif args.command == 'backtest':
            success = handle_backtest_command(args)
        elif args.command == 'status':
            success = handle_status_command(args)
        elif args.command == 'migrate':
            success = handle_migrate_command(args)
        elif args.command == 'reset':
            success = handle_reset_command(args)
        else:
            logger.error(f"Unknown command: {args.command}")
            parser.print_help()
            return 1
        
        if success:
            logger.info(f"Command '{args.command}' completed successfully")
            return 0
        else:
            logger.error(f"Command '{args.command}' failed")
            return 1
    
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())