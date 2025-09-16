#!/usr/bin/env python3
"""
Ultra-high precision SuperTrend parameter search
Target: 0.01 point accuracy instead of 1-2 points
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from models import Database
from logger import setup_logger

logger = setup_logger()

def calculate_supertrend_precision(df, atr_period=10, multiplier=3.2, atr_method='sma'):
    """
    Ultra-precise SuperTrend calculation with multiple ATR methods
    """
    df = df.copy()
    df = df.sort_values('timestamp').reset_index(drop=True)
    
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
    
    # Different ATR calculation methods
    if atr_method == 'sma':
        df['atr'] = df['tr'].rolling(window=atr_period).mean()
    elif atr_method == 'ema':
        df['atr'] = df['tr'].ewm(span=atr_period).mean()
    elif atr_method == 'wilder':
        # Wilder's smoothing (used in TradingView)
        df['atr'] = df['tr'].ewm(alpha=1/atr_period, adjust=False).mean()
    
    df['atr'] = df['atr'].fillna(df['tr'])
    
    # Calculate HL2 source
    df['hl2'] = (df['high'] + df['low']) / 2
    
    # Calculate basic upper and lower bands
    df['basic_up'] = df['hl2'] - (multiplier * df['atr'])
    df['basic_dn'] = df['hl2'] + (multiplier * df['atr'])
    
    # Initialize final bands
    df['up'] = df['basic_up'].copy()
    df['dn'] = df['basic_dn'].copy()
    
    # Try different initial trends
    df['trend'] = -1  # Start with downtrend
    
    # Apply Pine Script logic with body crossing
    for i in range(1, len(df)):
        prev_close = df.iloc[i-1]['close']
        prev_up = df.iloc[i-1]['up'] 
        prev_dn = df.iloc[i-1]['dn']
        prev_trend = df.iloc[i-1]['trend']
        
        current_basic_up = df.iloc[i]['basic_up']
        current_basic_dn = df.iloc[i]['basic_dn']
        current_close = df.iloc[i]['close']
        current_open = df.iloc[i]['open']
        
        # up := close[1] > up1 ? max(up,up1) : up
        if prev_close > prev_up:
            final_up = max(current_basic_up, prev_up)
        else:
            final_up = current_basic_up
        df.iloc[i, df.columns.get_loc('up')] = final_up
        
        # dn := close[1] < dn1 ? min(dn, dn1) : dn
        if prev_close < prev_dn:
            final_dn = min(current_basic_dn, prev_dn)
        else:
            final_dn = current_basic_dn
        df.iloc[i, df.columns.get_loc('dn')] = final_dn
        
        # Candle body crossing logic
        candle_body_top = max(current_close, current_open)
        candle_body_bottom = min(current_close, current_open)
        
        if prev_trend == -1:  # Currently downtrend
            if candle_body_top > prev_dn:  # Body crosses above lower band
                new_trend = 1
            else:
                new_trend = prev_trend
        else:  # Currently uptrend
            if candle_body_bottom < prev_up:  # Body crosses below upper band
                new_trend = -1
            else:
                new_trend = prev_trend
        df.iloc[i, df.columns.get_loc('trend')] = new_trend
    
    # Calculate SuperTrend line
    df['supertrend_line'] = np.where(df['trend'] == 1, df['up'], df['dn'])
    df['trend_direction'] = np.where(df['trend'] == 1, 'UP', 'DN')
    
    return df

def score_precision_result(df_result):
    """Score with ultra-high precision (0.01 tolerance)"""
    real_values = [
        ("2025-09-12 17:00", "2025-09-12 22:15", 3653.45, "DN"),
        ("2025-09-15 04:00", "2025-09-15 05:00", 3641.31, "DN"), 
        ("2025-09-15 05:00", "2025-09-15 05:00", 3630.18, "UP"),
        ("2025-09-15 07:00", "2025-09-15 15:45", 3635.72, "UP"),
        ("2025-09-16 03:45", "2025-09-16 07:45", 3675.64, "UP"),
    ]
    
    score = 0
    details = []
    
    for start_time, end_time, expected_price, expected_trend in real_values:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        
        mask = (df_result['timestamp'] >= start_dt) & (df_result['timestamp'] <= end_dt)
        period_data = df_result[mask]
        
        if not period_data.empty:
            avg_price = period_data['supertrend_line'].mean()
            most_common_trend = period_data['trend_direction'].mode()[0] if not period_data['trend_direction'].mode().empty else 'N/A'
            price_diff = abs(avg_price - expected_price)
            
            # Ultra-strict: 0.01 tolerance
            is_good = price_diff <= 0.01 and most_common_trend == expected_trend
            if is_good:
                score += 1
                
            details.append({
                'period': start_time,
                'expected': expected_price,
                'actual': avg_price,
                'diff': price_diff,
                'trend_match': most_common_trend == expected_trend,
                'valid': is_good
            })
    
    return score, details

def ultra_precision_search():
    """Search for ultra-precise parameters"""
    try:
        db = Database()
        
        # Load data with context for stability
        context_start = datetime.strptime("2025-09-01 00:00:00", "%Y-%m-%d %H:%M:%S")
        end_date = datetime.strptime("2025-09-16 18:30:00", "%Y-%m-%d %H:%M:%S")
        
        df_full = db.load_candles(context_start, end_date, '15m')
        print(f"Loaded {len(df_full)} candles with context")
        
        # Ultra-fine parameter grid
        periods = [8, 9, 10, 11, 12, 13, 14]
        multipliers = [2.8, 2.9, 3.0, 3.1, 3.2, 3.3, 3.4, 3.5]
        atr_methods = ['sma', 'ema', 'wilder']
        
        best_score = 0
        best_config = None
        best_details = None
        all_results = []
        
        print("ULTRA-PRECISION PARAMETER SEARCH:")
        print("="*80)
        print("Target: 0.01 point accuracy (±0.01)")
        print("="*80)
        
        total_combinations = len(periods) * len(multipliers) * len(atr_methods)
        current = 0
        
        for atr_method in atr_methods:
            for period in periods:
                for mult in multipliers:
                    current += 1
                    print(f"Progress: {current}/{total_combinations} | Testing: Period={period}, Mult={mult}, ATR={atr_method}")
                    
                    # Calculate SuperTrend
                    df_st = calculate_supertrend_precision(df_full, atr_period=period, multiplier=mult, atr_method=atr_method)
                    
                    # Score the result
                    score, details = score_precision_result(df_st)
                    
                    result = {
                        'period': period,
                        'multiplier': mult,
                        'atr_method': atr_method,
                        'score': score,
                        'details': details
                    }
                    all_results.append(result)
                    
                    if score > best_score:
                        best_score = score
                        best_config = (period, mult, atr_method)
                        best_details = details
                    
                    if score == 5:  # Perfect score
                        print(f"🎯 PERFECT SCORE FOUND: Period={period}, Mult={mult}, ATR={atr_method}")
                        break
                
                if best_score == 5:
                    break
            if best_score == 5:
                break
        
        print("\n" + "="*80)
        print("ULTRA-PRECISION SEARCH RESULTS:")
        print("="*80)
        
        if best_score == 5:
            period, mult, atr_method = best_config
            print(f"🎯 PERFECT MATCH FOUND!")
            print(f"Parameters: Period={period}, Multiplier={mult}, ATR={atr_method}")
            print(f"Score: {best_score}/5")
        else:
            print(f"Best score achieved: {best_score}/5")
            if best_config:
                period, mult, atr_method = best_config
                print(f"Best parameters: Period={period}, Multiplier={mult}, ATR={atr_method}")
        
        if best_details:
            print("\nDETAILED RESULTS:")
            print("-" * 60)
            for detail in best_details:
                status = "✅" if detail['valid'] else "❌"
                print(f"{status} {detail['period']}: Expected={detail['expected']:.2f}, Actual={detail['actual']:.2f}, Diff={detail['diff']:.4f}")
        
        # Show top 5 results
        print(f"\nTOP 5 CONFIGURATIONS:")
        print("-" * 60)
        sorted_results = sorted(all_results, key=lambda x: (-x['score'], min(d['diff'] for d in x['details'])))
        
        for i, result in enumerate(sorted_results[:5]):
            avg_diff = sum(d['diff'] for d in result['details']) / len(result['details'])
            print(f"{i+1}. Period={result['period']}, Mult={result['multiplier']}, ATR={result['atr_method']} | Score={result['score']}/5, Avg_Diff={avg_diff:.4f}")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("RUNNING: test_precision_supertrend.py")
    print("Ultra-precision SuperTrend parameter search (0.01 accuracy target)")
    ultra_precision_search()