from sqlalchemy import create_engine, Column, Integer, DECIMAL, TIMESTAMP, String, BigInteger, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pandas as pd
from config import DATABASE_URL
from logger import setup_logger

Base = declarative_base()
logger = setup_logger()

class Candle(Base):
    __tablename__ = 'candles'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(TIMESTAMP, nullable=False, unique=True)
    open = Column(DECIMAL(10, 5), nullable=False)
    high = Column(DECIMAL(10, 5), nullable=False)
    low = Column(DECIMAL(10, 5), nullable=False)
    close = Column(DECIMAL(10, 5), nullable=False)
    volume = Column(BigInteger, nullable=False, default=0)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Signal(Base):
    __tablename__ = 'signals'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(TIMESTAMP, nullable=False)
    signal_type = Column(String(10), nullable=False)  # LONG or SHORT
    entry_price = Column(DECIMAL(10, 5), nullable=False)
    condition_type = Column(String(20), nullable=False)  # ENGULFING or INSIDE_BAR
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Database:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.connect()

    def connect(self):
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def get_session(self):
        return self.SessionLocal()

    def save_candles(self, df):
        try:
            session = self.get_session()
            candles = []
            
            for _, row in df.iterrows():
                candle = Candle(
                    timestamp=row['timestamp'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row.get('volume', 0))
                )
                candles.append(candle)
            
            # Use bulk insert with on conflict ignore
            session.execute(text("""
                INSERT INTO candles (timestamp, open, high, low, close, volume)
                VALUES (:timestamp, :open, :high, :low, :close, :volume)
                ON CONFLICT (timestamp) DO NOTHING
            """), [
                {
                    'timestamp': candle.timestamp,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume
                } for candle in candles
            ])
            
            session.commit()
            logger.info(f"Saved {len(candles)} candles to database")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save candles: {e}")
            raise
        finally:
            session.close()

    def load_candles(self, start_time=None, end_time=None):
        try:
            query = "SELECT * FROM candles"
            params = {}
            
            if start_time and end_time:
                query += " WHERE timestamp >= :start_time AND timestamp <= :end_time"
                params = {"start_time": start_time, "end_time": end_time}
            
            query += " ORDER BY timestamp ASC"
            
            df = pd.read_sql(query, self.engine, params=params)
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            logger.info(f"Loaded {len(df)} candles from database")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load candles: {e}")
            return pd.DataFrame()

    def save_signals(self, signals):
        try:
            session = self.get_session()
            
            for signal_data in signals:
                signal = Signal(
                    timestamp=signal_data['timestamp'],
                    signal_type=signal_data['signal_type'],
                    entry_price=signal_data['entry_price'],
                    condition_type=signal_data['condition_type']
                )
                session.add(signal)
            
            session.commit()
            logger.info(f"Saved {len(signals)} signals to database")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save signals: {e}")
            raise
        finally:
            session.close()

    def get_latest_candle_time(self):
        try:
            session = self.get_session()
            result = session.execute(text("SELECT MAX(timestamp) FROM candles")).scalar()
            session.close()
            return result
        except Exception as e:
            logger.error(f"Failed to get latest candle time: {e}")
            return None

    def close(self):
        self.engine.dispose()
        logger.info("Database connection closed")