import pandas as pd
from datetime import datetime, timedelta
from models import Database
from signal_detector import SignalDetector
from utils import (
    calculate_tp_sl_prices, 
    check_tp_sl_hit, 
    calculate_pnl,
    calculate_pnl_percentage,
    parse_datetime,
    save_results_to_csv,
    calculate_win_rate,
    print_backtest_summary,
    is_within_trading_hours
)
from config import ENABLE_TIMEOUT, TIMEOUT_HOURS, ENABLE_TIME_WINDOW, TRADE_START_TIME, TRADE_END_TIME, ENABLE_SINGLE_ORDER_MODE, TP_AMOUNT, SL_AMOUNT
from logger import setup_logger

logger = setup_logger()

class Backtester:
    def __init__(self, timeframe='15m'):
        self.db = Database()
        self.signal_detector = SignalDetector()
        self.active_orders = []  # Store active orders in memory
        self.completed_orders = []  # Store completed orders for results
        self.timeframe = timeframe
        
        # Log configuration
        config_info = []
        if ENABLE_TIME_WINDOW:
            config_info.append(f"time window: {TRADE_START_TIME}-{TRADE_END_TIME}")
        if ENABLE_SINGLE_ORDER_MODE:
            config_info.append("single order mode")
        
        if config_info:
            logger.info(f"Backtester initialized for {timeframe} with {', '.join(config_info)}")
        else:
            logger.info(f"Backtester initialized for {timeframe} (default mode: multiple orders, no time restrictions)")
        

    def run_backtest(self, start_date, end_date):
        """
        Run backtest from start_date to end_date
        
        Args:
            start_date: str or datetime - Backtest start date
            end_date: str or datetime - Backtest end date
            
        Returns:
            list: Backtest results
        """
        try:
            start_dt = parse_datetime(start_date) if isinstance(start_date, str) else start_date
            end_dt = parse_datetime(end_date) if isinstance(end_date, str) else end_date
            
            logger.info(f"Starting backtest from {start_dt} to {end_dt}")
            
            # Load historical data from database for specific timeframe (for signals)
            df = self.db.load_candles(start_dt, end_dt, self.timeframe)
            
            if df.empty:
                logger.error("No historical data found for backtest period")
                return []
            
            logger.info(f"Loaded {len(df)} {self.timeframe} candles for signal detection")
            
            # Calculate SuperTrend for entire dataset
            from utils import calculate_supertrend
            self.signal_detector.supertrend_data = calculate_supertrend(df)
            logger.info("SuperTrend calculated for signal confidence scoring")
            
            # Load 1-minute data for precise TP/SL checking
            df_1m = self.db.load_candles(start_dt, end_dt, '1m')
            
            if df_1m.empty:
                logger.error("No 1-minute data found for TP/SL checking")
                return []
            
            logger.info(f"Loaded {len(df_1m)} 1-minute candles for TP/SL precision")
            
            # Reset state
            self.active_orders = []
            self.completed_orders = []
            
            # Sort data by timestamp ASC for chronological processing
            df = df.sort_values('timestamp').reset_index(drop=True)
            df_1m = df_1m.sort_values('timestamp').reset_index(drop=True)
            
            # Start backtesting loop from index 3 (need 3 lookback candles)
            current_index = 3
            
            while current_index < len(df):
                current_time = df.iloc[current_index]['timestamp']
                current_candle = df.iloc[current_index].to_dict()
                
                logger.debug(f"Processing candle at {current_time}")
                
                # Step 1: Look for new signals at this time BEFORE checking/closing orders
                # Get the lookback candles (N1, N2, N3)
                if current_index >= 3:
                    n1 = df.iloc[current_index - 3].to_dict()  # lookback 3
                    n2 = df.iloc[current_index - 2].to_dict()  # lookback 2  
                    n3 = df.iloc[current_index - 1].to_dict()  # lookback 1
                    
                    signal = self.signal_detector.detect_signal(n1, n2, n3)
                    
                    if signal:
                        # Check single order mode first (if enabled)
                        if ENABLE_SINGLE_ORDER_MODE and len(self.active_orders) > 0:
                            logger.info(f"Signal ignored due to single order mode: {len(self.active_orders)} active order(s) at {current_time.strftime('%Y-%m-%d %H:%M')}")
                        else:
                            # Check if within trading time window (if enabled)
                            if ENABLE_TIME_WINDOW:
                                if is_within_trading_hours(current_time, TRADE_START_TIME, TRADE_END_TIME):
                                    self._place_order(signal, current_time)
                                else:
                                    logger.debug(f"Signal ignored outside trading hours: {current_time.strftime('%H:%M')} (Trading window: {TRADE_START_TIME}-{TRADE_END_TIME})")
                            else:
                                self._place_order(signal, current_time)
                
                # Step 2: Check existing orders for TP/SL hits and timeouts using 1-minute precision
                self._check_active_orders_with_1m_precision(current_candle, df_1m)
                
                current_index += 1
            
            # Process any remaining active orders at the end (only if TIMEOUT enabled)
            if ENABLE_TIMEOUT:
                self._close_remaining_orders(df.iloc[-1].to_dict())
            
            logger.info(f"Backtest completed. Total trades: {len(self.completed_orders)}")
            
            return self.completed_orders
            
        except Exception as e:
            logger.error(f"Error during backtest: {e}")
            return []

    def _check_active_orders_with_1m_precision(self, current_candle, df_1m):
        """
        Check active orders for TP/SL hits using 1-minute precision ONLY (no fallback)
        
        Args:
            current_candle: dict - Current main timeframe candle data  
            df_1m: DataFrame - 1-minute data for precise TP/SL checking
        """
        if not self.active_orders:
            return
            
        orders_to_remove = []
        current_time = current_candle['timestamp']
        
        # Calculate the timeframe duration for determining 1m range
        timeframe_minutes = self._get_timeframe_minutes(self.timeframe)
        
        for order in self.active_orders:
            # Check for time-based timeout first (if enabled)
            if TIMEOUT_HOURS > 0:
                order_age_hours = (current_time - order['entry_time']).total_seconds() / 3600
                if order_age_hours >= TIMEOUT_HOURS:
                    # Order timed out
                    exit_price = current_candle['close']
                    pnl = calculate_pnl(order['entry_price'], exit_price, order['signal_type'])
                    pnl_percentage = calculate_pnl_percentage(order['entry_price'], exit_price, order['signal_type'])
                    
                    # Determine if it would have been a win or loss based on exit price vs TP
                    if order['signal_type'] == 'LONG':
                        result = 'WIN' if exit_price >= order['tp_price'] else 'LOSS'
                    else:  # SHORT
                        result = 'WIN' if exit_price <= order['tp_price'] else 'LOSS'
                    
                    completed_order = {
                        'entry_time': order['entry_time'],
                        'exit_time': current_time,
                        'signal_type': order['signal_type'],
                        'condition': order['condition'],
                        'entry_price': order['entry_price'],
                        'exit_price': exit_price,
                        'tp_price': order['tp_price'],
                        'sl_price': order['sl_price'],
                        'hit_type': 'TIMEOUT',
                        'pnl': pnl,
                        'pnl_percentage': pnl_percentage,
                        'result': result,
                        'duration_minutes': int((current_time - order['entry_time']).total_seconds() / 60),
                        'confidence': order.get('confidence') or 'N/A'
                    }
                    
                    self.completed_orders.append(completed_order)
                    orders_to_remove.append(order)
                    
                    logger.info(f"TIMEOUT trade: {order['signal_type']} from {order['entry_time']} "
                               f"timed out at {current_time} after {order_age_hours:.1f}h, PnL: ${pnl:.4f}")
                    continue
            
            # Check for TP/SL hits using 1-minute precision ONLY
            # Skip orders placed at current time (they should be checked in next iteration)
            if order['entry_time'] >= current_time:
                continue  # Skip orders placed at or after current time
            
            # Get 1-minute candles between previous timeframe candle and current candle
            start_1m = current_time - timedelta(minutes=timeframe_minutes)
            end_1m = current_time
            
            # Filter 1-minute candles for this period (no look-ahead bias)
            mask_1m = (df_1m['timestamp'] > start_1m) & (df_1m['timestamp'] <= end_1m)
            period_1m_candles = df_1m[mask_1m]
            
            hit_found = False
            
            # Check each 1-minute candle in this period chronologically (NO fallback)
            for _, candle_1m in period_1m_candles.iterrows():
                # Only process 1m candles that occur after the order was placed
                if candle_1m['timestamp'] <= order['entry_time']:
                    continue
                    
                hit_type, exit_price = check_tp_sl_hit(
                    candle_1m.to_dict(), 
                    order['tp_price'], 
                    order['sl_price'], 
                    order['signal_type']
                )
                
                if hit_type:
                    # Order hit TP or SL on this 1-minute candle
                    pnl = calculate_pnl(order['entry_price'], exit_price, order['signal_type'])
                    pnl_percentage = calculate_pnl_percentage(order['entry_price'], exit_price, order['signal_type'])
                    result = 'WIN' if hit_type == 'TP' else 'LOSS'
                    
                    # Use the precise 1-minute timestamp for exit_time
                    exit_time_precise = candle_1m['timestamp']
                    
                    # Create completed order record
                    completed_order = {
                        'entry_time': order['entry_time'],
                        'exit_time': exit_time_precise,
                        'signal_type': order['signal_type'],
                        'condition': order['condition'],
                        'entry_price': order['entry_price'],
                        'exit_price': exit_price,
                        'tp_price': order['tp_price'],
                        'sl_price': order['sl_price'],
                        'hit_type': hit_type,
                        'pnl': pnl,
                        'pnl_percentage': pnl_percentage,
                        'result': result,
                        'duration_minutes': int((exit_time_precise - order['entry_time']).total_seconds() / 60),
                        'confidence': order.get('confidence') or 'N/A'
                    }
                    
                    self.completed_orders.append(completed_order)
                    orders_to_remove.append(order)
                    
                    logger.info(f"{result} trade: {order['signal_type']} from {order['entry_time']} "
                               f"hit {hit_type} at {exit_time_precise} (1m precision), PnL: ${pnl:.4f}")
                    
                    hit_found = True
                    break  # Exit 1m loop once we find a hit
            
            # Continue to next order (no fallback to main timeframe)
        
        # Remove completed orders from active list
        for order in orders_to_remove:
            self.active_orders.remove(order)

    def _get_timeframe_minutes(self, timeframe_str):
        """
        Convert timeframe string to minutes
        
        Args:
            timeframe_str: str - Timeframe like '1m', '5m', '15m', '30m', '1h', '4h', '1d'
            
        Returns:
            int: Number of minutes
        """
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

    def _check_active_orders(self, current_candle):
        """
        DEPRECATED: Original method kept for backward compatibility
        Check active orders against current candle for TP/SL hits and timeouts
        
        Args:
            current_candle: dict - Current candle data
        """
        orders_to_remove = []
        current_time = current_candle['timestamp']
        
        for order in self.active_orders:
            # Check for time-based timeout first (if enabled)
            if TIMEOUT_HOURS > 0:
                order_age_hours = (current_time - order['entry_time']).total_seconds() / 3600
                if order_age_hours >= TIMEOUT_HOURS:
                    # Order timed out
                    exit_price = current_candle['close']
                    pnl = calculate_pnl(order['entry_price'], exit_price, order['signal_type'])
                    pnl_percentage = calculate_pnl_percentage(order['entry_price'], exit_price, order['signal_type'])
                    
                    # Determine if it would have been a win or loss based on exit price vs TP
                    if order['signal_type'] == 'LONG':
                        result = 'WIN' if exit_price >= order['tp_price'] else 'LOSS'
                    else:  # SHORT
                        result = 'WIN' if exit_price <= order['tp_price'] else 'LOSS'
                    
                    completed_order = {
                        'entry_time': order['entry_time'],
                        'exit_time': current_time,
                        'signal_type': order['signal_type'],
                        'condition': order['condition'],
                        'entry_price': order['entry_price'],
                        'exit_price': exit_price,
                        'tp_price': order['tp_price'],
                        'sl_price': order['sl_price'],
                        'hit_type': 'TIMEOUT',
                        'pnl': pnl,
                        'pnl_percentage': pnl_percentage,
                        'result': result,
                        'duration_minutes': int((current_time - order['entry_time']).total_seconds() / 60),
                        'confidence': order.get('confidence') or 'N/A'
                    }
                    
                    self.completed_orders.append(completed_order)
                    orders_to_remove.append(order)
                    
                    logger.info(f"TIMEOUT trade: {order['signal_type']} from {order['entry_time']} "
                               f"timed out at {current_time} after {order_age_hours:.1f}h, PnL: ${pnl:.4f}")
                    continue
            
            # Check for TP/SL hits
            hit_type, exit_price = check_tp_sl_hit(
                current_candle, 
                order['tp_price'], 
                order['sl_price'], 
                order['signal_type']
            )
            
            if hit_type:
                # Order hit TP or SL
                pnl = calculate_pnl(order['entry_price'], exit_price, order['signal_type'])
                pnl_percentage = calculate_pnl_percentage(order['entry_price'], exit_price, order['signal_type'])
                result = 'WIN' if hit_type == 'TP' else 'LOSS'
                
                # Create completed order record
                completed_order = {
                    'entry_time': order['entry_time'],
                    'exit_time': current_time,
                    'signal_type': order['signal_type'],
                    'condition': order['condition'],
                    'entry_price': order['entry_price'],
                    'exit_price': exit_price,
                    'tp_price': order['tp_price'],
                    'sl_price': order['sl_price'],
                    'hit_type': hit_type,
                    'pnl': pnl,
                    'pnl_percentage': pnl_percentage,
                    'result': result,
                    'duration_minutes': int((current_time - order['entry_time']).total_seconds() / 60),
                    'confidence': order.get('confidence') or 'N/A'
                }
                
                self.completed_orders.append(completed_order)
                orders_to_remove.append(order)
                
                logger.info(f"{result} trade: {order['signal_type']} from {order['entry_time']} "
                           f"hit {hit_type} at {current_time}, PnL: ${pnl:.4f}")
        
        # Remove completed orders from active list
        for order in orders_to_remove:
            self.active_orders.remove(order)

    def _place_order(self, signal, current_time):
        """
        Place a new order based on detected signal
        
        Args:
            signal: dict - Signal information
            current_time: datetime - Current time for order placement
        """
        entry_price = signal['entry_price']
        signal_type = signal['signal_type']
        condition = signal['condition']
        
        # Calculate TP and SL prices
        tp_price, sl_price = calculate_tp_sl_prices(entry_price, signal_type)
        
        # Create order
        order = {
            'entry_time': current_time,
            'signal_type': signal_type,
            'condition': condition,
            'entry_price': entry_price,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'signal_details': signal['details'],
            'confidence': signal.get('confidence') or 'N/A'
        }
        
        self.active_orders.append(order)
        
        logger.info(f"Placed {signal_type} order at {current_time}: "
                   f"Entry=${entry_price:.4f}, TP=${tp_price:.4f}, SL=${sl_price:.4f}")

    def _close_remaining_orders(self, last_candle):
        """
        Close any remaining active orders at the end of backtest
        
        Args:
            last_candle: dict - Last candle data
        """
        for order in self.active_orders:
            exit_price = last_candle['close']
            exit_time = last_candle['timestamp']
            pnl = calculate_pnl(order['entry_price'], exit_price, order['signal_type'])
            pnl_percentage = calculate_pnl_percentage(order['entry_price'], exit_price, order['signal_type'])
            
            # Determine if it would have been a win or loss based on exit price
            if order['signal_type'] == 'LONG':
                result = 'WIN' if exit_price >= order['tp_price'] else 'LOSS'
            else:  # SHORT
                result = 'WIN' if exit_price <= order['tp_price'] else 'LOSS'
            
            completed_order = {
                'entry_time': order['entry_time'],
                'exit_time': exit_time,
                'signal_type': order['signal_type'],
                'condition': order['condition'],
                'entry_price': order['entry_price'],
                'exit_price': exit_price,
                'tp_price': order['tp_price'],
                'sl_price': order['sl_price'],
                'hit_type': 'TIMEOUT',
                'pnl': pnl,
                'pnl_percentage': pnl_percentage,
                'result': result,
                'duration_minutes': int((exit_time - order['entry_time']).total_seconds() / 60),
                'confidence': order.get('confidence', 'N/A')
            }
            
            self.completed_orders.append(completed_order)
            
            logger.info(f"Closed remaining {order['signal_type']} order at backtest end: "
                       f"Entry=${order['entry_price']:.4f}, Exit=${exit_price:.4f}, PnL=${pnl:.4f}")
        
        self.active_orders.clear()

    def export_results(self, results, filename_prefix="backtest_results"):
        """
        Export backtest results to CSV
        
        Args:
            results: list - Backtest results
            filename_prefix: str - Filename prefix
            
        Returns:
            str: Path to exported file
        """
        if not results:
            logger.warning("No results to export")
            return None
        
        filepath = save_results_to_csv(results, filename_prefix)
        logger.info(f"Results exported to {filepath}")
        return filepath

    def analyze_results(self, results):
        """
        Analyze and print backtest results
        
        Args:
            results: list - Backtest results
            
        Returns:
            dict: Analysis statistics
        """
        if not results:
            logger.warning("No results to analyze")
            return {}
        
        stats = calculate_win_rate(results)
        
        # Additional analysis
        long_trades = [r for r in results if r['signal_type'] == 'LONG']
        short_trades = [r for r in results if r['signal_type'] == 'SHORT']
        
        engulfing_trades = [r for r in results if r['condition'] == 'ENGULFING']
        inside_bar_trades = [r for r in results if r['condition'] == 'INSIDE_BAR']
        
        detailed_stats = {
            **stats,
            'long_trades': len(long_trades),
            'short_trades': len(short_trades),
            'long_wins': sum(1 for r in long_trades if r['result'] == 'WIN'),
            'short_wins': sum(1 for r in short_trades if r['result'] == 'WIN'),
            'long_win_rate': (sum(1 for r in long_trades if r['result'] == 'WIN') / len(long_trades)) * 100 if long_trades else 0,
            'short_win_rate': (sum(1 for r in short_trades if r['result'] == 'WIN') / len(short_trades)) * 100 if short_trades else 0,
            'engulfing_trades': len(engulfing_trades),
            'inside_bar_trades': len(inside_bar_trades),
            'engulfing_wins': sum(1 for r in engulfing_trades if r['result'] == 'WIN'),
            'inside_bar_wins': sum(1 for r in inside_bar_trades if r['result'] == 'WIN'),
            'engulfing_win_rate': (sum(1 for r in engulfing_trades if r['result'] == 'WIN') / len(engulfing_trades)) * 100 if engulfing_trades else 0,
            'inside_bar_win_rate': (sum(1 for r in inside_bar_trades if r['result'] == 'WIN') / len(inside_bar_trades)) * 100 if inside_bar_trades else 0,
            'avg_duration_minutes': sum(r['duration_minutes'] for r in results) / len(results) if results else 0
        }
        
        # Print detailed analysis
        print_backtest_summary(results)
        print("\nDETAILED ANALYSIS:")
        print(f"LONG Trades: {detailed_stats['long_trades']} (Win Rate: {detailed_stats['long_win_rate']:.2f}%)")
        print(f"SHORT Trades: {detailed_stats['short_trades']} (Win Rate: {detailed_stats['short_win_rate']:.2f}%)")
        print(f"Engulfing Pattern: {detailed_stats['engulfing_trades']} (Win Rate: {detailed_stats['engulfing_win_rate']:.2f}%)")
        print(f"Inside Bar Pattern: {detailed_stats['inside_bar_trades']} (Win Rate: {detailed_stats['inside_bar_win_rate']:.2f}%)")
        print(f"Average Trade Duration: {detailed_stats['avg_duration_minutes']:.1f} minutes")
        
        return detailed_stats

    def get_active_orders_count(self):
        """Get count of currently active orders"""
        return len(self.active_orders)

    def close(self):
        """Close database connection"""
        self.db.close()
        logger.info("Backtester closed")