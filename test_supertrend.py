#!/usr/bin/env python3
"""
Test SuperTrend calculation logic
"""

import pandas as pd
import numpy as np
from datetime import datetime
from models import Database
from logger import setup_logger

logger = setup_logger()

def calculate_supertrend_test(df, atr_period=10, multiplier=3.2):
    """
    Calculate SuperTrend indicator using corrected logic
    """
    df = df.copy()
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"Input data: {len(df)} candles from {df.iloc[0]['timestamp']} to {df.iloc[-1]['timestamp']}")
    
    # Calculate True Range
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            np.abs(df['high'] - df['prev_close']),
            np.abs(df['low'] - df['prev_close'])
        )
    )
    df['tr'] = df['tr'].fillna(df['high'] - df['low'])
    
    # Calculate ATR using SMA
    df['atr'] = df['tr'].rolling(window=atr_period).mean()
    df['atr'] = df['atr'].fillna(df['tr'])
    
    # Calculate HL2 source
    df['hl2'] = (df['high'] + df['low']) / 2
    
    # Calculate basic upper and lower bands
    df['basic_up'] = df['hl2'] - (multiplier * df['atr'])
    df['basic_dn'] = df['hl2'] + (multiplier * df['atr'])
    
    # Initialize final bands
    df['up'] = df['basic_up'].copy()
    df['dn'] = df['basic_dn'].copy()
    df['trend'] = -1  # Start with downtrend
    
    # Apply Pine Script logic
    for i in range(1, len(df)):
        prev_close = df.iloc[i-1]['close']
        prev_up = df.iloc[i-1]['up'] 
        prev_dn = df.iloc[i-1]['dn']
        prev_trend = df.iloc[i-1]['trend']
        
        current_basic_up = df.iloc[i]['basic_up']
        current_basic_dn = df.iloc[i]['basic_dn']
        current_close = df.iloc[i]['close']
        
        # Pine Script logic
        if prev_close > prev_up:
            final_up = max(current_basic_up, prev_up)
        else:
            final_up = current_basic_up
        df.iloc[i, df.columns.get_loc('up')] = final_up
        
        if prev_close < prev_dn:
            final_dn = min(current_basic_dn, prev_dn)
        else:
            final_dn = current_basic_dn
        df.iloc[i, df.columns.get_loc('dn')] = final_dn
        
        # Trend logic
        if prev_trend == -1 and current_close > prev_dn:
            new_trend = 1
        elif prev_trend == 1 and current_close < prev_up:
            new_trend = -1
        else:
            new_trend = prev_trend
        df.iloc[i, df.columns.get_loc('trend')] = new_trend
    
    # Calculate SuperTrend line
    df['supertrend_line'] = np.where(df['trend'] == 1, df['up'], df['dn'])
    df['trend_direction'] = np.where(df['trend'] == 1, 'UP', 'DN')
    
    return df

