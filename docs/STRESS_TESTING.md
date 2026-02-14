# Stress Testing & Failure Scenarios

Comprehensive stress testing scenarios, failure modes, and recovery procedures for PolyQuant.

## Table of Contents

1. [Overview](#overview)
2. [Test Scenarios](#test-scenarios)
3. [Failure Recovery Procedures](#failure-recovery-procedures)
4. [Performance Stress Tests](#performance-stress-tests)
5. [Security Penetration Tests](#security-penetration-tests)
6. [Disaster Recovery](#disaster-recovery)

---

## Overview

**Purpose**: Validate system behavior under adverse conditions before risking capital.

**Testing Schedule**:
- **Phase 1** (Simulation): Weekly full suite
- **Phase 2** (Live Pilot): Monthly + after any code changes
- **Phase 3** (Production): Quarterly + continuous chaos engineering

**Pass Criteria**: System must gracefully handle all scenarios without data loss or uncontrolled trading.

---

## Test Scenarios

### Scenario 1: Polymarket WebSocket Disconnect

**Trigger**: Simulate network failure to Polymarket

```bash
# Block Polymarket domain
sudo iptables -A OUTPUT -d ws-subscriptions-clob.polymarket.com -j DROP

# Wait 60 seconds
sleep 60

# Restore connectivity
sudo iptables -D OUTPUT -d ws-subscriptions-clob.polymarket.com -j DROP
```

**Expected Behavior**:
1. **0-5s**: Engine logs warning "Polymarket connection lost"
2. **5-30s**: Continue trading with last known probabilities (marked stale)
3. **30-60s**: Halt new entries, maintain existing positions
4. **60s+**: Begin exponential backoff reconnection (1s, 2s, 4s, 8s, max 30s)
5. **On reconnect**: Resume normal operation, log "Polymarket reconnected"

**Validation**:
```sql
-- Check system maintained positions
SELECT * FROM trades WHERE status = 'OPEN' AND entry_time < NOW() - INTERVAL '2 minutes';

-- Verify no new entries during outage
SELECT COUNT(*) FROM trades
WHERE entry_time BETWEEN '<outage_start>' AND '<outage_end>';
-- Should be 0
```

---

### Scenario 2: IBKR Gateway Crash

**Trigger**: Kill IB Gateway process

```bash
# Kill Gateway
killall java

# Wait 30 seconds
sleep 30

# Restart Gateway
~/Jts/ibgateway/latest/ibgateway &
```

**Expected Behavior**:
1. **0-5s**: Engine receives error code 502 (disconnected)
2. **5-10s**: Attempt reconnection (1st try)
3. **10-20s**: Attempt reconnection (2nd try with backoff)
4. **20-40s**: Attempt reconnection (3rd try with backoff)
5. **On reconnect**:
   - Reconcile positions (query IBKR for current holdings)
   - Resume trading if positions match internal state
   - Alert operator if mismatch detected

**Validation**:
```c++
// Check position reconciliation
TEST(StressTest, IBKRReconnectReconciliation) {
    // Kill and restart Gateway
    system("killall java && sleep 5 && ~/Jts/ibgateway/latest/ibgateway &");

    // Wait for reconnection
    std::this_thread::sleep_for(std::chrono::seconds(60));

    // Query IBKR positions
    auto ibkr_positions = adapter->get_positions();

    // Query internal positions
    auto internal_positions = portfolio->get_open_positions();

    // Compare
    EXPECT_EQ(ibkr_positions.size(), internal_positions.size());

    for (const auto& pos : ibkr_positions) {
        EXPECT_TRUE(internal_positions.contains(pos.contract_id));
    }
}
```

---

### Scenario 3: Database Offline

**Trigger**: Stop PostgreSQL service

```bash
# Stop database
sudo systemctl stop postgresql

# Wait 60 seconds (simulate maintenance)
sleep 60

# Restart database
sudo systemctl start postgresql
```

**Expected Behavior**:
1. **0-5s**: DB writes fail, queued in memory (ring buffer, max 10K records)
2. **5-60s**: Trading continues (DB writes are async, non-blocking)
3. **60s+**: If DB still offline, alert operator (CRITICAL)
4. **On reconnect**:
   - Flush queued writes to database
   - Log "Database reconnected, X records flushed"

**Validation**:
```c++
TEST(StressTest, DatabaseOfflineRecovery) {
    // Stop PostgreSQL
    system("sudo systemctl stop postgresql");

    // Generate 100 trades
    for (int i = 0; i < 100; ++i) {
        strategy.evaluate_signal(mock_market_data());
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    // Check queue depth
    int queued = db_writer->get_queue_depth();
    EXPECT_GT(queued, 0);
    EXPECT_LE(queued, 10000);  // Should not exceed buffer

    // Restart PostgreSQL
    system("sudo systemctl start postgresql");
    std::this_thread::sleep_for(std::chrono::seconds(5));

    // Wait for flush
    std::this_thread::sleep_for(std::chrono::seconds(10));

    // Verify all records written
    EXPECT_EQ(db_writer->get_queue_depth(), 0);

    // Check database has all records
    auto result = db->query("SELECT COUNT(*) FROM trades WHERE entry_time > NOW() - INTERVAL '5 minutes'");
    EXPECT_GE(result[0]["count"].as<int>(), 100);
}
```

---

### Scenario 4: Extreme Volatility (VIX Spike)

**Trigger**: Inject market data with VIX > 50, rapid price swings

```c++
// tests/stress_scenarios/extreme_volatility.c++
TEST(StressTest, ExtremeVolatility) {
    // Inject volatile market conditions
    MarketDataUpdate volatile_market{
        .ticker = "NVDA",
        .underlying_price = 500.0,
        .opt_bid = 10.0,
        .opt_ask = 15.0,  // 50% spread (widening)
        .opt_iv = 0.80,   // IV spike to 80%
        .opt_iv_percentile = 0.95,
        .vix_level = 55.0  // Extreme fear
    };

    // Should reject due to:
    // 1. Spread > 5% (actually 50%)
    // 2. IV percentile > 90
    auto signal = strategy.evaluate_entry(volatile_market);
    EXPECT_EQ(signal.decision, "HOLD");
    EXPECT_FALSE(signal.risk_checks_passed);
    EXPECT_THAT(signal.decision_reason, HasSubstr("spread exceeds limit"));
}
```

**Expected Behavior**:
- Reject new entries (spread > 5%, IV percentile > 90)
- Monitor existing positions closely
- Tighten stop-losses if spread < 8% (still tradeable)
- Exit at market if spread > 12% (liquidity crisis)

---

### Scenario 5: Daily Loss Circuit Breaker

**Trigger**: Simulate multiple losing trades in one day

```c++
TEST(StressTest, DailyLossCircuitBreaker) {
    // Set account value
    account_state.set_value(10000.0);

    // Simulate 10 losing trades (-30% each)
    for (int i = 0; i < 10; ++i) {
        Trade trade{
            .entry_price = 15.0,
            .exit_price = 10.5,  // -30%
            .quantity = 5,
            .net_pnl = -2200.0  // -$2200 per trade
        };

        portfolio.close_trade(trade);

        // Check if circuit breaker triggered
        if (account_state.daily_pnl_pct() <= -0.02) {
            EXPECT_TRUE(risk_manager.is_trading_halted());
            EXPECT_EQ(risk_manager.halt_reason(), "Daily loss limit reached");
            break;
        }
    }

    // Verify no new orders accepted
    Order test_order{.action = "BUY", .quantity = 5};
    EXPECT_FALSE(risk_manager.approve_order(test_order));
}
```

**Expected Behavior**:
1. **Daily P&L < -2%**: HALT all new trading
2. Alert operator (CRITICAL severity)
3. Maintain existing positions (do not force close)
4. Require manual reset next day (operator confirms review)

**Manual Reset**:
```bash
# Next trading day, after review
psql -U polyquant_user -d polyquant -c \
  "UPDATE account_state SET trading_halted = FALSE, halt_reason = NULL, daily_pnl = 0, daily_pnl_pct = 0;"
```

---

### Scenario 6: Model File Corruption

**Trigger**: Corrupt ONNX model file

```bash
# Corrupt model
dd if=/dev/urandom of=models/xgboost_v1.0.0.onnx bs=1024 count=10 seek=100 conv=notrunc

# Restart engine
sudo systemctl restart polyquant
```

**Expected Behavior**:
1. Engine startup fails with error: "Failed to load model: Invalid ONNX format"
2. **Does NOT start trading** (fail-safe mode)
3. Alerts operator (CRITICAL)
4. Waits for model to be restored

**Recovery**:
```bash
# Restore from backup
cp models/backups/xgboost_v1.0.0.onnx models/

# Verify integrity
python -c "import onnx; onnx.checker.check_model('models/xgboost_v1.0.0.onnx')"

# Restart engine
sudo systemctl restart polyquant
```

---

## Failure Recovery Procedures

### Recovery Matrix

| Failure | Detection Time | Auto-Recovery | Manual Steps | Data Loss Risk |
|---------|---------------|---------------|--------------|----------------|
| Polymarket disconnect | <5s | Yes (backoff reconnect) | None | None |
| IBKR disconnect | <5s | Yes (backoff reconnect) | Reconcile positions | None |
| Database offline | <5s | Yes (queue in memory) | Restart PostgreSQL | Low (10K buffer) |
| Model file missing | Startup | No | Restore from backup | None (trading halted) |
| Extreme volatility | <1s | Yes (reject orders) | Review risk params | None |
| Daily loss limit | <1s | Yes (halt trading) | Manual reset next day | None |
| OOM crash | N/A | No | Restart, investigate | Medium (in-flight data) |

### Standard Recovery Checklist

```bash
#!/bin/bash
# scripts/recovery_checklist.sh

echo "=== PolyQuant Recovery Checklist ==="

# 1. Check system services
echo "[1/7] Checking services..."
systemctl status polyquant
systemctl status postgresql
pgrep -f "ibgateway"

# 2. Verify connectivity
echo "[2/7] Checking connectivity..."
curl -s https://gamma-api.polymarket.com/markets?limit=1 > /dev/null && echo "✅ Polymarket API reachable" || echo "❌ Polymarket API unreachable"
nc -zv localhost 4002 2>&1 | grep succeeded && echo "✅ IB Gateway reachable" || echo "❌ IB Gateway unreachable"

# 3. Database integrity
echo "[3/7] Checking database..."
psql -U polyquant_user -d polyquant -c "SELECT COUNT(*) FROM trades WHERE status = 'OPEN';"

# 4. Position reconciliation
echo "[4/7] Reconciling positions..."
# Query IBKR positions via API
# Compare with database
# (Implementation depends on your API wrapper)

# 5. Check model file
echo "[5/7] Verifying model..."
python -c "import onnx; onnx.checker.check_model('models/xgboost_v1.0.0.onnx')" && echo "✅ Model valid" || echo "❌ Model corrupted"

# 6. Review logs for errors
echo "[6/7] Checking recent errors..."
journalctl -u polyquant --since "10 minutes ago" --priority err

# 7. Test order placement (paper trade)
echo "[7/7] Testing order placement..."
# Submit a small test order to IBKR paper account
# (Implementation depends on your API wrapper)

echo ""
echo "Recovery checklist complete. Review output above."
```

---

## Performance Stress Tests

### Test 1: High Message Volume

**Goal**: Validate system handles 1000 market data updates/second

```c++
TEST(PerformanceStressTest, HighMessageVolume) {
    const int MESSAGES_PER_SECOND = 1000;
    const int DURATION_SECONDS = 60;

    auto start = std::chrono::steady_clock::now();

    for (int i = 0; i < MESSAGES_PER_SECOND * DURATION_SECONDS; ++i) {
        MarketDataUpdate update = generate_random_market_data();
        event_bus.publish(update);

        // Maintain 1000 msg/sec rate
        if (i % MESSAGES_PER_SECOND == 0) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }

    auto end = std::chrono::steady_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::seconds>(end - start).count();

    // Validate processing kept up
    EXPECT_LE(duration, DURATION_SECONDS + 5);  // Allow 5s buffer

    // Check queue depth (should be near zero)
    EXPECT_LE(event_bus.queue_depth(), 100);
}
```

### Test 2: Memory Leak Detection

```bash
# Run engine with valgrind
valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes \
    ./build/polyquant_engine --config=config/dev/risk_params.yaml &

# Let it run for 1 hour
sleep 3600

# Stop and review report
killall polyquant_engine

# Expected: "All heap blocks were freed -- no leaks are possible"
```

### Test 3: Latency Under Load

**Goal**: Ensure p95 latency < 50ms even under load

```c++
TEST(PerformanceStressTest, LatencyUnderLoad) {
    std::vector<double> latencies;

    for (int i = 0; i < 10000; ++i) {
        auto start = std::chrono::high_resolution_clock::now();

        // Full tick-to-trade cycle
        MarketDataUpdate update = generate_market_data();
        event_bus.publish(update);
        // ... wait for signal generation and order placement

        auto end = std::chrono::high_resolution_clock::now();
        double latency_ms = std::chrono::duration<double, std::milli>(end - start).count();
        latencies.push_back(latency_ms);
    }

    // Calculate percentiles
    std::sort(latencies.begin(), latencies.end());
    double p50 = latencies[latencies.size() * 0.50];
    double p95 = latencies[latencies.size() * 0.95];
    double p99 = latencies[latencies.size() * 0.99];

    EXPECT_LT(p50, 25.0);  // Median < 25ms
    EXPECT_LT(p95, 50.0);  // 95th percentile < 50ms
    EXPECT_LT(p99, 100.0); // 99th percentile < 100ms
}
```

---

## Security Penetration Tests

### Test 1: SQL Injection Resistance

```c++
TEST(SecurityTest, SQLInjectionResistance) {
    // Attempt SQL injection in ticker symbol
    std::string malicious_ticker = "NVDA'; DROP TABLE trades; --";

    MarketDataUpdate update{.ticker = malicious_ticker};

    // Should sanitize and reject
    EXPECT_THROW(db_writer.write(update), std::invalid_argument);

    // Verify table still exists
    auto result = db->query("SELECT COUNT(*) FROM trades");
    EXPECT_NO_THROW(result);
}
```

### Test 2: Secrets Exposure

```bash
# Check that secrets are not logged
grep -r "IBKR_PASSWORD\|DB_PASSWORD" /var/log/polyquant/
# Should return no results

# Check that secrets are not in binary
strings build/polyquant_engine | grep -i "password"
# Should return no hardcoded passwords
```

### Test 3: Unauthorized Order Placement

```c++
TEST(SecurityTest, UnauthorizedOrderPrevention) {
    // Attempt to place order without risk approval
    Order order{.action = "BUY", .quantity = 1000000};  // Huge size

    // Should be rejected by risk manager
    EXPECT_FALSE(risk_manager.approve_order(order));
    EXPECT_THAT(risk_manager.last_rejection_reason(), HasSubstr("exceeds position limit"));
}
```

---

## Disaster Recovery

### Backup Strategy

```bash
#!/bin/bash
# scripts/backup_all.sh

BACKUP_DIR="/var/backups/polyquant/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

echo "=== Full PolyQuant Backup ==="

# 1. Database dump
echo "[1/4] Backing up database..."
pg_dump -U polyquant_user polyquant | gzip > $BACKUP_DIR/database.sql.gz

# 2. Configuration files
echo "[2/4] Backing up configuration..."
tar -czf $BACKUP_DIR/config.tar.gz config/

# 3. ML models
echo "[3/4] Backing up models..."
tar -czf $BACKUP_DIR/models.tar.gz models/

# 4. System state
echo "[4/4] Backing up system state..."
cp /var/log/polyquant/engine.log $BACKUP_DIR/
journalctl -u polyquant --since "7 days ago" > $BACKUP_DIR/systemd.log

# Upload to S3 (Phase 3 only)
if [ "$PHASE" = "3" ]; then
    aws s3 sync $BACKUP_DIR s3://polyquant-backups-2025/
fi

echo "✅ Backup complete: $BACKUP_DIR"
```

### Full System Restore

```bash
#!/bin/bash
# scripts/restore_from_backup.sh <backup_path>

BACKUP_DIR=$1

echo "=== Restoring PolyQuant from Backup ==="

# 1. Stop services
systemctl stop polyquant
systemctl stop postgresql

# 2. Restore database
echo "[1/4] Restoring database..."
dropdb -U postgres polyquant
createdb -U postgres polyquant
gunzip -c $BACKUP_DIR/database.sql.gz | psql -U postgres polyquant

# 3. Restore configuration
echo "[2/4] Restoring configuration..."
tar -xzf $BACKUP_DIR/config.tar.gz -C /home/hatef/Documents/code/polyquant/

# 4. Restore models
echo "[3/4] Restoring models..."
tar -xzf $BACKUP_DIR/models.tar.gz -C /home/hatef/Documents/code/polyquant/

# 5. Restart services
echo "[4/4] Restarting services..."
systemctl start postgresql
systemctl start polyquant

# 6. Verify
sleep 10
systemctl status polyquant

echo "✅ Restore complete"
```

### RTO & RPO Targets

| Phase | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) | Backup Frequency |
|-------|-------------------------------|--------------------------------|------------------|
| Phase 1 | 1 hour | 24 hours | Daily |
| Phase 2 | 15 minutes | 1 hour | Hourly |
| Phase 3 | 5 minutes | 5 minutes | Continuous (WAL streaming) |

---

**See Also**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - Failure modes by component
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment checklist
- [CONFIGURATION.md](CONFIGURATION.md) - Kill switch configuration

