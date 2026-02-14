-- PolyQuant Database Schema

-- Enable TimescaleDB extension
-- Note: In the official image, this might already be enabled or require superuser.
-- We wrap it in a block to avoid errors if it's already there.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS timescaledb;
EXCEPTION
    WHEN insufficient_privilege THEN
        NULL; -- Ignore if we can't create it (might be pre-installed)
END
$$;

-- 1. Market Data Ticks
CREATE TABLE IF NOT EXISTS market_data_ticks (
    time                    TIMESTAMPTZ NOT NULL,
    ticker                  VARCHAR(10) NOT NULL,
    contract_id             BIGINT,
    poly_prob               DOUBLE PRECISION,
    poly_prob_change_24h    DOUBLE PRECISION,
    poly_volume_usd         DOUBLE PRECISION,
    opt_bid                 DOUBLE PRECISION,
    opt_ask                 DOUBLE PRECISION,
    opt_last                DOUBLE PRECISION,
    opt_volume              INTEGER,
    opt_open_interest       INTEGER,
    opt_delta               DOUBLE PRECISION,
    opt_gamma               DOUBLE PRECISION,
    opt_vega                DOUBLE PRECISION,
    opt_theta               DOUBLE PRECISION,
    opt_iv                  DOUBLE PRECISION,
    opt_iv_percentile       DOUBLE PRECISION,
    spread_width_pct        DOUBLE PRECISION,
    underlying_price        DOUBLE PRECISION
);

-- Convert to hypertable (only if not already)
SELECT create_hypertable('market_data_ticks', 'time', if_not_exists => TRUE);

-- 2. Signals
CREATE TABLE IF NOT EXISTS signals (
    id                      BIGSERIAL PRIMARY KEY,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker                  VARCHAR(10) NOT NULL,
    contract_id             BIGINT NOT NULL,
    signal_strength         DOUBLE PRECISION NOT NULL CHECK (signal_strength BETWEEN 0 AND 1),
    model_version           VARCHAR(50) NOT NULL,
    features                JSONB NOT NULL,
    decision                VARCHAR(10) NOT NULL CHECK (decision IN ('BUY', 'SELL', 'HOLD', 'EXIT')),
    decision_reason         TEXT,
    expected_value          DOUBLE PRECISION,
    kelly_fraction          DOUBLE PRECISION,
    proposed_position_size  INTEGER,
    actual_outcome          BOOLEAN,
    actual_pnl              DOUBLE PRECISION,
    days_held               INTEGER,
    risk_checks_passed      BOOLEAN NOT NULL,
    risk_rejection_reason   TEXT
);

SELECT create_hypertable('signals', 'created_at', if_not_exists => TRUE);

-- 3. Trades
CREATE TABLE IF NOT EXISTS trades (
    id                      BIGSERIAL PRIMARY KEY,
    entry_time              TIMESTAMPTZ NOT NULL,
    exit_time               TIMESTAMPTZ,
    ticker                  VARCHAR(10) NOT NULL,
    contract_id             BIGINT NOT NULL,
    signal_id               BIGINT REFERENCES signals(id),
    entry_price             DOUBLE PRECISION NOT NULL,
    quantity                INTEGER NOT NULL,
    entry_order_id          BIGINT NOT NULL,
    exit_price              DOUBLE PRECISION,
    exit_order_id           BIGINT,
    exit_reason             VARCHAR(50),
    gross_pnl               DOUBLE PRECISION,
    gross_pnl_pct           DOUBLE PRECISION,
    commissions             DOUBLE PRECISION DEFAULT 1.30,
    net_pnl                 DOUBLE PRECISION,
    net_pnl_pct             DOUBLE PRECISION,
    status                  VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
    days_held               INTEGER,
    entry_delta             DOUBLE PRECISION,
    entry_iv                DOUBLE PRECISION,
    exit_delta              DOUBLE PRECISION,
    exit_iv                 DOUBLE PRECISION
);

SELECT create_hypertable('trades', 'entry_time', if_not_exists => TRUE);

-- 4. System Logs
CREATE TABLE IF NOT EXISTS system_logs (
    time                    TIMESTAMPTZ NOT NULL,
    level                   VARCHAR(10) NOT NULL CHECK (level IN ('TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    component               VARCHAR(50) NOT NULL,
    event                   VARCHAR(100),
    message                 TEXT NOT NULL,
    ticker                  VARCHAR(10),
    order_id                BIGINT,
    trade_id                BIGINT,
    metadata                JSONB,
    stack_trace             TEXT
);

SELECT create_hypertable('system_logs', 'time', if_not_exists => TRUE);

-- 5. Account State
CREATE TABLE IF NOT EXISTS account_state (
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    account_value           DOUBLE PRECISION NOT NULL,
    cash_balance            DOUBLE PRECISION NOT NULL,
    open_positions_count    INTEGER NOT NULL DEFAULT 0,
    total_position_value    DOUBLE PRECISION NOT NULL DEFAULT 0,
    mag7_exposure_pct       DOUBLE PRECISION NOT NULL DEFAULT 0,
    daily_pnl               DOUBLE PRECISION NOT NULL DEFAULT 0,
    daily_pnl_pct           DOUBLE PRECISION NOT NULL DEFAULT 0,
    daily_trade_count       INTEGER NOT NULL DEFAULT 0,
    max_drawdown_today      DOUBLE PRECISION,
    trading_halted          BOOLEAN NOT NULL DEFAULT FALSE,
    halt_reason             TEXT,
    PRIMARY KEY (updated_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_account_state_latest ON account_state((1));
