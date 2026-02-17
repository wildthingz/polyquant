# Changelog

## [Unreleased] - 2026-02-16

### Changed - Strategy Pivot to VRP Premium Selling

**Decision**: Pivot from "buy calls when Polymarket sentiment is high" to **VRP premium selling** (iron condors, credit spreads) with Polymarket as a timing signal.

**Rationale**: Premium selling (short volatility) has a structural edge — implied volatility consistently exceeds realized volatility. Combined with Polymarket timing (sell when crowd is confident but IV is still elevated), this provides a more reliable, higher win-rate approach than directional call buying.

#### Strategy Changes
- **From**: Long options only (buy calls when bullish sentiment)
- **To**: Sell premium via iron condors (neutral), put credit spreads (bullish), call credit spreads (bearish)
- **Holding Period**: 7-45 days (was 1-7 days)
- **Primary Profit Driver**: Theta decay and IV crush (was directional move)

#### Updated Targets
- **Return**: 12-18% annualized (was 20-40%)
- **Sharpe**: > 0.8 (was > 1.0)
- **Max Drawdown**: < 20% (was < 15%)
- **Win Rate**: > 65% (was > 55%)

#### Trade Types Added
- Iron Condor (poly_prob 40-60%)
- Put Credit Spread (poly_prob > 60%)
- Call Credit Spread (poly_prob < 40%)

#### Entry Criteria Updated
- IV percentile > 50 (sell elevated premium)
- Polymarket certainty > 70% (crowd confident)
- Divergence > 10% (IV overpricing vs sentiment)
- Short strike delta ~0.20, long strike delta ~0.08
- DTE 7-45 days
- Credit-to-width ratio > 30%

#### Exit Logic Updated
- Take profit: 50% of max credit captured
- Stop loss: Spread value doubles (2x)
- Post-event IV crush exit
- 1 DTE theta burn exit

#### Risk Management Updated
- 5% per trade (based on max loss, not notional)
- 3 positions per underlying
- 15% total exposure
- -2% daily halt, -4% weekly reduce, -15% kill switch

### Removed
- **SESSION_NOTES.md** — Stale session log from 2026-02-13, info already in STATUS.md and CHANGELOG.md
- **ML Model section** from TRADING_STRATEGY.md — Replaced with rule-based approach; ML deferred to Phase 2+

### Changed - Documentation Cleanup
- **docs/TRADING_STRATEGY.md** — Full rewrite for VRP premium selling
- **README.md** — Updated subtitle, overview, key features for premium selling
- **STATUS.md** — Updated priorities (VRP backtest first), StrategyEngine marked as old logic
- **CLAUDE.md** — Updated project overview and priorities
- **docs/ARCHITECTURE.md** — Updated strategy layer descriptions for premium selling
- **docs/PHASED_ROLLOUT.md** — Updated all phase exit criteria targets
- **docs/index.md** — Updated status and ML model reference
- **quantconnect/README.md** — Updated strategy description and expected results
- **quantconnect/main.py** — Added DEPRECATED header (pending rewrite)

---

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
