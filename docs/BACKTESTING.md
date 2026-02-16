# Backtesting Infrastructure

> **⚠️ DEPRECATED**: This document describes manual backtesting infrastructure (data collection, custom engine).
>
> **✅ RECOMMENDED**: Use QuantConnect platform instead. See [../quantconnect/README.md](../quantconnect/README.md)
>
> This document is kept for reference if you need to build custom backtesting infrastructure in the future.

---

## Overview

This describes how to build custom backtesting framework with train/validation/test splits to prevent overfitting and validate the Polymarket-to-options arbitrage strategy.

**Why you might need this**:
- QuantConnect doesn't have Polymarket data
- Need complete control over slippage model
- Want to backtest on proprietary data

**Why use QuantConnect instead** (recommended):
- Free tier includes options + sentiment data
- No data collection/storage needed
- Faster iteration (minutes vs weeks)
- Institutional-grade historical data

---

## Data Collection Strategy

### 1. Historical Polymarket Data

**Source**: Polymarket REST API (`https://clob.polymarket.com`)

**Markets to Track**: MAG7-related events
- Earnings outcomes (beat/miss)
- Product launches (successful/failed)
- Regulatory decisions (approval/rejection)
- Executive actions (CEO departures, scandals)

**Data Points Per Event**:
```json
{
  "market_id": "0x...",
  "condition_id": "0x...",
  "question": "Will AAPL beat Q1 2024 earnings?",
  "end_date": "2024-04-01T16:00:00Z",
  "resolution": "Yes",
  "timeseries": [
    {"timestamp": "2024-03-15T09:30:00Z", "yes_price": 0.55, "no_price": 0.45, "volume_24h": 125000},
    {"timestamp": "2024-03-15T10:00:00Z", "yes_price": 0.57, "no_price": 0.43, "volume_24h": 130000}
    // ... every 30 minutes
  ]
}
```

**Collection Script**: `scripts/collect_polymarket_history.py`
```python
# Collect 6-12 months of historical data
# Store in PostgreSQL: polymarket_events, polymarket_timeseries tables
```

---

### 2. Historical Options Data

**Source**: IBKR Historical Data API or vendor (Algoseek, TickData.com)

**Requirements**:
- **6-12 months** of minute-level data
- **All strikes** for 7-60 DTE options on MAG7
- **Bid/ask quotes** (not just last trade)
- **Implied volatility** already calculated
- **Greeks** (or raw data to compute them)

**Data Points Per Option**:
```json
{
  "timestamp": "2024-03-15T09:30:00Z",
  "underlying": "AAPL",
  "strike": 175.0,
  "expiration": "2024-04-19",
  "option_type": "CALL",
  "bid": 4.85,
  "ask": 4.95,
  "mid": 4.90,
  "iv": 0.28,
  "delta": 0.52,
  "gamma": 0.045,
  "vega": 0.18,
  "theta": -0.12,
  "volume": 1200,
  "open_interest": 8500
}
```

**Collection Script**: `scripts/collect_options_history.py`

**Cost Estimate**:
- **Free**: IBKR Historical Data API (limited to 60 days, 6 requests/min)
- **Paid**: Algoseek (~$200/month for MAG7 options history)

---

### 3. Database Schema

**New Tables**:

```sql
-- Historical Polymarket events
CREATE TABLE polymarket_events (
    event_id SERIAL PRIMARY KEY,
    market_id TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    question TEXT NOT NULL,
    underlying_ticker TEXT,  -- Manually tagged: AAPL, TSLA, etc.
    event_type TEXT,          -- earnings, product_launch, regulatory, executive
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    resolution TEXT,          -- Yes/No/Invalid
    resolution_price DOUBLE PRECISION,
    UNIQUE(market_id)
);

-- Minute-level Polymarket prices
CREATE TABLE polymarket_timeseries (
    id SERIAL PRIMARY KEY,
    event_id INT REFERENCES polymarket_events(event_id),
    timestamp TIMESTAMPTZ NOT NULL,
    yes_price DOUBLE PRECISION,
    no_price DOUBLE PRECISION,
    volume_24h DOUBLE PRECISION,
    liquidity DOUBLE PRECISION
);

SELECT create_hypertable('polymarket_timeseries', 'timestamp');
CREATE INDEX idx_poly_event_time ON polymarket_timeseries(event_id, timestamp DESC);

-- Historical options quotes
CREATE TABLE options_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    underlying TEXT NOT NULL,
    strike DOUBLE PRECISION NOT NULL,
    expiration DATE NOT NULL,
    option_type TEXT NOT NULL,  -- CALL/PUT
    bid DOUBLE PRECISION,
    ask DOUBLE PRECISION,
    mid DOUBLE PRECISION,
    iv DOUBLE PRECISION,
    delta DOUBLE PRECISION,
    gamma DOUBLE PRECISION,
    vega DOUBLE PRECISION,
    theta DOUBLE PRECISION,
    volume INT,
    open_interest INT
);

SELECT create_hypertable('options_history', 'timestamp');
CREATE INDEX idx_options_lookup ON options_history(underlying, expiration, strike, option_type, timestamp DESC);
```

