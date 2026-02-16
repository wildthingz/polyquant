# Data Collection Scripts

> **Note**: These scripts are for custom backtesting infrastructure (see [../docs/BACKTESTING.md](../docs/BACKTESTING.md)).
>
> **If using QuantConnect** (recommended), you don't need these - QuantConnect provides historical data.

## Scripts

### collect_polymarket_history.py
Fetches historical Polymarket prediction market events and timeseries data.

**Usage**:
```bash
python scripts/collect_polymarket_history.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

**Requires**: PostgreSQL with schema from `schema.sql` (tables: polymarket_events, polymarket_timeseries)

### collect_options_history.py
Fetches historical options quotes from IBKR or CSV vendor.

**Usage (IBKR)**:
```bash
python scripts/collect_options_history.py \
  --source ibkr \
  --ticker AAPL \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

**Usage (CSV vendor)**:
```bash
python scripts/collect_options_history.py \
  --source csv \
  --csv-path /path/to/options_data.csv
```

**Requires**: PostgreSQL with `options_history` table

## When to Use These

Use these scripts if:
- You want complete control over backtesting (not using QuantConnect)
- You have access to Polymarket historical data
- You want to integrate proprietary data sources
- QuantConnect's Brain Sentiment isn't a good proxy for your thesis

Otherwise, use [QuantConnect](../quantconnect/README.md) for faster iteration.
