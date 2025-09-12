import time
import threading
from collections import deque
from logger import setup_logger

logger = setup_logger()

class RateLimiter:
    def __init__(self, max_calls=60, period=60.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            
            # Remove calls outside the current window
            while self.calls and now - self.calls[0] >= self.period:
                self.calls.popleft()
            
            # If we've hit the rate limit, wait
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                    time.sleep(sleep_time)
            
            # Record this call
            self.calls.append(now)

    def acquire(self):
        """Alias for wait() to maintain compatibility with existing code"""
        self.wait()

    def reset(self):
        """Clear all recorded calls"""
        with self.lock:
            self.calls.clear()
            logger.info("Rate limiter reset")

    def get_remaining_calls(self):
        """Get number of remaining calls in current window"""
        with self.lock:
            now = time.time()
            
            # Remove calls outside the current window
            while self.calls and now - self.calls[0] >= self.period:
                self.calls.popleft()
            
            return max(0, self.max_calls - len(self.calls))

    def get_reset_time(self):
        """Get time until the rate limit window resets"""
        with self.lock:
            if not self.calls:
                return 0
            
            now = time.time()
            return max(0, self.period - (now - self.calls[0]))