---

## Train/Validation/Test Split Strategy

### Time-Based Split (Walk-Forward Analysis)

**Problem**: Financial data is time-series - can't use random shuffling

**Solution**: Walk-forward with expanding window

```
|<-------- 6 months historical data -------->|
|<-- Train -->|<- Val ->|<- Test ->| Future |
   (60%)        (20%)      (20%)
Month 1-3     Month 4-4.5  Month 5-6

Then roll forward:
|<-------- Train -------->|<- Val ->|<- Test ->|
       Month 1-4          Month 5-5.5 Month 6
```

**Implementation**:
```python
def create_splits(start_date, end_date):
    total_days = (end_date - start_date).days

    train_end = start_date + timedelta(days=int(total_days * 0.6))
    val_end = train_end + timedelta(days=int(total_days * 0.2))

    return {
        'train': (start_date, train_end),
        'validation': (train_end, val_end),
        'test': (val_end, end_date)
    }
```

---

## Feature Engineering

**Features for XGBoost Model**:

```python
def create_features(event, option_quote, timestamp):
    """
    Generate features at signal generation time
    """
    return {
        # Polymarket sentiment
        'poly_yes_price': event['yes_price'],
        'poly_no_price': event['no_price'],
        'poly_prob_change_1h': event['yes_price'] - event['yes_price_1h_ago'],
        'poly_prob_change_24h': event['yes_price'] - event['yes_price_24h_ago'],
        'poly_volume_24h': event['volume_24h'],
        'poly_days_to_event': (event['end_date'] - timestamp).days,

        # Options greeks
        'opt_delta': option_quote['delta'],
        'opt_gamma': option_quote['gamma'],
        'opt_vega': option_quote['vega'],
        'opt_theta': option_quote['theta'],
        'opt_iv': option_quote['iv'],
        'opt_iv_percentile': percentile(option_quote['iv'], window='90d'),

        # Options market structure
        'opt_spread_pct': (option_quote['ask'] - option_quote['bid']) / option_quote['mid'],
        'opt_volume': option_quote['volume'],
        'opt_open_interest': option_quote['open_interest'],
        'opt_days_to_expiry': (option_quote['expiration'] - timestamp).days,
        'opt_moneyness': option_quote['strike'] / underlying_price,

        # Divergence metrics (KEY ALPHA SOURCE)
        'sentiment_iv_divergence': event['yes_price'] - normalized_iv(option_quote['iv']),
        'sentiment_delta_divergence': event['yes_price'] - option_quote['delta'],

        # Underlying technicals
        'underlying_price': underlying_price,
        'underlying_sma_20': sma(underlying_price, 20),
        'underlying_rsi_14': rsi(underlying_price, 14),

        # Time features
        'hour_of_day': timestamp.hour,
        'day_of_week': timestamp.weekday(),
        'is_market_open': is_market_hours(timestamp)
    }
```

**Target Variable**:
```python
def create_target(entry_price, exit_price, holding_period_hours):
    """
    Binary classification: Did trade hit +50% profit target?
    """
    pnl_pct = (exit_price - entry_price) / entry_price

    # Penalize slow winners (theta decay)
    time_penalty = 0.05 * (holding_period_hours / 24)

    return 1 if (pnl_pct - time_penalty) >= 0.50 else 0
```

---

## Preventing Overfitting

### 1. Cross-Validation with Purging

**Problem**: Standard CV leaks future data into training

