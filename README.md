# XAU Signal Tools

Tool phân tích tín hiệu trading và backtesting cho thì trường vàng XAU/USD.

## Tính năng chính

- **Crawl Data**: Thu thập dữ liệu OHLCV lịch sử từ MetaTrader5
- **Import Data**: Import dữ liệu từ CSV với nhiều định dạng delimiter khác nhau
- **Signal Detection**: Phát hiện tín hiệu trading theo 2 mô hình:
  - Engulfing Pattern (Nến nhấn chìm)
  - Inside Bar Pattern
- **Backtesting**: Mô phỏng trading với TP/SL chính xác đến phút (1m precision)
- **Database**: Lưu trữ dữ liệu đa timeframe trong PostgreSQL
- **Export**: Xuất kết quả ra CSV và tạo MQL5 scripts cho MetaTrader5

## Cài đặt

### 1. Clone repository
```bash
git clone <repository-url>
cd xau-signal-tools
```

### 2. Thiết lập môi trường Python (Conda)
```bash
# Tạo môi trường conda mới (khuyến nghị)
conda create -n forex python=3.9 -y

# Kích hoạt môi trường
conda activate forex

# Hoặc nếu đã có môi trường forex
conda activate forex
```

**Lưu ý**: Từ giờ trở đi, mỗi khi sử dụng tool, bạn cần chạy `conda activate forex` trước.

### 3. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 4. Cấu hình môi trường
```bash
# Copy file cấu hình mẫu
cp .env.example .env

# Chỉnh sửa file .env và điền thông tin:
# - DATABASE_URL: Connection string PostgreSQL
# - DEFAULT_TIMEFRAME: Timeframe mặc định (1m, 5m, 15m, 30m, 1h, 4h, 1d)
# - TP_AMOUNT/SL_AMOUNT: Thông số Take Profit và Stop Loss
```

### 5. Khởi động database
```bash
# Chạy PostgreSQL container
docker-compose up -d

# Tạo schema database
python main.py migrate
```

### 6. Kiểm tra kết nối
```bash
python main.py status
```

## Hướng dẫn sử dụng

Hệ thống bao gồm 3 module chính có thể chạy độc lập:

## 1. 📋 Module Main (main.py) - Quản lý hệ thống chính

### Database Management

#### Khởi tạo database
```bash
python main.py migrate
```

#### Reset database (XÓA TOÀN BỘ DỮ LIỆU)
```bash
python main.py reset --confirm
```

#### Kiểm tra trạng thái hệ thống
```bash
python main.py status
```

### Thu thập dữ liệu (Data Crawling từ MetaTrader5)

**Lưu ý**: Chức năng này chỉ hoạt động trên Windows có cài đặt MetaTrader5

#### Crawl dữ liệu lịch sử theo timeframe
```bash
# Crawl với timeframe mặc định (từ .env)
python main.py crawl --start-date "2025-01-01 00:00:00" --end-date "2025-12-31 23:59:59"

# Crawl với timeframe cụ thể
python main.py crawl --start-date "2025-01-01 00:00:00" --end-date "2025-12-31 23:59:59" --timeframe 1m

# Sử dụng cấu hình từ .env (không cần nhập thời gian)
python main.py crawl
```

#### Crawl dữ liệu mới (incremental)
```bash
# Crawl dữ liệu mới từ thời điểm cuối cùng trong database
python main.py crawl --incremental

# Crawl incremental với timeframe cụ thể
python main.py crawl --incremental --timeframe 15m
```

#### Crawl với validation và fill gaps
```bash
python main.py crawl --start-date "2025-01-01 00:00:00" --end-date "2025-01-31 23:59:59" --validate --fill-gaps --timeframe 15m
```

### Phát hiện tín hiệu (Signal Detection)

#### Detect signals trong khoảng thời gian với timeframe
```bash
# Detect với timeframe mặc định
python main.py detect --start-date "2025-06-01 00:00:00" --end-date "2025-06-30 23:59:59"

# Detect với timeframe cụ thể
python main.py detect --start-date "2025-06-01 00:00:00" --end-date "2025-06-30 23:59:59" --timeframe 15m
```

#### Detect signals và export ra CSV
```bash
python main.py detect --start-date "2025-06-01 00:00:00" --end-date "2025-06-30 23:59:59" --timeframe 15m --export
```

### Backtesting với độ chính xác 1 phút

