from datetime import datetime, timedelta
import pandas as pd
import os
from config import TP_AMOUNT, SL_AMOUNT

def is_green_candle(candle):
    """Check if candle is green (close > open)"""
    return candle['close'] > candle['open']

def is_red_candle(candle):
    """Check if candle is red (close < open)"""
    return candle['close'] < candle['open']

def get_candle_body_range(candle):
    """Get the body range of a candle (abs(close - open))"""
    return abs(candle['close'] - candle['open'])

def calculate_tp_sl_prices(entry_price, signal_type):
    """
    Calculate TP and SL prices based on entry price and signal type
    
    Args:
        entry_price: float - Entry price in USD
        signal_type: str - 'LONG' or 'SHORT'
    
    Returns:
        tuple: (tp_price, sl_price)
    """
    tp_amount = TP_AMOUNT  # Convert to proper decimal (6.0 -> 0.006)
    sl_amount = SL_AMOUNT  # Convert to proper decimal (3.0 -> 0.003)
    
    if signal_type == 'LONG':
        tp_price = entry_price + tp_amount
        sl_price = entry_price - sl_amount
    else:  # SHORT
        tp_price = entry_price - tp_amount  
        sl_price = entry_price + sl_amount
    
    return tp_price, sl_price

def check_tp_sl_hit(candle, tp_price, sl_price, signal_type):
    """
    Check if a candle hits TP or SL
    
    Args:
        candle: dict - Candle data with high/low prices
        tp_price: float - Take profit price
        sl_price: float - Stop loss price
        signal_type: str - 'LONG' or 'SHORT'
    
    Returns:
        tuple: (hit_type, exit_price) where hit_type is 'TP', 'SL' or None
    """
    high = candle['high']
    low = candle['low']
    
    if signal_type == 'LONG':
        # For LONG: TP is above entry, SL is below entry
        if high >= tp_price:
            return 'TP', tp_price
        elif low <= sl_price:
            return 'SL', sl_price
    else:  # SHORT
        # For SHORT: TP is below entry, SL is above entry
        if low <= tp_price:
            return 'TP', tp_price
        elif high >= sl_price:
            return 'SL', sl_price
    
    return None, None

def calculate_pnl(entry_price, exit_price, signal_type):
    """
    Calculate PnL in USD
    
    Args:
        entry_price: float
        exit_price: float
        signal_type: str - 'LONG' or 'SHORT'
    
    Returns:
        float: PnL in USD
    """
    if signal_type == 'LONG':
        return exit_price - entry_price
    else:  # SHORT
        return entry_price - exit_price

def calculate_pnl_percentage(entry_price, exit_price, signal_type):
    """
    Calculate PnL as percentage
    
    Args:
        entry_price: float
        exit_price: float
        signal_type: str - 'LONG' or 'SHORT'
    
    Returns:
        float: PnL as percentage
    """
    if signal_type == 'LONG':
        return ((exit_price - entry_price) / entry_price) * 100
    else:  # SHORT
        return ((entry_price - exit_price) / entry_price) * 100

def get_candle_amplitude_percentage(candle):
    """
    Calculate candle amplitude as percentage
    
    Args:
        candle: dict - Candle data with open and close
    
    Returns:
        float: Amplitude as percentage (open-close)/open * 100
    """
    return abs(candle['close'] - candle['open']) / candle['open'] * 100

def is_within_trading_hours(timestamp, start_time_str, end_time_str):
    """
    Check if timestamp is within trading hours
    
    Args:
        timestamp: datetime - Time to check
        start_time_str: str - Start time in HH:MM format
        end_time_str: str - End time in HH:MM format
    
    Returns:
        bool: True if within trading hours, False otherwise
    """
    try:
        # Parse time strings
        start_hour, start_min = map(int, start_time_str.split(':'))
        end_hour, end_min = map(int, end_time_str.split(':'))
        
        # Get timestamp hour and minute
        current_hour = timestamp.hour
        current_min = timestamp.minute
        
        # Convert to minutes for easier comparison
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        current_minutes = current_hour * 60 + current_min
        
        # Handle case where trading window crosses midnight
        if end_minutes < start_minutes:
            # Window crosses midnight (e.g., 23:00 to 02:00)
            return current_minutes >= start_minutes or current_minutes <= end_minutes
        else:
            # Normal window (e.g., 16:00 to 23:00)
            return start_minutes <= current_minutes <= end_minutes
            
    except (ValueError, AttributeError) as e:
        # If there's an error parsing time, default to allowing trade
        return True

def format_datetime(dt):
    """Format datetime to string"""
    if isinstance(dt, str):
        return dt
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def parse_datetime(dt_str):
    """Parse datetime string to datetime object"""
    if isinstance(dt_str, datetime):
        return dt_str
    return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')

def create_directories():
    """Create necessary directories"""
    directories = ['logs', 'exports', 'data']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def save_results_to_csv(results, filename_prefix="backtest_results"):
    """
    Save backtest results to CSV file
    
    Args:
        results: list of dict - Backtest results
        filename_prefix: str - Prefix for filename
    
    Returns:
        str: Path to saved file
    """
    if not results:
        return None
    
    create_directories()
    
    # Convert results to DataFrame
    df = pd.DataFrame(results)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"exports/{filename_prefix}_{timestamp}.csv"
    
    # Save to CSV
    df.to_csv(filename, index=False)
    
    return filename

def calculate_win_rate(results):
    """
    Calculate win rate from backtest results
    
    Args:
        results: list of dict - Backtest results with 'result' field
    
    Returns:
        dict: Statistics including win_rate, total_trades, wins, losses
    """
    if not results:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'total_pnl_percentage': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0
        }
    
    total_trades = len(results)
    wins = sum(1 for r in results if r['result'] == 'WIN')
    losses = total_trades - wins
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0.0
    
    total_pnl = sum(r['pnl'] for r in results)
    
    # Calculate total %PNL as sum of all individual pnl_percentage
    total_pnl_percentage = sum(r.get('pnl_percentage', 0.0) for r in results)
    
    win_pnls = [r['pnl'] for r in results if r['result'] == 'WIN']
    loss_pnls = [r['pnl'] for r in results if r['result'] == 'LOSS']
    
    avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
    avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
    
    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'total_pnl_percentage': total_pnl_percentage,
        'avg_win': avg_win,
        'avg_loss': avg_loss
    }

def print_backtest_summary(results):
    """Print backtest summary statistics"""
    stats = calculate_win_rate(results)
    
    print("\n" + "="*50)
    print("BACKTEST SUMMARY")
    print("="*50)
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Wins: {stats['wins']}")
    print(f"Losses: {stats['losses']}")
    print(f"Win Rate: {stats['win_rate']:.2f}%")
    print(f"Total PnL: ${stats['total_pnl']:.4f}")
    print(f"Total PnL%: {stats['total_pnl_percentage']:.4f}%")
    print(f"Average Win: ${stats['avg_win']:.4f}")
    print(f"Average Loss: ${stats['avg_loss']:.4f}")
    print("="*50)