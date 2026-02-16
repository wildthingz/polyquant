#!/usr/bin/env python3
"""
Polymarket Historical Data Collector

Fetches historical prediction market data for MAG7-related events from Polymarket CLOB API.
Stores timeseries data in PostgreSQL for backtesting.

Usage:
    python scripts/collect_polymarket_history.py --start-date 2024-01-01 --end-date 2024-12-31
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
import psycopg2
from psycopg2.extras import execute_values

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Polymarket API endpoints
CLOB_API_BASE = "https://clob.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# MAG7 tickers for keyword matching
MAG7_KEYWORDS = {
    'AAPL': ['apple', 'iphone', 'ipad', 'mac', 'tim cook'],
    'MSFT': ['microsoft', 'windows', 'azure', 'satya nadella'],
    'NVDA': ['nvidia', 'jensen huang', 'gpu', 'ai chip'],
    'AMZN': ['amazon', 'aws', 'jeff bezos', 'andy jassy'],
    'TSLA': ['tesla', 'elon musk', 'spacex', 'ev'],
    'META': ['meta', 'facebook', 'instagram', 'mark zuckerberg'],
    'GOOGL': ['google', 'alphabet', 'sundar pichai', 'youtube']
}

# Event type patterns
EVENT_PATTERNS = {
    'earnings': ['earnings', 'revenue', 'profit', 'quarterly report', 'q1', 'q2', 'q3', 'q4'],
    'product_launch': ['launch', 'release', 'announce', 'unveil', 'new product'],
    'regulatory': ['sec', 'fda', 'ftc', 'approval', 'regulation', 'lawsuit'],
    'executive': ['ceo', 'resign', 'depart', 'hire', 'fire', 'scandal']
}


class PolymarketCollector:
    """Collects historical Polymarket data for backtesting"""

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def connect_db(self):
        """Connect to PostgreSQL database"""
        return psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )

    async def fetch_markets(self, closed: bool = True, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Fetch markets from Polymarket CLOB API

        Args:
            closed: If True, fetch only resolved markets
            limit: Number of markets per request
            offset: Pagination offset

        Returns:
            List of market dictionaries
        """
        url = f"{CLOB_API_BASE}/markets"
        params = {
            'closed': str(closed).lower(),
            'limit': limit,
            'offset': offset
        }

        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return data if isinstance(data, list) else data.get('data', [])
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    async def fetch_orderbook_snapshot(self, token_id: str) -> Optional[Dict]:
        """
        Fetch current orderbook snapshot for a token

        Args:
            token_id: Polymarket token/asset ID

        Returns:
            Orderbook data with bids/asks
        """
        url = f"{CLOB_API_BASE}/book"
        params = {'token_id': token_id}

        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {token_id}: {e}")
            return None

    def classify_market(self, question: str) -> tuple[Optional[str], Optional[str]]:
        """
        Classify market by MAG7 ticker and event type

        Args:
            question: Market question text

        Returns:
            (ticker, event_type) or (None, None) if not MAG7-related
        """
        question_lower = question.lower()

        # Find matching ticker
        ticker = None
        for stock, keywords in MAG7_KEYWORDS.items():
            if any(keyword.lower() in question_lower for keyword in keywords):
                ticker = stock
                break

        if not ticker:
            return None, None

        # Find matching event type
        event_type = 'other'
        for evt_type, patterns in EVENT_PATTERNS.items():
            if any(pattern in question_lower for pattern in patterns):
                event_type = evt_type
                break

        return ticker, event_type

    def store_event(self, conn, market: Dict, ticker: str, event_type: str) -> int:
        """
        Store Polymarket event in database

        Args:
            conn: Database connection
            market: Market data from API
            ticker: MAG7 ticker (AAPL, etc.)
            event_type: Event classification

        Returns:
            event_id
        """
        cursor = conn.cursor()

        # Extract resolution
        resolution = None
        resolution_price = None
        if market.get('closed') and market.get('outcome'):
            resolution = market['outcome']
            # Polymarket outcomes are typically "Yes"/"No"
            resolution_price = 1.0 if resolution.lower() == 'yes' else 0.0

        query = """
            INSERT INTO polymarket_events (
                market_id, condition_id, question, underlying_ticker, event_type,
                start_date, end_date, resolution, resolution_price
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (market_id) DO UPDATE SET
                resolution = EXCLUDED.resolution,
                resolution_price = EXCLUDED.resolution_price
            RETURNING event_id
        """

        values = (
            market.get('condition_id'),  # Using condition_id as market_id
            market.get('condition_id'),
            market.get('question'),
            ticker,
            event_type,
            market.get('start_date_iso') or market.get('created_at'),
            market.get('end_date_iso') or market.get('end_date'),
            resolution,
            resolution_price
        )

        cursor.execute(query, values)
        event_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()

        return event_id

    def store_timeseries(self, conn, event_id: int, timeseries: List[Dict]):
        """
        Store price timeseries for an event

        Args:
            conn: Database connection
            event_id: Foreign key to polymarket_events
            timeseries: List of price snapshots
        """
        if not timeseries:
            return

        cursor = conn.cursor()

        query = """
            INSERT INTO polymarket_timeseries (
                event_id, timestamp, yes_price, no_price, volume_24h, liquidity
            )
            VALUES %s
            ON CONFLICT DO NOTHING
        """

        values = [
            (
                event_id,
                snapshot['timestamp'],
                snapshot.get('yes_price'),
                snapshot.get('no_price'),
                snapshot.get('volume_24h'),
                snapshot.get('liquidity')
            )
            for snapshot in timeseries
        ]

        execute_values(cursor, query, values)
        conn.commit()
        cursor.close()

    async def collect_market_history(self, market: Dict, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Simulate historical price collection for a market
        (Polymarket doesn't provide historical API - this would need data vendor)

        For MVP: Just collect current snapshot as single data point

        Args:
            market: Market metadata
            start_date: Collection start
            end_date: Collection end

        Returns:
            List of price snapshots
        """
        # TODO: Replace with actual historical data vendor (Dune Analytics, etc.)
        # For now, fetch current orderbook as proxy

        tokens = market.get('tokens', [])
        if not tokens or len(tokens) < 2:
            return []

        yes_token_id = tokens[0].get('token_id')
        no_token_id = tokens[1].get('token_id')

        orderbook = await self.fetch_orderbook_snapshot(yes_token_id)
        if not orderbook:
            return []

        # Extract best bid/ask
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return []

        yes_price = float(asks[0]['price']) if asks else 0.5
        no_price = 1.0 - yes_price

        snapshot = {
            'timestamp': datetime.utcnow().isoformat(),
            'yes_price': yes_price,
            'no_price': no_price,
            'volume_24h': market.get('volume_24h', 0),
            'liquidity': sum(float(bid['size']) for bid in bids[:10])  # Top 10 bids
        }

        return [snapshot]

    async def run_collection(self, start_date: datetime, end_date: datetime):
        """
        Main collection loop

        Args:
            start_date: Start of historical period
            end_date: End of historical period
        """
        logger.info(f"Starting collection from {start_date} to {end_date}")

        conn = self.connect_db()

        # Fetch all closed markets (resolved events)
        offset = 0
        limit = 100
        total_collected = 0
        mag7_collected = 0

        while True:
            markets = await self.fetch_markets(closed=True, limit=limit, offset=offset)

            if not markets:
                break

            logger.info(f"Processing batch: offset={offset}, count={len(markets)}")

            for market in markets:
                question = market.get('question', '')
                ticker, event_type = self.classify_market(question)

                if not ticker:
                    continue  # Skip non-MAG7 markets

                logger.info(f"MAG7 market found: {ticker} | {event_type} | {question[:60]}...")

                # Store event
                event_id = self.store_event(conn, market, ticker, event_type)

                # Collect timeseries (would be historical, but using current snapshot for MVP)
                timeseries = await self.collect_market_history(market, start_date, end_date)
                self.store_timeseries(conn, event_id, timeseries)

                mag7_collected += 1

            total_collected += len(markets)
            offset += limit

            # Rate limiting
            await asyncio.sleep(1)

        conn.close()

        logger.info(f"Collection complete: {total_collected} total markets, {mag7_collected} MAG7-related")


def main():
    parser = argparse.ArgumentParser(description='Collect Polymarket historical data')
    parser.add_argument('--start-date', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--db-host', type=str, default=os.getenv('DB_HOST', 'localhost'))
    parser.add_argument('--db-port', type=int, default=int(os.getenv('DB_PORT', 5432)))
    parser.add_argument('--db-name', type=str, default=os.getenv('DB_NAME', 'polyquant'))
    parser.add_argument('--db-user', type=str, default=os.getenv('DB_USER', 'polyquant'))
    parser.add_argument('--db-password', type=str, default=os.getenv('DB_PASSWORD', 'your_password'))

    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')

    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }

    async def run():
        async with PolymarketCollector(db_config) as collector:
            await collector.run_collection(start_date, end_date)

    asyncio.run(run())


if __name__ == '__main__':
    main()
