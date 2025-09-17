#!/usr/bin/env python3
"""
XAU Signal Tools - Daemon Scheduler

This module provides daemon mode functionality for continuous data crawling
and signal detection. Runs as a background service that:

1. Crawls latest OHLCV data every N minutes (configurable)
2. Auto-detects signals on newly crawled data  
3. Sends Telegram notifications for detected signals
4. Monitors service health and handles errors gracefully

Usage:
    python main.py daemon --start    # Start daemon
    python main.py daemon --stop     # Stop daemon
    python main.py daemon --status   # Check status
    python main.py daemon --logs     # View logs
"""

import os
import sys
import time
import signal
import threading
import schedule
from datetime import datetime, timedelta
import json
from pathlib import Path

from data_crawler import DataCrawler
from signal_detector import SignalDetector
from models import Database
from telegram_utils import send_signal_notification, send_system_notification
from config import (
    SCHEDULER_ENABLED, CRAWL_INTERVAL_MINUTES, AUTO_DETECT_ENABLED, 
    DEFAULT_TIMEFRAME, ENABLE_TELEGRAM_NOTIFICATIONS
)
from logger import setup_logger
from utils import get_utc3_now, convert_to_vietnam_time, format_dual_timezone

logger = setup_logger()

class DaemonScheduler:
    def __init__(self):
        """Initialize daemon scheduler"""
        self.running = False
        self.crawler = None
        self.detector = None
        self.db = None
        self.last_crawl_time = None
        self.last_health_check = None
        self.pid_file = "xau_daemon.pid"
        self.status_file = "xau_daemon_status.json"
        self.stats = {
            'started_at': None,
            'last_crawl': None,
            'last_signal': None,
            'total_crawls': 0,
            'total_signals': 0,
            'errors': 0
        }
        
        logger.info("Daemon scheduler initialized")
    
    def start(self):
        """Start daemon in background"""
        try:
            # Check if already running
            if self.is_running():
                logger.error("Daemon is already running")
                return False
            
            # Write PID file
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Initialize components
            if not self._initialize_components():
                return False
            
            # Set up signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Start daemon
            self.running = True
            self.stats['started_at'] = get_utc3_now().isoformat()
            
            logger.info("🚀 XAU Signal Daemon started")
            if ENABLE_TELEGRAM_NOTIFICATIONS:
                send_system_notification("🚀 XAU Signal Daemon started successfully!", "INFO")
            
            self._update_status("running", "Daemon started successfully")
            
            # Main daemon loop
            self._run_daemon_loop()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            self._cleanup()
            return False
    
    def stop(self):
        """Stop daemon gracefully"""
        try:
            if not self.is_running():
                logger.warning("Daemon is not running")
                return True
            
            # Read PID and send termination signal
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown
            time.sleep(2)
            
            # Force cleanup if still running
            if self.is_running():
                logger.warning("Force stopping daemon")
                self._cleanup()
            
            logger.info("Daemon stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            return False
    
    def status(self):
        """Get daemon status"""
        try:
            if not os.path.exists(self.status_file):
                return {
                    'status': 'stopped',
                    'message': 'Daemon is not running'
                }
            
            with open(self.status_file, 'r') as f:
                status_data = json.loads(f.read())
            
            # Check if PID is still valid
            if self.is_running():
                status_data['uptime'] = self._get_uptime()
                status_data['stats'] = self.stats
                # Add current time in both timezones
                current_time = get_utc3_now()
                status_data['current_time'] = {
                    'utc3': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'vietnam': convert_to_vietnam_time(current_time).strftime('%Y-%m-%d %H:%M:%S'),
                    'dual_format': format_dual_timezone(current_time)
                }
            else:
                status_data['status'] = 'stopped'
                status_data['message'] = 'Process not found'
            
            return status_data
            
        except Exception as e:
            logger.error(f"Error getting daemon status: {e}")
            return {
                'status': 'error',
                'message': f'Error: {str(e)}'
            }
    
    def is_running(self):
        """Check if daemon is currently running"""
        try:
            if not os.path.exists(self.pid_file):
                return False
            
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            os.kill(pid, 0)  # Send signal 0 to check if process exists
            return True
            
        except (OSError, FileNotFoundError, ValueError):
            return False
    
    def _initialize_components(self):
        """Initialize crawler, detector, and database components"""
        try:
            # Check configuration
            if not SCHEDULER_ENABLED:
                logger.error("Scheduler is disabled in configuration")
                return False
            
            self.crawler = DataCrawler(timeframe=DEFAULT_TIMEFRAME)
            self.detector = SignalDetector()
            self.db = Database()
            
            logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            return False
    
    def _run_daemon_loop(self):
        """Main daemon loop using schedule for precise timing"""
        self.last_health_check = get_utc3_now()
        
        # Log startup time in both timezones
        startup_time = get_utc3_now()
        logger.info(f"Daemon loop started at {format_dual_timezone(startup_time)}")
        
        # Setup scheduled jobs for market intervals with 2-second delay
        schedule.every().hour.at("00:03").do(self._scheduled_crawl)
        schedule.every().hour.at("15:03").do(self._scheduled_crawl)
        schedule.every().hour.at("30:03").do(self._scheduled_crawl)
        schedule.every().hour.at("45:03").do(self._scheduled_crawl)
        
        # Health check every 30 minutes
        schedule.every(30).minutes.do(self._scheduled_health_check)
        
        # Status update every 30 seconds (separate from crawl timing)
        schedule.every(30).seconds.do(self._update_daemon_status)
        
        logger.info("📅 Scheduled jobs: XX:00:02, XX:15:02, XX:30:02, XX:45:02 for crawling")
        
        while self.running:
            try:
                # Run scheduled jobs (no other logic here to avoid delay)
                schedule.run_pending()
                
                # Sleep 1 seconds - faster response, schedule handles precision
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}")
                self.stats['errors'] += 1
                
                if ENABLE_TELEGRAM_NOTIFICATIONS:
                    send_system_notification(f"Daemon error: {str(e)}", "ERROR")
                
                # Continue running despite errors
                time.sleep(60)  # Wait longer after error
    
    def _scheduled_crawl(self):
        """Scheduled crawl job - runs at market intervals"""
        try:
            current_time = get_utc3_now()
            logger.info(f"🔄 Scheduled crawl triggered at {format_dual_timezone(current_time)}")
            
            self._execute_crawl_cycle()
            
        except Exception as e:
            logger.error(f"Error in scheduled crawl: {e}")
            self.stats['errors'] += 1
    
    def _scheduled_health_check(self):
        """Scheduled health check job"""
        try:
            logger.info("🏥 Scheduled health check triggered")
            self._perform_health_check()
            self.last_health_check = get_utc3_now()
        except Exception as e:
            logger.error(f"Error in scheduled health check: {e}")
    
    def _update_daemon_status(self):
        """Scheduled status update job"""
        try:
            current_time = get_utc3_now()
            time_display = format_dual_timezone(current_time)
            self._update_status("running", f"Last activity: {time_display}")
        except Exception as e:
            logger.error(f"Error updating daemon status: {e}")
    
    
    def _execute_crawl_cycle(self):
        """Execute complete crawl and detection cycle"""
        try:
            cycle_start = get_utc3_now()
            logger.info(f"🔄 Starting scheduled crawl cycle at {format_dual_timezone(cycle_start)}")
            
            # Step 1: Incremental crawl
            crawl_success = self._perform_incremental_crawl()
            
            if crawl_success and AUTO_DETECT_ENABLED:
                # Step 2: Auto-detect signals on new data
                signals = self._perform_auto_detection()
                
                # Step 3: Send notifications for detected signals
                if signals and ENABLE_TELEGRAM_NOTIFICATIONS:
                    self._send_signal_notifications(signals)
            
            # Update statistics
            self.last_crawl_time = cycle_start
            self.stats['total_crawls'] += 1
            self.stats['last_crawl'] = cycle_start.isoformat()
            
            cycle_duration = (get_utc3_now() - cycle_start).total_seconds()
            logger.info(f"✅ Crawl cycle completed in {cycle_duration:.1f} seconds")
            
        except Exception as e:
            logger.error(f"Error in crawl cycle: {e}")
            self.stats['errors'] += 1
            raise
    
    def _perform_incremental_crawl(self):
        """Perform incremental data crawl"""
        try:
            logger.info("📊 Performing incremental data crawl")
            
            # Perform incremental crawl (crawler handles timing internally)
            success = self.crawler.crawl_incremental_data()
            
            if success:
                logger.info("✅ Incremental crawl completed successfully")
            else:
                logger.warning("⚠️ Incremental crawl failed or no new data")
            
            return success
            
        except Exception as e:
            logger.error(f"Incremental crawl failed: {e}")
            return False
    
    def _perform_auto_detection(self):
        """Perform signal detection on newly closed candle"""
        try:
            logger.info("🔍 Performing auto signal detection")
            
            # Load sufficient historical context for SuperTrend calculation accuracy
            end_time = get_utc3_now().replace(tzinfo=None)
            start_time = end_time - timedelta(days=20)  # 2 weeks of historical context for SuperTrend stability
            
            # Convert to string format for database query
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            
            logger.info(f"Loading data from {format_dual_timezone(start_time)} to {format_dual_timezone(end_time)}")
            
            df = self.db.load_candles(
                start_time_str,
                end_time_str,
                DEFAULT_TIMEFRAME
            )
            
            if df.empty:
                logger.warning("No recent data found for signal detection")
                return []
            
            # Sort by timestamp DESC (latest first) for proper indexing
            df = df.sort_values('timestamp', ascending=False).reset_index(drop=True)
            
            if len(df) < 4:
                logger.warning("Not enough candles for signal detection (need at least 4)")
                return []
            
            logger.info(f"Loaded {len(df)} candles with historical context for accurate SuperTrend calculation")
            
            # Detect signal ONLY on the latest closed candle (index 3 for proper lookback)
            # Index 0 = N0 (current/incomplete), Index 1 = N1 (latest closed), Index 2 = N2, Index 3 = N3
            # Use full historical data for SuperTrend calculation but scan only index 3
            signals = self.detector.scan_for_signals_with_supertrend(df, start_index=3, end_index=3)
            
            # Should only have max 1 signal since we check only 1 candle position
            if signals:
                latest_signal = signals[0]  # Take first (should be only one)
                
                # ĐẶC BIỆT QUAN TRỌNG: Set entry_time = current time (notification time)
                entry_time_utc3 = get_utc3_now()
                latest_signal['entry_time'] = entry_time_utc3.replace(tzinfo=None)
                latest_signal['entry_time_str'] = format_dual_timezone(entry_time_utc3)
                
                logger.info(f"🎯 Signal detected at {format_dual_timezone(latest_signal['timestamp'])}: {latest_signal['signal_type']} - {latest_signal['condition']}")
                logger.info(f"📍 Entry time (notification time): {latest_signal['entry_time_str']}")
                
                self.stats['total_signals'] += 1
                self.stats['last_signal'] = entry_time_utc3.isoformat()
                
                return [latest_signal]
            else:
                logger.info("No signal detected on latest closed candle")
                return []
            
        except Exception as e:
            logger.error(f"Auto detection failed: {e}")
            return []
    
    def _send_signal_notifications(self, signals):
        """Send Telegram notifications for detected signals"""
        try:
            logger.info(f"📱 Sending notifications for {len(signals)} signals")
            
            for signal in signals:
                success = send_signal_notification(signal)
                if success:
                    logger.info(f"✅ Notification sent for {signal['signal_type']} signal at {signal['timestamp']}")
                else:
                    logger.warning(f"❌ Failed to send notification for signal at {signal['timestamp']}")
            
        except Exception as e:
            logger.error(f"Error sending signal notifications: {e}")
    
    def _perform_health_check(self):
        """Perform system health check"""
        try:
            logger.info("🏥 Performing health check")
            
            health_status = {
                'database': 'unknown',
                'crawler': 'unknown', 
                'telegram': 'unknown'
            }
            
            # Check database connection
            try:
                self.db.load_candles(limit=1)
                health_status['database'] = 'ok'
            except Exception:
                health_status['database'] = 'error'
            
            # Check crawler (MT5 not available on macOS, so just check initialization)
            health_status['crawler'] = 'ok' if self.crawler else 'error'
            
            # Check Telegram (if enabled)
            if ENABLE_TELEGRAM_NOTIFICATIONS:
                try:
                    from telegram_utils import telegram_notifier
                    health_status['telegram'] = 'ok' if telegram_notifier.enabled else 'disabled'
                except Exception:
                    health_status['telegram'] = 'error'
            else:
                health_status['telegram'] = 'disabled'
            
            # Log health status
            issues = [k for k, v in health_status.items() if v == 'error']
            if issues:
                logger.warning(f"Health check issues: {', '.join(issues)}")
            else:
                logger.info("✅ All systems healthy")
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    def _update_status(self, status, message):
        """Update daemon status file"""
        try:
            status_data = {
                'status': status,
                'message': message,
                'timestamp': get_utc3_now().isoformat(),
                'pid': os.getpid(),
                'config': {
                    'crawl_interval_minutes': CRAWL_INTERVAL_MINUTES,
                    'auto_detect_enabled': AUTO_DETECT_ENABLED,
                    'telegram_enabled': ENABLE_TELEGRAM_NOTIFICATIONS,
                    'timeframe': DEFAULT_TIMEFRAME
                }
            }
            
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to update status file: {e}")
    
    def _get_uptime(self):
        """Calculate daemon uptime"""
        try:
            if self.stats['started_at']:
                started = datetime.fromisoformat(self.stats['started_at'])
                uptime_seconds = (get_utc3_now() - started).total_seconds()
                
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                seconds = int(uptime_seconds % 60)
                
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            return "Unknown"
            
        except Exception:
            return "Error"
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        self._cleanup()
        sys.exit(0)
    
    def _cleanup(self):
        """Clean up daemon resources"""
        try:
            self.running = False
            
            # Close database connection
            if self.db:
                self.db.close()
            
            # Close crawler
            if self.crawler:
                self.crawler.close()
            
            # Remove PID file
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            
            # Update status to stopped
            self._update_status("stopped", "Daemon stopped")
            
            logger.info("Daemon cleanup completed")
            
            # if ENABLE_TELEGRAM_NOTIFICATIONS:
            #     send_system_notification("🛑 XAU Signal Daemon stopped", "INFO")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main entry point for daemon operations"""
    if len(sys.argv) < 2:
        print("Usage: python scheduler.py [start|stop|status]")
        return 1
    
    command = sys.argv[1].lower()
    daemon = DaemonScheduler()
    
    if command == 'start':
        success = daemon.start()
        return 0 if success else 1
    elif command == 'stop':
        success = daemon.stop()
        return 0 if success else 1
    elif command == 'status':
        status = daemon.status()
        print(json.dumps(status, indent=2))
        return 0
    else:
        print(f"Unknown command: {command}")
        return 1

if __name__ == "__main__":
    sys.exit(main())