**Solution**: Purged K-Fold
```python
from sklearn.model_selection import TimeSeriesSplit

def purged_cv(data, n_splits=5, embargo_pct=0.02):
    """
    Time-series CV with embargo period to prevent lookahead
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)

    for train_idx, test_idx in tscv.split(data):
        # Add embargo: remove samples too close to test set
        embargo_size = int(len(train_idx) * embargo_pct)
        train_idx = train_idx[:-embargo_size]

        yield train_idx, test_idx
```

### 2. Regularization

```python
xgb_params = {
    'max_depth': 3,              # Shallow trees prevent overfitting
    'min_child_weight': 5,        # Require minimum samples per leaf
    'gamma': 1.0,                 # Min loss reduction for split
    'subsample': 0.8,             # Row sampling
    'colsample_bytree': 0.8,      # Feature sampling
    'lambda': 1.0,                # L2 regularization
    'alpha': 0.1,                 # L1 regularization
    'learning_rate': 0.01,        # Low learning rate
    'n_estimators': 500,
    'early_stopping_rounds': 50   # Stop when val score plateaus
}
```

### 3. Out-of-Sample Testing

**Rule**: Test set is NEVER touched until final evaluation

```python
# Train on train set
model.fit(X_train, y_train)

# Tune hyperparameters on validation set
best_params = hyperopt(X_val, y_val)

# ONLY AFTER FINALIZING MODEL: evaluate on test set
final_metrics = evaluate(X_test, y_test)
```

### 4. Walk-Forward Validation

**Test Model Degredation Over Time**:
```python
# Train on Month 1-3, test on Month 4
# Train on Month 1-4, test on Month 5
# Train on Month 1-5, test on Month 6

# Check if test performance degrades → model is overfit to older data
```

---

## Backtesting Engine

### Architecture

```
scripts/backtest.py
├── DataLoader          # Load historical poly + options data
├── FeatureEngine       # Compute features for each timestamp
├── MLModel             # XGBoost inference
├── StrategyEngine      # Entry/exit logic (from src/cpp/core)
├── RiskManager         # Pre-trade checks (from docs/TRADING_STRATEGY.md)
├── PositionTracker     # Track P&L, exits
└── PerformanceAnalyzer # Sharpe, drawdown, calibration
```

### Simulation Details

**Slippage Model**:
```python
def simulate_fill(order, market_data):
    """
    Realistic fill simulation
    """
    if order.type == 'LIMIT':
        # Assume filled at limit price if within bid/ask
        if order.side == 'BUY' and order.price >= market_data['ask']:
            fill_price = market_data['ask']
        elif order.side == 'SELL' and order.price <= market_data['bid']:
            fill_price = market_data['bid']
        else:
            # Limit order sits on book - not filled this bar
            return None
    elif order.type == 'MARKET':
        # Market orders always fill, pay the spread
        slippage = market_data['spread'] / 2
        fill_price = market_data['mid'] + slippage

    return fill_price
```

**Transaction Costs**:
```python
COSTS = {
    'commission_per_contract': 0.65,  # IBKR options commission
    'exchange_fee': 0.12,             # Per contract
    'sec_fee': 0.0000278,             # SEC fee (per $ of premium)
    'slippage_bps': 10                # 0.1% average slippage
}
```

### Backtest Loop

```python
def run_backtest(start_date, end_date, model):
    positions = []
    cash = 10000
    equity_curve = []

    # Iterate through each timestamp
    for timestamp in date_range(start_date, end_date, freq='30min'):
        # 1. Get market data
        poly_data = get_polymarket_snapshot(timestamp)
        options_data = get_options_quotes(timestamp)

        # 2. Generate features
        features = create_features(poly_data, options_data, timestamp)

        # 3. ML inference
        signal_strength = model.predict_proba(features)[1]

        # 4. Strategy decision
        if signal_strength > 0.8 and risk_manager.approve_order():
            # Entry logic
            order = create_order(signal_strength, options_data)
            fill_price = simulate_fill(order, options_data)
            if fill_price:
                positions.append(Position(order, fill_price, timestamp))
                cash -= order.value

        # 5. Check exits for existing positions
        for pos in positions:
            exit_signal = check_exit_triggers(pos, options_data, poly_data)
            if exit_signal:
                exit_price = simulate_fill(exit_order, options_data)
                pos.close(exit_price, timestamp)
                cash += pos.exit_value

        # 6. Track equity
        equity = cash + sum(pos.unrealized_pnl for pos in positions if pos.is_open)
        equity_curve.append({'timestamp': timestamp, 'equity': equity})

    return analyze_performance(equity_curve, positions)
```

