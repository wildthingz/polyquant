#!/usr/bin/env python3
"""
Options Historical Data Collector

Fetches historical options quotes for MAG7 stocks from IBKR or data vendor.
Stores minute-level data in PostgreSQL for backtesting.

Usage:
    python scripts/collect_options_history.py --start-date 2024-01-01 --end-date 2024-12-31 --ticker AAPL
"""

import argparse
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

import psycopg2
from psycopg2.extras import execute_values

# Try to import IBKR API
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.common import BarData
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    logging.warning("IBKR API not available. Install with: pip install ibapi")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

MAG7_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'TSLA', 'META', 'GOOGL']


class IBKRHistoricalCollector(EWrapper, EClient):
    """
    Collect historical options data from IBKR

    Note: IBKR limits historical data to 60 days for options.
    For longer history, need to use paid data vendor (Algoseek, etc.)
    """

    def __init__(self, db_config: Dict[str, str]):
        EClient.__init__(self, self)
        self.db_config = db_config
        self.conn = None
        self.next_req_id = 1
        self.historical_data = []
        self.request_complete = False

    def connect_db(self):
        """Connect to PostgreSQL database"""
        if not self.conn:
            self.conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )

    def error(self, reqId, errorCode, errorString):
        """Handle IBKR errors"""
        logger.error(f"Error {errorCode}: {errorString}")

    def historicalData(self, reqId, bar: BarData):
        """Callback for historical data bars"""
        self.historical_data.append({
            'timestamp': bar.date,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume
        })

    def historicalDataEnd(self, reqId, start, end):
        """Callback when historical data request completes"""
        logger.info(f"Historical data complete: {len(self.historical_data)} bars")
        self.request_complete = True

    def create_option_contract(self, ticker: str, strike: float, expiration: str, right: str) -> Contract:
        """
        Create IBKR option contract

        Args:
            ticker: Underlying ticker
            strike: Strike price
            expiration: Expiration date (YYYYMMDD)
            right: 'C' for call, 'P' for put

        Returns:
            IBKR Contract object
        """
        contract = Contract()
        contract.symbol = ticker
        contract.secType = "OPT"
        contract.exchange = "SMART"
        contract.currency = "USD"
        contract.lastTradeDateOrContractMonth = expiration
        contract.strike = strike
        contract.right = right
        contract.multiplier = "100"
        return contract

    def fetch_historical_options(self, ticker: str, start_date: datetime, end_date: datetime):
        """
        Fetch historical options data for a ticker

        Args:
            ticker: Stock ticker
            start_date: Start of historical period
            end_date: End of historical period
        """
        logger.info(f"Fetching options history for {ticker}")

        # TODO: Implement option chain discovery
        # For MVP: hardcode some strikes near ATM

        # This is a placeholder - actual implementation would:
        # 1. Fetch underlying price
        # 2. Get option chain for dates 7-60 DTE
        # 3. Select strikes within ±20% of underlying
        # 4. Request historical data for each contract

        logger.warning("Option chain discovery not implemented yet")
        logger.info("Consider using data vendor: Algoseek, HistoricalOptionData.com, or TickData.com")

    def store_options_quote(self, ticker: str, bar: Dict, contract_details: Dict):
        """
        Store options quote in database

        Args:
            ticker: Underlying ticker
            bar: Price bar from IBKR
            contract_details: Strike, expiration, type
        """
        self.connect_db()
        cursor = self.conn.cursor()

        query = """
            INSERT INTO options_history (
                timestamp, underlying, strike, expiration, option_type,
                bid, ask, mid, iv, delta, gamma, vega, theta, volume, open_interest
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """

        # IBKR historical bars don't include bid/ask - would need snapshot quotes
        # For now, approximate: mid = close, bid = close - spread/2, ask = close + spread/2
        mid = bar['close']
        spread_est = mid * 0.02  # Assume 2% spread
        bid = mid - spread_est / 2
        ask = mid + spread_est / 2

        values = (
            bar['timestamp'],
            ticker,
            contract_details['strike'],
            contract_details['expiration'],
            contract_details['option_type'],
            bid,
            ask,
            mid,
            None,  # IV - would need calculation
            None,  # Delta - would need calculation
            None,  # Gamma
            None,  # Vega
            None,  # Theta
            bar['volume'],
            None   # Open interest not in historical bars
        )

        cursor.execute(query, values)
        self.conn.commit()
        cursor.close()


