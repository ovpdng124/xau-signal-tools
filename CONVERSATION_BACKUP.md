# XAU Signal Tools - Conversation Backup & Context

## 📋 Current Project Status

**Project:** XAU/USD Signal Detection & Trading System  
**Phase:** Daemon Scheduler Development & Timezone Fixes  
**Last Updated:** 2025-09-15  
**Platform:** Moving from macOS to Windows for MT5 testing

## 🎯 Core Requirements & Critical Notes

### ⚠️ ĐẶC BIỆT QUAN TRỌNG - CLOSED CANDLES ONLY
**User's critical requirement:**
> "chúng ta chỉ phân tích các nến ĐÃ ĐÓNG, vì thế nến current_candle luôn luôn là nến chưa đóng"

**Examples:**
- 15:15 scheduler runs → crawl 15:00 candle (CLOSED) → save to DB
- 15:30 scheduler runs → crawl 15:15 candle (CLOSED) → save to DB  
- Current 15:15 candle is INCOMPLETE → NOT saved to DB

**Signal Detection Logic:**
- N1 = 14:30 (oldest in pattern)
- N2 = 14:45 (middle)  
- N3 = 15:00 (latest closed, newest in pattern)
- Entry time = 15:15 (notification time in UTC+3)

### 🕐 Timezone Requirements
- **MT5 Data:** UTC+3 (market timezone)
- **All Logic:** Must use UTC+3 for consistency
- **Display:** Show both UTC+3 and Vietnam time (UTC+7)
- **NO datetime.now():** Always use get_utc3_now()

### 🔄 Daemon Schedule Requirements
- **Market Intervals:** XX:00, XX:15, XX:30, XX:45 only
- **No spam crawling:** One signal per 15-minute cycle maximum
- **Precise timing:** Use schedule library, not sleep-based timing

## 🚀 Recent Major Fixes Completed

### 1. Timezone Consistency (COMPLETED ✅)
- **Fixed:** data_crawler.py timezone from UTC+7 → UTC+3
- **Fixed:** scheduler.py all datetime.now() → get_utc3_now()
- **Added:** Dual timezone display utilities in utils.py

### 2. Closed Candles Logic (COMPLETED ✅)
- **Added:** `_get_last_closed_candle_time()` in data_crawler.py
- **Fixed:** Incremental crawl only to closed candles
- **Ensured:** No incomplete candles saved to database

### 3. Signal Detection Precision (COMPLETED ✅)
- **Fixed:** signal_detector.py added end_index parameter
- **Fixed:** scheduler.py scan_for_signals call with correct params
- **Added:** entry_time = notification time logic

### 4. Schedule Library Implementation (COMPLETED ✅)
- **Replaced:** Sleep-based timing with schedule library
- **Added:** Market interval scheduling (XX:00, XX:15, XX:30, XX:45)
- **Separated:** Status updates from crawl timing

## 📁 File Structure & Key Components

```
xau-signal-tools/
├── main.py              # Entry point with daemon commands
├── scheduler.py         # Daemon scheduler (RECENTLY MODIFIED)
├── data_crawler.py      # MT5 data crawler (RECENTLY MODIFIED)  
├── signal_detector.py   # Pattern detection (RECENTLY MODIFIED)
├── backtester.py        # Backtest engine (stable)
├── telegram_utils.py    # Notifications (stable)
├── models.py           # Database models (stable)
├── utils.py            # Utilities + timezone functions (RECENTLY MODIFIED)
├── config.py           # Configuration (stable)
└── requirements.txt    # Dependencies (needs schedule added)
```

## 🔧 Current Implementation Status

### Scheduler (scheduler.py) - RECENTLY COMPLETED
**Key Features:**
- Schedule-based timing (no sleep drift)
- UTC+3 timezone consistency
- Closed candles only logic
- Single signal per cycle
- Dual timezone logging

**Recent Changes:**
```python
# Schedule jobs at market intervals
schedule.every().hour.at(":00").do(self._scheduled_crawl)
schedule.every().hour.at(":15").do(self._scheduled_crawl)
schedule.every().hour.at(":30").do(self._scheduled_crawl)
schedule.every().hour.at(":45").do(self._scheduled_crawl)

# Entry time = notification time
entry_time_utc3 = get_utc3_now()
latest_signal['entry_time'] = entry_time_utc3.replace(tzinfo=None)
```

### Data Crawler (data_crawler.py) - RECENTLY COMPLETED
**Key Features:**
- UTC+3 timezone for all operations
- Closed candles only logic
- MT5 integration (Windows only)

