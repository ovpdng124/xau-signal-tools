from sqlalchemy import create_engine, Column, Integer, DECIMAL, TIMESTAMP, String, BigInteger, text, UniqueConstraint
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
    timestamp = Column(TIMESTAMP, nullable=False)
    timeframe = Column(String(10), nullable=False, default='15m')  # '1m', '5m', '15m', '30m', '1h', '4h', '1d'
    open = Column(DECIMAL(10, 5), nullable=False)
    high = Column(DECIMAL(10, 5), nullable=False)
    low = Column(DECIMAL(10, 5), nullable=False)
    close = Column(DECIMAL(10, 5), nullable=False)
    volume = Column(BigInteger, nullable=False, default=0)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Composite unique constraint for timestamp + timeframe
    __table_args__ = (
        UniqueConstraint('timestamp', 'timeframe', name='uq_candles_timestamp_timeframe'),
    )

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

    def save_candles(self, df, timeframe='15m'):
        try:
            session = self.get_session()
            candles = []
            
            for _, row in df.iterrows():
                candle = Candle(
                    timestamp=row['timestamp'],
                    timeframe=timeframe,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row.get('volume', 0))
                )
                candles.append(candle)
            
            # Use bulk insert with on conflict ignore (updated for timestamp + timeframe)
            session.execute(text("""
                INSERT INTO candles (timestamp, timeframe, open, high, low, close, volume)
                VALUES (:timestamp, :timeframe, :open, :high, :low, :close, :volume)
                ON CONFLICT (timestamp, timeframe) DO NOTHING
            """), [
                {
                    'timestamp': candle.timestamp,
                    'timeframe': candle.timeframe,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume
                } for candle in candles
            ])
            
            session.commit()
            logger.info(f"Saved {len(candles)} {timeframe} candles to database")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save candles: {e}")
            raise
        finally:
            session.close()

    def load_candles(self, start_time=None, end_time=None, timeframe='15m'):
        try:
            if start_time and end_time:
                # Use SQLAlchemy text with bound parameters
                query = text("""
                    SELECT * FROM candles 
                    WHERE timestamp >= :start_time AND timestamp <= :end_time AND timeframe = :timeframe
                    ORDER BY timestamp ASC
                """)
                df = pd.read_sql(query, self.engine, params={
                    "start_time": start_time, 
                    "end_time": end_time,
                    "timeframe": timeframe
                })
            else:
                # Simple query without parameters but with timeframe filter
                query = text("SELECT * FROM candles WHERE timeframe = :timeframe ORDER BY timestamp ASC")
                df = pd.read_sql(query, self.engine, params={"timeframe": timeframe})
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            logger.info(f"Loaded {len(df)} {timeframe} candles from database")
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

    def get_latest_candle_time(self, timeframe='15m'):
        try:
            session = self.get_session()
            result = session.execute(text("SELECT MAX(timestamp) FROM candles WHERE timeframe = :timeframe"), 
                                   {"timeframe": timeframe}).scalar()
            session.close()
            return result
        except Exception as e:
            logger.error(f"Failed to get latest candle time: {e}")
            return None

    def close(self):
        self.engine.dispose()
        logger.info("Database connection closed")