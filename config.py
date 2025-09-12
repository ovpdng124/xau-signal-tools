import os
from dotenv import load_dotenv

load_dotenv()

# Twelve Data API Configuration
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")
TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:Abc123%40%40@localhost:5432/xau_signals")

# Crawl Settings
CRAWL_START_DATE = os.getenv("CRAWL_START_DATE", "2024-01-01 00:00:00")
CRAWL_END_DATE = os.getenv("CRAWL_END_DATE", "2024-12-31 23:59:59")

# Backtest Settings
BACKTEST_START_DATE = os.getenv("BACKTEST_START_DATE", "2024-01-01 00:00:00")
BACKTEST_END_DATE = os.getenv("BACKTEST_END_DATE", "2024-12-31 23:59:59")

# Trading Parameters (in USD)
TP_AMOUNT = float(os.getenv("TP_AMOUNT", 6.0))
SL_AMOUNT = float(os.getenv("SL_AMOUNT", 3.0))

# Timeframe in minutes
TIMEFRAME = int(os.getenv("TIMEFRAME", 15))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")

# Symbol Configuration  
SYMBOL = os.getenv("SYMBOL", "XAU/USD")  # Gold/USD symbol for Twelve Data time_series

# Rate Limiting - Twelve Data free plan: 8 requests/minute, 800 requests/day
API_RATE_LIMIT_PER_MINUTE = 8
API_RATE_LIMIT_PER_DAY = 800
MAX_POINTS_PER_REQUEST = 5000  # Maximum data points per request