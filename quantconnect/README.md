# PolyQuant - QuantConnect Implementation

Backtesting our VRP premium selling strategy (iron condors, credit spreads) on QuantConnect platform, using sentiment data as a timing signal.

## Why QuantConnect?

**Advantages over custom backtesting**:
- ✅ Free tier includes US equity options + sentiment data
- ✅ Institutional-grade historical data (tick/minute resolution)
- ✅ Realistic slippage and transaction costs built-in
- ✅ Unlimited backtests
- ✅ No need to collect/store historical data
- ✅ Cloud compute (no local resources)

**Trade-offs**:
- ❌ No direct Polymarket data (using Brain Sentiment as proxy)
- ❌ Python-based (our C++ engine is for live trading)
- ❌ Limited to QuantConnect's data universe

## Data Sources

### Primary: Brain Sentiment Indicator
**Proxy for Polymarket probabilities**

Brain Sentiment analyzes:
- SEC filings sentiment
- News sentiment
- Social media sentiment
- Wikipedia page views

**Mapping to our thesis**:
```
Polymarket "Will AAPL beat earnings?" at 75%
≈ Brain Sentiment showing high bullish score (0.7+)

Both capture forward-looking sentiment that may not be fully priced into IV
```

### Options Data
- US Equity Options Universe (all strikes, all expirations)
- Minute-level bid/ask quotes
- Greeks (Delta, Gamma, Vega, Theta, IV)
- Volume and open interest

## Strategy Implementation

**NOTE**: `main.py` currently implements the OLD call-buying strategy. It needs to be rewritten for VRP premium selling.

### Target Trade Types
- **Iron Condor**: When sentiment is neutral (poly_prob 40-60%)
- **Put Credit Spread**: When sentiment is bullish (poly_prob > 60%)
- **Call Credit Spread**: When sentiment is bearish (poly_prob < 40%)

### Entry Criteria
```python
1. IV Percentile > 50 (elevated premium to sell)
2. Polymarket Certainty > 70% (crowd is confident)
3. Divergence > 10% (IV overpricing vs sentiment)
4. Short strike delta ~ 0.20, long strike delta ~ 0.08
5. Spread < 5% (all legs)
6. DTE: 7-45 days
7. Credit-to-width ratio > 30%
```

### Exit Rules
```python
- Take Profit: 50% of max credit captured
- Stop Loss: Spread value doubles (2x credit)
- Theta Burn: 1 DTE remaining
- Post-event IV crush: Close after event resolves
- Liquidity: Any leg spread > 8%
```

### Risk Management
```python
- Max position size: 5% per trade (based on max loss)
- Max 3 positions per underlying
- Max sector exposure: 15% (all MAG7)
- Daily loss limit: -2%
- Weekly loss limit: -4% (reduce sizes)
- Kill switch: -15% drawdown
```

## Getting Started

### 1. Create QuantConnect Account
- Go to https://www.quantconnect.com
- Sign up for free account
- Verify email

### 2. Create New Algorithm
- Click "Lab" → "New Algorithm"
- Name: "PolyQuant Sentiment Strategy"
- Language: Python
- Copy contents of `main.py` into editor

### 3. Run Backtest
- Set date range (default: 2023-01-01 to 2024-01-01)
- Click "Backtest" button
- Wait 2-5 minutes for results

### 4. Analyze Results
**Minimum targets to proceed to live trading**:
- Sharpe Ratio > 0.8
- Total Return > 12% annualized
- Max Drawdown < 20%
- Win Rate > 65%
- Profit Factor > 1.3

## File Structure

```
quantconnect/
├── main.py          # Main algorithm (paste into QuantConnect)
├── README.md        # This file
└── results/         # Save backtest reports here
```

## Limitations & Future Work

### Current Limitations

1. **No Polymarket Data**
   - Using Brain Sentiment as proxy
   - Correlation unknown (need to validate)

2. **IV Percentile Approximation**
   - Currently using simple heuristic
   - Need to calculate actual historical percentile

3. **No Model Training**
   - Rule-based strategy (no XGBoost)
   - Can add ML in next iteration

### Enhancements

**Phase 1: Validate Sentiment Proxy**
```python
# Add correlation analysis
correlation = np.corrcoef(sentiment_signals, option_returns)
```

**Phase 2: Add ML Model**
```python
# Train XGBoost on features
features = [
    'sentiment_score',
    'iv_percentile',
    'divergence',
    'delta',
    'days_to_expiry'
]
model = self.TrainModel(features, target='profitable')
```

**Phase 3: Multi-Asset**
```python
# Expand beyond MAG7
self.universe = self.AddUniverseSelection(
    QC500UniverseSelectionModel()
)
```

## Expected Results

**Conservative Estimates** (based on VRP premium selling strategies):
- Sharpe Ratio: 0.8 - 1.2
- Annual Return: 12-18%
- Win Rate: 65-75%
- Max Drawdown: 15-20%
- Avg Trade Duration: 10-25 days

**If Sharpe < 0.8**:
- IV percentile threshold may need adjustment
- Polymarket certainty threshold may be too low
- Credit-to-width ratio filter may need tightening
- Consider tighter strike selection (higher delta for short legs)

## Integration with C++ Engine

After successful backtest:

1. **Export Parameters**
   - Optimal thresholds (IV percentile, certainty, divergence)
   - Strike selection rules (delta targets)
   - Exit triggers and position sizing

2. **Rewrite StrategyEngine in C++**
   - Replace call-buying logic with multi-leg spread evaluation
   - Implement iron condor / credit spread signal generation
   - Add IV percentile calculation
   - Test in paper trading (Phase 1)

3. **Monitor Divergence**
   - Compare QuantConnect backtest vs live results
   - Track multi-leg fill quality and slippage
   - Adjust for execution quality on combo orders

## Running the Backtest

### Option 1: QuantConnect Web IDE (Recommended)
1. Copy `main.py` to QuantConnect editor
2. Click "Backtest"
3. Download results PDF

### Option 2: Local Development (Requires Paid Tier)
```bash
# Install LEAN CLI
pip install lean

# Login
lean login

# Create project
lean project-create "PolyQuant"

# Copy main.py to project
cp main.py ~/Lean/PolyQuant/

# Run backtest
lean backtest "PolyQuant"
```

## Success Criteria

Before proceeding to C++ live implementation:

✅ **Performance**:
- Sharpe > 0.8
- Max DD < 20%
- Win rate > 65%

✅ **Statistical Significance**:
- 100+ trades in backtest
- Consistent across multiple 3-month periods

✅ **Robustness**:
- Test on 2022 (bear market)
- Test on 2021 (bull market)
- Performance doesn't degrade >30%

✅ **Execution Feasibility**:
- Avg spread < 4%
- Fill rate > 80% (simulated)
- Avg trade frequency: 2-5/week

## Next Steps

1. **Run Initial Backtest** (30 min)
   - Upload to QuantConnect
   - Run 1-year backtest
   - Review results

2. **Parameter Tuning** (2-3 hours)
   - Optimize sentiment threshold
   - Test different DTE ranges
   - Tune position sizing

3. **Walk-Forward Validation** (1 day)
   - Train on 2023 H1
   - Test on 2023 H2
   - Compare metrics

4. **Final Report** (2 hours)
   - Document parameters
   - Export for C++ implementation
   - Create STATUS.md update

---

**Questions?**
- QuantConnect Docs: https://www.quantconnect.com/docs/v2
- QuantConnect Community: https://www.quantconnect.com/forum
- Discord: https://discord.gg/quantconnect
