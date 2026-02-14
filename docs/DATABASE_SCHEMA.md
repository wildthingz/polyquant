# Database Schema

Complete PostgreSQL + TimescaleDB schema for storing market data, signals, trades, and system logs.

## Table of Contents

1. [Schema Overview](#schema-overview)
2. [Core Tables](#core-tables)
3. [Hypertables](#hypertables)
4. [Views](#views)
5. [Indexes](#indexes)
6. [Migrations](#migrations)

---

## Schema Overview

**Database**: `polyquant`
**Extensions**: TimescaleDB 2.0+, pg_stat_statements
**Storage**: Time-series optimized with automatic compression

### Retention Policy

| Table | Retention | Rationale |
|-------|-----------|-----------|
| `market_data_ticks` | 90 days | Training data, audit trail |
| `signals` | 1 year | Model retraining, backtesting |
| `trades` | Indefinite | Regulatory, tax reporting |
| `system_logs` | 30 days | Debugging, incident response |

---

## Core Tables

### 1. `market_data_ticks`

**Purpose**: Store unified market snapshots (Polymarket + IBKR data merged)

```sql
CREATE TABLE market_data_ticks (
    time                    TIMESTAMPTZ NOT NULL,
    ticker                  VARCHAR(10) NOT NULL,
    contract_id             BIGINT,

    -- Polymarket data
    poly_prob               DOUBLE PRECISION,
    poly_prob_change_24h    DOUBLE PRECISION,
    poly_volume_usd         DOUBLE PRECISION,

    -- IBKR option data
    opt_bid                 DOUBLE PRECISION,
    opt_ask                 DOUBLE PRECISION,
    opt_last                DOUBLE PRECISION,
    opt_volume              INTEGER,
    opt_open_interest       INTEGER,

    -- Greeks
    opt_delta               DOUBLE PRECISION,
    opt_gamma               DOUBLE PRECISION,
    opt_vega                DOUBLE PRECISION,
    opt_theta               DOUBLE PRECISION,
    opt_iv                  DOUBLE PRECISION,

    -- Derived metrics
    opt_iv_percentile       DOUBLE PRECISION,
    spread_width_pct        DOUBLE PRECISION,
    underlying_price        DOUBLE PRECISION,

    PRIMARY KEY (time, ticker, contract_id)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('market_data_ticks', 'time');

-- Enable compression (90 days old)
ALTER TABLE market_data_ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('market_data_ticks', INTERVAL '90 days');

-- Retention policy (delete after 90 days)
SELECT add_retention_policy('market_data_ticks', INTERVAL '90 days');
```

**Typical Insert**:
```sql
INSERT INTO market_data_ticks (
    time, ticker, contract_id,
    poly_prob, poly_prob_change_24h, poly_volume_usd,
    opt_bid, opt_ask, opt_delta, opt_iv, opt_iv_percentile,
    spread_width_pct, underlying_price
) VALUES (
    NOW(), 'NVDA', 123456789,
    0.75, 0.05, 125000.50,
    15.20, 15.50, 0.45, 0.35, 0.62,
    0.0197, 520.00
);
```

### 2. `signals`

**Purpose**: Store ML model outputs and entry/exit decisions

```sql
CREATE TABLE signals (
    id                      BIGSERIAL PRIMARY KEY,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker                  VARCHAR(10) NOT NULL,
    contract_id             BIGINT NOT NULL,

    -- ML model output
    signal_strength         DOUBLE PRECISION NOT NULL CHECK (signal_strength BETWEEN 0 AND 1),
    model_version           VARCHAR(50) NOT NULL,

    -- Input features (for retraining)
    features                JSONB NOT NULL,

    -- Decision
    decision                VARCHAR(10) NOT NULL CHECK (decision IN ('BUY', 'SELL', 'HOLD', 'EXIT')),
    decision_reason         TEXT,

    -- Expected value calculation
    expected_value          DOUBLE PRECISION,
    kelly_fraction          DOUBLE PRECISION,
    proposed_position_size  INTEGER,

    -- Outcome (filled after trade resolves)
    actual_outcome          BOOLEAN,
    actual_pnl              DOUBLE PRECISION,
    days_held               INTEGER,

    -- Audit
    risk_checks_passed      BOOLEAN NOT NULL,
    risk_rejection_reason   TEXT
);

-- Convert to hypertable
SELECT create_hypertable('signals', 'created_at');

-- Index for model calibration queries
CREATE INDEX idx_signals_model_outcome ON signals(model_version, signal_strength, actual_outcome)
WHERE actual_outcome IS NOT NULL;

-- Index for feature analysis
CREATE INDEX idx_signals_features ON signals USING GIN(features);
```

**Typical Insert**:
```sql
INSERT INTO signals (
    ticker, contract_id, signal_strength, model_version,
    features, decision, decision_reason,
    expected_value, kelly_fraction, proposed_position_size,
    risk_checks_passed
) VALUES (
    'NVDA', 123456789, 0.85, 'xgboost_v1.2.0',
    '{"poly_prob": 0.75, "poly_prob_change_24h": 0.05, "opt_delta": 0.45, "opt_iv": 0.35, "opt_iv_percentile": 0.62, "days_to_expiry": 14, "spread_width_pct": 0.0197, "underlying_price_change_5d": 0.03, "vix_level": 18.5}'::jsonb,
    'BUY', 'EV=23%, signal=0.85, all filters passed',
    0.23, 0.12, 5,
    TRUE
);
```

### 3. `trades`

**Purpose**: Record all executed trades (entries and exits)

```sql
CREATE TABLE trades (
    id                      BIGSERIAL PRIMARY KEY,
    entry_time              TIMESTAMPTZ NOT NULL,
    exit_time               TIMESTAMPTZ,

    ticker                  VARCHAR(10) NOT NULL,
    contract_id             BIGINT NOT NULL,
    signal_id               BIGINT REFERENCES signals(id),

    -- Entry
    entry_price             DOUBLE PRECISION NOT NULL,
    quantity                INTEGER NOT NULL,
    entry_order_id          BIGINT NOT NULL,

    -- Exit
    exit_price              DOUBLE PRECISION,
    exit_order_id           BIGINT,
    exit_reason             VARCHAR(50) CHECK (exit_reason IN (
        'TAKE_PROFIT', 'STOP_LOSS', 'SIGNAL_REVERSAL',
        'THETA_BURN', 'LIQUIDITY_CRISIS', 'POLYMARKET_SHIFT',
        'TIME_SCALING', 'MANUAL'
    )),

    -- P&L
    gross_pnl               DOUBLE PRECISION,
    gross_pnl_pct           DOUBLE PRECISION,
    commissions             DOUBLE PRECISION DEFAULT 1.30, -- $0.65 per side
    net_pnl                 DOUBLE PRECISION,
    net_pnl_pct             DOUBLE PRECISION,

    -- Position tracking
    status                  VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
    days_held               INTEGER,

    -- Greeks at entry/exit
    entry_delta             DOUBLE PRECISION,
    entry_iv                DOUBLE PRECISION,
    exit_delta              DOUBLE PRECISION,
    exit_iv                 DOUBLE PRECISION,

    -- Risk
    max_drawdown_during     DOUBLE PRECISION,
    peak_profit_during      DOUBLE PRECISION
);

-- Convert to hypertable
SELECT create_hypertable('trades', 'entry_time');

-- Index for performance analysis
CREATE INDEX idx_trades_ticker_status ON trades(ticker, status);
CREATE INDEX idx_trades_exit_reason ON trades(exit_reason) WHERE exit_time IS NOT NULL;
CREATE INDEX idx_trades_pnl ON trades(net_pnl_pct) WHERE exit_time IS NOT NULL;
```

**Typical Insert (Entry)**:
```sql
INSERT INTO trades (
    entry_time, ticker, contract_id, signal_id,
    entry_price, quantity, entry_order_id,
    entry_delta, entry_iv, status
) VALUES (
    NOW(), 'NVDA', 123456789, 1001,
    15.35, 5, 987654321,
    0.45, 0.35, 'OPEN'
);
```

**Update (Exit)**:
```sql
UPDATE trades
SET exit_time = NOW(),
    exit_price = 23.02,
    exit_order_id = 987654322,
    exit_reason = 'TAKE_PROFIT',
    gross_pnl = (23.02 - 15.35) * 5 * 100,
    gross_pnl_pct = (23.02 - 15.35) / 15.35,
    commissions = 1.30,
    net_pnl = ((23.02 - 15.35) * 5 * 100) - 1.30,
    net_pnl_pct = (((23.02 - 15.35) * 5 * 100) - 1.30) / (15.35 * 5 * 100),
    status = 'CLOSED',
    days_held = EXTRACT(DAY FROM NOW() - entry_time),
    exit_delta = 0.72,
    exit_iv = 0.28
WHERE id = 1001;
```

### 4. `system_logs`

**Purpose**: Application-level structured logs for debugging

```sql
CREATE TABLE system_logs (
    time                    TIMESTAMPTZ NOT NULL,
    level                   VARCHAR(10) NOT NULL CHECK (level IN ('TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    component               VARCHAR(50) NOT NULL,
    event                   VARCHAR(100),
    message                 TEXT NOT NULL,

    -- Context
    ticker                  VARCHAR(10),
    order_id                BIGINT,
    trade_id                BIGINT,

    -- Metadata
    metadata                JSONB,
    stack_trace             TEXT,

    PRIMARY KEY (time, component)
);

-- Convert to hypertable
SELECT create_hypertable('system_logs', 'time');

-- Retention: 30 days
SELECT add_retention_policy('system_logs', INTERVAL '30 days');

-- Index for error investigation
CREATE INDEX idx_logs_level_time ON system_logs(level, time DESC) WHERE level IN ('ERROR', 'CRITICAL');
CREATE INDEX idx_logs_component ON system_logs(component, time DESC);
```

### 5. `account_state`

**Purpose**: Track account balance, positions, and exposure (not time-series)

```sql
CREATE TABLE account_state (
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    account_value           DOUBLE PRECISION NOT NULL,
    cash_balance            DOUBLE PRECISION NOT NULL,

    -- Position summary
    open_positions_count    INTEGER NOT NULL DEFAULT 0,
    total_position_value    DOUBLE PRECISION NOT NULL DEFAULT 0,
    mag7_exposure_pct       DOUBLE PRECISION NOT NULL DEFAULT 0,

    -- Daily tracking
    daily_pnl               DOUBLE PRECISION NOT NULL DEFAULT 0,
    daily_pnl_pct           DOUBLE PRECISION NOT NULL DEFAULT 0,
    daily_trade_count       INTEGER NOT NULL DEFAULT 0,

    -- Risk metrics
    max_drawdown_today      DOUBLE PRECISION,
    trading_halted          BOOLEAN NOT NULL DEFAULT FALSE,
    halt_reason             TEXT,

    PRIMARY KEY (updated_at)
);

-- Single-row table (always UPSERT latest state)
CREATE UNIQUE INDEX idx_account_state_latest ON account_state((1));
```

**Update**:
```sql
INSERT INTO account_state (
    account_value, cash_balance, open_positions_count,
    total_position_value, mag7_exposure_pct,
    daily_pnl, daily_pnl_pct, daily_trade_count
) VALUES (
    10000.00, 8500.00, 3,
    1500.00, 0.15,
    150.00, 0.015, 5
)
ON CONFLICT ((1)) DO UPDATE SET
    updated_at = NOW(),
    account_value = EXCLUDED.account_value,
    cash_balance = EXCLUDED.cash_balance,
    open_positions_count = EXCLUDED.open_positions_count,
    total_position_value = EXCLUDED.total_position_value,
    mag7_exposure_pct = EXCLUDED.mag7_exposure_pct,
    daily_pnl = EXCLUDED.daily_pnl,
    daily_pnl_pct = EXCLUDED.daily_pnl_pct,
    daily_trade_count = EXCLUDED.daily_trade_count;
```

---

## Hypertables

TimescaleDB automatically chunks time-series data:

```sql
-- View chunk information
SELECT * FROM timescaledb_information.chunks
WHERE hypertable_name = 'market_data_ticks';

-- View compression stats
SELECT * FROM timescaledb_information.compression_settings;

-- Manual compression (if needed)
SELECT compress_chunk(i) FROM show_chunks('market_data_ticks', older_than => INTERVAL '7 days') i;
```

---

## Views

### 1. `v_open_positions`

**Purpose**: Real-time view of open positions with current P&L

```sql
CREATE VIEW v_open_positions AS
SELECT
    t.id AS trade_id,
    t.ticker,
    t.contract_id,
    t.entry_time,
    t.entry_price,
    t.quantity,
    t.entry_delta,
    t.entry_iv,
    t.signal_id,

    -- Current market data (latest tick)
    m.opt_bid AS current_bid,
    m.opt_ask AS current_ask,
    m.opt_delta AS current_delta,
    m.opt_iv AS current_iv,

    -- Unrealized P&L (using mid price)
    ((m.opt_bid + m.opt_ask) / 2.0 - t.entry_price) * t.quantity * 100 AS unrealized_pnl,
    (((m.opt_bid + m.opt_ask) / 2.0 - t.entry_price) / t.entry_price) AS unrealized_pnl_pct,

    -- Time tracking
    EXTRACT(DAY FROM NOW() - t.entry_time) AS days_held,

    -- Spread check
    ((m.opt_ask - m.opt_bid) / ((m.opt_ask + m.opt_bid) / 2.0)) AS current_spread_pct
FROM trades t
JOIN LATERAL (
    SELECT *
    FROM market_data_ticks
    WHERE ticker = t.ticker AND contract_id = t.contract_id
    ORDER BY time DESC
    LIMIT 1
) m ON TRUE
WHERE t.status = 'OPEN';
```

**Usage**:
```sql
-- Check exit triggers
SELECT * FROM v_open_positions
WHERE unrealized_pnl_pct >= 0.50 OR unrealized_pnl_pct <= -0.30;

-- Monitor spread widening
SELECT * FROM v_open_positions WHERE current_spread_pct > 0.08;
```

### 2. `v_model_calibration`

**Purpose**: Analyze ML model prediction accuracy

```sql
CREATE VIEW v_model_calibration AS
SELECT
    model_version,
    FLOOR(signal_strength * 20) / 20.0 AS predicted_bucket,
    COUNT(*) AS sample_count,
    AVG(signal_strength) AS avg_predicted,
    AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END) AS actual_win_rate,
    ABS(AVG(signal_strength) - AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END)) AS calibration_error
FROM signals
WHERE actual_outcome IS NOT NULL
GROUP BY model_version, predicted_bucket
HAVING COUNT(*) >= 5
ORDER BY model_version, predicted_bucket;
```

**Usage**:
```sql
-- Check if model is well-calibrated (error < 15%)
SELECT * FROM v_model_calibration WHERE calibration_error > 0.15;
```

### 3. `v_performance_summary`

**Purpose**: Daily performance metrics

```sql
CREATE VIEW v_performance_summary AS
SELECT
    DATE(entry_time) AS trade_date,
    COUNT(*) AS trades_count,
    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN net_pnl <= 0 THEN 1 ELSE 0 END) AS losses,
    SUM(net_pnl) AS total_pnl,
    AVG(net_pnl_pct) AS avg_pnl_pct,
    STDDEV(net_pnl_pct) AS stddev_pnl_pct,

    -- Sharpe Ratio (annualized, assuming 252 trading days)
    (AVG(net_pnl_pct) / NULLIF(STDDEV(net_pnl_pct), 0)) * SQRT(252) AS sharpe_ratio,

    -- Win rate
    (SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*)) AS win_rate,

    -- Max drawdown
    MIN(net_pnl_pct) AS worst_trade,
    MAX(net_pnl_pct) AS best_trade
FROM trades
WHERE status = 'CLOSED'
GROUP BY DATE(entry_time)
ORDER BY trade_date DESC;
```

---

## Indexes

### Performance-Critical Indexes

```sql
-- Fast lookup of latest market data per contract
CREATE INDEX idx_market_data_ticker_contract_time ON market_data_ticks(ticker, contract_id, time DESC);

-- Signal analysis by model version
CREATE INDEX idx_signals_model_created ON signals(model_version, created_at DESC);

-- Trade analysis by ticker and time
CREATE INDEX idx_trades_ticker_entry_time ON trades(ticker, entry_time DESC);

-- Open positions quick scan
CREATE INDEX idx_trades_status_entry_time ON trades(status, entry_time DESC) WHERE status = 'OPEN';

-- Error log investigation
CREATE INDEX idx_logs_error_time ON system_logs(time DESC) WHERE level IN ('ERROR', 'CRITICAL');
```

---

## Migrations

### Initial Schema (v1.0.0)

```bash
# schema.sql
psql -U postgres -d polyquant -f schema.sql
```

### Migration Example (v1.1.0: Add IV Percentile)

```sql
-- migrations/001_add_iv_percentile.sql
BEGIN;

-- Add column
ALTER TABLE market_data_ticks ADD COLUMN opt_iv_percentile DOUBLE PRECISION;

-- Backfill (calculate from historical data)
WITH percentiles AS (
    SELECT
        time,
        ticker,
        contract_id,
        PERCENT_RANK() OVER (
            PARTITION BY ticker, contract_id
            ORDER BY opt_iv
        ) AS iv_percentile
    FROM market_data_ticks
    WHERE time >= NOW() - INTERVAL '30 days'
)
UPDATE market_data_ticks m
SET opt_iv_percentile = p.iv_percentile
FROM percentiles p
WHERE m.time = p.time
  AND m.ticker = p.ticker
  AND m.contract_id = p.contract_id;

-- Add constraint
ALTER TABLE market_data_ticks ADD CONSTRAINT chk_iv_percentile CHECK (opt_iv_percentile BETWEEN 0 AND 1);

COMMIT;
```

### Rollback Plan

```sql
-- migrations/001_add_iv_percentile_rollback.sql
BEGIN;

ALTER TABLE market_data_ticks DROP COLUMN opt_iv_percentile;

COMMIT;
```

---

## Backup & Recovery

### Automated Backups

```bash
# scripts/backup_db.sh
#!/bin/bash

BACKUP_DIR="/var/backups/polyquant"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/polyquant_$TIMESTAMP.sql.gz"

# Create backup
pg_dump -U postgres -d polyquant | gzip > "$BACKUP_FILE"

# Keep last 7 days
find "$BACKUP_DIR" -name "polyquant_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

**Cron Job**:
```cron
# Daily at 2 AM
0 2 * * * /home/hatef/polyquant/scripts/backup_db.sh >> /var/log/polyquant/backup.log 2>&1
```

### Recovery

```bash
# Restore from backup
gunzip -c /var/backups/polyquant/polyquant_20250213_020000.sql.gz | psql -U postgres -d polyquant
```

---

## Monitoring Queries

### Connection Count

```sql
SELECT COUNT(*) FROM pg_stat_activity WHERE datname = 'polyquant';
```

### Table Sizes

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Slow Queries

```sql
SELECT
    query,
    calls,
    total_time / 1000 AS total_time_seconds,
    mean_time / 1000 AS mean_time_seconds,
    max_time / 1000 AS max_time_seconds
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

---

**See Also**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - DB Writer component
- [DEPLOYMENT.md](DEPLOYMENT.md) - PostgreSQL setup script
- [CONFIGURATION.md](CONFIGURATION.md) - Connection strings

