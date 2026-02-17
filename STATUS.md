# PolyQuant Project Status

**Last Updated**: 2026-02-14
**Phase**: 1 (Local Simulation)
**Completion**: ~50%

---

## Quick Status

| Component | Status | Notes |
|-----------|--------|-------|
| EventBus | ✅ Working | Thread-safe pub/sub, 3 tests passing |
| Polymarket Feed | ✅ Live Data | WebSocket receiving real-time prices |
| IBKR Feed | ⚠️ Skeleton | Needs paper trading account |
| MarketDataAggregator | ✅ Working | Merges feeds, 2 tests passing |
| StrategyEngine | ⚠️ Old Logic | Generates call-buying signals (pending VRP premium selling rewrite) |
| Pricing Engine | ✅ Complete | Black-Scholes, Greeks, IV solver (5 tests) |
| Risk Manager | ❌ Missing | **CRITICAL - Top Priority** |
| Database | ⚠️ Ready | Schema exists, no data written |
| Rule-Based Signals | ❌ Not Started | VRP premium selling logic (replaces ML model) |
| Tests | ✅ Passing | 14/14 tests (35ms) |

---

## What Works Right Now

### Data Flow (Live & Tested)
```
Polymarket WSS → PolymarketClient → EventBus → MarketDataAggregator → StrategyEngine
```

**Confirmed with live data** (2026-02-14):
```
[06:22:39] Published price_change: market=0xaf9d...4214 price=0.9140
[06:22:39] SIGNAL GENERATED: BUY AAPL (Strength: 0.85)
```

### Working Components

**EventBus** (`include/polyquant/core/EventBus.h`)
- Thread-safe publish/subscribe
- Multiple subscribers supported
- Tests: PublishAndSubscribe, MultipleSubscribers, ThreadSafety

**Polymarket WebSocket** (`src/cpp/feed/PolymarketClient.cpp`)
- Endpoint: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- Subscription: `{"type": "market", "assets_ids": ["token1", "token2"]}`
- Receives: `book` and `price_change` events
- **Currently subscribed**: 2 test markets (not MAG7)

**MarketDataAggregator** (`src/cpp/core/MarketDataAggregator.cpp`)
- Merges Polymarket + IBKR data by contract_id
- Thread-safe snapshot retrieval
- Calculates spread percentage
- Tests: StoresAndRetrievesSnapshot, ReturnsEmptyForUnknownContract

**StrategyEngine** (`src/cpp/core/StrategyEngine.cpp`)
- **OLD LOGIC**: Entry logic: `poly_prob > 0.80` AND `spread < 5%` (call-buying, pending rewrite)
- Generates BUY/HOLD/SELL signals for single-leg calls
- **Pending**: Rewrite for VRP premium selling (iron condors, credit spreads)
- **Limitation**: Logs only, doesn't execute or persist
- Tests: GeneratesSignalOnHighProbability, RejectsWideSpread

**Pricing Engine** (`src/cpp/pricing/BlackScholes.cpp`)
- Black-Scholes call/put pricing
- Greeks: Delta, Gamma, Vega, Theta
- IV solver (Newton-Raphson)
- 5 tests passing, ready to use

**Database** (`schema.sql`)
- TimescaleDB with 5 hypertables
- Tables: market_data_ticks, signals, trades, system_logs, account_state
- **Not yet used** - no writes implemented

---

## What's Missing

### Critical (Blocking Phase 1)

**1. VRP Premium Selling Backtest** ⚠️ **TOP PRIORITY**
- Rewrite QuantConnect strategy for iron condors / credit spreads
- Validate VRP + Polymarket timing thesis
- Target: Sharpe > 0.8, max DD < 20%, win rate > 65%
- **Impact**: Must validate before building more infrastructure
- **Effort**: 2-3 days

**2. StrategyEngine Rewrite**
- Replace call-buying logic with premium selling signals
- Multi-leg spread evaluation (iron condors, credit spreads)
- IV percentile + poly certainty + divergence filters
- **Impact**: Core strategy logic is outdated
- **Effort**: 2-3 days

**3. Risk Manager**
- Position sizing (max loss per spread, not notional)
- Daily/weekly loss limits (-2% daily, -4% weekly, -15% kill switch)
- Max 3 positions per underlying, 15% total exposure
- Order validation for multi-leg spreads
- Kill switch logic
- **Impact**: Cannot execute any trades safely
- **Effort**: 2-3 days

**4. Order Execution Flow**
- RiskManager validates SpreadSignal → creates multi-leg Order
- Order sent to IBKRClient (combo orders)
- Track fills, handle rejections
- Write to trades table
- **Impact**: Cannot execute trades
- **Effort**: 1-2 days

**5. Data Persistence**
- Write signals to database
- Write trades to database
- Write market data (optional for Phase 1)
- **Impact**: No historical record
- **Effort**: 1 day

### Important (Phase 1 Nice-to-Have)

**6. Polymarket Market Discovery**
- REST API to find MAG7-related markets
- Auto-subscribe to relevant tokens
- **Current**: Hardcoded 2 test markets

**7. Monitoring**
- Prometheus metrics
- Grafana dashboards
- Alerting rules

---

## Known Issues

### Code Issues

**Hardcoded Test Markets** (`src/cpp/feed/PolymarketClient.cpp:84`)
```cpp
// TODO: Replace with dynamic market discovery
"101676997363687199724245607342877036148401850938023978421879460310389391082353"
```
Current market: "Will Trump deport <250k?" (not MAG7)

