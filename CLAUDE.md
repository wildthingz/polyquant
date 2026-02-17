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
- **quantconnect/main.py**: QuantConnect backtesting strategy (current priority)
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

## Current Status & Priorities

1. **VRP backtest rewrite** — Rewrite QuantConnect strategy for premium selling (iron condors, credit spreads)
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
- StrategyEngine still implements old call-buying logic (pending VRP premium selling rewrite)