**Critical Method Added:**
```python
def _get_last_closed_candle_time(self, timeframe):
    """Only return timestamps of CLOSED candles"""
    # Complex logic to calculate last closed candle based on UTC+3
```

### Signal Detector (signal_detector.py) - RECENTLY COMPLETED  
**Key Features:**
- Added end_index parameter to scan_for_signals()
- Supports single candle analysis
- Engulfing and Inside Bar patterns

**Recent Changes:**
```python
def scan_for_signals(self, df, start_index=3, end_index=None):
    # Now supports range scanning for scheduler precision
```

## 🧪 Testing Requirements

### 1. Daemon Testing (PRIORITY)
```bash
# Test commands on Windows
python main.py daemon start
python main.py daemon status  
python main.py daemon stop
```

**Expected Behavior:**
- Start at any time, wait for next market interval (XX:00, XX:15, XX:30, XX:45)
- Crawl only closed candles
- Detect max 1 signal per cycle
- Show dual timezone in logs
- Entry time = notification time

### 2. Manual Crawl Testing
```bash
python main.py crawl --incremental --timeframe 15m
```

**Expected:**
- Only crawl to last closed candle
- No incomplete candles in database
- UTC+3 timestamps in logs

### 3. Signal Detection Testing
```bash
python main.py detect --start-date "2024-01-01 00:00:00" --end-date "2024-01-31 23:59:59"
```

**Expected:**
- Detect signals on closed candles only
- Entry time logic working

## ⚠️ Known Issues & Dependencies

### 1. Missing Dependencies
- **schedule library:** Not in requirements.txt
- **Installation:** Need `conda activate forex` then `pip install schedule`

### 2. Windows-Specific 
- **MT5 Available:** Only on Windows platform
- **Testing:** All MT5 functions can be tested on Windows

### 3. Database Schema
- **Migration vs Reset:** migrate doesn't alter existing tables, only reset works
- **Timeframe Column:** Added to candles table with unique constraint

## 🎯 Next Steps on Windows

### 1. Immediate Testing
1. **Install missing dependency:** `pip install schedule` 
2. **Test daemon start/stop/status**
3. **Verify MT5 connection** 
4. **Test incremental crawl**
5. **Verify timezone consistency**

### 2. Validation Checklist
- [ ] Daemon starts and waits for market intervals
- [ ] Crawl only gets closed candles  
- [ ] Signal detection returns max 1 signal
- [ ] Entry time = notification time
- [ ] Dual timezone display working
- [ ] No datetime.now() in logs (should be UTC+3)

### 3. Production Readiness
- [ ] Add schedule to requirements.txt
- [ ] Test full cycle: crawl → detect → notify
- [ ] Verify database timestamps are UTC+3
- [ ] Test Telegram notifications

## 📝 User Feedback & Preferences

### Development Style
- **Simple code:** "code đơn giản cho dễ maintenance nhé, đừng làm phức tạp hóa vấn đề lên quá"
- **Direct approach:** "đi xa quá khó về"
- **Minimal changes:** Prefer editing existing files over creating new ones

### Critical Requirements Mentioned
1. **Timezone consistency:** UTC+3 throughout system
2. **Closed candles only:** Never process incomplete candles  
3. **Market timing:** Precise 15-minute intervals (XX:00, XX:15, XX:30, XX:45)
4. **Single signal:** Max 1 signal per cycle
5. **Entry time accuracy:** entry_time = notification_time

### Installation Preferences
- **Conda environment:** Must use `conda activate forex` before pip install
- **No system pip:** Never install packages in system Python
- **Requirements.txt:** Keep dependencies tracked

## 🔄 Continuation Instructions

When continuing on Windows:

1. **Pull latest changes** from git
2. **Activate environment:** `conda activate forex`  
3. **Install dependencies:** `pip install schedule`
4. **Test daemon immediately:** `python main.py daemon start`
5. **Monitor logs** for UTC+3 timestamps and closed candle logic
6. **Verify MT5 connection** works on Windows
7. **Test full crawl cycle** with real data

## 📞 Communication Context

**User Characteristics:**
- Experienced trader familiar with MT5
- Prefers Vietnamese time display but understands UTC+3 necessity
- Values precision and accuracy over complexity
- Focused on production-ready, reliable system
- Direct communication style, specific requirements

**Technical Preferences:**
- PostgreSQL database
- Pure Python implementations (no heavy frameworks)
- Clean, maintainable code
- Comprehensive logging
- Dual timezone displays for UX

---

**Last Context:** User completed timezone and closed candle fixes on macOS, moving to Windows for MT5 testing and daemon validation. System ready for production testing.