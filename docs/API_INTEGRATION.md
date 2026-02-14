# API Integration Guide

Complete guide for integrating with Polymarket (WebSocket + REST) and IBKR (TWS API) for real-time data ingestion and trade execution.

## Table of Contents

1. [Polymarket Integration](#polymarket-integration)
2. [IBKR Integration](#ibkr-integration)
3. [Connection Management](#connection-management)
4. [Error Handling](#error-handling)
5. [Rate Limits](#rate-limits)

---

## Polymarket Integration

### Overview

Polymarket provides two APIs:
- **REST API**: Historical data, market metadata
- **WebSocket API**: Real-time probability updates (primary use)

**Base URLs**:
- REST: `https://gamma-api.polymarket.com/`
- WebSocket: `wss://ws-subscriptions-clob.polymarket.com/ws/market`

### WebSocket Client (C++ Implementation)

```c++
#include <boost/beast/core.hpp>
#include <boost/beast/websocket.hpp>
#include <boost/asio/strand.hpp>
#include <nlohmann/json.hpp>

namespace beast = boost::beast;
namespace websocket = beast::websocket;
namespace net = boost::asio;
using tcp = boost::asio::ip::tcp;
using json = nlohmann::json;

class PolymarketWebSocket {
private:
    net::io_context& ioc_;
    websocket::stream<beast::tcp_stream> ws_;
    beast::flat_buffer buffer_;
    std::function<void(const json&)> callback_;

public:
    PolymarketWebSocket(net::io_context& ioc,
                        std::function<void(const json&)> callback)
        : ioc_(ioc), ws_(net::make_strand(ioc)), callback_(callback) {}

    void connect() {
        tcp::resolver resolver{ioc_};
        auto const results = resolver.resolve(
            "ws-subscriptions-clob.polymarket.com", "443");

        // Connect TCP socket
        beast::get_lowest_layer(ws_).connect(results);

        // Perform SSL/TLS handshake
        ws_.next_layer().handshake(tcp::socket::handshake_type::client);

        // Perform WebSocket handshake
        ws_.handshake("ws-subscriptions-clob.polymarket.com",
                      "/ws/market");

        // Subscribe to markets
        subscribe_to_mag7_markets();

        // Start reading messages
        start_read();
    }

    void subscribe_to_mag7_markets() {
        // Subscribe using CLOB API format with token IDs
        // Token IDs must be obtained via REST API first
        json subscribe_msg = {
            {"type", "market"},
            {"assets_ids", {
                "101676997363687199724245607342877036148401850938023978421879460310389391082353",
                "4153292802911610701832309484716814274802943278345248636922528170020319407796"
                // Add more token IDs from REST API /markets endpoint
            }}
        };

        ws_.write(net::buffer(subscribe_msg.dump()));
    }

private:
    void start_read() {
        ws_.async_read(buffer_,
            beast::bind_front_handler(&PolymarketWebSocket::on_read,
                                     shared_from_this()));
    }

    void on_read(beast::error_code ec, std::size_t bytes_transferred) {
        if (ec) {
            handle_error(ec);
            return;
        }

        // Parse JSON message
        std::string message = beast::buffers_to_string(buffer_.data());
        json msg = json::parse(message);

        // Invoke callback with parsed data
        callback_(msg);

        // Clear buffer and continue reading
        buffer_.consume(buffer_.size());
        start_read();
    }

    void handle_error(beast::error_code ec) {
        if (ec == websocket::error::closed) {
            spdlog::info("WebSocket closed gracefully");
        } else {
            spdlog::error("WebSocket error: {}", ec.message());
            reconnect_with_backoff();
        }
    }

    void reconnect_with_backoff() {
        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        static int retry_count = 0;
        int delay = std::min(30, (int)std::pow(2, retry_count));

        spdlog::warn("Reconnecting in {} seconds (attempt {})",
                     delay, retry_count + 1);

        net::steady_timer timer(ioc_, std::chrono::seconds(delay));
        timer.async_wait([this](beast::error_code ec) {
            if (!ec) connect();
        });

        retry_count = std::min(retry_count + 1, 5);
    }
};
```

### Message Format

**Book Message (Order Book Snapshot)**:
```json
{
  "event_type": "book",
  "asset_id": "101676997363687199724245607342877036148401850938023978421879460310389391082353",
  "market": "0xaf9d0e448129a9f657f851d49495ba4742055d80e0ef1166ba0ee81d4d594214",
  "bids": [
    {"price": "0.953", "size": "1729.38"},
    {"price": "0.952", "size": "500.00"}
  ],
  "asks": [
    {"price": "0.955", "size": "2000.00"},
    {"price": "0.956", "size": "1500.00"}
  ],
  "timestamp": "1771050149008",
  "hash": "c86831e697fe0ce2256f76b502950ff2039fa53a"
}
```

**Price Change Message (Incremental Update)**:
```json
{
  "event_type": "price_change",
  "market": "0xaf9d0e448129a9f657f851d49495ba4742055d80e0ef1166ba0ee81d4d594214",
  "price_changes": [{
    "asset_id": "4153292802911610701832309484716814274802943278345248636922528170020319407796",
    "price": "0.914",
    "size": "938",
    "side": "BUY",
    "hash": "9b1c7951ae5cdb17ac0715a3d5c2c4f064227dde",
    "best_bid": "0.953",
    "best_ask": "0.955"
  }],
  "timestamp": "1771050149370"
}
```

**Data Extraction**:
```c++
void process_polymarket_update(const json& msg) {
    if (!msg.contains("event_type")) return;

    std::string event_type = msg["event_type"];

    if (event_type == "book") {
        // Full order book snapshot
        MarketDataUpdate update;
        update.source = "polymarket";
        update.timestamp = std::chrono::system_clock::now();
        update.asset_id = msg.value("asset_id", "");
        update.market_id = msg.value("market", "");

        if (msg.contains("bids") && !msg["bids"].empty()) {
            update.bid = std::stod(msg["bids"][0]["price"].get<std::string>());
            update.bid_size = std::stod(msg["bids"][0]["size"].get<std::string>());
        }
        if (msg.contains("asks") && !msg["asks"].empty()) {
            update.ask = std::stod(msg["asks"][0]["price"].get<std::string>());
            update.ask_size = std::stod(msg["asks"][0]["size"].get<std::string>());
        }

        event_bus_.publish(update);

    } else if (event_type == "price_change") {
        // Incremental price update
        auto price_change = msg["price_changes"][0];

        MarketDataUpdate update;
        update.source = "polymarket";
        update.timestamp = std::chrono::system_clock::now();
        update.asset_id = price_change.value("asset_id", "");
        update.market_id = msg.value("market", "");
        update.price = std::stod(price_change.value("price", "0"));

        if (price_change.contains("best_bid")) {
            update.bid = std::stod(price_change["best_bid"].get<std::string>());
        }
        if (price_change.contains("best_ask")) {
            update.ask = std::stod(price_change["best_ask"].get<std::string>());
        }

        event_bus_.publish(update);
    }
}
```

### REST API (Market Metadata)

Used for initialization and validation:

```c++
#include <curl/curl.h>

class PolymarketREST {
public:
    std::vector<Market> fetch_active_markets() {
        CURL* curl = curl_easy_init();
        std::string url = "https://gamma-api.polymarket.com/markets?active=true";

        // Set options
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);

        std::string response;
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

        // Execute request
        CURLcode res = curl_easy_perform(curl);
        curl_easy_cleanup(curl);

        // Parse JSON response
        json markets = json::parse(response);

        std::vector<Market> result;
        for (const auto& m : markets) {
            if (is_mag7_related(m["question"])) {
                result.push_back(parse_market(m));
            }
        }

        return result;
    }

private:
    static size_t write_callback(void* contents, size_t size,
                                 size_t nmemb, void* userp) {
        ((std::string*)userp)->append((char*)contents, size * nmemb);
        return size * nmemb;
    }

    bool is_mag7_related(const std::string& question) {
        static const std::vector<std::string> tickers = {
            "AAPL", "NVDA", "MSFT", "AMZN", "TSLA", "META", "GOOGL"
        };

        return std::any_of(tickers.begin(), tickers.end(),
            [&](const std::string& ticker) {
                return question.find(ticker) != std::string::npos;
            });
    }
};
```

---

## IBKR Integration

### Overview

IBKR provides the TWS API (Trader Workstation API) via:
- **IB Gateway**: Headless Java application
- **TWS Desktop**: Full GUI application

**Connection**: TCP socket (localhost:4002 for paper trading, 4001 for live)

### Installation & Setup

```bash
# Download IB Gateway (Linux)
wget https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/ibgateway-latest-standalone-linux-x64.sh

# Install
chmod +x ibgateway-latest-standalone-linux-x64.sh
./ibgateway-latest-standalone-linux-x64.sh -q

# Configure headless mode
echo "IBC_INI=/path/to/config.ini" >> ~/.bashrc
```

**config.ini** (IBC configuration):
```ini
IbLoginId=YOUR_USERNAME
IbPassword=YOUR_PASSWORD
TradingMode=paper
AcceptIncomingConnectionAction=accept
AcceptNonBrokerageAccountWarning=yes
```

### C++ Client Implementation

```c++
#include "EWrapper.h"
#include "EClientSocket.h"
#include <memory>

class IBKRAdapter : public EWrapper {
private:
    std::unique_ptr<EClientSocket> client_;
    EventBus& event_bus_;
    int next_request_id_ = 0;

public:
    IBKRAdapter(EventBus& bus)
        : event_bus_(bus),
          client_(std::make_unique<EClientSocket>(this, &signal_)) {}

    // Connection
    bool connect() {
        bool success = client_->eConnect("127.0.0.1", 4002, 0);
        if (!success) {
            spdlog::error("Failed to connect to IBKR Gateway");
            return false;
        }

        // Start message processing thread
        std::thread([this]() { client_->run(); }).detach();

        spdlog::info("Connected to IBKR Gateway");
        return true;
    }

    // Request option chain
    void request_option_chain(const std::string& underlying) {
        Contract contract;
        contract.symbol = underlying;
        contract.secType = "OPT";
        contract.exchange = "SMART";
        contract.currency = "USD";

        client_->reqContractDetails(++next_request_id_, contract);
    }

    // Request market data (Greeks)
    void request_market_data(int contract_id, const Contract& contract) {
        client_->reqMktData(contract_id, contract,
                           "100,101,104,105,106", // Bid, Ask, IV, Delta, Gamma
                           false, false, TagValueListSPtr());
    }

    // Place order
    void place_limit_order(int order_id, const Contract& contract,
                          const std::string& action, int quantity,
                          double limit_price) {
        Order order;
        order.action = action; // "BUY" or "SELL"
        order.orderType = "LMT";
        order.totalQuantity = quantity;
        order.lmtPrice = limit_price;
        order.tif = "DAY";

        client_->placeOrder(order_id, contract, order);
    }

    // EWrapper callbacks
    void tickPrice(TickerId tickerId, TickType field, double price,
                   const TickAttrib& attrib) override {
        MarketDataUpdate update;
        update.contract_id = tickerId;

        switch (field) {
            case BID:
                update.bid = price;
                break;
            case ASK:
                update.ask = price;
                break;
            case LAST:
                update.last = price;
                break;
        }

        event_bus_.publish(update);
    }

    void tickOptionComputation(TickerId tickerId, TickType tickType,
                              int tickAttrib, double impliedVol,
                              double delta, double optPrice,
                              double pvDividend, double gamma,
                              double vega, double theta,
                              double undPrice) override {
        GreeksUpdate update{
            .contract_id = tickerId,
            .implied_vol = impliedVol,
            .delta = delta,
            .gamma = gamma,
            .vega = vega,
            .theta = theta,
            .underlying_price = undPrice
        };

        event_bus_.publish(update);
    }

    void orderStatus(OrderId orderId, const std::string& status,
                    double filled, double remaining,
                    double avgFillPrice, int permId, int parentId,
                    double lastFillPrice, int clientId,
                    const std::string& whyHeld, double mktCapPrice) override {
        OrderUpdate update{
            .order_id = orderId,
            .status = status,
            .filled_qty = (int)filled,
            .remaining_qty = (int)remaining,
            .avg_fill_price = avgFillPrice
        };

        event_bus_.publish(update);

        if (status == "Filled") {
            spdlog::info("Order {} filled: {} @ ${}",
                        orderId, filled, avgFillPrice);
        }
    }

    void error(int id, int errorCode, const std::string& errorString,
              const std::string& advancedOrderRejectJson) override {
        if (errorCode == 502) {
            spdlog::warn("Disconnected from IBKR Gateway, reconnecting...");
            reconnect();
        } else if (errorCode >= 2000) {
            // System messages (not errors)
            spdlog::debug("IBKR system message: {}", errorString);
        } else {
            spdlog::error("IBKR error {}: {}", errorCode, errorString);
        }
    }

private:
    void reconnect() {
        client_->eDisconnect();
        std::this_thread::sleep_for(std::chrono::seconds(5));
        connect();
    }

    EReaderOSSignal signal_;
};
```

### Contract Definition Helper

```c++
Contract create_option_contract(const std::string& underlying,
                               const std::string& expiry, // "20251219"
                               double strike,
                               const std::string& right) { // "C" or "P"
    Contract contract;
    contract.symbol = underlying;
    contract.secType = "OPT";
    contract.exchange = "SMART";
    contract.currency = "USD";
    contract.lastTradeDateOrContractMonth = expiry;
    contract.strike = strike;
    contract.right = right;
    contract.multiplier = "100";

    return contract;
}

// Example usage
Contract nvda_call = create_option_contract("NVDA", "20251219", 520.0, "C");
```

---

## Connection Management

### Unified Connection Monitor

```c++
class ConnectionMonitor {
private:
    std::atomic<bool> polymarket_connected_{false};
    std::atomic<bool> ibkr_connected_{false};
    std::chrono::steady_clock::time_point last_polymarket_update_;
    std::chrono::steady_clock::time_point last_ibkr_update_;

public:
    void start_monitoring() {
        std::thread([this]() {
            while (true) {
                check_connection_health();
                std::this_thread::sleep_for(std::chrono::seconds(5));
            }
        }).detach();
    }

    void check_connection_health() {
        auto now = std::chrono::steady_clock::now();

        // Polymarket check
        auto poly_elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            now - last_polymarket_update_).count();

        if (poly_elapsed > 30) {
            spdlog::warn("No Polymarket updates for {} seconds", poly_elapsed);
            polymarket_connected_ = false;

            if (poly_elapsed > 60) {
                trigger_kill_switch("Polymarket feed lost");
            }
        }

        // IBKR check
        auto ibkr_elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            now - last_ibkr_update_).count();

        if (ibkr_elapsed > 15) {
            spdlog::warn("No IBKR updates for {} seconds", ibkr_elapsed);
            ibkr_connected_ = false;

            if (ibkr_elapsed > 30) {
                trigger_kill_switch("IBKR feed lost");
            }
        }
    }

    void on_polymarket_update() {
        last_polymarket_update_ = std::chrono::steady_clock::now();
        polymarket_connected_ = true;
    }

    void on_ibkr_update() {
        last_ibkr_update_ = std::chrono::steady_clock::now();
        ibkr_connected_ = true;
    }

    bool all_connected() const {
        return polymarket_connected_ && ibkr_connected_;
    }

private:
    void trigger_kill_switch(const std::string& reason) {
        spdlog::critical("KILL SWITCH TRIGGERED: {}", reason);
        // Halt new orders, begin position flattening
        RiskManager::instance().halt_trading();
    }
};
```

---

## Error Handling

### Polymarket Specific Errors

| Error | Code | Handling |
|-------|------|----------|
| Rate limit exceeded | 429 | Backoff 60s, reduce subscription count |
| Invalid market ID | 404 | Remove from watch list, log warning |
| WebSocket disconnect | N/A | Exponential backoff reconnect (max 30s) |
| Malformed JSON | N/A | Log error, skip message, continue |

### IBKR Specific Errors

| Error Code | Meaning | Handling |
|------------|---------|----------|
| 502 | Disconnected | Auto-reconnect with 5s delay |
| 110 | Price does not conform to minimum price variation | Reprice to tick size |
| 201 | Order rejected | Log, alert, do not retry |
| 321 | Error validating request | Check contract definition |
| 2104 | Market data farm connected | Resume trading |
| 2110 | Connectivity between TWS and server is broken | Wait for reconnect |

**Reconnection Logic**:
```c++
void handle_ibkr_error(int error_code, const std::string& message) {
    switch (error_code) {
        case 502: // Disconnected
            schedule_reconnect(5);
            break;
        case 110: // Price increment violation
            reprice_to_tick_size();
            break;
        case 201: // Order rejected
            log_rejection(message);
            alert_operator();
            break;
        default:
            if (error_code >= 2000) {
                // Informational message
                spdlog::debug("IBKR info: {}", message);
            } else {
                spdlog::error("IBKR error {}: {}", error_code, message);
            }
    }
}
```

---

## Rate Limits

### Polymarket

- **WebSocket**: No explicit limit, but throttle subscriptions to <100 markets
- **REST API**: 100 requests/minute per IP
- **Best Practice**: Cache market metadata, use WebSocket for real-time data

### IBKR

- **Market Data**: 100 simultaneous subscriptions per account
- **Orders**: 50 orders/second (paper trading: 10/second)
- **Historical Data**: 60 requests/600 seconds

**Rate Limiter Implementation**:
```c++
class RateLimiter {
private:
    std::deque<std::chrono::steady_clock::time_point> requests_;
    int max_requests_;
    std::chrono::seconds window_;
    std::mutex mutex_;

public:
    RateLimiter(int max_requests, std::chrono::seconds window)
        : max_requests_(max_requests), window_(window) {}

    bool allow_request() {
        std::lock_guard<std::mutex> lock(mutex_);
        auto now = std::chrono::steady_clock::now();

        // Remove old requests outside window
        while (!requests_.empty() &&
               (now - requests_.front()) > window_) {
            requests_.pop_front();
        }

        if (requests_.size() < max_requests_) {
            requests_.push_back(now);
            return true;
        }

        return false;
    }
};

// Usage
RateLimiter ibkr_limiter(50, std::chrono::seconds(1));

if (ibkr_limiter.allow_request()) {
    place_order(order);
} else {
    queue_order_for_retry(order);
}
```

---

## Testing

### Mock Polymarket WebSocket

```python
# tests/mock_polymarket_server.py
import asyncio
import websockets
import json

async def mock_polymarket(websocket, path):
    """Simulates Polymarket WebSocket for testing"""
    while True:
        # Send mock probability update
        msg = {
            "event_ticker": "NVDA-Q4-2025-REVENUE-BEAT",
            "market_id": "0xtest",
            "outcome": "YES",
            "price": 0.75,
            "volume_24h": 100000.0,
            "timestamp": "2025-02-13T14:30:00.000Z"
        }
        await websocket.send(json.dumps(msg))
        await asyncio.sleep(1)

start_server = websockets.serve(mock_polymarket, "localhost", 8765)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
```

### IBKR Paper Trading Validation

```bash
# tests/validate_ibkr_connection.sh
#!/bin/bash

# 1. Check Gateway is running
if ! pgrep -f "ibgateway" > /dev/null; then
    echo "ERROR: IB Gateway not running"
    exit 1
fi

# 2. Check port is listening
if ! netstat -tuln | grep ":4002" > /dev/null; then
    echo "ERROR: Port 4002 not listening"
    exit 1
fi

# 3. Run connection test
./build/tests/test_ibkr_connection

echo "✅ IBKR connection validated"
```

---

**See Also**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - Event bus integration
- [TRADING_STRATEGY.md](TRADING_STRATEGY.md) - How data flows into strategy
- [STRESS_TESTING.md](STRESS_TESTING.md) - Connection failure scenarios
