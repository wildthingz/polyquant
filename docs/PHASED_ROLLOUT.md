# Phased Rollout Strategy

Progressive deployment strategy for PolyQuant across three phases: Local Simulation (Lab), Local Live (Incubator), and Cloud Production.

## Table of Contents

1. [Overview](#overview)
2. [Phase 1: The Lab](#phase-1-the-lab-local-simulation)
3. [Phase 2: The Incubator](#phase-2-the-incubator-local-live)
4. [Phase 3: Production](#phase-3-production-aws-cloud)
5. [Rollback Procedures](#rollback-procedures)
6. [Success Metrics](#success-metrics)

---

## Overview

**Philosophy**: Capital preservation > Growth. Only advance to next phase when current phase demonstrates statistical significance and stability.

### Phase Summary

| Phase | Duration | Capital | Environment | Goal |
|-------|----------|---------|-------------|------|
| **Phase 1: Lab** | 30 days OR 100 trades | $0 (paper) | Local Arch Linux | Validate strategy, fix bugs |
| **Phase 2: Incubator** | 60 days OR 200 trades | $500 → $2,000 | Local production | Prove real-money viability |
| **Phase 3: Production** | Ongoing | $2,000+ | AWS EC2 | Scale and optimize |

---

## Phase 1: The Lab (Local Simulation)

**Goal**: Prove the strategy works in simulation before risking real capital.

### Environment Setup

- **Location**: Local Arch Linux workstation
- **Broker**: IBKR Paper Trading Account
- **Capital**: Virtual $10,000
- **Trading Hours**: 9:30 AM - 4:00 PM ET (manual start/stop)
- **Monitoring**: Console logs + PostgreSQL queries

### Entry Criteria

✅ All subsystems implemented:
- [ ] C++ pricing engine with Black-Scholes + Greeks
- [ ] Polymarket WebSocket adapter
- [ ] IBKR TWS API adapter with EWrapper callbacks
- [ ] Risk manager with pre-trade checks
- [ ] Order executor with state machine
- [ ] PostgreSQL TimescaleDB schema
- [ ] XGBoost model trained on 20+ historical samples
- [ ] 80%+ unit test coverage

✅ Documentation complete:
- [ ] All markdown docs in docs/
- [ ] setup.sh tested on clean Arch install
- [ ] README.md accurate and clear

### Exit Criteria (ALL must pass)

#### 1. Statistical Significance

```sql
-- Minimum 100 fully resolved trades
SELECT COUNT(*) FROM trades WHERE status = 'CLOSED';
-- Required: >= 100

-- Sharpe Ratio > 1.0 (risk-adjusted returns)
WITH daily_returns AS (
    SELECT
        DATE(entry_time) AS trade_date,
        AVG(net_pnl_pct) AS avg_return,
        STDDEV(net_pnl_pct) AS stddev_return
    FROM trades
    WHERE status = 'CLOSED'
    GROUP BY DATE(entry_time)
)
SELECT
    AVG(avg_return) / NULLIF(STDDEV(avg_return), 0) * SQRT(252) AS sharpe_ratio
FROM daily_returns;
-- Required: > 1.0
```

#### 2. Model Calibration

```sql
-- Win rate within ±10% of average signal strength
SELECT
    AVG(signal_strength) AS avg_predicted,
    AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END) AS actual_win_rate,
    ABS(AVG(signal_strength) - AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END)) AS calibration_error
FROM signals
WHERE actual_outcome IS NOT NULL;
-- Required: calibration_error < 0.10
```

#### 3. Risk Discipline

```sql
-- Max drawdown < 8%
SELECT MIN(cumulative_pnl_pct) AS max_drawdown
FROM (
    SELECT
        entry_time,
        SUM(net_pnl_pct) OVER (ORDER BY entry_time) AS cumulative_pnl_pct
    FROM trades
    WHERE status = 'CLOSED'
) AS running_total;
-- Required: > -0.08
```

#### 4. System Stability

```sql
-- Zero unhandled exceptions
SELECT COUNT(*) FROM system_logs
WHERE level = 'CRITICAL' AND message LIKE '%exception%';
-- Required: 0

-- Average order latency < 50ms (p95)
SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)
FROM (
    SELECT
        EXTRACT(EPOCH FROM (filled_time - submitted_time)) * 1000 AS latency_ms
    FROM trades
    WHERE status = 'CLOSED'
) AS latencies;
-- Required: < 50ms
```

#### 5. Fill Rate

```sql
-- >80% of limit orders filled within 60 seconds
SELECT
    COUNT(*) FILTER (WHERE filled_time - submitted_time < INTERVAL '60 seconds') * 100.0 / COUNT(*) AS fill_rate_pct
FROM trades
WHERE status = 'CLOSED';
-- Required: > 80
```

### Phase 1 Deliverables

- [x] 100+ completed trades logged in database
- [x] Sharpe ratio report with statistical significance test
- [x] Model calibration chart (predicted vs actual)
- [x] Stress test results (all 6 scenarios passed)
- [x] Performance report (latency, throughput, uptime)
- [x] Incident log (all CRITICAL/ERROR events reviewed)

### Decision Point

**If ALL exit criteria pass**: Proceed to Phase 2
**If ANY criteria fail**:
1. Identify root cause (strategy, implementation, or data issue)
2. Fix and re-run Phase 1 from day 1
3. Do NOT proceed until statistical confidence achieved

---

## Phase 2: The Incubator (Local Live)

**Goal**: Prove the strategy works with real money at small scale.

### Environment Setup

- **Location**: Local Arch Linux workstation
- **Broker**: IBKR Live Trading Account
- **Initial Capital**: $500
- **Trading Hours**: 9:30 AM - 4:00 PM ET (systemd service)
- **Monitoring**: Grafana dashboard + Prometheus alerts

### Capital Growth Plan

| Milestone | Capital | Condition |
|-----------|---------|-----------|
| Start | $500 | Funded from personal savings |
| +30 days | +$500 ($1,000 total) | If Sharpe > 1.2, no >-5% drawdown |
| +60 days | +$1,000 ($2,000 total) | If cumulative return > 15%, calibration error < 12% |
| Exit | $2,000 | Ready for Phase 3 |

**Capital Withdrawal Rule**: If account drops below $400 (-20%), HALT trading and review.

### Entry Criteria

✅ Phase 1 exit criteria met
✅ Stress testing complete (6 scenarios passed)
✅ Monitoring infrastructure deployed:
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboard configured
- [ ] Alerting rules set (daily loss, feed disconnect, model drift)
- [ ] Backup automation (hourly DB dumps to S3)

✅ Operational procedures documented:
- [ ] Recovery checklist tested
- [ ] Kill switch tested manually
- [ ] Contact information for IBKR support

### Exit Criteria (ALL must pass)

#### 1. Positive Returns

```sql
-- Cumulative return > 15% over 60 days
SELECT
    SUM(net_pnl) / 500.0 AS cumulative_return_pct  -- $500 initial capital
FROM trades
WHERE status = 'CLOSED'
  AND entry_time >= '<phase_2_start_date>';
-- Required: > 0.15
```

#### 2. Sharpe Ratio Maintained

```sql
-- Sharpe ratio > 1.2 (higher bar than Phase 1)
WITH daily_returns AS (
    SELECT
        DATE(entry_time) AS trade_date,
        SUM(net_pnl) / 500.0 AS daily_return_pct
    FROM trades
    WHERE status = 'CLOSED'
      AND entry_time >= '<phase_2_start_date>'
    GROUP BY DATE(entry_time)
)
SELECT
    AVG(daily_return_pct) / NULLIF(STDDEV(daily_return_pct), 0) * SQRT(252) AS sharpe_ratio
FROM daily_returns;
-- Required: > 1.2
```

#### 3. Max Drawdown

```sql
-- Max drawdown < 10%
SELECT MIN(cumulative_pnl_pct) AS max_drawdown
FROM (
    SELECT
        entry_time,
        SUM(net_pnl) OVER (ORDER BY entry_time) / 500.0 AS cumulative_pnl_pct
    FROM trades
    WHERE status = 'CLOSED'
      AND entry_time >= '<phase_2_start_date>'
) AS running_total;
-- Required: > -0.10
```

#### 4. Model Still Calibrated

```sql
-- Calibration error < 12%
SELECT
    ABS(AVG(signal_strength) - AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END)) AS calibration_error
FROM signals
WHERE actual_outcome IS NOT NULL
  AND created_at >= '<phase_2_start_date>';
-- Required: < 0.12
```

#### 5. Operational Uptime

```sql
-- 99%+ uptime during market hours
-- (Calculate manually from system logs)
SELECT
    SUM(EXTRACT(EPOCH FROM (resolved_time - detected_time))) / (60 * 6.5 * 60) AS downtime_pct  -- 6.5 hours per day
FROM system_incidents
WHERE detected_time >= '<phase_2_start_date>';
-- Required: < 0.01 (1% downtime allowance)
```

#### 6. Minimum Trade Count

```sql
-- At least 200 fully resolved trades
SELECT COUNT(*) FROM trades
WHERE status = 'CLOSED'
  AND entry_time >= '<phase_2_start_date>';
-- Required: >= 200
```

### Phase 2 Operational Procedures

#### Daily Checklist

```bash
#!/bin/bash
# scripts/daily_checklist.sh

echo "=== PolyQuant Daily Checklist (Phase 2) ==="

# 1. Check system health
systemctl status polyquant

# 2. Review overnight performance
psql -U polyquant_user -d polyquant -c "
    SELECT
        COUNT(*) AS trades_yesterday,
        SUM(net_pnl) AS total_pnl,
        AVG(net_pnl_pct) AS avg_return
    FROM trades
    WHERE DATE(entry_time) = CURRENT_DATE - 1;
"

# 3. Check for alerts
journalctl -u polyquant --since "24 hours ago" --priority warning

# 4. Verify model is current
MODEL_AGE=$(stat -c %Y models/xgboost_v1.0.0.onnx)
NOW=$(date +%s)
AGE_DAYS=$(( ($NOW - $MODEL_AGE) / 86400 ))
if [ $AGE_DAYS -gt 7 ]; then
    echo "⚠️  Model is $AGE_DAYS days old, consider retraining"
fi

# 5. Check backup succeeded
ls -lh /var/backups/polyquant/ | tail -1

echo ""
echo "✅ Daily checklist complete"
```

#### Weekly Review

- **Sundays, 11 AM**: Review week's performance
  - Cumulative P&L vs target
  - Sharpe ratio trending
  - Model calibration check
  - Review all ERROR/CRITICAL logs
  - Test recovery procedures (kill Gateway, restart DB)

#### Monthly Model Retraining

```bash
# scripts/monthly_retrain.sh
source ~/polyquant-venv/bin/activate

# 1. Export training data (last 60 days)
psql -U polyquant_user -d polyquant -c "COPY (
    SELECT
        signal_strength,
        features,
        actual_outcome
    FROM signals
    WHERE actual_outcome IS NOT NULL
      AND created_at >= NOW() - INTERVAL '60 days'
) TO '/tmp/training_data.csv' WITH CSV HEADER;"

# 2. Train new model
python src/python/train_model.py \
    --input /tmp/training_data.csv \
    --output models/xgboost_v$(date +%Y%m%d).onnx

# 3. Validate calibration on holdout set
python src/python/validate_model.py \
    --model models/xgboost_v$(date +%Y%m%d).onnx \
    --test-data /tmp/training_data.csv

# 4. Hot-reload (engine watches file system)
cp models/xgboost_v$(date +%Y%m%d).onnx models/xgboost_v1.0.0.onnx

echo "✅ Model retrained and deployed"
```

### Phase 2 Deliverables

- [x] 200+ completed real-money trades
- [x] Audited P&L report (cross-checked with IBKR statements)
- [x] Sharpe ratio > 1.2 with 95% confidence interval
- [x] Model drift analysis (showing no significant degradation)
- [x] Incident report (all downtime reviewed)
- [x] Operational runbook updated with lessons learned

### Decision Point

**If ALL exit criteria pass**: Proceed to Phase 3
**If ANY criteria fail**:
1. If drawdown > -20%: HALT, withdraw capital, full post-mortem
2. If Sharpe < 1.0: Extend Phase 2 by 30 days, lower capital to $500
3. If calibration error > 15%: Retrain model, restart Phase 2 timer

---

## Phase 3: Production (AWS Cloud)

**Goal**: Scale to 24/7 operation with institutional-grade reliability.

### Environment Setup

- **Location**: AWS EC2 (us-east-1, t3.medium)
- **Database**: AWS RDS PostgreSQL (db.t3.small, Multi-AZ)
- **Broker**: IBKR Live Trading Account
- **Capital**: $2,000+ (gradual scaling)
- **Trading Hours**: 24/7 (pre-market + after-hours for analysis)
- **Monitoring**: CloudWatch + Grafana + PagerDuty

### Infrastructure

```
┌─────────────────────────────────────────────────────────┐
│                   AWS Cloud (VPC)                       │
│                                                         │
│  ┌──────────────┐       ┌──────────────┐              │
│  │   EC2        │──────▶│   RDS        │              │
│  │ t3.medium    │       │ PostgreSQL   │              │
│  │              │       │ Multi-AZ     │              │
│  └──────┬───────┘       └──────────────┘              │
│         │                                               │
│         │                ┌──────────────┐              │
│         └───────────────▶│ CloudWatch   │              │
│                          │ Logs/Metrics │              │
│                          └──────────────┘              │
└─────────────────────────────────────────────────────────┘
                 │
                 │ (Internet)
                 │
        ┌────────▼────────┐
        │  Polymarket API │
        │  IBKR Gateway   │
        └─────────────────┘
```

### Entry Criteria

✅ Phase 2 exit criteria met
✅ AWS infrastructure provisioned:
- [ ] EC2 instance running with Docker
- [ ] RDS PostgreSQL with automated backups
- [ ] S3 bucket for model storage
- [ ] CloudWatch alarms configured
- [ ] PagerDuty integration tested

✅ Security hardened:
- [ ] Secrets in AWS Secrets Manager (not env files)
- [ ] VPC security groups configured (database not publicly accessible)
- [ ] SSH key-based authentication only
- [ ] SSL/TLS for all external connections

### Operational Targets

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| **Uptime** | 99.9% | <99.5% in 7-day window |
| **Sharpe Ratio** | >1.5 | <1.2 for 30 days |
| **Max Drawdown** | <12% | >-10% from peak |
| **Order Latency (p95)** | <50ms | >100ms for 1 hour |
| **Model Calibration** | <10% error | >15% error for 20 trades |
| **Daily Loss Circuit** | -2% | Triggered |

### Capital Scaling Plan

| Milestone | Capital | Condition |
|-----------|---------|-----------|
| Start | $2,000 | Phase 2 graduation |
| +90 days | $5,000 | If Sharpe > 1.5, returns > 20%, drawdown < 10% |
| +180 days | $10,000 | If all targets maintained, no major incidents |
| Ongoing | Gradual | Reinvest 50% of profits, withdraw 50% |

### Continuous Improvement

**Weekly**:
- Model retraining with last 90 days of data
- Performance review vs benchmarks (SPY, QQQ)
- Cost optimization (EC2 instance sizing)

**Monthly**:
- Full stress testing suite
- Security audit (dependency updates, penetration test)
- Disaster recovery drill (restore from backup)

**Quarterly**:
- Strategy review (is Polymarket edge persisting?)
- Expand to new tickers if Mag 7 saturated
- Consider portfolio construction (multiple uncorrelated strategies)

### Phase 3 Success Metrics

**After 1 Year**:
- Cumulative return > 30% (after fees)
- Sharpe ratio > 1.5
- Max drawdown < 15%
- Zero unrecoverable incidents
- Model calibration error < 10%
- 99.9%+ uptime

**Long-Term Vision** (2-3 years):
- Expand beyond Mag 7 (Russell 2000, sector ETFs)
- Add short strategies (sell options when IV overpriced)
- Build portfolio of uncorrelated sub-strategies
- Open-source anonymized framework (after alpha decays)

---

## Rollback Procedures

### Phase 2 → Phase 1 Rollback

**Trigger**: Drawdown > -20% OR Sharpe < 0.5 for 30 days

```bash
#!/bin/bash
# scripts/rollback_to_phase1.sh

echo "=== Rolling Back to Phase 1 (Simulation) ==="

# 1. HALT live trading
sudo systemctl stop polyquant

# 2. Switch to paper trading
sed -i 's/IBKR_TRADING_MODE=live/IBKR_TRADING_MODE=paper/' config/secrets.env

# 3. Withdraw remaining capital from IBKR
echo "⚠️  MANUAL STEP: Log into IBKR and initiate withdrawal"

# 4. Full post-mortem
echo "Generating incident report..."
psql -U polyquant_user -d polyquant -f scripts/post_mortem_report.sql > reports/phase2_rollback_$(date +%Y%m%d).txt

# 5. Restart in simulation mode
sudo systemctl start polyquant

echo "✅ Rolled back to Phase 1. Review report and iterate."
```

### Phase 3 → Phase 2 Rollback

**Trigger**: AWS costs exceed $500/month OR security incident

```bash
#!/bin/bash
# scripts/rollback_to_phase2.sh

echo "=== Rolling Back to Phase 2 (Local) ==="

# 1. Backup RDS database
aws rds create-db-snapshot \
    --db-instance-identifier polyquant-db \
    --db-snapshot-identifier polyquant-rollback-$(date +%Y%m%d)

# 2. Export to local PostgreSQL
pg_dump -h <rds-endpoint> -U admin polyquant | psql -U polyquant_user -d polyquant

# 3. Stop AWS resources (DO NOT TERMINATE - keep for analysis)
aws ec2 stop-instances --instance-ids <instance-id>

# 4. Restart local deployment
cd ~/Documents/code/polyquant
sudo systemctl start polyquant

echo "✅ Rolled back to Phase 2. AWS resources stopped (not terminated)."
```

---

## Success Metrics

### Statistical Significance Tests

**Hypothesis Test**: Does the strategy generate alpha vs random trading?

```python
# scripts/statistical_significance.py
import pandas as pd
import numpy as np
from scipy import stats

# Load trade results
trades = pd.read_sql("SELECT net_pnl_pct FROM trades WHERE status = 'CLOSED'", conn)

# Test: Mean return > 0
t_stat, p_value = stats.ttest_1samp(trades['net_pnl_pct'], 0)

print(f"T-statistic: {t_stat:.4f}")
print(f"P-value: {p_value:.6f}")

if p_value < 0.05:
    print("✅ Statistically significant alpha (p < 0.05)")
else:
    print("❌ No significant alpha detected")

# Confidence interval
ci = stats.t.interval(0.95, len(trades) - 1,
                      loc=trades['net_pnl_pct'].mean(),
                      scale=stats.sem(trades['net_pnl_pct']))
print(f"95% CI for mean return: [{ci[0]:.4f}, {ci[1]:.4f}]")
```

### Benchmark Comparison

```sql
-- Compare against buy-and-hold SPY
WITH strategy_returns AS (
    SELECT
        DATE(entry_time) AS date,
        SUM(net_pnl) / 10000.0 AS daily_return  -- $10K base capital
    FROM trades
    WHERE status = 'CLOSED'
    GROUP BY DATE(entry_time)
),
spy_returns AS (
    SELECT
        date,
        (close - LAG(close) OVER (ORDER BY date)) / LAG(close) OVER (ORDER BY date) AS daily_return
    FROM market_prices
    WHERE ticker = 'SPY'
)
SELECT
    (EXP(SUM(LN(1 + s.daily_return))) - 1) * 100 AS strategy_cumulative_pct,
    (EXP(SUM(LN(1 + b.daily_return))) - 1) * 100 AS spy_cumulative_pct,
    (EXP(SUM(LN(1 + s.daily_return))) - 1) - (EXP(SUM(LN(1 + b.daily_return))) - 1) AS alpha
FROM strategy_returns s
JOIN spy_returns b USING (date);
```

---

**See Also**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design for each phase
- [DEPLOYMENT.md](DEPLOYMENT.md) - Phase-specific deployment guides
- [STRESS_TESTING.md](STRESS_TESTING.md) - Pre-phase gate testing
- [CONFIGURATION.md](CONFIGURATION.md) - Risk parameters by phase

