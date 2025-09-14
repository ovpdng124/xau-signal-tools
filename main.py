#!/usr/bin/env python3

import argparse
import sys
from datetime import datetime
from data_crawler import DataCrawler
from signal_detector import SignalDetector
from backtester import Backtester
from models import Database
from config import CRAWL_START_DATE, CRAWL_END_DATE, BACKTEST_START_DATE, BACKTEST_END_DATE, DEFAULT_TIMEFRAME, ENABLE_TELEGRAM_NOTIFICATIONS
from logger import setup_logger
from utils import create_directories, parse_datetime
from telegram_utils import send_signal_notification, send_backtest_summary, test_telegram_connection

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
  %(prog)s crawl --start-date "2024-01-01 00:00:00" --end-date "2024-12-31 23:59:59" --timeframe 15m
  %(prog)s crawl --incremental --timeframe 1h  # Crawl new 1H data
  %(prog)s crawl --timeframe 4h  # Crawl 4H data using config dates
  %(prog)s detect --start-date "2024-06-01 00:00:00" --end-date "2024-06-30 23:59:59"
  %(prog)s backtest --start-date "2024-01-01 00:00:00" --end-date "2024-12-31 23:59:59" --timeframe 15m
  %(prog)s backtest --timeframe 1h  # Backtest 1H data using config dates
  %(prog)s daemon start  # Start continuous crawling daemon
  %(prog)s daemon stop   # Stop daemon
  %(prog)s daemon status # Check daemon status
  %(prog)s status  # Show system status
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Crawl command
    crawl_parser = subparsers.add_parser('crawl', help='Crawl historical OHLCV data from MetaTrader5')
    crawl_parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD HH:MM:SS)')
    crawl_parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD HH:MM:SS)')
    crawl_parser.add_argument('--timeframe', type=str, default=DEFAULT_TIMEFRAME, help=f'Timeframe to crawl (1m, 5m, 15m, 30m, 1h, 4h, 1d). Default: {DEFAULT_TIMEFRAME}')
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
    backtest_parser.add_argument('--timeframe', type=str, default=DEFAULT_TIMEFRAME, help=f'Timeframe for backtest data (1m, 5m, 15m, 30m, 1h, 4h, 1d). Default: {DEFAULT_TIMEFRAME}')
    backtest_parser.add_argument('--export', action='store_true', default=True, help='Export results to CSV (default: True)')
    
    # Daemon command
    daemon_parser = subparsers.add_parser('daemon', help='Daemon mode for continuous crawling and signal detection')
    daemon_subparsers = daemon_parser.add_subparsers(dest='daemon_action', help='Daemon actions')
    daemon_subparsers.add_parser('start', help='Start daemon in background')
    daemon_subparsers.add_parser('stop', help='Stop running daemon')
    daemon_subparsers.add_parser('status', help='Check daemon status')
    daemon_subparsers.add_parser('logs', help='View daemon logs in real-time')
    
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
        crawler = DataCrawler(timeframe=args.timeframe)
        
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
        
        # Send Telegram notifications for detected signals
        if ENABLE_TELEGRAM_NOTIFICATIONS:
            for signal in signals:
                success = send_signal_notification(signal)
                if success:
                    logger.info(f"Telegram notification sent for {signal['signal_type']} signal at {signal['timestamp']}")
                else:
                    logger.warning(f"Failed to send Telegram notification for signal at {signal['timestamp']}")
        
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
        
        logger.info(f"Starting backtest from {start_date} to {end_date} with {args.timeframe} timeframe")
        
        backtester = Backtester(timeframe=args.timeframe)
        
        # Run backtest
        results = backtester.run_backtest(start_date, end_date)
        
        if not results:
            logger.warning("No trades were executed during backtest period")
            return True
        
        # Analyze results
        stats = backtester.analyze_results(results)
        
        # Send backtest summary to Telegram if enabled
        if ENABLE_TELEGRAM_NOTIFICATIONS and stats:
            success = send_backtest_summary(stats)
            if success:
                logger.info("Backtest summary sent to Telegram")
            else:
                logger.warning("Failed to send backtest summary to Telegram")
        
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
        
        # Test MT5 connection (replaced API connection test)
        print("\nMT5 STATUS:")
        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                print("MetaTrader5: Connected")
                account_info = mt5.account_info()
                if account_info:
                    print(f"Account: {account_info.login}")
                    print(f"Server: {account_info.server}")
                mt5.shutdown()
            else:
                print("MetaTrader5: Connection failed")
        except ImportError:
            print("MetaTrader5: Not available (library not installed or not on Windows)")
        
        # Test database connection
        print("\nDATABASE STATUS:")
        try:
            db = Database()
            print("PostgreSQL: Connected")
            db.close()
        except Exception as e:
            print(f"PostgreSQL: Connection failed - {e}")
        
        # Test Telegram connection
        print("\nTELEGRAM STATUS:")
        if ENABLE_TELEGRAM_NOTIFICATIONS:
            if test_telegram_connection():
                print("Telegram Bot: Connected and working")
            else:
                print("Telegram Bot: Connection failed or not configured")
        else:
            print("Telegram Bot: Disabled in configuration")
        
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