**No Reconnection Logic** (`src/cpp/feed/PolymarketClient.cpp:88`)
```cpp
// TODO: Implement exponential backoff reconnection
if (ec) {
    spdlog::error("Polymarket read failed: {} - will attempt reconnect", ec.message());
    return;  // Just exits
}
```

**Strategy Doesn't Check IBKR Data** (`src/cpp/core/StrategyEngine.cpp:40`)
```cpp
if (snapshot.poly_prob > 0.80) {
    // Generates signal even if opt_bid doesn't exist
    // Should verify IBKR data is available
}
```

**No Graceful Shutdown** (`src/cpp/main.cpp:145`)
```cpp
ioc.run();  // Runs forever, no SIGTERM handler
```

### Environment Issues

**Docker Compose Version Warning**
```
WARN: version attribute is obsolete
```
Fix: Remove `version: '3.8'` from docker-compose.yml line 1

**IBKR Gateway Login Failures**
```
Too many failed login attempts
```
Expected - using demo credentials, not a real issue

---

## Test Results

**Last Run**: 2026-02-14 06:26:23
```
[==========] 14 tests from 7 test suites ran (35ms)
[  PASSED  ] 14 tests

EventBusTest (3 tests)
MarketDataAggregatorTest (2 tests)
StrategyEngineTest (2 tests)
MarketDataUpdateTest (2 tests)
BlackScholesTest (2 tests)
GreeksTest (1 test)
IVSolverTest (2 tests)
```

**To run tests**:
```bash
docker-compose exec engine ./cmake-build-debug-docker/polyquant_tests
```

---

## Phase 1 Exit Criteria Progress

| Criterion | Progress | Blocker |
|-----------|----------|---------|
| Sharpe Ratio > 0.8 | 0% | Need 100 trades first |
| 100+ trades | 0/100 | Risk Manager needed |
| Win rate > 65% | 0% | Need backtest + live data |
| Max drawdown < 20% | 0% | Need live trading |
| Zero unhandled exceptions | ~90% | Good error handling exists |

**Estimated time to Phase 1 complete**: 2-3 weeks

---

## Next Actions (Priority Order)

### 1. VRP Premium Selling Backtest (HIGHEST PRIORITY)

**Decision**: Rewrite QuantConnect strategy for VRP premium selling before building more C++ infrastructure.

**Strategy Pivot**: From call-buying on high sentiment to premium selling (iron condors, credit spreads) with Polymarket timing.

**Steps**:
1. **Rewrite QuantConnect Backtest** (2-3 days)
   - Replace `quantconnect/main.py` with VRP premium selling logic
   - Iron condors when neutral, credit spreads when directional
   - Target: Sharpe > 0.8, Win Rate > 65%, Max DD < 20%

2. **Analyze Results & Tune** (1 day)
   - Review backtest metrics
   - Optimize IV percentile, certainty, and divergence thresholds
   - Walk-forward validation

3. **Export Parameters to C++** (1 day)
   - Document optimal parameters for StrategyEngine rewrite

---

### 2. Bug Fixes & Known Issues

- Fix hardcoded test markets in PolymarketClient
- Add WebSocket reconnection logic
- Add graceful shutdown (SIGTERM handler)

### 3. StrategyEngine Rewrite

- Replace call-buying logic with VRP premium selling
- Multi-leg spread signal generation
- IV percentile + poly certainty + divergence evaluation
- Files: `src/cpp/core/StrategyEngine.cpp`, `include/polyquant/core/StrategyEngine.h`

### 4. Risk Manager Implementation

- Files: `include/polyquant/risk/RiskManager.h`, `src/cpp/risk/RiskManager.cpp`
- Tests: `tests/test_risk_manager.cpp`
- Multi-leg spread validation, exposure limits, circuit breakers

### Then: Execution & Persistence

5. **Order Execution** — Multi-leg combo orders via IBKR
6. **Database Integration** — Write signals and trades
7. **Paper Trading** — Collect 100+ trades, validate against backtest

---

## How to Run

**Start Services**:
```bash
docker-compose up -d
```

**Build & Run Engine**:
```bash
docker-compose exec engine bash -c "
  cd /app &&
  cmake -B cmake-build-debug-docker -S . &&
  cmake --build cmake-build-debug-docker --target polyquant_engine &&
  ./cmake-build-debug-docker/src/cpp/polyquant_engine
"
```

**Run Tests**:
```bash
docker-compose exec engine bash -c "
  cd /app &&
  cmake --build cmake-build-debug-docker --target polyquant_tests &&
  ./cmake-build-debug-docker/polyquant_tests
"
```

**View Logs**:
```bash
docker-compose logs -f engine
```

---

## Recent Changes (2026-02-14)

- ✅ Fixed Polymarket WebSocket subscription format
- ✅ Confirmed live data flowing through entire pipeline
- ✅ Added 9 new unit tests (14 total now passing)
- ✅ Fixed .env loading for CLion
- ✅ Updated all documentation to reflect reality

**Files Changed**: 13 files (~362 additions, ~261 deletions)

---

## Technical Debt

1. **StrategyEngine implements old call-buying logic** - Needs full rewrite for VRP premium selling
2. **Lock-based EventBus** - May be bottleneck at high frequency (defer to Phase 2)
3. **Synchronous database writes** - Will block event loop (add batching)
4. **No rate limiting** - Could hit API limits (add before Phase 1 exit)
5. **Hardcoded market IDs** - Need dynamic discovery (medium priority)
6. **No metrics export** - Add Prometheus before Phase 2

---

**Questions?** See [docs/](docs/) for detailed documentation on architecture, APIs, and trading strategy.
