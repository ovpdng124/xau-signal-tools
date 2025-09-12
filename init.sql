-- Initialize XAU Signals Database

CREATE TABLE IF NOT EXISTS candles (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(10,5) NOT NULL,
    high DECIMAL(10,5) NOT NULL,
    low DECIMAL(10,5) NOT NULL,
    close DECIMAL(10,5) NOT NULL,
    volume BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp)
);

CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    signal_type VARCHAR(10) NOT NULL CHECK (signal_type IN ('LONG', 'SHORT')),
    entry_price DECIMAL(10,5) NOT NULL,
    condition_type VARCHAR(20) NOT NULL CHECK (condition_type IN ('ENGULFING', 'INSIDE_BAR')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_candles_timestamp ON candles(timestamp);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);