# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PolyQuant is an event-driven options trading system that sells premium (iron condors, credit spreads) on Mag 7 stocks (AAPL, NVDA, MSFT, AMZN, TSLA, META, GOOGL), using Polymarket prediction market data as a timing signal to identify when event uncertainty is overpriced. Strategy: VRP (Volatility Risk Premium) harvesting with Polymarket timing overlay. Target: 12-18% annualized, Sharpe ~0.8. Currently in Phase 1 (Local Simulation, ~50% complete).

**Tech stack**: C++20 execution engine + Python 3.10 backtesting + PostgreSQL/TimescaleDB + Docker

## Build & Development Commands

All builds run inside Docker containers:

```bash
# Start all services (db, ib_gateway, engine, ml_worker)
docker-compose up -d

# Build C++ engine
docker-compose exec engine bash -c "cd /app && cmake -B cmake-build-debug-docker -S . && cmake --build cmake-build-debug-docker --target polyquant_engine"

# Run C++ engine
docker-compose exec engine ./cmake-build-debug-docker/src/cpp/polyquant_engine

# Run all tests (14 tests, GoogleTest)
docker-compose exec engine bash -c "cmake --build cmake-build-debug-docker --target polyquant_tests && ./cmake-build-debug-docker/polyquant_tests"

# Run a single test by filter
docker-compose exec engine ./cmake-build-debug-docker/polyquant_tests --gtest_filter="PricingTest.CallPutParity"

# View engine logs
docker-compose logs -f engine

# Reset database (schema auto-loads from schema.sql)
docker-compose down && docker-compose up -d
```

CMake uses C++20 with `-Wall -Wextra -O3`. Dependencies: Boost (asio), nlohmann/json, spdlog, libpqxx, GoogleTest, OpenSSL, ONNX Runtime, IBKR TWS API.

## Architecture

### Data Flow
```
Polymarket WebSocket → PolymarketClient → EventBus → MarketDataAggregator → StrategyEngine → [Risk Manager] → [Order Execution]
```

The EventBus (`include/polyquant/core/EventBus.h`) is a thread-safe pub/sub system that decouples all components. Currently, live Polymarket data flows through to signal generation but risk management and order execution are not yet implemented. StrategyEngine will be rewritten to generate multi-leg premium selling signals (iron condors, credit spreads) instead of current call-buying signals.

### C++ Engine (src/cpp/, include/polyquant/)
- **core/**: EventBus (pub/sub), MarketDataAggregator (merges Polymarket + IBKR feeds), StrategyEngine (signal generation)
- **feed/**: PolymarketClient (WebSocket, live), IBKRClient (skeleton)
- **pricing/**: BlackScholes (options pricing, Greeks, IV solver)

### Python Components
- **quantconnect/main.py**: VRP premium selling backtest (iron condors, bull put spreads, bear call spreads) using Brain Sentiment as Polymarket proxy. Ready to run on QuantConnect (2022-2024, $100K). Requires BrainSentimentIndicator7Day data subscription.
- **scripts/**: Historical data collection (Polymarket events, options quotes)

### Database (schema.sql)
8 TimescaleDB hypertables: market_data_ticks, signals, trades, system_logs, account_state, polymarket_events, polymarket_timeseries, options_history.

### Docker Services (docker-compose.yml)
- **db**: TimescaleDB on port 5432
- **ib_gateway**: IBKR Gateway on port 4002 (API) / 5900 (VNC)
- **engine**: C++ build environment with SSH on port 2222
- **ml_worker**: Python ML environment

### Test Files
- `tests/test_pricing.cpp` — Black-Scholes, Greeks, IV solver (5 tests)
- `tests/test_market_data.cpp` — EventBus, Aggregator, StrategyEngine (9 tests)

## Strategy Validation Protocol

Every new strategy (or major strategy change) goes through this pipeline before production. Each stage is cheaper to fail at than the next — filter out bad ideas early.

1. **Rule-based backtest (QuantConnect)** — Implement strategy as simple if/then rules, backtest on QC historical data. Validates the core thesis. Minutes to run.
2. **ML backtest (QuantConnect)** — Use trade data from step 1 to train XGBoost. Replace fixed thresholds with learned model. Backtest again with walk-forward validation (train on earlier period, test on later). Compare ML vs rule-based.
3. **Real historical data backtest** — Gather actual data from primary sources (e.g., Polymarket, IBKR), clean it, and backtest locally. Catches proxy bias from step 1-2 (Brain Sentiment ≠ Polymarket).
4. **Paper forward test** — Run the strategy live with paper money (no real capital). Catches execution issues, slippage, fill quality, operational bugs.
5. **Small live test ($500)** — Real money, small scale. Catches real market impact and psychological factors.
6. **Production** — Scale up capital gradually per PHASED_ROLLOUT.md.

A strategy must pass each stage before advancing to the next. If it fails at any stage, iterate or discard — don't skip ahead.

## Current Status & Priorities

1. **~~VRP backtest rewrite~~** — DONE. `quantconnect/main.py` rewritten for VRP premium selling. Next: run on QuantConnect, validate metrics (Sharpe > 0.8, DD < 20%, WR > 65%). Note: requires BrainSentimentIndicator7Day paid data subscription; may need a free-tier fallback proxy.
2. **Bug fixes** — Hardcoded markets, reconnection logic, graceful shutdown
3. **StrategyEngine rewrite** — Replace call-buying logic with VRP premium selling signals
4. **Risk Manager** — Not yet implemented; needed before any live trading
5. **Order Execution** — IBKRClient needs multi-leg combo order support
6. **Database Persistence** — Schema exists but no writes from C++ engine yet

## Known Issues

- PolymarketClient uses hardcoded non-MAG7 test markets
- No WebSocket reconnection logic
- No graceful shutdown (no SIGTERM handler)
- Strategy generates signals even without IBKR options data
- StrategyEngine (C++) still implements old call-buying logic (pending VRP premium selling rewrite)
- quantconnect/main.py not yet validated on QuantConnect — needs backtest run and metrics review