def collect_from_csv_vendor(csv_path: str, db_config: Dict[str, str]):
    """
    Load historical options data from CSV vendor (Algoseek, etc.)

    Expected CSV format:
    timestamp,underlying,strike,expiration,option_type,bid,ask,iv,delta,gamma,vega,theta,volume,open_interest

    Args:
        csv_path: Path to CSV file
        db_config: Database configuration
    """
    import csv

    logger.info(f"Loading options data from {csv_path}")

    conn = psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )

    cursor = conn.cursor()
    rows_inserted = 0

    query = """
        INSERT INTO options_history (
            timestamp, underlying, strike, expiration, option_type,
            bid, ask, mid, iv, delta, gamma, vega, theta, volume, open_interest
        )
        VALUES %s
        ON CONFLICT DO NOTHING
    """

    batch = []
    batch_size = 1000

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            mid = (float(row['bid']) + float(row['ask'])) / 2

            values = (
                row['timestamp'],
                row['underlying'],
                float(row['strike']),
                row['expiration'],
                row['option_type'],
                float(row['bid']),
                float(row['ask']),
                mid,
                float(row.get('iv')) if row.get('iv') else None,
                float(row.get('delta')) if row.get('delta') else None,
                float(row.get('gamma')) if row.get('gamma') else None,
                float(row.get('vega')) if row.get('vega') else None,
                float(row.get('theta')) if row.get('theta') else None,
                int(row.get('volume', 0)),
                int(row.get('open_interest', 0))
            )

            batch.append(values)

            if len(batch) >= batch_size:
                execute_values(cursor, query, batch)
                conn.commit()
                rows_inserted += len(batch)
                logger.info(f"Inserted {rows_inserted} rows...")
                batch = []

        # Insert remaining
        if batch:
            execute_values(cursor, query, batch)
            conn.commit()
            rows_inserted += len(batch)

    cursor.close()
    conn.close()

    logger.info(f"Import complete: {rows_inserted} rows inserted")


def main():
    parser = argparse.ArgumentParser(description='Collect options historical data')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--ticker', type=str, choices=MAG7_TICKERS, help='Stock ticker')
    parser.add_argument('--source', type=str, choices=['ibkr', 'csv'], default='csv',
                        help='Data source: ibkr or csv')
    parser.add_argument('--csv-path', type=str, help='Path to CSV file (if source=csv)')
    parser.add_argument('--db-host', type=str, default=os.getenv('DB_HOST', 'localhost'))
    parser.add_argument('--db-port', type=int, default=int(os.getenv('DB_PORT', 5432)))
    parser.add_argument('--db-name', type=str, default=os.getenv('DB_NAME', 'polyquant'))
    parser.add_argument('--db-user', type=str, default=os.getenv('DB_USER', 'polyquant'))
    parser.add_argument('--db-password', type=str, default=os.getenv('DB_PASSWORD', 'your_password'))

    args = parser.parse_args()

    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }

    if args.source == 'csv':
        if not args.csv_path:
            logger.error("--csv-path required for CSV source")
            return

        collect_from_csv_vendor(args.csv_path, db_config)

    elif args.source == 'ibkr':
        if not IBKR_AVAILABLE:
            logger.error("IBKR API not available. Install with: pip install ibapi")
            return

        if not args.start_date or not args.end_date or not args.ticker:
            logger.error("--start-date, --end-date, and --ticker required for IBKR source")
            return

        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')

        collector = IBKRHistoricalCollector(db_config)
        collector.connect("127.0.0.1", 4002, clientId=1)  # IBKR Gateway paper trading port

        # Wait for connection
        time.sleep(2)

        collector.fetch_historical_options(args.ticker, start_date, end_date)

        collector.disconnect()

    logger.info("Options data collection complete")
    logger.info("\nNext steps:")
    logger.info("1. Verify data quality: SELECT COUNT(*) FROM options_history;")
    logger.info("2. Check coverage: SELECT underlying, COUNT(*), MIN(timestamp), MAX(timestamp) FROM options_history GROUP BY underlying;")
    logger.info("3. Run feature engineering: python scripts/feature_engineering.py")


if __name__ == '__main__':
    main()
