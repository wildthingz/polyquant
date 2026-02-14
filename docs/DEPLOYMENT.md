# Deployment Guide

Complete deployment guide for PolyQuant across all three phases: Local Simulation, Local Live, and AWS Cloud.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Phase 1: Local Simulation (Docker)](#phase-1-local-simulation-docker)
3. [Phase 2: Local Live](#phase-2-local-live)
4. [Phase 3: AWS Cloud](#phase-3-aws-cloud)
5. [Monitoring Setup](#monitoring-setup)
6. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Hardware

**Minimum** (Phase 1):
- CPU: 4 cores (x86_64)
- RAM: 16 GB
- Disk: 50 GB SSD
- Network: 10 Mbps (stable connection)

**Recommended** (Phase 2-3):
- CPU: 8 cores
- RAM: 32 GB
- Disk: 100 GB NVMe SSD
- Network: 100 Mbps (low latency)

### Software

**Operating System**:
- Any OS with Docker support (Linux, macOS, Windows WSL2)
- Arch Linux (preferred for host)

**Required**:
- Docker 24+
- Docker Compose v2+
- Git

---

## Phase 1: Local Simulation (Docker)

**Goal**: Paper trading on local workstation using a fully containerized environment.

### Automated Setup

```bash
#!/bin/bash
# setup.sh - Automated installation script

set -e  # Exit on error

echo "=== PolyQuant Setup (Phase 1: Dockerized) ==="

# 1. Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker could not be found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose could not be found. Please install Docker Compose."
    exit 1
fi

# 2. Clone repository (if not already)
# git clone https://github.com/yourusername/polyquant.git
# cd polyquant

# 3. Create configuration
echo "[1/3] Creating configuration files..."
if [ ! -f .env ]; then
    cp .env.template .env
    echo "⚠️  IMPORTANT: Edit .env with your IBKR credentials"
fi

# 4. Build and Start Containers
echo "[2/3] Building and starting containers..."
docker-compose up -d --build

# 5. Initialize Database
echo "[3/3] Waiting for database to initialize..."
sleep 10 # Wait for DB to start
# Schema is automatically applied via schema.sql mapping in docker-compose

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your credentials"
echo "2. View logs: docker-compose logs -f"
echo "3. Access shell: docker-compose exec engine /bin/bash"
```

### Configuration Files

**.env**:
```bash
# IBKR Credentials
IBKR_USERNAME=edemo
IBKR_PASSWORD=demouser
IBKR_TRADING_MODE=paper

# Database (Internal Docker Network)
DB_HOST=db
DB_PORT=5432
DB_NAME=polyquant
DB_USER=polyquant_user
DB_PASSWORD=password123
```

**docker-compose.yml**:
(See project root for full file)

### Running Phase 1

```bash
# Start all services
docker-compose up -d

# View logs of the C++ engine
docker-compose logs -f engine

# Rebuild after code changes
docker-compose up -d --build engine
```

### Health Check

```bash
#!/bin/bash
# scripts/health_check.sh

echo "=== PolyQuant Health Check ==="

# 1. Check Containers
echo -n "Containers: "
if [ $(docker-compose ps -q | wc -l) -eq 4 ]; then
    echo "✅ All running"
else
    echo "❌ Some containers missing"
    docker-compose ps
fi

# 2. Database connection
echo -n "Database: "
docker-compose exec db psql -U polyquant_user -d polyquant -c "SELECT 1" > /dev/null 2>&1 && echo "✅" || echo "❌"

# 3. IB Gateway
echo -n "IB Gateway: "
docker-compose exec ib_gateway netstat -tuln | grep ":4002" > /dev/null 2>&1 && echo "✅" || echo "❌"

echo ""
```

---

## Phase 2: Local Live

**Goal**: Real money trading on local workstation with full observability.

### Additional Setup

1.  **Switch to Live Mode**:
    Update `.env`:
    ```bash
    IBKR_TRADING_MODE=live
    ```

2.  **Enable Monitoring**:
    Uncomment Prometheus and Grafana services in `docker-compose.yml` (if commented out) or ensure they are running.

3.  **Restart**:
    ```bash
    docker-compose down
    docker-compose up -d
    ```

---

## Phase 3: AWS Cloud

**Goal**: 24/7 cloud deployment with high availability.

### AWS Infrastructure

**Stack**: EC2 + RDS PostgreSQL + S3 + CloudWatch

1.  **Provision EC2**: Launch a `t3.medium` instance (Ubuntu or Amazon Linux 2).
2.  **Install Docker**:
    ```bash
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose
    sudo usermod -aG docker $USER
    ```
3.  **Deploy**:
    Copy project files to EC2.
    ```bash
    scp -r polyquant/ ubuntu@<ec2-ip>:~/polyquant
    ssh ubuntu@<ec2-ip>
    cd polyquant
    docker-compose up -d
    ```

*Note: For production RDS, update `DB_HOST` in `.env` to point to the RDS endpoint instead of the local `db` container.*

---

## Monitoring Setup

### Prometheus Metrics Endpoint (C++)

The C++ engine exposes metrics on port `8080`.

```cpp
// src/cpp/observability/metrics.h
// ... (Prometheus C++ implementation)
```

---

## Troubleshooting

### Common Issues

#### 1. IB Gateway Connection Failed
*   Check logs: `docker-compose logs ib_gateway`
*   Ensure credentials in `.env` are correct.
*   Note: IBKR requires 2FA for live accounts; the headless gateway might need helper scripts or manual initial login if not using IBC properly.

#### 2. Database Connection Refused
*   Ensure `db` container is healthy.
*   Check `docker-compose logs db`.

#### 3. Build Errors
*   Check `docker-compose logs engine` during build.
*   If adding new dependencies, rebuild: `docker-compose build --no-cache engine`.

---

**See Also**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - Deployment models
- [CONFIGURATION.md](CONFIGURATION.md) - risk_params.yaml reference
- [STRESS_TESTING.md](STRESS_TESTING.md) - Failure recovery procedures