#### Chạy backtest với thời gian và timeframe cụ thể
```bash
# Backtest với timeframe mặc định (signals trên 15m, TP/SL check trên 1m)
python main.py backtest --start-date "2025-01-01 00:00:00" --end-date "2025-12-31 23:59:59"

# Backtest với timeframe cụ thể
python main.py backtest --start-date "2025-01-01 00:00:00" --end-date "2025-12-31 23:59:59" --timeframe 15m
```

#### Chạy backtest với cấu hình từ .env
```bash
python main.py backtest
```

**Lưu ý**: Backtesting hiện tại sẽ:
- Detect signals trên timeframe chính (VD: 15m)
- Check TP/SL trên dữ liệu 1 phút để có độ chính xác cao hơn
- Cần có cả dữ liệu timeframe chính và 1m trong database

## 2. 📥 Module Import CSV (import_csv_data.py) - Import dữ liệu từ CSV

### Import CSV với delimiter mặc định (tab-separated từ MT5)
```bash
# Import file mặc định xauusd_export.csv
python import_csv_data.py

# Import file CSV cụ thể
python import_csv_data.py --file my_data.csv
```

### Import CSV với delimiter khác nhau
```bash
# CSV phân tách bằng dấu phẩy
python import_csv_data.py --file data.csv --delimiter comma

# CSV phân tách bằng dấu chấm phẩy (định dạng châu Âu)  
python import_csv_data.py --file data.csv --delimiter semicolon

# Sử dụng ký tự trực tiếp
python import_csv_data.py --file data.csv --delimiter ";"

# CSV phân tách bằng pipe (|)
python import_csv_data.py --file data.csv --delimiter pipe

# CSV phân tách bằng khoảng trắng
python import_csv_data.py --file data.csv --delimiter space
```

### Import với timeframe cụ thể
```bash
# Auto-detect timeframe từ tên file (VD: xauusd_m15_export.csv → 15m)
python import_csv_data.py --file xauusd_m15_export.csv

# Chỉ định timeframe thủ công (ghi đè auto-detect)
python import_csv_data.py --file data.csv --timeframe 1m --delimiter comma

# Import dữ liệu 5 phút với delimiter semicolon
python import_csv_data.py --file data.csv --timeframe 5m --delimiter semicolon
```

### Import với batch size và dry-run
```bash
# Dry run để validate trước khi import thật
python import_csv_data.py --file data.csv --delimiter comma --dry-run

# Import với batch size lớn hơn (tốc độ nhanh hơn)
python import_csv_data.py --file data.csv --batch-size 5000

# Kết hợp tất cả options
python import_csv_data.py --file my_data.csv --delimiter semicolon --timeframe 15m --batch-size 2000 --dry-run
```

### Định dạng CSV yêu cầu
```csv
timestamp,open,high,low,close,volume
2025-09-12 02:31:00,3635.33,3635.50,3634.33,3634.50,100
2025-09-12 02:32:00,3634.50,3634.80,3634.10,3634.30,150
```

**Hỗ trợ delimiter**: `tab` (mặc định), `comma`, `semicolon`, `pipe`, `space` hoặc ký tự trực tiếp như `";"`, `","`

## 3. 🔧 Module Tạo MQL5 Script (create_mql5_export.py) - Xuất dữ liệu từ MT5

### Chạy script tương tác
```bash
# Chạy script và làm theo hướng dẫn trên màn hình
python create_mql5_export.py
```

### Quy trình sử dụng:

1. **Chọn phương thức export:**
   - **Option 1**: Export theo số lượng bars (VD: lấy 5000 bars gần nhất từ một ngày cụ thể)
   - **Option 2**: Export theo khoảng thời gian (từ ngày A đến ngày B)

2. **Nhập thông tin:**
   - Symbol (mặc định: XAUUSD)
   - Timeframe (M1, M5, M15, M30, H1, H4, D1)
   - Thông số tương ứng với option đã chọn

3. **Kết quả:**
   - Script MQL5 (.mq5) sẽ được tạo trong thư mục hiện tại
   - Copy script vào MetaEditor, compile (F7) và chạy (F5)
   - File CSV sẽ được tạo trong thư mục MQL5/Files/

### Ví dụ outputs:
```bash
# Option 1 - Export by bars count
✅ Created: XAUUSDExport_M15_5000bars.mq5
📏 Gets 5000 bars going backward from 2025.09.14 23:59

# Option 2 - Export by date range  
✅ Created: XAUUSDExport_M15_range.mq5
📅 Gets data from 2025.01.01 to 2025.09.14
```

