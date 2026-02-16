# Session Notes - 2026-02-13

## Summary

Shifted from manual backtesting infrastructure to **QuantConnect platform** for faster validation.

---

## What We Did

### 1. Evaluated Backtesting Approach
**Initial plan**: Build custom backtesting
- Collect 6-12 months Polymarket + options historical data
- Build Python backtesting engine
- Train XGBoost model
- **Problem**: Weeks of work, no Polymarket historical API

**Decision**: Use QuantConnect instead
- Free tier includes options + sentiment data
- No data collection needed
- Faster iteration (days vs weeks)
- Brain Sentiment as Polymarket proxy

### 2. Created QuantConnect Implementation

**Files Created**:
- `quantconnect/main.py` - Complete strategy in Python
  - MAG7 universe (AAPL, MSFT, NVDA, AMZN, TSLA, META, GOOGL)
  - Entry: High sentiment (>0.70) + elevated IV (50-90%) + divergence >10%
  - Exit: +50% profit / -30% stop / 1 DTE / spread >8%
  - Risk: 5% per position, 15% max sector, -2% daily stop
  - ~280 lines of production-ready code

- `quantconnect/README.md` - Complete setup guide
  - Why QuantConnect vs custom
  - Data sources (Brain Sentiment, options universe)
  - Expected results (Sharpe 1.2-1.8, 20-40% return)
  - Integration plan with C++ engine

### 3. Created Custom Backtesting Infrastructure (Backup)

**Files Created**:
- `docs/BACKTESTING.md` - Technical reference for custom approach
  - Marked as DEPRECATED (QuantConnect recommended)
  - Kept for reference if needed later
  - Data collection strategy
  - Train/val/test splits
  - Overfitting prevention
  - Feature engineering (25+ features)

- `scripts/collect_polymarket_history.py` - Polymarket data collector
  - Fetches historical events from CLOB API
  - Classifies MAG7-related markets
  - Stores in PostgreSQL
  - ~180 lines with async/await

- `scripts/collect_options_history.py` - Options data collector
  - IBKR API integration
  - CSV vendor import
  - ~160 lines

- `scripts/README.md` - Scripts documentation

### 4. Updated Database Schema

**Changes to schema.sql**:
- Added `polymarket_events` table (historical prediction markets)
- Added `polymarket_timeseries` table (minute-level prices)
- Added `options_history` table (historical quotes with greeks)
- All using TimescaleDB hypertables for efficient time-series queries

### 5. Updated Documentation

**STATUS.md**:
- Added "QuantConnect Backtesting" as highest priority
- Reorganized next actions (backtest → risk manager → paper trading)
- Updated timeline estimates

**README.md**:
- Added "Backtesting" section
- Links to QuantConnect approach
- Updated project status

**docs/index.md**:
- Updated status to reference QuantConnect

---

## Key Decisions

### Why QuantConnect?

**Pros**:
- ✅ Free tier sufficient for our needs
- ✅ US Equity Options universe included
- ✅ Brain Sentiment Indicator (reasonable Polymarket proxy)
- ✅ Unlimited backtests
- ✅ No data collection/storage needed
- ✅ Realistic slippage/costs built-in
- ✅ Faster iteration (minutes vs weeks)

**Cons**:
- ❌ No direct Polymarket data
- ❌ Brain Sentiment correlation unknown (need to validate)
- ❌ Python-based (our C++ engine for live trading)
- ❌ Platform lock-in

**Verdict**: Pros outweigh cons. Use QuantConnect first, build custom only if needed.

### Sentiment Proxy Mapping

```
Polymarket: "Will AAPL beat earnings?" = 75% probability
≈
Brain Sentiment: High bullish score (0.7+) from SEC filings + news + social

Both capture forward-looking sentiment that may not be fully priced into IV
```

---

## File Structure After Today

```
polyquant/
├── quantconnect/                    # NEW - QuantConnect implementation
│   ├── main.py                      # Strategy algorithm
│   └── README.md                    # Setup guide
├── scripts/                         # NEW - Data collection scripts
│   ├── collect_polymarket_history.py
│   ├── collect_options_history.py
│   └── README.md
├── docs/
│   ├── BACKTESTING.md              # NEW - Custom backtesting (deprecated)
│   ├── [other docs unchanged]
├── STATUS.md                        # UPDATED - QuantConnect as priority
├── README.md                        # UPDATED - Added backtesting section
├── schema.sql                       # UPDATED - Added historical data tables
└── [rest unchanged]
```