def handle_daemon_command(args):
    """Handle daemon command"""
    try:
        from scheduler import DaemonScheduler
        import json
        import subprocess
        import os
        
        daemon = DaemonScheduler()
        
        if args.daemon_action == 'start':
            print("🚀 Starting XAU Signal Daemon...")
            
            # Check if already running
            if daemon.is_running():
                print("❌ Daemon is already running!")
                print("Use 'python main.py daemon status' to check status")
                print("Use 'python main.py daemon stop' to stop it first")
                return False
            
            # Start daemon in background
            success = daemon.start()
            
            if success:
                print("✅ Daemon started successfully!")
                print("Use 'python main.py daemon status' to monitor")
                print("Use 'python main.py daemon logs' to view logs")
            else:
                print("❌ Failed to start daemon. Check logs for details.")
            
            return success
            
        elif args.daemon_action == 'stop':
            print("🛑 Stopping XAU Signal Daemon...")
            
            if not daemon.is_running():
                print("⚠️ Daemon is not running")
                return True
            
            success = daemon.stop()
            
            if success:
                print("✅ Daemon stopped successfully!")
            else:
                print("❌ Failed to stop daemon")
            
            return success
            
        elif args.daemon_action == 'status':
            status = daemon.status()
            
            print("\n📊 XAU Signal Daemon Status")
            print("=" * 40)
            
            if status['status'] == 'running':
                print(f"Status: 🟢 {status['status'].upper()}")
                print(f"PID: {status.get('pid', 'Unknown')}")
                print(f"Uptime: {status.get('uptime', 'Unknown')}")
                print(f"Last Activity: {status.get('message', 'Unknown')}")
                
                if 'config' in status:
                    config = status['config']
                    print(f"\nConfiguration:")
                    print(f"  Crawl Interval: {config.get('crawl_interval_minutes', 'Unknown')} minutes")
                    print(f"  Auto Detect: {'Enabled' if config.get('auto_detect_enabled') else 'Disabled'}")
                    print(f"  Telegram: {'Enabled' if config.get('telegram_enabled') else 'Disabled'}")
                    print(f"  Timeframe: {config.get('timeframe', 'Unknown')}")
                
            elif status['status'] == 'stopped':
                print(f"Status: 🔴 {status['status'].upper()}")
            else:
                print(f"Status: ⚠️ {status['status'].upper()}")
            
            print(f"Message: {status.get('message', 'No message')}")
            print(f"Last Check: {status.get('timestamp', 'Unknown')}")
            
            return True
            
        elif args.daemon_action == 'logs':
            print("📋 XAU Signal Daemon Logs")
            print("=" * 40)
            print("Press Ctrl+C to exit log viewing\n")
            
            try:
                # Try to read from log files
                log_files = ['logs/xau_signal_tools.log']
                
                for log_file in log_files:
                    if os.path.exists(log_file):
                        print(f"Tailing {log_file}...")
                        # Use subprocess to tail log file
                        subprocess.run(['tail', '-f', log_file])
                        break
                else:
                    print("No log files found. Daemon might not be running or logging is disabled.")
                    
            except KeyboardInterrupt:
                print("\nLog viewing stopped.")
            except Exception as e:
                print(f"Error viewing logs: {e}")
                return False
            
            return True
            
        else:
            print(f"Unknown daemon action: {args.daemon_action}")
            return False
            
    except ImportError as e:
        logger.error(f"Failed to import scheduler module: {e}")
        print("❌ Daemon functionality is not available")
        return False
    except Exception as e:
        logger.error(f"Error in daemon command: {e}")
        print(f"❌ Daemon command failed: {e}")
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
        elif args.command == 'daemon':
            success = handle_daemon_command(args)
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