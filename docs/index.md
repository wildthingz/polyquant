# PolyQuant Documentation

Welcome to the PolyQuant documentation. This guide will help you understand, build, and deploy the system.

## 🚀 Getting Started

**New to PolyQuant?** Follow this path:

1. Read the [main README](../README.md) for project overview
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) to understand system design
3. Study [TRADING_STRATEGY.md](TRADING_STRATEGY.md) to learn the trading logic
4. Follow [DEPLOYMENT.md](DEPLOYMENT.md) to set up your environment

---

## 📚 Documentation Index

### Core Concepts

| Document | Description | When to Read |
|----------|-------------|--------------|
| [**ARCHITECTURE.md**](ARCHITECTURE.md) | System design, C4 diagrams, component interactions | Before coding any component |
| [**TRADING_STRATEGY.md**](TRADING_STRATEGY.md) | Entry/exit logic, Greeks, risk management | When implementing strategy engine |
| [**PHASED_ROLLOUT.md**](PHASED_ROLLOUT.md) | Phase 1/2/3 criteria, operational procedures | Before starting each phase |

### Implementation Guides

| Document | Description | When to Read |
|----------|-------------|--------------|
| [**API_INTEGRATION.md**](API_INTEGRATION.md) | Polymarket + IBKR WebSocket/API patterns | When building data adapters |
| [**DATABASE_SCHEMA.md**](DATABASE_SCHEMA.md) | Full PostgreSQL schema, indexes, views | When setting up database |
| [**MATH_SPECS.md**](MATH_SPECS.md) | Black-Scholes, Greeks, IV solver | When implementing pricing engine |
| [**DEPLOYMENT.md**](DEPLOYMENT.md) | Arch Linux setup, Docker, AWS | When provisioning infrastructure |

### Operations & Testing

| Document | Description | When to Read |
|----------|-------------|--------------|
| [**STRESS_TESTING.md**](STRESS_TESTING.md) | Failure scenarios, recovery procedures | Before Phase 1 exit |
| [**CONFIGURATION.md**](CONFIGURATION.md) | risk_params.yaml, secrets.env reference | When tuning parameters |

---

## 🗺️ Learning Paths

### Path 1: System Architect
**Goal**: Understand the entire system design

1. [ARCHITECTURE.md](ARCHITECTURE.md) - System overview
2. [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Data model
3. [API_INTEGRATION.md](API_INTEGRATION.md) - External integrations
4. [DEPLOYMENT.md](DEPLOYMENT.md) - Infrastructure

### Path 2: Quant Developer
**Goal**: Implement trading logic and pricing

1. [TRADING_STRATEGY.md](TRADING_STRATEGY.md) - Trading rules
2. [MATH_SPECS.md](MATH_SPECS.md) - Financial mathematics
3. [CONFIGURATION.md](CONFIGURATION.md) - Risk parameters
4. [PHASED_ROLLOUT.md](PHASED_ROLLOUT.md) - Testing strategy

### Path 3: DevOps Engineer
**Goal**: Deploy and monitor the system

1. [DEPLOYMENT.md](DEPLOYMENT.md) - Setup procedures
2. [ARCHITECTURE.md](ARCHITECTURE.md#observability) - Monitoring
3. [STRESS_TESTING.md](STRESS_TESTING.md) - Resilience testing
4. [PHASED_ROLLOUT.md](PHASED_ROLLOUT.md#phase-3) - Production deployment

---

## 📊 System Components Quick Reference

| Component | Technology | Documentation |
|-----------|-----------|---------------|
| **Core Engine** | C++20 | [ARCHITECTURE.md](ARCHITECTURE.md#level-3-component-diagram) |
| **Pricing** | Black-Scholes | [MATH_SPECS.md](MATH_SPECS.md) |
| **ML Model** | XGBoost → ONNX | [TRADING_STRATEGY.md](TRADING_STRATEGY.md#ml-model) |
| **Database** | PostgreSQL + TimescaleDB | [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) |
| **Data Feeds** | Polymarket + IBKR | [API_INTEGRATION.md](API_INTEGRATION.md) |
| **Deployment** | Docker + AWS EC2 | [DEPLOYMENT.md](DEPLOYMENT.md) |

---

## 🔧 Common Tasks

### Setup Tasks
- **Initial Setup**: [DEPLOYMENT.md](DEPLOYMENT.md#installation-script)
- **Database Init**: [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md#initialization)
- **Config Files**: [CONFIGURATION.md](CONFIGURATION.md)

### Development Tasks
- **Build C++ Engine**: [DEPLOYMENT.md](DEPLOYMENT.md#cmake-build)
- **Run Unit Tests**: [MATH_SPECS.md](MATH_SPECS.md#validation)
- **Train ML Model**: [TRADING_STRATEGY.md](TRADING_STRATEGY.md#model-bootstrap)

### Operational Tasks
- **Start Trading**: [PHASED_ROLLOUT.md](PHASED_ROLLOUT.md#phase-1)
- **Monitor System**: [ARCHITECTURE.md](ARCHITECTURE.md#observability)
- **Handle Failures**: [STRESS_TESTING.md](STRESS_TESTING.md)

---

## 🐛 Troubleshooting

| Problem | Solution | Documentation |
|---------|----------|---------------|
| Build fails | Check dependencies | [DEPLOYMENT.md](DEPLOYMENT.md#verification) |
| DB connection error | Verify PostgreSQL running | [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md#troubleshooting) |
| IBKR connection lost | Check Gateway status | [API_INTEGRATION.md](API_INTEGRATION.md#reconnection) |
| Greeks mismatch | Validate against reference | [MATH_SPECS.md](MATH_SPECS.md#validation) |
| High latency | Profile event loop | [ARCHITECTURE.md](ARCHITECTURE.md#performance) |

---

## 📈 Current Project Status

**See [../STATUS.md](../STATUS.md) for detailed, up-to-date project status.**

Quick summary:
- Phase 1 (~50% complete)
- Live Polymarket data flowing
- 14/14 tests passing
- **Next: QuantConnect backtesting** (see [../quantconnect/](../quantconnect/))
- Risk Manager after backtest validation

---

## 📝 Documentation Standards

When updating docs:
- Keep code examples runnable
- Update README.md if API changes
- Add diagrams for complex logic
- Include troubleshooting tips
- Version control all changes

---

## 🆘 Getting Help

1. **Check docs first**: Use search (Ctrl+F) in relevant doc
2. **Review examples**: See code snippets in each guide
3. **Run tests**: Automated tests validate correctness
4. **Open issue**: For bugs or unclear documentation

---

## 🔗 External Resources

- **IBKR API Docs**: https://interactivebrokers.github.io
- **Polymarket API**: https://docs.polymarket.com
- **TimescaleDB**: https://docs.timescale.com
- **ONNX Runtime**: https://onnxruntime.ai/docs
- **Black-Scholes**: Hull's "Options, Futures, and Other Derivatives"

---

**Last Updated**: 2026-02-13
**Version**: 1.0.0 (Phase 1)