---

## Metrics & Evaluation

### Performance Metrics

```python
def calculate_metrics(trades):
    returns = [t.pnl_pct for t in trades]

    return {
        # Profitability
        'total_return': sum(returns),
        'sharpe_ratio': np.mean(returns) / np.std(returns) * np.sqrt(252),
        'win_rate': sum(1 for r in returns if r > 0) / len(returns),
        'avg_win': np.mean([r for r in returns if r > 0]),
        'avg_loss': np.mean([r for r in returns if r < 0]),
        'profit_factor': abs(sum(r for r in returns if r > 0) / sum(r for r in returns if r < 0)),

        # Risk
        'max_drawdown': calculate_max_drawdown(equity_curve),
        'volatility': np.std(returns) * np.sqrt(252),
        'downside_deviation': np.std([r for r in returns if r < 0]) * np.sqrt(252),

        # Model calibration
        'calibration_error': abs(avg_signal_strength - win_rate),

        # Execution
        'avg_holding_period_hours': np.mean([t.exit_time - t.entry_time for t in trades]),
        'num_trades': len(trades)
    }
```

### Overfitting Detection

```python
def detect_overfitting(train_metrics, val_metrics, test_metrics):
    """
    Compare metrics across splits
    """

    # Warning signs:
    checks = {
        'train_val_sharpe_gap': train_metrics['sharpe'] - val_metrics['sharpe'] > 0.5,
        'val_test_sharpe_gap': val_metrics['sharpe'] - test_metrics['sharpe'] > 0.3,
        'test_sharpe_negative': test_metrics['sharpe'] < 0,
        'calibration_degrades': test_metrics['calibration_error'] > 0.15
    }

    if any(checks.values()):
        print("⚠️  OVERFITTING DETECTED")
        for check, failed in checks.items():
            if failed:
                print(f"  - {check}: FAILED")
        return True

    return False
```

---

## Implementation Plan

### Phase 1: Data Collection (Week 1-2)
- [ ] Script to pull Polymarket historical events
- [ ] Script to pull IBKR options history (or purchase data)
- [ ] Manually tag events to MAG7 tickers
- [ ] Create database schema and load data
- [ ] Validation: 50+ tagged events, 6+ months coverage

### Phase 2: Feature Engineering (Week 2-3)
- [ ] Implement feature extraction pipeline
- [ ] Generate training dataset
- [ ] Exploratory analysis (correlations, distributions)
- [ ] Create train/val/test splits

### Phase 3: Model Training (Week 3-4)
- [ ] Train XGBoost with conservative hyperparams
- [ ] Hyperparameter tuning on validation set
- [ ] Walk-forward validation
- [ ] Check for overfitting

### Phase 4: Backtesting (Week 4-5)
- [ ] Build Python backtesting engine
- [ ] Implement slippage/cost model
- [ ] Run backtest on test set
- [ ] Generate performance report

### Phase 5: Validation (Week 5-6)
- [ ] Compare backtest vs Phase 1 paper trading
- [ ] Stress test with 2020 volatility data
- [ ] Sensitivity analysis (fees, slippage)
- [ ] Final overfitting check

---

## Success Criteria

**Minimum Requirements to Proceed to Paper Trading**:

✅ **Data Quality**:
- 6+ months of aligned Polymarket + options data
- 50+ tagged events (earnings, launches, etc.)
- <5% missing data in critical fields

✅ **Model Performance** (on test set):
- Sharpe Ratio > 1.0
- Win rate within ±10% of avg signal strength
- Max drawdown < 15%
- Calibration error < 0.10

✅ **Overfitting Checks**:
- Train/val Sharpe gap < 0.5
- Val/test Sharpe gap < 0.3
- Walk-forward validation shows consistent performance

✅ **Execution Feasibility**:
- Avg trade frequency: 2-5 trades/week
- Avg holding period: 1-5 days
- 80%+ of trades have spread <5%

---

## Future Enhancements

- [ ] Monte Carlo simulation (1000+ scenarios)
- [ ] Regime detection (bull/bear/sideways)
- [ ] Multi-asset correlation analysis
- [ ] Real-time model retraining pipeline
- [ ] A/B testing framework (compare model versions)

---

**Next Steps**: Start with `scripts/collect_polymarket_history.py` to gather data.
