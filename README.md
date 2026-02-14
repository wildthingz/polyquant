# PolyQuant: Sentiment-Enhanced Options Trading

A high-performance, event-driven trading system that uses Polymarket prediction market data as a real-time sentiment indicator for options trading on the Mag 7 stocks (AAPL, NVDA, MSFT, AMZN, TSLA, META, GOOGL).

**Status**: Phase 1 (Local Simulation) | **Stack**: C++20 + Python 3.10 + PostgreSQL + TimescaleDB

## Overview

Unlike institutional HFT systems, PolyQuant is designed for retail quants: it uses professional-grade infrastructure to identify sentiment-driven IV mispricing before broader market participants react.

**Alpha Hypothesis**: Retail traders lack access to real-time sentiment aggregation from prediction markets. By synthesizing Polymarket probability shifts with options greeks and technical indicators, PolyQuant captures mispricing opportunities.

### Key Features

- **Low-Latency Core**: C++20 event loop with <50ms tick-to-trade latency
- **ML-Powered Signals**: XGBoost model with automatic retraining (nightly)
- **Comprehensive Risk Management**: Position limits, daily loss stops, graceful kill switch
- **Production Ready**: TimescaleDB storage, Prometheus metrics, Docker deployment

---

## Quick Start

### Prerequisites
- Arch Linux (or compatible)
- 16GB RAM, 4 cores
- IBKR account (paper trading for Phase 1)

### Installation

```bash
# 1. Run automated setup
bash setup.sh

# 2. Activate Python environment
source $HOME/polyquant-venv/bin/activate

# 3. Initialize database
psql -U postgres -d polyquant -f schema.sql

# 4. Configure secrets
cp config/secrets.env.template config/secrets.env
# Edit config/secrets.env with your credentials

# 5. Build C++ engine
mkdir build && cd build
cmake .. && make -j$(nproc)

# 6. Run paper trading
./polyquant_engine --config=../config/dev/risk_params.yaml
```

### Verify Installation

```bash
# Check system health
./polyquant_engine --health-check

# Run unit tests
cd build && ctest --output-on-failure

# Monitor dashboard
open http://localhost:3000  # Grafana (default: admin/admin)
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Quantitative Trader                      │
│                   (Configure & Monitor)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────▼────────────────────┐
        │      PolyQuant Engine (C++20)       │
        │                                     │
        │  ┌──────────┐      ┌────────────┐  │
        │  │  Event   │─────▶│  Strategy  │  │
        │  │   Bus    │      │   Engine   │  │
        │  └─────┬────┘      └─────┬──────┘  │
        │        │                 │         │
        │   ┌────▼─────┐    ┌─────▼──────┐  │
        │   │ Pricing  │    │    Risk    │  │
        │   │ Engine   │    │  Manager   │  │
        │   └──────────┘    └────────────┘  │
        └─────┬──────────────────┬───────────┘
              │                  │
    ┌─────────▼────┐      ┌──────▼────────┐
    │  Polymarket  │      │  IBKR TWS API │
    │  WebSocket   │      │  (Port 4002)  │
    └──────────────┘      └───────────────┘
```

**Core Components**:
- **C++ Engine**: Low-latency event loop, Black-Scholes pricing, risk checks
- **Python ML Worker**: XGBoost training, ONNX model export
- **PostgreSQL + TimescaleDB**: Time-series storage for ticks, trades, signals
- **IBKR Gateway**: Options data + paper/live trading execution

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed C4 diagrams.

---

## Trading Strategy

### Signal Generation

Trades are triggered when ALL conditions pass:

1. **Event Timing**: Polymarket event occurs ≥1 day before option expiry AND ≤7 days after
2. **ML Signal**: XGBoost model outputs `signal_strength > 0.8`
3. **Liquidity**: Option bid-ask spread < 5%
4. **Delta Range**: 0.20 < Delta < 0.80
5. **Expected Value**: `EV > 0.10` (10% minimum expected return)
6. **Risk Limits**: Position < 5% account, sector exposure < 15%

### Position Management

**Entry**: Limit orders at mid-to-ask
**Exit** (first trigger wins):
- Take profit: +50%
- Stop loss: -30%
- Signal reversal: ML strength drops below 0.3
- Theta acceleration: 1 day to expiry
- Liquidity crisis: Spread widens >8%
- Sentiment reversal: Polymarket probability shifts >20%

See [docs/TRADING_STRATEGY.md](docs/TRADING_STRATEGY.md) for complete Greeks usage and exit logic.

---

## Project Status

### Phase 1: Local Simulation ("The Lab") - **CURRENT**

**Environment**: Local Arch Linux
**Capital**: $0 (IBKR Paper Trading)
**Duration**: 30 days OR 100 trades

**Progress**:
- [x] System requirements defined
- [x] Architecture designed
- [x] Database schema complete
- [x] Documentation structure
- [ ] C++ pricing engine (0%)
- [ ] API adapters (0%)
- [ ] Risk manager (0%)
- [ ] ML model bootstrap (0%)

