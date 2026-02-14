#include "polyquant/core/MarketDataAggregator.h"

namespace polyquant {

MarketDataAggregator::MarketDataAggregator(std::shared_ptr<EventBus> event_bus)
    : event_bus_(event_bus) {

    // Subscribe to market data updates
    event_bus_->subscribe([this](const MarketDataUpdate& update) {
        this->on_market_data_update(update);
    });
}

std::optional<MarketSnapshot> MarketDataAggregator::get_snapshot(long contract_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = snapshots_.find(contract_id);
    if (it != snapshots_.end()) {
        return it->second;
    }
    return std::nullopt;
}

void MarketDataAggregator::on_market_data_update(const MarketDataUpdate& update) {
    std::lock_guard<std::mutex> lock(mutex_);

    // Get or create snapshot
    auto& snapshot = snapshots_[update.contract_id];
    snapshot.contract_id = update.contract_id;
    if (!update.ticker.empty()) {
        snapshot.ticker = update.ticker;
    }
    snapshot.last_update = update.timestamp;

    // Merge Data
    if (update.source == "polymarket") {
        if (update.poly_prob) snapshot.poly_prob = *update.poly_prob;
        if (update.poly_prob_change_24h) snapshot.poly_prob_change_24h = *update.poly_prob_change_24h;
        if (update.poly_volume_usd) snapshot.poly_volume_usd = *update.poly_volume_usd;
    }
    else if (update.source == "ibkr") {
        if (update.opt_bid) snapshot.opt_bid = *update.opt_bid;
        if (update.opt_ask) snapshot.opt_ask = *update.opt_ask;
        if (update.opt_last) snapshot.opt_last = *update.opt_last;
        if (update.opt_volume) snapshot.opt_volume = *update.opt_volume;
        if (update.opt_open_interest) snapshot.opt_open_interest = *update.opt_open_interest;

        if (update.opt_iv) snapshot.opt_iv = *update.opt_iv;
        if (update.opt_delta) snapshot.opt_delta = *update.opt_delta;
        if (update.opt_gamma) snapshot.opt_gamma = *update.opt_gamma;
        if (update.opt_vega) snapshot.opt_vega = *update.opt_vega;
        if (update.opt_theta) snapshot.opt_theta = *update.opt_theta;

        // Calculate Derived Metrics
        if (snapshot.opt_bid > 0 && snapshot.opt_ask > 0) {
            double mid = (snapshot.opt_bid + snapshot.opt_ask) / 2.0;
            snapshot.spread_pct = (snapshot.opt_ask - snapshot.opt_bid) / mid;
        }
    }

    // Log significant updates (e.g., every 100th update or on specific condition)
    // spdlog::debug("Updated snapshot for contract {}: Price={}", snapshot.contract_id, snapshot.opt_last);
}

} // namespace polyquant