### Sử dụng MQL5 Scripts:
1. Mở MetaTrader5
2. Copy script .mq5 vào MetaEditor
3. Compile script (F7)
4. Chạy script (F5)
5. Tìm file CSV trong thư mục `MQL5/Files/`
6. Import CSV vào hệ thống bằng `import_csv_data.py`

## Cấu hình

Các thông số cấu hình trong file `.env`:

```env
# Trading Symbol
SYMBOL=XAU/USD

# Database
DATABASE_URL=postgresql://postgres:Abc123%40%40@localhost:5432/xau_signals

# Crawl Settings
CRAWL_START_DATE=2025-06-12 00:00:00
CRAWL_END_DATE=2025-09-12 23:59:59

# Backtest Settings  
BACKTEST_START_DATE=2025-01-01 00:00:00
BACKTEST_END_DATE=2025-09-13 23:59:59

# Trading Parameters (USD)
TP_AMOUNT=2.0    # Take Profit: $2
SL_AMOUNT=1.0    # Stop Loss: $1

# Timeframe Configuration
DEFAULT_TIMEFRAME=15m  # Hỗ trợ: 1m, 5m, 15m, 30m, 1h, 4h, 1d

# Backtest Configuration
ENABLE_TIMEOUT=false     # Bật/tắt timeout cho orders
TIMEOUT_HOURS=0          # Số giờ timeout (0 = không timeout)

# Trading Time Window Configuration
ENABLE_TIME_WINDOW=false    # Bật/tắt giới hạn khung giờ giao dịch
TRADE_START_TIME=16:00      # Thời gian bắt đầu giao dịch (HH:MM)
TRADE_END_TIME=23:00        # Thời gian kết thúc giao dịch (HH:MM)

# Single Order Mode Configuration
ENABLE_SINGLE_ORDER_MODE=true  # Bật/tắt chế độ chỉ 1 order tại một thời điểm

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
```

## Logic Signal Detection

### Điều kiện 1 - Engulfing Pattern (Nến nhấn chìm)
- **SHORT**: N1 xanh + N2 đỏ + open_N1 > close_N2
- **LONG**: N1 đỏ + N2 xanh + open_N1 > close_N2

### Điều kiện 2 - Inside Bar Pattern
- **SHORT**: N1 xanh + N2&N3 đỏ + biên_độ_N1 < biên_độ_tổng_hợp_(N2+N3)
- **LONG**: N1 đỏ + N2&N3 xanh + biên_độ_N1 < biên_độ_tổng_hợp_(N2+N3)

### Quy ước
- **N1**: Nến lookback 3 (xa nhất)
- **N2**: Nến lookback 2 (giữa)
- **N3**: Nến lookback 1 (gần nhất, nến entry)
- **Nến xanh**: close > open
- **Nến đỏ**: close < open

## Kết quả Backtesting

Sau khi chạy backtest, tool sẽ hiển thị:

```
BACKTEST SUMMARY
==================================================
Total Trades: 145
Wins: 87
Losses: 58
Win Rate: 60.00%
Total PnL: $127.4500
Average Win: $4.8200
Average Loss: -$2.9100
==================================================

DETAILED ANALYSIS:
LONG Trades: 72 (Win Rate: 58.33%)
SHORT Trades: 73 (Win Rate: 61.64%)
Engulfing Pattern: 89 (Win Rate: 62.92%)
Inside Bar Pattern: 56 (Win Rate: 55.36%)
Average Trade Duration: 142.3 minutes
```

Kết quả được tự động export ra file CSV trong thư mục `exports/`.

## Cấu trúc files

```
xau-signal-tools/
├── main.py                 # Entry point CLI
├── config.py               # Cấu hình từ ENV
├── logger.py               # Logging system
├── models.py               # Database models
├── RateLimiter.py          # API rate limiting
├── api_client.py           # Finnhub API client
├── utils.py                # Helper functions
├── data_crawler.py         # Data crawling logic
├── signal_detector.py      # Signal detection logic
├── backtester.py           # Backtesting engine
├── requirements.txt        # Dependencies
├── .env.example           # Environment template
├── docker-compose.yml     # PostgreSQL setup
├── init.sql               # Database schema
└── README.md              # Hướng dẫn sử dụng
```

## Quy trình làm việc khuyến nghị

