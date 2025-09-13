#!/usr/bin/env python3
"""
CSV Data Import Script for XAU Signal Tools

This script imports historical OHLCV data from CSV file into the database.
It's designed to work with the XAU_15m_data.csv file format.

Usage:
    python import_csv_data.py [--file CSV_FILE_PATH] [--batch-size BATCH_SIZE] [--dry-run]

CSV Format Expected:
    Date;Open;High;Low;Close;Volume
    2004.06.11 07:15;384;384.3;383.8;384.3;12
"""

import argparse
import pandas as pd
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from config import DATABASE_URL
from logger import setup_logger

logger = setup_logger()

class CSVDataImporter:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        logger.info("CSV Data Importer initialized")

    def parse_csv_date(self, date_str):
        """
        Parse CSV date format (YYYY.MM.DD HH:MM) to datetime object
        
        Args:
            date_str: Date string in format "YYYY.MM.DD HH:MM"
        
        Returns:
            datetime: Parsed datetime object
        """
        try:
            # Convert "2004.06.11 07:15" to datetime
            return datetime.strptime(date_str, "%Y.%m.%d %H:%M")
        except ValueError as e:
            logger.error(f"Failed to parse date '{date_str}': {e}")
            return None

    def validate_csv_format(self, df):
        """
        Validate that CSV has the expected format and columns
        
        Args:
            df: DataFrame to validate
        
        Returns:
            bool: True if valid, False otherwise
        """
        expected_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        if list(df.columns) != expected_columns:
            logger.error(f"Invalid CSV columns. Expected: {expected_columns}, Got: {list(df.columns)}")
            return False
        
        # Check if we have data
        if df.empty:
            logger.error("CSV file is empty")
            return False
        
        # Sample a few date entries to validate format
        sample_dates = df['Date'].head(3).tolist()
        for date_str in sample_dates:
            if self.parse_csv_date(date_str) is None:
                logger.error(f"Invalid date format found: {date_str}")
                return False
        
        logger.info(f"CSV validation passed. Found {len(df)} records")
        return True

    def process_csv_data(self, df):
        """
        Process CSV data into the format expected by database
        
        Args:
            df: Raw DataFrame from CSV
        
        Returns:
            DataFrame: Processed DataFrame ready for database insert
        """
        logger.info("Processing CSV data...")
        
        # Create a copy to avoid modifying original
        processed_df = df.copy()
        
        # Parse dates
        processed_df['timestamp'] = processed_df['Date'].apply(self.parse_csv_date)
        
        # Remove rows with invalid dates
        invalid_dates = processed_df['timestamp'].isna()
        if invalid_dates.any():
            invalid_count = invalid_dates.sum()
            logger.warning(f"Removing {invalid_count} rows with invalid dates")
            processed_df = processed_df.dropna(subset=['timestamp'])
        
        # Rename columns to match database schema
        processed_df = processed_df.rename(columns={
            'Open': 'open',
            'High': 'high', 
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        # Select only the columns we need
        processed_df = processed_df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        # Convert numeric columns to proper types
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
        
        # Remove rows with invalid numeric data
        invalid_numeric = processed_df[numeric_columns].isna().any(axis=1)
        if invalid_numeric.any():
            invalid_count = invalid_numeric.sum()
            logger.warning(f"Removing {invalid_count} rows with invalid numeric data")
            processed_df = processed_df.dropna(subset=numeric_columns)
        
        # Sort by timestamp
        processed_df = processed_df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Data processing completed. {len(processed_df)} records ready for import")
        return processed_df

    def get_existing_data_range(self):
        """
        Get the date range of existing data in database
        
        Returns:
            dict: Dictionary with min_date and max_date, or None if no data
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        MIN(timestamp) as min_date,
                        MAX(timestamp) as max_date,
                        COUNT(*) as total_count
                    FROM candles
                """)).fetchone()
                
                if result and result.total_count > 0:
                    return {
                        'min_date': result.min_date,
                        'max_date': result.max_date, 
                        'total_count': result.total_count
                    }
                else:
                    return None
        except Exception as e:
            logger.error(f"Failed to get existing data range: {e}")
            return None

    def import_data_batch(self, df_batch, batch_num, total_batches):
        """
        Import a batch of data into database
        
        Args:
            df_batch: DataFrame batch to import
            batch_num: Current batch number
            total_batches: Total number of batches
        
        Returns:
            int: Number of records successfully inserted
        """
        try:
            logger.info(f"Importing batch {batch_num}/{total_batches} ({len(df_batch)} records)")
            
            # Prepare data for bulk insert
            records = []
            for _, row in df_batch.iterrows():
                records.append({
                    'timestamp': row['timestamp'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume'])
                })
            
            # Use bulk insert with ON CONFLICT DO NOTHING
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    INSERT INTO candles (timestamp, open, high, low, close, volume)
                    VALUES (:timestamp, :open, :high, :low, :close, :volume)
                    ON CONFLICT (timestamp) DO NOTHING
                """), records)
                
                conn.commit()
                inserted_count = result.rowcount
                
                logger.info(f"Batch {batch_num}/{total_batches} completed: {inserted_count} new records inserted")
                return inserted_count
                
        except Exception as e:
            logger.error(f"Failed to import batch {batch_num}: {e}")
            return 0

    def import_csv_file(self, csv_file_path, batch_size=1000, dry_run=False):
        """
        Import data from CSV file into database
        
        Args:
            csv_file_path: Path to CSV file
            batch_size: Number of records to process in each batch
            dry_run: If True, only validate and show statistics without importing
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Starting CSV import from: {csv_file_path}")
            
            # Read CSV file
            logger.info("Reading CSV file...")
            df = pd.read_csv(csv_file_path, sep=';')
            logger.info(f"CSV file loaded: {len(df)} records")
            
            # Validate CSV format
            if not self.validate_csv_format(df):
                return False
            
            # Process data
            processed_df = self.process_csv_data(df)
            if processed_df.empty:
                logger.error("No valid data to import after processing")
                return False
            
            # Show data range information
            min_date = processed_df['timestamp'].min()
            max_date = processed_df['timestamp'].max()
            logger.info(f"CSV data range: {min_date} to {max_date}")
            
            # Check existing data
            existing_range = self.get_existing_data_range()
            if existing_range:
                logger.info(f"Existing DB data: {existing_range['total_count']} records from {existing_range['min_date']} to {existing_range['max_date']}")
            else:
                logger.info("No existing data in database")
            
            if dry_run:
                logger.info("DRY RUN MODE - No data will be imported")
                logger.info(f"Would import {len(processed_df)} records in {(len(processed_df) + batch_size - 1) // batch_size} batches")
                return True
            
            # Import data in batches
            total_inserted = 0
            total_batches = (len(processed_df) + batch_size - 1) // batch_size
            
            logger.info(f"Starting import of {len(processed_df)} records in {total_batches} batches")
            
            for i in range(0, len(processed_df), batch_size):
                batch_df = processed_df.iloc[i:i+batch_size]
                batch_num = (i // batch_size) + 1
                
                inserted = self.import_data_batch(batch_df, batch_num, total_batches)
                total_inserted += inserted
            
            logger.info(f"Import completed successfully!")
            logger.info(f"Total records processed: {len(processed_df)}")
            logger.info(f"Total new records inserted: {total_inserted}")
            logger.info(f"Duplicates skipped: {len(processed_df) - total_inserted}")
            
            return True
            
        except Exception as e:
            logger.error(f"CSV import failed: {e}")
            return False

    def close(self):
        """Close database connection"""
        self.engine.dispose()
        logger.info("CSV Data Importer closed")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Import historical OHLCV data from CSV file into XAU Signal Tools database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python import_csv_data.py                                    # Import XAU_15m_data.csv with default settings
  python import_csv_data.py --file my_data.csv               # Import custom CSV file  
  python import_csv_data.py --batch-size 5000                # Use larger batch size
  python import_csv_data.py --dry-run                        # Validate only, don't import
  python import_csv_data.py --file data.csv --dry-run        # Test custom file validation
        """
    )
    
    parser.add_argument('--file', type=str, default='XAU_15m_data.csv',
                       help='Path to CSV file (default: XAU_15m_data.csv)')
    parser.add_argument('--batch-size', type=int, default=1000,
                       help='Number of records to process in each batch (default: 1000)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Validate file and show statistics without importing data')
    
    args = parser.parse_args()
    
    try:
        # Initialize importer
        importer = CSVDataImporter()
        
        # Run import
        success = importer.import_csv_file(
            csv_file_path=args.file,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        
        importer.close()
        
        if success:
            if args.dry_run:
                print("\n✅ CSV validation completed successfully!")
            else:
                print("\n✅ CSV import completed successfully!")
            return 0
        else:
            print("\n❌ CSV import failed!")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Import interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())