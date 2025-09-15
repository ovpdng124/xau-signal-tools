import pandas as pd
from datetime import datetime, timedelta
from utils import is_green_candle, is_red_candle, get_candle_body_range, get_candle_amplitude_percentage
from logger import setup_logger

logger = setup_logger()

class SignalDetector:
    def __init__(self):
        logger.info("Signal detector initialized")

    def detect_signal(self, n1, n2, n3):
        """
        Detect trading signals based on two conditions:
        1. Engulfing candle pattern (uses N2, N3 as lookback 2, 1)
        2. Inside bar pattern (uses N1, N2, N3 as lookback 3, 2, 1)
        
        Prerequisites:
        - All 3 candles must have amplitude > 0.02%
        - Amplitude difference between candles must be > 0.01%
        
        Args:
            n1: dict - Candle 1 (lookback 3)
            n2: dict - Candle 2 (lookback 2) 
            n3: dict - Candle 3 (lookback 1) - Entry candle
        
        Returns:
            dict: Signal information or None if no signal
        """

        # Check Condition 1: Engulfing pattern (N2 vs N3, entry at N3)
        engulfing_signal = self._check_engulfing_pattern(n2, n3)
        if engulfing_signal and self._check_prerequisite_conditions(n1, n2, n3, 'engulfing'):
            return {
                'signal_type': engulfing_signal,
                'condition': 'ENGULFING',
                'entry_price': n3['close'],  # Entry at N3 close price
                'timestamp': n3['timestamp'] + timedelta(minutes=15),
                'details': {
                    'engulfing_n1': self._candle_info(n2),  # N2 is N1 for engulfing
                    'engulfing_n2': self._candle_info(n3),  # N3 is N2 for engulfing
                    'entry_candle': self._candle_info(n3)
                }
            }
        
        # Check Condition 2: Inside bar pattern (N1, N2, N3, entry at N3)
        inside_bar_signal = self._check_inside_bar_pattern(n1, n2, n3)
        if inside_bar_signal and self._check_prerequisite_conditions(n1, n2, n3, 'inside_bar'):
            return {
                'signal_type': inside_bar_signal,
                'condition': 'INSIDE_BAR',
                'entry_price': n3['close'],  # Entry at N3 close price
                'timestamp': n3['timestamp'] + timedelta(minutes=15),
                'details': {
                    'inside_n1': self._candle_info(n1),  # N1 for inside bar
                    'inside_n2': self._candle_info(n2),  # N2 for inside bar
                    'inside_n3': self._candle_info(n3),  # N3 for inside bar (entry)
                }
            }
        
        return None

    def _check_prerequisite_conditions(self, n1, n2, n3, signal = 'inside_bar'):
        """
        Check prerequisite conditions before pattern detection
        
        Conditions:
        - All 3 candles must have amplitude > 0.02%
        - Amplitude difference between candles must be > 0.01%
        
        Args:
            n1: dict - Candle 1
            n2: dict - Candle 2 
            n3: dict - Candle 3
        
        Returns:
            bool: True if prerequisites are met, False otherwise
        """
        # Calculate amplitude percentages for all 3 candles
        amp1 = get_candle_amplitude_percentage(n1)
        amp2 = get_candle_amplitude_percentage(n2)
        amp3 = get_candle_amplitude_percentage(n3)
        
        # Check if all amplitudes are > 0.02%
        if signal == 'engulfing':
            if amp2 < 0.02 or amp3 < 0.02:
                logger.debug(f"Amplitude check failed for signal ENGULFING: N2={amp2:.4f}%, N3={amp3:.4f}% (all must be > 0.02%)")
                return False
        else:
            if amp1 < 0.02 or amp2 < 0.02 or amp3 < 0.02:
                logger.debug(f"Amplitude check failed for signal INSIDE_BAR: N1={amp1:.4f}%, N2={amp2:.4f}%, N3={amp3:.4f}% (all must be > 0.02%)")
                return False
        
        # Check amplitude differences > 0.01% - Tạm thời xóa, sau 2 phiên bản update ko xài nữa thì clear hẳn.
        # diff_12 = abs(amp1 - amp2)
        # diff_23 = abs(amp2 - amp3)
        # diff_13 = abs(amp1 - amp3)
        #
        # if signal == 'engulfing':
        #     if diff_23 < 0.01:
        #         logger.debug(f"Amplitude difference check failed: diff_12={diff_23:.4f}% (all must be > 0.01%)")
        #         return False
        # else:
        #     if diff_12 < 0.01 or diff_23 < 0.01 or diff_13 < 0.01:
        #         logger.debug(f"Amplitude difference check failed: diff_12={diff_12:.4f}%, diff_23={diff_23:.4f}%, diff_13={diff_13:.4f}% (all must be > 0.01%)")
        #         return False
        
        logger.debug(f"Prerequisites passed: Amplitudes N1={amp1:.4f}%, N2={amp2:.4f}%, N3={amp3:.4f}%")
        return True

    def _check_engulfing_pattern(self, n1, n2):
        """
        Check for engulfing candle pattern (2-candle lookback)
        
        Condition 1:
        - SHORT: N1 green AND N2 red AND open_N1 > close_N2
        - LONG: N1 red AND N2 green AND open_N1 < close_N2
        
        Args:
            n1: dict - Candle 1 (lookback 2)
            n2: dict - Candle 2 (lookback 1, entry candle)
            
        Returns:
            str: 'LONG', 'SHORT' or None
        """
        n1_green = is_green_candle(n1)
        n1_red = is_red_candle(n1)
        n2_green = is_green_candle(n2)
        n2_red = is_red_candle(n2)
        
        open_n1 = n1['open']
        close_n2 = n2['close']
        
        # SHORT: N1 green AND N2 red AND open_N1 > close_N2
        if n1_green and n2_red and open_n1 > close_n2:
            logger.debug(f"Engulfing SHORT signal detected: N1 green, N2 red, open_N1({open_n1}) > close_N2({close_n2})")
            return 'SHORT'
        
        # LONG: N1 red AND N2 green AND open_N1 < close_N2  
        if n1_red and n2_green and open_n1 < close_n2:
            logger.debug(f"Engulfing LONG signal detected: N1 red, N2 green, open_N1({open_n1}) < close_N2({close_n2})")
            return 'LONG'
        
        return None

    def _check_inside_bar_pattern(self, n1, n2, n3):
        """
        Check for inside bar pattern (3-candle lookback)
        
        Condition 2:
        - SHORT: N1 green AND N2 red AND N3 red AND N1_body_range < (N2+N3)_combined_range AND N2_body_range < N1_body_range
        - LONG: N1 red AND N2 green AND N3 green AND N1_body_range < (N2+N3)_combined_range AND N2_body_range < N1_body_range
        
        Args:
            n1: dict - Candle 1 (lookback 3)
            n2: dict - Candle 2 (lookback 2)
            n3: dict - Candle 3 (lookback 1, entry candle)
            
        Returns:
            str: 'LONG', 'SHORT' or None
        """
        n1_green = is_green_candle(n1)
        n1_red = is_red_candle(n1)
        n2_green = is_green_candle(n2)
        n2_red = is_red_candle(n2)
        n3_green = is_green_candle(n3)
        n3_red = is_red_candle(n3)
        
        # Calculate N1 and N2 body ranges
        n1_body_range = get_candle_body_range(n1)
        n2_body_range = get_candle_body_range(n2)
        
        # Additional condition: N2 body range must be smaller than N1 body range
        if n2_body_range >= n1_body_range:
            return None
        
        # Calculate combined N2+N3 range based on their colors
        if n2_red and n3_red:
            # Both red: take from highest open to lowest close
            combined_range = abs(n2['open'] - n3['close'])
        elif n2_green and n3_green:
            # Both green: take from highest close to lowest open  
            combined_range = abs(n3['close'] - n2['open'])
        else:
            # Different colors: not valid for inside bar pattern
            return None
        
        # N1 body must be smaller than combined N2+N3 range
        if n1_body_range >= combined_range:
            return None
        
        # SHORT: N1 green AND N2 red AND N3 red
        if n1_green and n2_red and n3_red:
            logger.debug(f"Inside bar SHORT signal: N1 green, N2&N3 red, N1_range({n1_body_range:.5f}) < combined({combined_range:.5f}), N2_range({n2_body_range:.5f}) < N1_range({n1_body_range:.5f})")
            return 'SHORT'
        
        # LONG: N1 red AND N2 green AND N3 green
        if n1_red and n2_green and n3_green:
            logger.debug(f"Inside bar LONG signal: N1 red, N2&N3 green, N1_range({n1_body_range:.5f}) < combined({combined_range:.5f}), N2_range({n2_body_range:.5f}) < N1_range({n1_body_range:.5f})")
            return 'LONG'
        
        return None

    def _candle_info(self, candle):
        """Get candle information for logging/debugging"""
        color = 'green' if is_green_candle(candle) else 'red'
        body_range = get_candle_body_range(candle)
        
        return {
            'timestamp': candle['timestamp'],
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'color': color,
            'body_range': body_range
        }

    def scan_for_signals(self, df, start_index=3, end_index=None):
        """
        Scan DataFrame for signals starting from specified index
        
        Args:
            df: DataFrame - OHLCV data sorted by timestamp DESC (latest first)
            start_index: int - Starting index (default 3 for lookback 3)
            end_index: int - Ending index (default None = scan all from start_index)
            
        Returns:
            list: List of detected signals
        """
        signals = []
        
        if len(df) < start_index + 1:
            logger.warning(f"Not enough data for signal detection. Need at least {start_index + 1} candles, got {len(df)}")
            return signals
        
        # Determine end point for scanning
        if end_index is None:
            end_point = len(df)
        else:
            end_point = min(end_index + 1, len(df))  # +1 because range is exclusive
        
        # Iterate through DataFrame starting from start_index to end_point
        for i in range(start_index, end_point):
            # Get the three lookback candles
            # Note: df is sorted DESC, so index 0 is latest
            n3 = df.iloc[i-3].to_dict()  # lookback 1 (most recent)
            n2 = df.iloc[i-2].to_dict()  # lookback 2
            n1 = df.iloc[i-1].to_dict()  # lookback 3 (oldest)
            
            # Detect signal
            signal = self.detect_signal(n1, n2, n3)
            
            if signal:
                logger.info(f"Signal detected at {signal['timestamp']}: {signal['signal_type']} ({signal['condition']})")
                signals.append(signal)
        
        logger.info(f"Signal scan completed. Found {len(signals)} signals")
        return signals

    def detect_signal_at_time(self, df, target_time):
        """
        Detect signal at a specific time (for backtest simulation)
        
        Args:
            df: DataFrame - OHLCV data sorted by timestamp ASC
            target_time: datetime - Time to check for signal
            
        Returns:
            dict: Signal information or None
        """
        # Find the target time in DataFrame
        target_candles = df[df['timestamp'] <= target_time].tail(3)
        
        if len(target_candles) < 3:
            return None
        
        # Get N1, N2, N3 (ordered chronologically)
        n1 = target_candles.iloc[0].to_dict()  # oldest
        n2 = target_candles.iloc[1].to_dict()  # middle  
        n3 = target_candles.iloc[2].to_dict()  # newest (target time)
        
        return self.detect_signal(n1, n2, n3)