### 1. Setup lần đầu
```bash
# Kích hoạt môi trường conda
conda activate forex

# Khởi động database
docker-compose up -d

# Tạo schema database (với support timeframe)
python main.py migrate

# Kiểm tra kết nối
python main.py status
```

### 2. Thu thập dữ liệu từ MetaTrader5 (Windows)
```bash
# Option A: Trực tiếp crawl từ MT5 (chỉ Windows)
python main.py crawl --start-date "2025-01-01 00:00:00" --end-date "2025-01-31 23:59:59" --timeframe 15m --validate --fill-gaps

# Crawl thêm dữ liệu 1m để có precision cao cho backtesting
python main.py crawl --start-date "2025-01-01 00:00:00" --end-date "2025-01-31 23:59:59" --timeframe 1m
```

### 3. Hoặc thu thập dữ liệu từ CSV (tất cả OS)
```bash
# Bước 1: Tạo MQL5 script để export từ MT5
python create_mql5_export.py
# Chọn Option 2 → Date range → 2025.01.01 to 2025.01.31 → M15

# Bước 2: Chạy script trong MT5 → Lấy CSV file

# Bước 3: Import CSV vào database
python import_csv_data.py --file xauusd_m15_range_export.csv --timeframe 15m

# Bước 4: Import thêm data 1m để có precision
python create_mql5_export.py  # Tạo script M1
python import_csv_data.py --file xauusd_m1_range_export.csv --timeframe 1m
```

### 4. Test signal detection
```bash
# Detect signals trên dữ liệu 15m
python main.py detect --start-date "2025-01-01 00:00:00" --end-date "2025-01-31 23:59:59" --timeframe 15m --export
```

### 5. Chạy backtest với 1m precision
```bash
# Backtest: signals trên 15m + TP/SL check trên 1m
python main.py backtest --start-date "2025-01-01 00:00:00" --end-date "2025-01-31 23:59:59" --timeframe 15m
```

### 6. Phân tích kết quả
- Kiểm tra file CSV trong thư mục `exports/`
- Xem logs chi tiết trong thư mục `logs/`
- So sánh win rate với/không có 1m precision
- Adjust parameters TP_AMOUNT/SL_AMOUNT nếu cần

## Troubleshooting

### Lỗi MetaTrader5 (Windows)
```bash
# Kiểm tra MT5 có được cài đặt và chạy không
# Crawl chỉ hoạt động trên Windows với MT5

# Nếu lỗi MT5, sử dụng CSV workflow:
python create_mql5_export.py  # Tạo script
# Chạy script trong MT5 manually → Lấy CSV
python import_csv_data.py --file exported.csv
```

### Lỗi database
```bash
# Reset và tạo lại database với timeframe support
python main.py reset --confirm
python main.py migrate
```

### Lỗi import CSV
```bash
# Kiểm tra format CSV và delimiter
python import_csv_data.py --file data.csv --dry-run

# Thử delimiter khác nhau
python import_csv_data.py --file data.csv --delimiter comma --dry-run
python import_csv_data.py --file data.csv --delimiter semicolon --dry-run
```

### Lỗi backtesting - thiếu dữ liệu 1m
```bash
# Backtesting cần cả dữ liệu timeframe chính VÀ 1m
# Kiểm tra data hiện có
python main.py status

# Import thêm dữ liệu 1m nếu thiếu
python create_mql5_export.py  # Tạo M1 script
python import_csv_data.py --file xauusd_m1_export.csv --timeframe 1m
```

### Không có dữ liệu
```bash
# Kiểm tra data trong database theo timeframe
python main.py status

# Crawl/Import dữ liệu mới
python main.py crawl --start-date "2025-01-01 00:00:00" --end-date "2025-01-31 23:59:59" --timeframe 15m
```

## Support

Nếu gặp vấn đề, hãy kiểm tra:

1. **Database**: `docker ps` để xem PostgreSQL có chạy không
2. **Logs**: Kiểm tra thư mục `logs/` để xem chi tiết lỗi
3. **Status**: Chạy `python main.py status` để kiểm tra tổng thể
4. **Data**: Đảm bảo có đủ dữ liệu timeframe cần thiết cho backtesting
5. **CSV Format**: Sử dụng `--dry-run` để validate CSV trước khi import
6. **MetaTrader5**: Workflow CSV hoạt động trên mọi OS, không cần MT5 trực tiếp