**Exit Criteria** (ALL must pass):
- ✅ Sharpe Ratio > 1.0
- ✅ 100+ fully resolved trades
- ✅ Win rate within ±10% of avg ML signal_strength
- ✅ Max drawdown < 8%
- ✅ Zero unhandled exceptions

### Phase 2: Local Live Pilot ("The Incubator")
**Capital**: $500 → $2,000
See [docs/PHASED_ROLLOUT.md](docs/PHASED_ROLLOUT.md)

### Phase 3: Cloud Deployment ("Production")
**Capital**: $2,000+
**Target**: AWS EC2, 24/7 operation

---

## Documentation

### Core Concepts
- [**Architecture**](docs/ARCHITECTURE.md) - System design, C4 diagrams, component interactions
- [**Trading Strategy**](docs/TRADING_STRATEGY.md) - Entry/exit logic, Greeks, risk management
- [**Phased Rollout**](docs/PHASED_ROLLOUT.md) - Phase 1/2/3 criteria and operational procedures

### Implementation Guides
- [**API Integration**](docs/API_INTEGRATION.md) - Polymarket + IBKR connection patterns
- [**Database Schema**](docs/DATABASE_SCHEMA.md) - Full schema, indexes, views, migrations
- [**Math Specs**](docs/MATH_SPECS.md) - Black-Scholes, Greeks, IV solver implementations
- [**Deployment**](docs/DEPLOYMENT.md) - Arch Linux setup, Docker, AWS migration

### Reference
- [**Stress Testing**](docs/STRESS_TESTING.md) - Failure scenarios and recovery procedures
- [**Configuration**](docs/CONFIGURATION.md) - risk_params.yaml reference

**New to the project?** Start with [docs/index.md](docs/index.md)

---

## Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Latency** | <50ms | Tick-to-trade loop (Polymarket update → IBKR order) |
| **Uptime** | 99.9% | During market hours (9:30 AM - 4:00 PM ET) |
| **Sharpe Ratio** | >1.5 | Risk-adjusted returns (Phase 2 target) |
| **Max Drawdown** | <10% | Capital preservation |
| **Fill Rate** | >80% | Execution quality (limit orders) |
| **Model Calibration** | <15% error | Predicted vs actual win rate |

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Execution** | C++20 (GCC/Clang) | Low-latency event loop, pricing engine |
| **ML Training** | Python 3.10 + XGBoost | Model training and backtesting |
| **ML Inference** | ONNX Runtime | Bridge between Python and C++ |
| **Database** | PostgreSQL 15 + TimescaleDB | Time-series storage |
| **Broker** | IBKR Gateway (Headless) | Options data + execution |
| **Monitoring** | Prometheus + Grafana | Metrics and alerting |
| **Deployment** | Docker + AWS EC2 | Containerization and cloud hosting |

**Dependencies**: boost::asio, nlohmann/json, spdlog, libpqxx, googletest

---

## Development

### Build from Source

```bash
# Install dependencies (see docs/DEPLOYMENT.md for full guide)
bash setup.sh

# Build
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)

# Run tests
ctest --output-on-failure

# Install
sudo make install
```

### Project Structure

```
polyquant/
├── config/           # Configuration files (dev/prod)
├── docs/             # Detailed documentation
├── src/
│   ├── cpp/          # C++ core engine
│   └── python/       # ML training scripts
├── tests/            # Unit, integration, stress tests
├── scripts/          # Setup and deployment scripts
├── models/           # Trained ML models (.onnx)
├── schema.sql        # Database schema
├── setup.sh          # Automated installation
└── CMakeLists.txt    # Build configuration
```

---

## Contributing

This is a personal trading system. Not accepting external contributions at this time.

---

## Monitoring & Alerting

**Grafana Dashboard**: http://localhost:3000

Key metrics:
- `polyquant_daily_pnl_pct` - Current daily P&L
- `polyquant_open_positions_count` - Active positions
- `polyquant_model_calibration_error` - Model accuracy
- `polyquant_order_latency_ms` - Execution speed

**Critical Alerts** (page operator):
- Daily loss > -1.5%
- Feed disconnected > 30s
- Model calibration error > 20%

---

## Risk Disclosure

**This is experimental software for educational purposes.**

- Options trading involves substantial risk of loss
- Past performance does not guarantee future results
- Only risk capital you can afford to lose
- Phase 1 uses paper trading (no real money)
- Phase 2/3 involve real capital at your own risk

By using this software, you acknowledge these risks and agree to trade responsibly.

---

## License

MIT License - see LICENSE file for details.

---

## Support & Resources

- **Documentation**: [docs/index.md](docs/index.md)
- **Issues**: Open GitHub issue for bugs
- **Email**: [your-email] (for security issues only)

**Recommended Reading**:
- "Options, Futures, and Other Derivatives" by John Hull
- "Quantitative Trading" by Ernest Chan
- IBKR API Documentation: https://interactivebrokers.github.io
- Polymarket API: https://docs.polymarket.com

---

**Built with**: C++20, Python, PostgreSQL, and lots of coffee ☕
