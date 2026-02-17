# PolyQuant: VRP Premium Selling with Prediction Market Timing

A high-performance, event-driven trading system that sells options premium (iron condors, credit spreads) on Mag 7 stocks, using Polymarket prediction market data as a timing signal to identify when event uncertainty is overpriced.

**Status**: Phase 1 (Local Simulation) | **Stack**: C++20 + Python 3.10 + PostgreSQL + TimescaleDB

## Overview

PolyQuant harvests the Volatility Risk Premium (VRP) — the well-documented tendency for implied volatility to exceed realized volatility — with a Polymarket timing overlay. When Polymarket shows high certainty about an event outcome but options IV remains elevated, we sell premium and collect theta decay as IV crushes post-event.

**Alpha Hypothesis**: Structural VRP provides ~8-10% annualized edge. Polymarket timing adds ~4-8% by filtering entries to moments when the crowd is confident but IV hasn't adjusted. Target: 12-18% annualized, Sharpe ~0.8.

### Key Features

- **Low-Latency Core**: C++20 event loop with <50ms tick-to-trade latency
- **Rule-Based Premium Selling Signals**: IV percentile + Polymarket certainty + divergence filters
- **Comprehensive Risk Management**: Position limits, daily loss stops, graceful kill switch
- **Production Ready**: TimescaleDB storage, Prometheus metrics, Docker deployment

---

## Quick Start

### Prerequisites
- Docker 24+
- Docker Compose v2+
- IBKR account (paper trading for Phase 1)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/polyquant.git
cd polyquant

# 2. Configure secrets
cp .env.template .env
# Edit .env with your IBKR credentials

# 3. Build and Start
docker-compose up -d --build

# 4. View Logs
docker-compose logs -f engine
```

### Verify Installation

```bash
# Run unit tests inside container
docker-compose exec engine ./build/polyquant_tests

# Check system health
docker-compose ps
```

---

## Project Structure

```
polyquant/
├── include/
│   └── polyquant/
│       ├── core/             # Core data structures (EventBus, MarketData)
│       ├── feed/             # Data adapters (Polymarket, IBKR)
│       └── pricing/          # Black-Scholes & Greeks engine
├── src/
│   └── cpp/                  # C++ implementation files
│       ├── main.cpp          # Entry point
│       ├── feed/
│       └── pricing/
├── tests/                    # GoogleTest unit tests
├── docker/                   # Dockerfiles for C++ and Python
├── config/                   # Configuration files
├── docs/                     # Detailed documentation
├── models/                   # Trained ML models (.onnx)
├── schema.sql                # Database schema
└── CMakeLists.txt            # Build configuration
```

---

## Project Status

**Phase 1** (~50% complete) - See [**STATUS.md**](STATUS.md) for detailed progress, test results, and next actions.

**Quick Summary**:
- ✅ Live Polymarket data flowing
- ✅ 14/14 tests passing
- ✅ Signal generation working (old call-buying logic, pending rewrite)
- 🔄 **Next: VRP premium selling backtest** (see [quantconnect/](quantconnect/))
- ⚠️ StrategyEngine rewrite needed for premium selling
- ⚠️ Risk Manager needed (after backtest validation)

---

## Backtesting

**Recommended Approach**: Use [QuantConnect](quantconnect/) platform for VRP premium selling backtest
- Iron condors and credit spreads on Mag 7 stocks
- Free tier includes options + sentiment data
- See [quantconnect/README.md](quantconnect/README.md) for setup

**Alternative**: Build custom infrastructure with [docs/BACKTESTING.md](docs/BACKTESTING.md) (for advanced users)

---

## Documentation

### 🚀 Start Here
- [**STATUS.md**](STATUS.md) - ⭐ **READ THIS FIRST** - Detailed progress, component status, test results, next actions

### Core Concepts
- [**Architecture**](docs/ARCHITECTURE.md) - System design, C4 diagrams, component interactions
- [**Trading Strategy**](docs/TRADING_STRATEGY.md) - Entry/exit logic, Greeks, risk management
- [**Phased Rollout**](docs/PHASED_ROLLOUT.md) - Phase 1/2/3 criteria and operational procedures

### Implementation Guides
- [**API Integration**](docs/API_INTEGRATION.md) - Polymarket + IBKR connection patterns
- [**Database Schema**](docs/DATABASE_SCHEMA.md) - Full schema, indexes, views, migrations
- [**Math Specs**](docs/MATH_SPECS.md) - Black-Scholes, Greeks, IV solver implementations
- [**Deployment**](docs/DEPLOYMENT.md) - Docker setup, AWS migration

### Reference
- [**Stress Testing**](docs/STRESS_TESTING.md) - Failure scenarios and recovery procedures
- [**Configuration**](docs/CONFIGURATION.md) - risk_params.yaml reference

**New to the project?** Start with [docs/index.md](docs/index.md)

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Execution** | C++20 (GCC/Clang) | Low-latency event loop, pricing engine |
| **Backtesting** | Python 3.10 + QuantConnect | Strategy validation |
| **ML Inference** | ONNX Runtime (Phase 2+) | Bridge between Python and C++ |
| **Database** | PostgreSQL 15 + TimescaleDB | Time-series storage |
| **Broker** | IBKR Gateway (Headless) | Options data + execution |
| **Monitoring** | Prometheus + Grafana | Metrics and alerting |
| **Deployment** | Docker | Containerization |

**Dependencies**: boost::asio, nlohmann/json, spdlog, libpqxx, googletest, openssl

---

## License

MIT License - see LICENSE file for details.

---

**Built with**: C++20, Python, PostgreSQL, and lots of coffee ☕
