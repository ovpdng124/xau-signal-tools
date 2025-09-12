# XAU Signal Tools

Tool phân tích tín hiệu trading và backtesting cho thị trường vàng XAU/USD.

## Tính năng chính

- **Crawl Data**: Thu thập dữ liệu OHLCV lịch sử từ Twelve Data API
- **Signal Detection**: Phát hiện tín hiệu trading theo 2 mô hình:
  - Engulfing Pattern (Nến nhấn chìm)
  - Inside Bar Pattern
- **Backtesting**: Mô phỏng trading với TP/SL theo giá tuyệt đối
- **Database**: Lưu trữ dữ liệu trong PostgreSQL
- **Export**: Xuất kết quả ra CSV để phân tích

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
# - TWELVE_DATA_API_KEY: API key từ twelvedata.com
# - DATABASE_URL: Connection string PostgreSQL
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

## Cách sử dụng

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

### Thu thập dữ liệu (Data Crawling)

#### Crawl dữ liệu lịch sử theo khoảng thời gian
```bash
# Với thời gian cụ thể
python main.py crawl --start-date "2024-01-01 00:00:00" --end-date "2024-12-31 23:59:59"

# Sử dụng cấu hình từ .env (không cần nhập thời gian)
python main.py crawl
```

#### Crawl dữ liệu mới (incremental)
```bash
python main.py crawl --incremental
```

#### Crawl với validation và fill gaps
```bash
python main.py crawl --start-date "2024-01-01 00:00:00" --end-date "2024-01-31 23:59:59" --validate --fill-gaps
```

### Phát hiện tín hiệu (Signal Detection)

#### Detect signals trong khoảng thời gian
```bash
python main.py detect --start-date "2024-06-01 00:00:00" --end-date "2024-06-30 23:59:59"
```

#### Detect signals và export ra CSV
```bash
python main.py detect --start-date "2024-06-01 00:00:00" --end-date "2024-06-30 23:59:59" --export
```

### Backtesting

#### Chạy backtest với thời gian cụ thể
```bash
python main.py backtest --start-date "2024-01-01 00:00:00" --end-date "2024-12-31 23:59:59"
```

#### Chạy backtest với cấu hình từ .env
```bash
python main.py backtest
```

## Cấu hình

Các thông số cấu hình trong file `.env`:

```env
# Twelve Data API
TWELVE_DATA_API_KEY=your_twelve_data_api_key_here

# Database
DATABASE_URL=postgresql://postgres:Abc123%40%40@localhost:5432/xau_signals

# Crawl Settings
CRAWL_START_DATE=2024-01-01 00:00:00
CRAWL_END_DATE=2024-12-31 23:59:59

# Backtest Settings
BACKTEST_START_DATE=2024-01-01 00:00:00
BACKTEST_END_DATE=2024-12-31 23:59:59

# Trading Parameters (in USD)
TP_AMOUNT=6.0    # Take Profit: $0.006
SL_AMOUNT=3.0    # Stop Loss: $0.003

# Timeframe
TIMEFRAME=15     # 15 minutes

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

# Tạo schema
python main.py migrate

# Kiểm tra kết nối
python main.py status
```

### 2. Thu thập dữ liệu
```bash
# Crawl dữ liệu 1 tháng để test (hoặc dùng cấu hình từ .env)
python main.py crawl --start-date "2024-01-01 00:00:00" --end-date "2024-01-31 23:59:59" --validate --fill-gaps

# Hoặc sử dụng config từ .env
python main.py crawl --validate --fill-gaps
```

### 3. Test signal detection
```bash
# Detect signals trong tháng vừa crawl
python main.py detect --start-date "2024-01-01 00:00:00" --end-date "2024-01-31 23:59:59" --export
```

### 4. Chạy backtest
```bash
# Backtest trên dữ liệu đã có
python main.py backtest --start-date "2024-01-01 00:00:00" --end-date "2024-01-31 23:59:59"
```

### 5. Phân tích kết quả
- Kiểm tra file CSV trong thư mục `exports/`
- Xem logs trong thư mục `logs/`
- Đánh giá win rate và adjust parameters nếu cần

## Troubleshooting

### Lỗi kết nối API
```bash
# Kiểm tra API key Twelve Data trong .env
# Test kết nối
python main.py status

# Lưu ý: API có giới hạn 8 requests/phút và 800 requests/ngày
# Nếu lỗi 429 (Rate Limit), chờ vài phút rồi thử lại
```

### Lỗi database
```bash
# Reset và tạo lại database
python main.py reset --confirm
python main.py migrate
```

### Không có dữ liệu
```bash
# Kiểm tra data trong database
python main.py status

# Crawl dữ liệu mới
python main.py crawl --start-date "2024-01-01 00:00:00" --end-date "2024-01-31 23:59:59"
```

## Support

Nếu gặp vấn đề, hãy kiểm tra:
1. API key Twelve Data có hợp lệ không (lấy từ twelvedata.com)
2. Database có đang chạy không (`docker ps`)
3. Logs trong thư mục `logs/` để xem chi tiết lỗi
4. Chạy `python main.py status` để kiểm tra tổng thể hệ thống
5. Rate limit: tool tự động chờ 8 giây giữa các requests để tránh vượt giới hạn