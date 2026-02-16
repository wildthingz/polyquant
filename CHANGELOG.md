# Changelog

## [Unreleased] - 2026-02-13

### Added - QuantConnect Backtesting Infrastructure

#### New Files
- **`quantconnect/main.py`** - Complete strategy implementation for QuantConnect platform
  - MAG7 universe (7 tickers)
  - Brain Sentiment as Polymarket proxy
  - Entry/exit logic with risk management
  - ~280 lines, production-ready

- **`quantconnect/README.md`** - Comprehensive setup guide
  - Platform comparison (QuantConnect vs custom)
  - Expected results and success criteria
  - Integration plan with C++ engine

- **`docs/BACKTESTING.md`** - Custom backtesting reference (marked DEPRECATED)
  - Manual data collection strategy
  - Train/val/test splits
  - Feature engineering (25+ features)
  - Overfitting prevention techniques
  - Kept for reference if QuantConnect approach fails

- **`scripts/collect_polymarket_history.py`** - Polymarket historical data collector
  - Fetches events from CLOB API
  - MAG7 classification
  - Stores in PostgreSQL

- **`scripts/collect_options_history.py`** - Options historical data collector
  - IBKR API integration
  - CSV vendor import

- **`scripts/README.md`** - Scripts documentation and usage guide

- **`SESSION_NOTES.md`** - Detailed session summary

#### Database Schema Updates
- Added `polymarket_events` table for historical prediction markets
- Added `polymarket_timeseries` table for minute-level Polymarket prices
- Added `options_history` table for historical options quotes with greeks
- All using TimescaleDB hypertables

#### Documentation Updates
- **`STATUS.md`** - Added QuantConnect backtesting as highest priority
- **`README.md`** - Added Backtesting section with QuantConnect recommendation
- **`docs/index.md`** - Updated project status to reference QuantConnect

### Changed

#### Strategy Shift
- **From**: Manual backtesting (collect data → build engine → train model)
- **To**: QuantConnect platform (free tier, institutional data, faster iteration)
- **Reason**: Weeks → days validation, no Polymarket historical API exists

#### Next Actions Priority
1. ~~Implement Risk Manager~~ → **Run QuantConnect backtest first**
2. Analyze results and tune parameters
3. Export parameters to C++ engine
4. Then implement Risk Manager (if backtest successful)

### Rationale

**Why QuantConnect?**
- ✅ Free tier includes US equity options + Brain Sentiment data
- ✅ Unlimited backtests on institutional-grade historical data
- ✅ Realistic slippage/transaction costs built-in
- ✅ No data collection/storage infrastructure needed
- ✅ Faster validation (3 days vs 3 weeks)

**Trade-offs Accepted**:
- ❌ Brain Sentiment (not Polymarket) - reasonable proxy, needs validation
- ❌ Python algorithm (C++ for live trading) - worth it for speed
- ❌ Platform dependency - mitigated by keeping custom infrastructure docs

### Decision Log

**Decision**: Use QuantConnect for initial strategy validation
**Date**: 2026-02-13
**Rationale**: Faster iteration, lower risk, validates thesis before heavy C++ development
**Alternatives Considered**: Custom backtesting (too slow), paper trading without backtest (too risky)
**Reversibility**: High - custom infrastructure documented if needed

### Success Metrics

**QuantConnect Backtest Targets**:
- Sharpe Ratio > 1.0
- Total Return > 15% (1 year)
- Max Drawdown < 15%
- Win Rate > 55%
- Profit Factor > 1.5
- 100+ trades for statistical significance

**If Targets Met**: Export parameters to C++ engine, proceed to Risk Manager
**If Targets Missed**: Analyze failure mode, iterate on strategy or use custom backtesting

---

## Previous Changes

See git history for changes from previous sessions.

---

## Format

This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

### Categories
- **Added** - New features
- **Changed** - Changes to existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Vulnerability fixes
