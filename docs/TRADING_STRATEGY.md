# Trading Strategy & Logic

Complete specification of PolyQuant's VRP (Volatility Risk Premium) premium selling strategy, using Polymarket prediction market data as a timing signal.

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Target Universe](#target-universe)
3. [Trade Types](#trade-types)
4. [The Greeks](#the-greeks)
5. [Entry Criteria](#entry-criteria)
6. [Position Management](#position-management)
7. [Exit Logic](#exit-logic)
8. [Risk Management](#risk-management)
9. [Edge Analysis](#edge-analysis)

---

## Strategy Overview

**Core Thesis**: Sell options premium when implied volatility is elevated, using Polymarket probabilities as a timing signal to identify when event uncertainty is overpriced relative to likely outcomes.

**Strategy Type**: Volatility Risk Premium (VRP) harvesting with Polymarket timing overlay

**Holding Period**: 7-45 days (average ~21 days)

**Direction**: Sell premium, not buy direction. We are net short volatility, collecting theta decay as our primary profit driver.

**Target**: 12-18% annualized return, Sharpe ~0.8, max drawdown < 20%

---

## Target Universe

### The "Mag 7" Stocks

| Ticker | Company | Rationale |
|--------|---------|-----------|
| **AAPL** | Apple | Highest option liquidity, frequent events |
| **MSFT** | Microsoft | Tech sector leader, tight spreads |
| **NVDA** | NVIDIA | High volatility, active Polymarket coverage |
| **AMZN** | Amazon | Earnings-driven, good volume |
| **TSLA** | Tesla | Elon-driven sentiment spikes |
| **META** | Meta | Social/tech crossover events |
| **GOOGL** | Google | Regulatory events, AI developments |

**Selection Criteria**:
- Daily option volume > 100K contracts
- Average bid-ask spread < 3%
- Open interest > 10K per strike
- Polymarket markets exist for earnings/events

---

## Trade Types

### Iron Condor (Neutral — poly_prob 40-60%)

When Polymarket signals uncertainty (no strong directional lean), sell both sides.

```
Sell Put Credit Spread (below)  +  Sell Call Credit Spread (above)

Example: NVDA @ $500
  Sell 480 Put / Buy 470 Put  (put credit spread)
  Sell 520 Call / Buy 530 Call (call credit spread)
  Net credit: ~$3.50
  Max loss: $6.50 per spread
  Max profit: $3.50 (if NVDA stays between 480-520 at expiry)
```

### Put Credit Spread (Bullish — poly_prob > 60%)

When Polymarket signals bullish outcome, sell downside premium.

```
Sell OTM Put + Buy further OTM Put (protection)

Example: AAPL @ $200, Polymarket "AAPL beats earnings" = 75%
  Sell 190 Put (~0.20 delta) / Buy 185 Put (~0.08 delta)
  Net credit: ~$1.50
  Max loss: $3.50
  Thesis: Market pricing too much downside risk given bullish sentiment
```

### Call Credit Spread (Bearish — poly_prob < 40%)

When Polymarket signals bearish outcome, sell upside premium.

```
Sell OTM Call + Buy further OTM Call (protection)

Example: TSLA @ $300, Polymarket "TSLA hits $400" = 25%
  Sell 320 Call (~0.20 delta) / Buy 325 Call (~0.08 delta)
  Net credit: ~$1.80
  Max loss: $3.20
  Thesis: Market pricing too much upside given bearish sentiment
```

### Trade Type Selection

| Polymarket Signal | poly_prob | Trade Type |
|-------------------|-----------|------------|
| Strong bullish | > 70% | Put Credit Spread |
| Mild bullish | 60-70% | Put Credit Spread (tighter wings) |
| Neutral / uncertain | 40-60% | Iron Condor |
| Mild bearish | 30-40% | Call Credit Spread (tighter wings) |
| Strong bearish | < 30% | Call Credit Spread |

---

## The Greeks

### Delta ($\Delta$): Direction & Position Risk

**Definition**: $\frac{\partial V}{\partial S}$ - Rate of change of option price w.r.t. underlying

**Usage in Premium Selling**:
- **Short Strike Selection**: Target ~0.20 delta for short legs (80% probability of expiring OTM)
- **Long Strike Selection**: Target ~0.08 delta for long legs (protection wings)
- **Position Delta**: Near-zero for iron condors, slightly directional for credit spreads
- **Monitoring**: Track net delta to ensure positions aren't becoming too directional

**Example**:
```
Iron Condor on NVDA @ $500:
  Short 480 Put: delta = -0.20
  Long 470 Put:  delta = -0.08
  Short 520 Call: delta = +0.20 (short call has negative delta for seller)
  Long 530 Call:  delta = +0.08
  Net delta: ~0.00 (market neutral)
```

### Gamma ($\Gamma$): Convexity Risk

**Definition**: $\frac{\partial^2 V}{\partial S^2}$ - Rate of change of delta

**Usage in Premium Selling**:
- **We are short gamma**: Large underlying moves hurt us
- **Risk Monitor**: High gamma = position delta changes rapidly on moves
- **DTE Effect**: Gamma increases as expiration approaches — close positions before last 7 days to avoid gamma risk acceleration

### Vega ($\nu$): IV Sensitivity — We're Short Vega

**Definition**: $\frac{\partial V}{\partial \sigma}$ - Sensitivity to implied volatility

**Strategy**:
- **We are short vega**: We profit when IV decreases (IV crush)
- **Entry Sweet Spot**: IV Percentile > 50 (sell when IV is elevated)
- **Best Scenario**: Sell premium before known event, collect credit as IV crushes post-event
- **Avoid**: IV Percentile < 30 (not enough premium to sell)

**Example**:
```
AAPL pre-earnings: IV = 45% (80th percentile)
Polymarket: "AAPL beats earnings" = 75% (high confidence)
-> Market pricing high uncertainty, but sentiment shows confidence
-> SELL premium (expect IV crush post-earnings)
-> IV drops to 25% post-earnings -> spreads lose value -> we keep credit
```

### Theta ($\Theta$): Time Decay — Our Friend

**Definition**: $\frac{\partial V}{\partial t}$ - Daily time decay

**Usage in Premium Selling**:
- **Theta is positive for us**: As time passes, sold options lose value — we profit
- **Theta is our primary profit driver**: We want time to pass uneventfully
- **DTE Sweet Spot**: 30-45 DTE at entry — theta acceleration kicks in during our hold period
- **Daily Income**: Each day, our short options decay, bringing us closer to max profit

**Example**:
```
Put credit spread sold for $2.00 credit
Combined theta: +$0.05/day
After 20 days of no movement: ~$1.00 of time decay collected
-> Close at 50% profit ($1.00 remaining value)
```

### Rho ($\rho$): Interest Rate Risk

**Ignored**: Short-dated options (<45 DTE) have minimal interest rate sensitivity.

---

## Entry Criteria

### Primary Filters (ALL must pass)

#### 1. IV Percentile Check
```
Condition: iv_percentile > 50
```
- Ensures sufficient premium to sell
- Higher IV = wider credit received = better risk/reward

#### 2. Polymarket Certainty
```
Condition: poly_certainty > 70%
Where: poly_certainty = max(poly_prob, 1 - poly_prob)
```
- Polymarket must show conviction in some direction
- Certainty > 70% means the crowd is confident — we sell the opposite side's premium

#### 3. Sentiment-IV Divergence
```
Condition: divergence > 10%
Where: divergence = poly_certainty - (1 - iv_percentile/100)
```
- The market (IV) prices uncertainty, but Polymarket shows confidence
- Divergence = the gap we exploit

#### 4. Liquidity Gate
```
Condition: (ask - bid) / mid < 0.05
```
- Tight spreads (<5%) on all legs
- Validates during entry AND continuously while holding

#### 5. DTE Range
```
Condition: 7 <= days_to_expiry <= 45
```
- Minimum 7 DTE to avoid gamma risk
- Maximum 45 DTE for capital efficiency

#### 6. Short Strike Delta
```
Condition: short_strike_delta ~ 0.20
         long_strike_delta ~ 0.08
```
- Short strikes at ~0.20 delta (1 standard deviation OTM)
- Long strikes at ~0.08 delta (protection, defines max loss)

### Risk-Adjusted Filters

#### 7. Credit-to-Width Ratio
```
Condition: credit_received / spread_width > 0.30
```
- Must receive at least 30% of the spread width as credit
- Ensures favorable risk/reward (e.g., $1.50 credit on $5 wide spread)

#### 8. Sector Exposure
```
Condition: sum(open_mag7_positions) < 3 per underlying
       AND total_exposure < 15% of account
```
- Max 3 open positions per ticker
- Prevents concentration risk (all Mag 7 are correlated)

#### 9. Position Sizing
```
Position_size = min(0.05 * account_value, available_capacity)
```
- Max 5% of account per trade
- Based on max loss (spread width - credit received), not notional

---

## Position Management

### Entry Execution

**Order Type**: Limit order (credit)
**Price**: Mid price, walk down to natural over 60 seconds
**Time in Force**: DAY
**Legs**: Multi-leg spread order (not individual legs)

**Entry Algorithm**:
```
1. Calculate spread parameters (strikes, width)
2. Place multi-leg limit order at mid credit
3. If not filled in 30 seconds, reduce credit by $0.05
4. If not filled in 60 seconds, reduce to natural
5. If not filled at natural, CANCEL (spread too competitive)
```

---

## Exit Logic

### Exit Triggers (First to Fire Wins)

#### 1. Take Profit: 50% of Max Credit
```
Trigger: spread_value <= 0.50 * initial_credit
Action: Place limit order to buy back spread at 50% of credit
Rationale: Capture half the premium, free up capital for next trade
```
This is the primary exit. Most winning trades close here in 10-25 days.

#### 2. Stop Loss: Spread Value Doubles (2x)
```
Trigger: spread_value >= 2.0 * initial_credit
Action: Market order to close
Rationale: Cut losses before they compound
```
Example: Sold spread for $1.50, close if spread value reaches $3.00.

#### 3. Theta Burn: 1 DTE Remaining
```
Trigger: days_to_expiry <= 1
Action: Market order to close all legs
Rationale: Gamma risk too high near expiration, avoid assignment risk
```

#### 4. Post-Event IV Crush
```
Trigger: event_resolved AND iv_drop > 20%
Action: Close at limit (IV has crushed, most profit captured)
Rationale: The trade thesis has played out — take profits
```

#### 5. Liquidity Deterioration
```
Trigger: any_leg_spread > 8%
Action:
  - If profitable: Close at limit
  - If losing: Reduce by 50% at market, hold rest
  - If all legs spread > 12%: Full exit at market
Rationale: Preserve capital, avoid trapped positions
```

### Market Event Overrides

**Halts/Circuit Breakers**:
```
Action:
  - Cancel all working orders immediately
  - DO NOT attempt to close existing positions
  - Wait for trading to resume
  - Re-evaluate all positions when market reopens
```

**IBKR Gateway Restart**:
```
Action:
  - Enter "safe mode"
  - Cancel new order submissions
  - Maintain existing positions (spreads have defined risk)
  - Resume normal operation after reconnection confirmed
```

---

## Risk Management

### Pre-Trade Checks (Enforced by Risk Manager)

```c++
class RiskManager {
  bool approve_order(const SpreadOrder& order) {
    // 1. Position size check (based on max loss)
    if (order.max_loss > 0.05 * account_value) {
      log_rejection("Single position max loss exceeds 5%");
      return false;
    }

    // 2. Per-underlying limit
    int positions_for_ticker = count_positions(order.underlying);
    if (positions_for_ticker >= 3) {
      log_rejection("Max 3 positions per underlying");
      return false;
    }

    // 3. Total sector exposure check
    double total_exposure = calculate_total_exposure();
    if (total_exposure + order.max_loss > 0.15 * account_value) {
      log_rejection("Total exposure would exceed 15%");
      return false;
    }

    // 4. Daily loss check
    if (daily_pnl_pct < -0.02) {
      log_rejection("Daily loss limit reached (-2%)");
      halt_trading();
      return false;
    }

    // 5. Weekly loss check
    if (weekly_pnl_pct < -0.04) {
      log_rejection("Weekly loss limit reached (-4%)");
      reduce_position_sizes();
      return false;
    }

    // 6. Spread check (all legs)
    for (const auto& leg : order.legs) {
      if (leg.spread_pct > 0.05) {
        log_rejection("Leg spread exceeds 5%");
        return false;
      }
    }

    return true;
  }
};
```

### Continuous Monitoring

**Position Monitoring (Every Tick)**:
- Update unrealized P&L for all spreads
- Check stop-loss triggers (spread value 2x)
- Monitor individual leg liquidity
- Track net portfolio delta

**Loss Circuit Breakers**:
```
Daily loss >= -2%:
  - HALT all new trades for the day
  - Keep existing positions (defined risk)
  - Send alert

Weekly loss >= -4%:
  - REDUCE position sizes by 50% for next week
  - Close any positions at breakeven or better
  - Send critical alert

Account drawdown >= -15%:
  - KILL SWITCH: Close ALL positions
  - Halt trading indefinitely
  - Require manual review and restart
```

**Kill Switch Triggers**:
```
Level 1 (5 seconds): Data feed lost
  Action: Stop new orders

Level 2 (30 seconds): Data feed still lost
  Action: Hold positions (spreads have defined risk)

Level 3 (60 seconds): Data feed still lost
  Action: Alert operator, positions remain (max loss is defined)
```

---

## Edge Analysis

**Why does the VRP edge exist?**

1. **Structural VRP**: Options are systematically overpriced — implied volatility consistently exceeds realized volatility by 2-4% on average. This is a well-documented risk premium that insurance sellers collect.
2. **Polymarket Timing**: Adds a timing overlay — sell premium specifically when Polymarket shows high certainty but IV is still elevated (pre-event). This filters out the worst entries (selling before genuinely uncertain events).
3. **Retail Inaccessibility**: Multi-leg spreads are harder for retail traders to execute and manage. Most retail buys single-leg options (long calls/puts), providing premium for sellers.
4. **Event-Driven IV Cycle**: Mag 7 stocks have frequent events (earnings, product launches, regulatory). Each event creates an IV ramp-up and post-event crush — a repeating cycle we exploit.
5. **Small Size Advantage**: At <$10K per trade, we're below institutional radar. Large funds can't deploy this strategy at scale on individual names.

**Expected Lifespan**: 12-18 months before Polymarket/ICE launch and mainstream adoption erodes the timing edge. The structural VRP itself is permanent — only our timing advantage decays.

**Alpha Thesis**:
- VRP structural edge: ~8-10% annualized (permanent, well-documented)
- Polymarket timing overlay: ~4-8% additional (decaying over 12-18 months)
- Combined target: 12-18% annualized

---

**See Also**:
- [MATH_SPECS.md](MATH_SPECS.md) - Greeks calculation implementation
- [API_INTEGRATION.md](API_INTEGRATION.md) - Polymarket data ingestion
- [CONFIGURATION.md](CONFIGURATION.md) - risk_params.yaml tuning
