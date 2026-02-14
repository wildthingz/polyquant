#include "polyquant/core/StrategyEngine.h"

namespace polyquant {

StrategyEngine::StrategyEngine(std::shared_ptr<EventBus> event_bus, std::shared_ptr<MarketDataAggregator> aggregator)
    : event_bus_(event_bus), aggregator_(aggregator) {}

void StrategyEngine::start() {
    running_ = true;
    spdlog::info("Strategy Engine started");

    // In a real implementation, we might poll the aggregator or subscribe to specific events.
    // For now, we hook into the EventBus to react to every market data update.

    event_bus_->subscribe([this](const MarketDataUpdate& update) {
        if (!running_) return;

        // Query the full snapshot for this contract
        auto snapshot_opt = aggregator_->get_snapshot(update.contract_id);
        if (snapshot_opt) {
            Signal signal = evaluate_entry(*snapshot_opt);
            if (signal.decision != "HOLD") {
                spdlog::info("SIGNAL GENERATED: {} {} (Strength: {:.2f}) - {}",
                             signal.decision, signal.ticker, signal.signal_strength, signal.reason);
                // TODO: Publish Signal event
            }
        }
    });
}

Signal StrategyEngine::evaluate_entry(const MarketSnapshot& snapshot) {
    Signal signal;
    signal.ticker = snapshot.ticker;
    signal.contract_id = snapshot.contract_id;
    signal.timestamp = std::chrono::system_clock::now();
    signal.decision = "HOLD";
    signal.signal_strength = 0.0;

    // 1. Check Polymarket Sentiment
    if (snapshot.poly_prob > 0.80) {
        signal.signal_strength = snapshot.poly_prob;

        // 2. Check Liquidity (Spread)
        if (snapshot.opt_bid > 0 && snapshot.spread_pct > 0.05) {
            signal.reason = "High sentiment but spread too wide (>5%)";
            return signal;
        }

        // 3. Generate Signal
        signal.decision = "BUY";
        signal.reason = fmt::format("High certainty ({:.2f}%), potential IV crush", snapshot.poly_prob * 100);
    }

    return signal;
}

} // namespace polyquant
