# Configuration Reference

Complete reference for all configuration files, parameters, and environment variables used in PolyQuant.

## Table of Contents

1. [Configuration Files](#configuration-files)
2. [Risk Parameters](#risk-parameters)
3. [Environment Variables](#environment-variables)
4. [Database Configuration](#database-configuration)
5. [Monitoring Configuration](#monitoring-configuration)
6. [Phase-Specific Configurations](#phase-specific-configurations)

---

## Configuration Files

### File Structure

```
polyquant/
├── config/
│   ├── secrets.env                    # Credentials (git-ignored)
│   ├── secrets.env.template           # Template for secrets
│   ├── dev/
│   │   └── risk_params.yaml           # Phase 1 (conservative)
│   ├── prod/
│   │   └── risk_params.yaml           # Phase 2-3 (optimized)
│   ├── prometheus.yml                 # Metrics scraping
│   ├── alerts.yml                     # Alerting rules
│   └── grafana/
│       └── dashboard.json             # Monitoring dashboard
└── models/
    └── xgboost_v1.0.0.onnx            # ML model (referenced in config)
```

---

## Risk Parameters

### risk_params.yaml (Complete Reference)

```yaml
# PolyQuant Risk Configuration
# Version: 1.0.0
# Phase: 1 (Dev) | 2 (Prod) | 3 (Cloud)

##############################################################################
# PHASE CONFIGURATION
##############################################################################
phase: 1  # 1 = Simulation, 2 = Local Live, 3 = AWS Cloud

##############################################################################
# POSITION SIZING
##############################################################################
position_sizing:
  # Maximum position size as % of account value
  max_position_size_pct: 0.05  # 5% per position

  # Maximum sector exposure (Mag 7 stocks are correlated)
  max_sector_exposure_pct: 0.15  # 15% total Mag 7

  # Kelly Criterion multiplier (use fractional Kelly for safety)
  kelly_fraction: 0.25  # Use 1/4 Kelly

  # Minimum position size (in option contracts)
  min_contracts: 1

  # Maximum position size (in option contracts, absolute cap)
  max_contracts: 50

##############################################################################
# STRATEGY PARAMETERS
##############################################################################
strategy:
  # ML signal thresholds
  min_signal_strength: 0.80  # Only trade signals > 80%
  signal_refresh_interval_seconds: 3600  # Re-evaluate hourly

  # Entry filters
  min_delta: 0.20  # Avoid deep OTM
  max_delta: 0.80  # Avoid deep ITM
  min_iv_percentile: 0.50  # Prefer elevated IV
  max_iv_percentile: 0.90  # Avoid extreme fear

  # Expected value
  min_expected_value: 0.10  # 10% minimum EV
  take_profit_pct: 0.50  # +50% take profit target
  stop_loss_pct: 0.30  # -30% stop loss
  expected_days_held: 3  # Used in EV calculation

  # Event timing
  min_days_before_expiry: 1  # Event must occur >= 1 day before expiry
  max_days_after_expiry: 7  # Event must occur <= 7 days after expiry

##############################################################################
# RISK MANAGEMENT
##############################################################################
risk:
  # Daily loss circuit breaker
  daily_loss_limit_pct: 0.02  # Halt at -2% daily

  # Maximum drawdown alert threshold
  max_drawdown_alert_pct: 0.08  # Alert at -8% from peak

  # Maximum trades per day (prevent overtrading)
  max_trades_per_day: 10

  # Maximum open positions
  max_open_positions: 5

  # Kill switch thresholds
  kill_switch:
    polymarket_disconnect_seconds: 60  # Halt new entries after 60s
    ibkr_disconnect_seconds: 30  # Begin flattening after 30s
    database_offline_seconds: 300  # Critical alert after 5 minutes
    max_memory_usage_pct: 0.90  # Restart if RAM > 90%

##############################################################################
# EXECUTION
##############################################################################
execution:
  # Spread checks
  max_spread_pct: 0.05  # Reject if spread > 5%
  liquidity_crisis_spread_pct: 0.08  # Reduce position if > 8%
  extreme_spread_pct: 0.12  # Full exit if > 12%

  # Order timeouts
  order_timeout_seconds: 60  # Cancel if not filled in 60s
  limit_order_walk_steps: 3  # mid → (mid+ask)/2 → ask
  limit_order_walk_interval_seconds: 20  # 20s between steps

  # Retry logic
  retry_attempts: 3
  retry_backoff_seconds: 5  # Exponential: 5s, 10s, 20s

  # Order types
  entry_order_type: "LIMIT"  # LIMIT | MARKET
  exit_order_type: "LIMIT"  # LIMIT | MARKET (stop loss always MARKET)

##############################################################################
# EXIT LOGIC
##############################################################################
exit:
  # Take profit
  take_profit_pct: 0.50  # +50%

  # Stop loss
  stop_loss_pct: 0.30  # -30%

  # Signal reversal
  signal_reversal_threshold: 0.30  # Exit if signal drops below 30%

  # Theta acceleration
  theta_burn_days_to_expiry: 1  # Exit at 1 day to expiry

  # Polymarket sentiment reversal
  poly_shift_threshold_pct: 0.20  # Exit if probability shifts >20%
  poly_shift_trailing_stop_pct: 0.15  # Tighten stop to -15%

  # Time-weighted scaling
  time_scaling_days: 3  # Start reducing after 3 days
  time_scaling_reduction_pct: 0.25  # Reduce by 25% daily

##############################################################################
# MODEL CONFIGURATION
##############################################################################
model:
  # Model file path (relative to project root)
  model_path: "models/xgboost_v1.0.0.onnx"

  # Feature names (must match ONNX input)
  features:
    - poly_prob
    - poly_prob_change_24h
    - poly_volume_usd
    - opt_delta
    - opt_iv
    - opt_iv_percentile
    - days_to_expiry
    - spread_width_pct
    - underlying_price_change_5d
    - vix_level

  # Model monitoring
  calibration_check_interval_trades: 20  # Check every 20 resolved trades
  max_calibration_error: 0.15  # Alert if error > 15%

  # Retraining
  retrain_interval_days: 30  # Retrain monthly
  min_training_samples: 50  # Need 50+ resolved trades

##############################################################################
# DATA SOURCES
##############################################################################
data_sources:
  # Polymarket
  polymarket:
    wss_url: "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    rest_url: "https://gamma-api.polymarket.com"
    reconnect_backoff_seconds: [1, 2, 4, 8, 16, 30]  # Exponential backoff
    max_reconnect_attempts: 10
    heartbeat_interval_seconds: 30

  # IBKR
  ibkr:
    host: "127.0.0.1"
    port: 4002  # Paper trading
    client_id: 0
    reconnect_backoff_seconds: 5
    max_reconnect_attempts: 5
    request_timeout_seconds: 10

  # Market data
  risk_free_rate: 0.045  # 10-year Treasury (update quarterly)

##############################################################################
# DATABASE
##############################################################################
database:
  # Connection (secrets loaded from env vars)
  max_connections: 10
  connection_timeout_seconds: 5

  # Async write queue
  write_queue_max_size: 10000  # Drop writes if queue > 10K
  write_batch_size: 100  # Flush every 100 records
  write_flush_interval_seconds: 1  # OR every 1 second

  # Retention policies (applied via TimescaleDB)
  retention:
    market_data_ticks_days: 90
    signals_days: 365
    trades_days: -1  # Keep indefinitely
    system_logs_days: 30

##############################################################################
# OBSERVABILITY
##############################################################################
observability:
  # Logging
  log_level: "INFO"  # TRACE | DEBUG | INFO | WARN | ERROR | CRITICAL
  log_file: "/var/log/polyquant/engine.log"
  log_rotation_size_mb: 100
  log_rotation_count: 10

  # Metrics (Prometheus)
  metrics_port: 8080
  metrics_endpoint: "/metrics"

  # Health check
  health_check_port: 8081
  health_check_endpoint: "/health"

##############################################################################
# TARGET UNIVERSE
##############################################################################
universe:
  tickers:
    - AAPL
    - MSFT
    - NVDA
    - AMZN
    - TSLA
    - META
    - GOOGL

  # Option selection criteria
  min_daily_volume: 100000  # contracts
  min_open_interest: 10000  # contracts
  max_bid_ask_spread_pct: 0.03  # 3%

##############################################################################
# BACKTESTING (Phase 1 Only)
##############################################################################
backtesting:
  enabled: true
  start_date: "2024-01-01"
  end_date: "2025-01-01"
  initial_capital: 10000.0
  commission_per_contract: 0.65
  slippage_bps: 5  # 5 basis points
```

---

## Environment Variables

### secrets.env (Template)

```bash
##############################################################################
# IBKR CREDENTIALS
##############################################################################
IBKR_USERNAME=your_username
IBKR_PASSWORD=your_password
IBKR_TRADING_MODE=paper  # paper | live
IBKR_ACCOUNT_ID=U1234567  # Your IBKR account number

##############################################################################
# DATABASE
##############################################################################
DB_HOST=localhost
DB_PORT=5432
DB_NAME=polyquant
DB_USER=polyquant_user
DB_PASSWORD=changeme_secure_password

# AWS RDS (Phase 3 only)
# DB_HOST=polyquant-db.c9akrzovzx.us-east-1.rds.amazonaws.com
# DB_PASSWORD=<from AWS Secrets Manager>

##############################################################################
# POLYMARKET
##############################################################################
# No authentication required for public data
POLYMARKET_WSS_URL=wss://ws-subscriptions-clob.polymarket.com/ws/market
POLYMARKET_REST_URL=https://gamma-api.polymarket.com

##############################################################################
# MARKET DATA
##############################################################################
RISK_FREE_RATE=0.045  # 10-year Treasury yield (update quarterly)

##############################################################################
# MONITORING (Phase 2-3 only)
##############################################################################
GRAFANA_ADMIN_PASSWORD=secure_password_here
PAGERDUTY_API_KEY=your_pagerduty_integration_key

##############################################################################
# AWS (Phase 3 only)
##############################################################################
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
S3_BACKUP_BUCKET=polyquant-backups-2025

##############################################################################
# SECURITY
##############################################################################
# Encryption key for sensitive data in database
ENCRYPTION_KEY=<generate with: openssl rand -hex 32>

# JWT secret for API authentication (future use)
# JWT_SECRET=<generate with: openssl rand -hex 64>
```

### Loading Environment Variables (C++)

```cpp
// src/cpp/config/config_loader.h
#include <fstream>
#include <string>
#include <unordered_map>

class ConfigLoader {
public:
    static void load_env_file(const std::string& path) {
        std::ifstream file(path);
        std::string line;

        while (std::getline(file, line)) {
            // Skip comments and empty lines
            if (line.empty() || line[0] == '#') continue;

            // Parse KEY=VALUE
            size_t pos = line.find('=');
            if (pos != std::string::npos) {
                std::string key = line.substr(0, pos);
                std::string value = line.substr(pos + 1);
                setenv(key.c_str(), value.c_str(), 1);
            }
        }
    }

    static std::string get_env(const std::string& key, const std::string& default_val = "") {
        const char* val = std::getenv(key.c_str());
        return val ? std::string(val) : default_val;
    }
};

// Usage
ConfigLoader::load_env_file("config/secrets.env");
std::string db_host = ConfigLoader::get_env("DB_HOST", "localhost");
```

---

## Database Configuration

### PostgreSQL (postgresql.conf)

```ini
# Memory
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
work_mem = 64MB

# Write-ahead log
wal_buffers = 16MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB

# Query planner
random_page_cost = 1.1  # SSD
effective_io_concurrency = 200

# TimescaleDB
shared_preload_libraries = 'timescaledb'
timescaledb.max_background_workers = 8

# Connections
max_connections = 100
```

### Connection String Format

```cpp
// Connection string builder
std::string build_connection_string() {
    std::ostringstream oss;
    oss << "host=" << ConfigLoader::get_env("DB_HOST")
        << " port=" << ConfigLoader::get_env("DB_PORT")
        << " dbname=" << ConfigLoader::get_env("DB_NAME")
        << " user=" << ConfigLoader::get_env("DB_USER")
        << " password=" << ConfigLoader::get_env("DB_PASSWORD")
        << " connect_timeout=5"
        << " sslmode=prefer";
    return oss.str();
}
```

---

## Monitoring Configuration

### Prometheus (prometheus.yml)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'polyquant-prod'
    phase: '2'  # 1 = Lab, 2 = Incubator, 3 = Production

scrape_configs:
  - job_name: 'polyquant_engine'
    static_configs:
      - targets: ['localhost:8080']
    scrape_interval: 5s  # Higher frequency for trading system

  - job_name: 'node_exporter'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'postgres_exporter'
    static_configs:
      - targets: ['localhost:9187']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

rule_files:
  - 'alerts.yml'
```

### Alert Rules (alerts.yml)

```yaml
groups:
  - name: trading_critical
    interval: 5s
    rules:
      - alert: DailyLossLimitReached
        expr: polyquant_daily_pnl_pct < -0.015
        for: 10s
        labels:
          severity: critical
          component: risk_manager
        annotations:
          summary: "Daily loss approaching -2% limit"
          description: "Current: {{ $value | humanizePercentage }}"
          action: "Trading will halt at -2.0%"

      - alert: FeedDisconnected
        expr: (time() - polyquant_last_update_timestamp) > 30
        for: 30s
        labels:
          severity: critical
          component: data_feed
        annotations:
          summary: "Market data feed disconnected"
          description: "No updates for {{ $value }}s"
          action: "New entries halted"

      - alert: ModelDrift
        expr: abs(polyquant_model_calibration_error) > 0.20
        for: 1h
        labels:
          severity: warning
          component: ml_model
        annotations:
          summary: "Model predictions drifting"
          description: "Calibration error: {{ $value | humanizePercentage }}"
          action: "Consider retraining model"

  - name: trading_warnings
    interval: 30s
    rules:
      - alert: HighLatency
        expr: polyquant_order_latency_ms{quantile="0.95"} > 100
        for: 5m
        labels:
          severity: warning
          component: execution
        annotations:
          summary: "Order placement latency elevated"
          description: "p95: {{ $value }}ms (target: <50ms)"

      - alert: LowFillRate
        expr: (
          polyquant_orders_filled_total /
          polyquant_orders_submitted_total
        ) < 0.80
        for: 1h
        labels:
          severity: warning
          component: execution
        annotations:
          summary: "Fill rate below 80%"
          description: "Current: {{ $value | humanizePercentage }}"
          action: "Review spread limits or order types"
```

---

## Phase-Specific Configurations

### Phase 1: Local Simulation

```yaml
# config/dev/risk_params.yaml
phase: 1
position_sizing:
  max_position_size_pct: 0.05
strategy:
  min_signal_strength: 0.85  # Very conservative
execution:
  entry_order_type: "LIMIT"  # Learn spreads
```

**Characteristics**:
- Conservative signal threshold (0.85)
- LIMIT orders to avoid overpaying
- Verbose logging (`log_level: DEBUG`)

### Phase 2: Local Live

```yaml
# config/prod/risk_params.yaml
phase: 2
position_sizing:
  max_position_size_pct: 0.05
strategy:
  min_signal_strength: 0.80  # Optimized after Phase 1
execution:
  entry_order_type: "LIMIT"
  order_timeout_seconds: 60
```

**Characteristics**:
- Slightly relaxed threshold (0.80) based on Phase 1 learnings
- Production logging (`log_level: INFO`)
- Monitoring enabled (Prometheus + Grafana)

### Phase 3: AWS Cloud

```yaml
# config/prod/risk_params.yaml
phase: 3
position_sizing:
  max_position_size_pct: 0.05
  kelly_fraction: 0.30  # Slightly more aggressive
strategy:
  min_signal_strength: 0.78  # Further optimized
execution:
  entry_order_type: "LIMIT"
  order_timeout_seconds: 45  # Lower latency environment
```

**Characteristics**:
- Optimized parameters from 6+ months of data
- AWS-specific settings (RDS connection pooling)
- Advanced monitoring (PagerDuty, CloudWatch)

---

## Validation & Testing

### Configuration Validator

```cpp
// src/cpp/config/validator.h
class ConfigValidator {
public:
    static void validate(const Config& config) {
        // Position sizing
        assert(config.max_position_size_pct > 0 && config.max_position_size_pct <= 0.20);
        assert(config.max_sector_exposure_pct <= 0.50);
        assert(config.kelly_fraction > 0 && config.kelly_fraction <= 1.0);

        // Strategy
        assert(config.min_signal_strength >= 0.5 && config.min_signal_strength <= 1.0);
        assert(config.min_delta > 0 && config.min_delta < 1.0);
        assert(config.max_delta > config.min_delta && config.max_delta < 1.0);

        // Risk
        assert(config.daily_loss_limit_pct > 0 && config.daily_loss_limit_pct < 0.10);
        assert(config.max_trades_per_day > 0 && config.max_trades_per_day <= 100);

        // Execution
        assert(config.max_spread_pct > 0 && config.max_spread_pct < 0.20);
        assert(config.order_timeout_seconds > 10 && config.order_timeout_seconds < 300);

        // Exit
        assert(config.take_profit_pct > 0);
        assert(config.stop_loss_pct > 0);
        assert(config.take_profit_pct > config.stop_loss_pct);  // Positive expectancy

        spdlog::info("✅ Configuration validated successfully");
    }
};
```

### Unit Test Example

```cpp
TEST(ConfigTest, LoadsValidConfiguration) {
    Config config = Config::load("config/dev/risk_params.yaml");

    EXPECT_EQ(config.phase, 1);
    EXPECT_DOUBLE_EQ(config.max_position_size_pct, 0.05);
    EXPECT_DOUBLE_EQ(config.min_signal_strength, 0.80);
    EXPECT_EQ(config.max_trades_per_day, 10);

    EXPECT_NO_THROW(ConfigValidator::validate(config));
}
```

---

## Updating Configuration

### Hot Reload (Runtime Changes)

**Supported**:
- Risk parameters (position limits, spread thresholds)
- Logging level
- Model file path (triggers reload)

**Not Supported (Requires Restart)**:
- Database connection strings
- Prometheus port
- Phase number

```cpp
// Watch for config file changes
class ConfigWatcher {
private:
    std::filesystem::path config_path_;
    std::filesystem::file_time_type last_modified_;

public:
    void start_watching() {
        std::thread([this]() {
            while (true) {
                auto current_modified = std::filesystem::last_write_time(config_path_);
                if (current_modified != last_modified_) {
                    spdlog::info("Config file changed, reloading...");
                    reload_config();
                    last_modified_ = current_modified;
                }
                std::this_thread::sleep_for(std::chrono::seconds(5));
            }
        }).detach();
    }
};
```

---

**See Also**:
- [DEPLOYMENT.md](DEPLOYMENT.md) - Setting up configuration files
- [ARCHITECTURE.md](ARCHITECTURE.md) - How configuration is loaded
- [PHASED_ROLLOUT.md](PHASED_ROLLOUT.md) - Configuration evolution across phases