def main():
    """Test SuperTrend calculation"""
    try:
        # Connect to database
        db = Database()
        
        # Load data from 2025-09-12 17:00 to 2025-09-16 17:00
        start_date = datetime.strptime("2025-09-12 17:00:00", "%Y-%m-%d %H:%M:%S")
        end_date = datetime.strptime("2025-09-16 18:30:00", "%Y-%m-%d %H:%M:%S")
        
        print(f"Loading 15m data from {start_date} to {end_date}")
        
        df = db.load_candles(start_date, end_date, '15m')
        
        if df.empty:
            print("No data found!")
            return
            
        print(f"Loaded {len(df)} candles")
        
        # Calculate SuperTrend
        df_with_st = calculate_supertrend_test(df)
        
        print("\n" + "="*60)
        print("SUPERTREND LINE VALUES (CORRECTED)")
        print("="*60)
        print("Format: YYYY.MM.DD HH:MM: SUPERTREND_LINE_PRICE (trend)")
        print("="*60)
        
        # Print results in requested format
        for i, row in df_with_st.iterrows():
            timestamp = row['timestamp']
            supertrend_line_price = row['supertrend_line']
            trend_direction = row['trend_direction']
            close_price = row['close']
            
            # Format: YYYY.DD.MM HH:MM: price
            formatted_time = timestamp.strftime("%Y.%d.%m %H:%M")
            
            print(f"{formatted_time}: {supertrend_line_price:.2f} ({trend_direction}) | Close: {close_price:.2f}")
        
        print("="*60)
        print(f"Total {len(df_with_st)} SuperTrend values calculated")
        
        # Validation against expected values
        print("\n" + "="*60)
        print("VALIDATION AGAINST EXPECTED VALUES:")
        print("="*60)
        
        real_values = [
            ("2025-09-12 17:00", "2025-09-12 22:15", 3653.45, "DN"),
            ("2025-09-15 04:00", "2025-09-15 05:00", 3641.31, "DN"), 
            ("2025-09-15 05:00", "2025-09-15 05:00", 3630.18, "UP"),
            ("2025-09-15 07:00", "2025-09-15 15:45", 3635.72, "UP"),
            ("2025-09-16 03:45", "2025-09-16 07:45", 3675.64, "UP"),
        ]
        
        score = 0
        for start_time, end_time, expected_line_price, expected_trend in real_values:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            
            mask = (df_with_st['timestamp'] >= start_dt) & (df_with_st['timestamp'] <= end_dt)
            period_data = df_with_st[mask]
            
            if not period_data.empty:
                avg_line_price = period_data['supertrend_line'].mean()
                most_common_trend = period_data['trend_direction'].mode()[0] if not period_data['trend_direction'].mode().empty else 'N/A'
                price_diff = abs(avg_line_price - expected_line_price)
                
                is_good = price_diff <= 0.01 and most_common_trend == expected_trend
                if is_good:
                    score += 1
                
                status = "✅" if is_good else "❌"
                print(f"{status} {start_time}: SuperTrend Line = {avg_line_price:.2f} ({most_common_trend})")
                print(f"     Expected: {expected_line_price:.2f} ({expected_trend})")
                print(f"     Difference: {price_diff:.2f}")
                print()
        
        print(f"FINAL SCORE: {score}/5")
        
        # ANALYZE TREND CHANGES with new logic
        print("\n" + "="*60)
        print("TREND CHANGES ANALYSIS (CANDLE BODY CROSSING):")
        print("="*60)
        
        trend_changes = []
        for i in range(1, len(df_with_st)):
            if df_with_st.iloc[i]['trend'] != df_with_st.iloc[i-1]['trend']:
                current = df_with_st.iloc[i]
                prev = df_with_st.iloc[i-1]
                
                # Check if body crossing logic worked
                body_top = max(current['open'], current['close'])
                body_bottom = min(current['open'], current['close'])
                
                if current['trend'] == 1:  # Changed to uptrend
                    prev_dn = prev['dn'] if 'dn' in df_with_st.columns else prev['supertrend_line']
                    crossing_check = body_top > prev_dn  # Body crosses ABOVE lower band
                    change_type = f"DN→UP (body_top {body_top:.2f} > prev_dn {prev_dn:.2f})"
                else:  # Changed to downtrend
                    prev_up = prev['up'] if 'up' in df_with_st.columns else prev['supertrend_line']
                    crossing_check = body_bottom < prev_up  # Body crosses BELOW upper band
                    change_type = f"UP→DN (body_bottom {body_bottom:.2f} < prev_up {prev_up:.2f})"
                
                status_icon = "✅" if crossing_check else "❌"
                trend_changes.append({
                    'time': current['timestamp'],
                    'change': change_type,
                    'valid': crossing_check,
                    'supertrend_line': current['supertrend_line'],
                    'close': current['close']
                })
                
                print(f"{status_icon} {current['timestamp']}: {change_type}")
                print(f"     ST Line: {current['supertrend_line']:.2f}, Close: {current['close']:.2f}")
        
        print(f"\nTotal trend changes: {len(trend_changes)}")
        valid_changes = sum(1 for tc in trend_changes if tc['valid'])
        print(f"Valid body crossings: {valid_changes}/{len(trend_changes)}")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Error in SuperTrend test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()