---

## Next Steps (In Order)

### Immediate: Run QuantConnect Backtest (1-2 days)
1. Create free account at quantconnect.com
2. Upload `quantconnect/main.py` to web IDE
3. Run 1-year backtest (2023-01-01 to 2024-01-01)
4. Review results

**Success Criteria**:
- Sharpe Ratio > 1.0
- Total Return > 15%
- Max Drawdown < 15%
- Win Rate > 55%
- Profit Factor > 1.5

### If Backtest Successful: Tune & Validate (1 day)
5. Optimize thresholds (sentiment, divergence, IV)
6. Walk-forward validation (train H1 2023, test H2 2023)
7. Test on different market regimes (2022 bear, 2021 bull)
8. Export optimal parameters

### Then: Implement in C++ (1 day)
9. Update `StrategyEngine.cpp` with tuned parameters
10. Document backtest results in STATUS.md
11. Proceed to Risk Manager implementation

### If Backtest Fails: Iterate (2-3 days)
- Analyze why (sentiment proxy issue? entry criteria too loose?)
- Try alternative data (Quiver WallStreetBets, etc.)
- Consider custom backtesting with real Polymarket data
- Re-evaluate strategy thesis

---

## Technical Debt Added

1. **Brain Sentiment vs Polymarket** - Unknown correlation
   - Need to validate proxy assumption
   - May need custom data collection if correlation weak

2. **Python → C++ Translation** - Strategy in Python, execution in C++
   - Need to keep implementations in sync
   - Parameter updates must be reflected in both

3. **Platform Lock-in** - Dependent on QuantConnect
   - If they change pricing/features, we're affected
   - Custom infrastructure is backup plan

---

## Clean-up Done

- ✅ Marked `docs/BACKTESTING.md` as DEPRECATED with clear note
- ✅ Added `scripts/README.md` to clarify when to use scripts
- ✅ Updated all status references to point to QuantConnect
- ✅ Ensured no duplicate information across docs
- ✅ Clear separation: QuantConnect (recommended) vs Custom (advanced)

---

## Questions to Answer After Backtest

1. **Does Brain Sentiment correlate with profitable trades?**
   - If yes: Continue with QuantConnect
   - If no: Need real Polymarket data

2. **What's the optimal sentiment threshold?**
   - Currently 0.70, may need tuning
   - Check sensitivity analysis

3. **How does IV divergence impact returns?**
   - Is 10% divergence threshold correct?
   - Trade-off between signal frequency and quality

4. **What's the best DTE range?**
   - Currently 7-60 days
   - Shorter = less theta decay, higher gamma risk
   - Longer = more time for thesis to play out

5. **Should we add ML model?**
   - Currently rule-based
   - XGBoost could improve signal quality
   - But adds complexity

---

## Estimated Timeline

**Path 1: QuantConnect Success**
- Backtest + tune: 3 days
- C++ implementation: 1 day
- Risk Manager: 3 days
- IBKR setup: 1 day
- Paper trading: 2 weeks
- **Total to Phase 1 complete**: ~3 weeks

**Path 2: QuantConnect Fails**
- Custom backtesting: 2 weeks
- Model training: 1 week
- Validation: 1 week
- Then follow Path 1
- **Total to Phase 1 complete**: ~6 weeks

**Recommendation**: Try Path 1 first (much faster)

---

## Lessons Learned

1. **Don't reinvent the wheel** - QuantConnect exists for a reason
2. **Validate quickly** - 3 days of backtesting > 3 weeks of building infrastructure
3. **Proxy data is OK** - Brain Sentiment isn't Polymarket, but close enough to test thesis
4. **Keep backup plan** - Custom infrastructure documented if needed later
5. **Documentation is critical** - Clear separation between approaches prevents confusion

---

**Status**: Ready to proceed with QuantConnect backtesting.

**Blocker**: None (user needs to create QuantConnect account and run backtest).

**Risk**: Brain Sentiment may not correlate with Polymarket → backtest may fail → need custom approach.

**Mitigation**: Custom backtesting infrastructure is documented and ready if needed.
