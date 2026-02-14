#pragma once

#include "polyquant/core/EventBus.h"
#include "polyquant/core/MarketData.h"
#include <unordered_map>
#include <mutex>
#include <memory>
#include <spdlog/spdlog.h>

namespace polyquant {

struct MarketSnapshot {
    std::string ticker;
    long contract_id;

    // Merged Data
    double poly_prob = 0.0;
    double poly_prob_change_24h = 0.0;
    double poly_volume_usd = 0.0;

    double opt_bid = 0.0;
    double opt_ask = 0.0;
    double opt_last = 0.0;
    int opt_volume = 0;
    int opt_open_interest = 0;

    double opt_iv = 0.0;
    double opt_delta = 0.0;
    double opt_gamma = 0.0;
    double opt_vega = 0.0;
    double opt_theta = 0.0;

    // Derived
    double spread_pct = 0.0;

    std::chrono::system_clock::time_point last_update;
};

class MarketDataAggregator {
public:
    MarketDataAggregator(std::shared_ptr<EventBus> event_bus);

    // Thread-safe access to snapshot
    std::optional<MarketSnapshot> get_snapshot(long contract_id);

private:
    void on_market_data_update(const MarketDataUpdate& update);

    std::shared_ptr<EventBus> event_bus_;
    std::unordered_map<long, MarketSnapshot> snapshots_;
    std::mutex mutex_;
};

} // namespace polyquant
