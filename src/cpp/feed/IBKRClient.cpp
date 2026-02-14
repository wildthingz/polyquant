#include "polyquant/feed/IBKRClient.h"
#include <spdlog/spdlog.h>
#include <chrono>

namespace polyquant {
namespace feed {

IBKRClient::IBKRClient(std::shared_ptr<EventBus> event_bus)
    : event_bus_(event_bus),
      signal_(2000), // Timeout in ms
      client_(std::make_unique<EClientSocket>(this, &signal_)) {}

IBKRClient::~IBKRClient() {
    disconnect();
}

bool IBKRClient::connect(const std::string& host, int port, int client_id) {
    std::lock_guard<std::mutex> lock(mutex_);

    if (is_connected_) {
        spdlog::warn("IBKR Client already connected");
        return true;
    }

    spdlog::info("Connecting to IBKR Gateway at {}:{}", host, port);

    bool success = client_->eConnect(host.c_str(), port, client_id);

    if (success) {
        // Start EReader thread
        reader_ = std::make_unique<EReader>(client_.get(), &signal_);
        reader_->start();

        is_connected_ = true;

        // Start processing thread
        reader_thread_ = std::thread(&IBKRClient::process_messages, this);

        spdlog::info("Successfully connected to IBKR Gateway");
        return true;
    } else {
        spdlog::error("Failed to connect to IBKR Gateway");
        return false;
    }
}

void IBKRClient::disconnect() {
    std::lock_guard<std::mutex> lock(mutex_);

    if (is_connected_) {
        is_connected_ = false;
        client_->eDisconnect();

        if (reader_thread_.joinable()) {
            reader_thread_.join();
        }

        spdlog::info("Disconnected from IBKR Gateway");
    }
}

bool IBKRClient::is_connected() const {
    return is_connected_;
}

void IBKRClient::process_messages() {
    while (is_connected_) {
        signal_.waitForSignal();
        reader_->processMsgs();
    }
}

void IBKRClient::request_market_data(int req_id, const std::string& symbol, const std::string& sec_type, const std::string& exchange, const std::string& currency) {
    Contract contract;
    contract.symbol = symbol;
    contract.secType = sec_type;
    contract.exchange = exchange;
    contract.currency = currency;

    // Generic ticks: 100 (Option Volume), 101 (Option Open Interest), 104 (Hist Vol), 106 (Option Implied Vol)
    client_->reqMktData(req_id, contract, "100,101,104,106", false, false, TagValueListSPtr());
}

// EWrapper Callbacks

void IBKRClient::connectAck() {
    spdlog::info("IBKR Connection Acknowledged");
}

void IBKRClient::nextValidId(OrderId orderId) {
    spdlog::info("Next Valid Order ID: {}", orderId);
}

void IBKRClient::error(int id, int errorCode, const std::string& errorString) {
    if (id == -1 && errorCode == 502) {
        spdlog::error("IBKR Connection Error: {}", errorString);
        // Handle reconnection logic here if needed
    } else if (errorCode >= 2000) {
        spdlog::info("IBKR Info ({}): {}", errorCode, errorString);
    } else {
        spdlog::error("IBKR Error (Id: {}, Code: {}): {}", id, errorCode, errorString);
    }
}

void IBKRClient::connectionClosed() {
    spdlog::warn("IBKR Connection Closed");
    is_connected_ = false;
}

void IBKRClient::tickPrice(TickerId tickerId, TickType field, double price, const TickAttrib& attrib) {
    MarketDataUpdate update;
    update.contract_id = tickerId;
    update.source = "ibkr";
    update.timestamp = std::chrono::system_clock::now();

    switch (field) {
        case BID:
            update.opt_bid = price;
            break;
        case ASK:
            update.opt_ask = price;
            break;
        case LAST:
            update.opt_last = price;
            break;
        default:
            return; // Ignore other price types for now
    }

    event_bus_->publish(update);
}

void IBKRClient::tickSize(TickerId tickerId, TickType field, int size) {
    MarketDataUpdate update;
    update.contract_id = tickerId;
    update.source = "ibkr";
    update.timestamp = std::chrono::system_clock::now();

    switch (field) {
        case BID_SIZE:
            // update.bid_size = size;
            break;
        case ASK_SIZE:
            // update.ask_size = size;
            break;
        case VOLUME:
            update.opt_volume = size;
            event_bus_->publish(update);
            break;
        case OPTION_CALL_OPEN_INTEREST:
        case OPTION_PUT_OPEN_INTEREST:
            update.opt_open_interest = size;
            event_bus_->publish(update);
            break;
        default:
            break;
    }
}

void IBKRClient::tickOptionComputation(TickerId tickerId, TickType tickType, double impliedVol, double delta, double optPrice, double pvDividend, double gamma, double vega, double theta, double undPrice) {
    // Filter out invalid values (IBKR sends -1 or -2 for invalid)
    if (impliedVol < 0 || delta == -2) return;

    MarketDataUpdate update;
    update.contract_id = tickerId;
    update.source = "ibkr";
    update.timestamp = std::chrono::system_clock::now();

    update.opt_iv = impliedVol;
    update.opt_delta = delta;
    update.opt_gamma = gamma;
    update.opt_vega = vega;
    update.opt_theta = theta;

    // Also provides underlying price
    // update.underlying_price = undPrice;

    event_bus_->publish(update);
}

void IBKRClient::orderStatus(OrderId orderId, const std::string& status, double filled, double remaining, double avgFillPrice, int permId, int parentId, double lastFillPrice, int clientId, const std::string& whyHeld, double mktCapPrice) {
    spdlog::info("Order Status - Id: {}, Status: {}, Filled: {}, AvgPrice: {}", orderId, status, filled, avgFillPrice);

    // In a real implementation, we would publish an OrderUpdate event here
}

} // namespace feed
} // namespace polyquant
