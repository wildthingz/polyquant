#pragma once

#include "polyquant/core/EventBus.h"
#include "polyquant/core/MarketDataAggregator.h"
#include <memory>
#include <spdlog/spdlog.h>

namespace polyquant {

struct Signal {
    std::string ticker;
    long contract_id;
    double signal_strength; // 0.0 to 1.0
    std::string decision;   // "BUY", "SELL", "HOLD"
    std::string reason;
    std::chrono::system_clock::time_point timestamp;
};

class StrategyEngine {
public:
    StrategyEngine(std::shared_ptr<EventBus> event_bus, std::shared_ptr<MarketDataAggregator> aggregator);

    void start();

private:
    void on_market_snapshot_update(const MarketSnapshot& snapshot);
    Signal evaluate_entry(const MarketSnapshot& snapshot);

    std::shared_ptr<EventBus> event_bus_;
    std::shared_ptr<MarketDataAggregator> aggregator_;
    bool running_ = false;
};

} // namespace polyquant
