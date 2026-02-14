#pragma once

#include <string>
#include <chrono>
#include <optional>

namespace polyquant {

struct MarketDataUpdate {
    std::string ticker;           // e.g., "NVDA"
    long contract_id = 0;         // IBKR Contract ID (0 for Polymarket-only updates)

    // Polymarket-specific fields
    std::string asset_id;         // Polymarket asset/token ID
    std::string market_id;        // Polymarket market/condition ID
    double price = 0.0;           // Current price
    double bid = 0.0;             // Best bid
    double ask = 0.0;             // Best ask
    double bid_size = 0.0;        // Bid size
    double ask_size = 0.0;        // Ask size

    // Polymarket Data
    std::optional<double> poly_prob;
    std::optional<double> poly_prob_change_24h;
    std::optional<double> poly_volume_usd;

    // Option Data (IBKR)
    std::optional<double> opt_bid;
    std::optional<double> opt_ask;
    std::optional<double> opt_last;
    std::optional<int> opt_volume;
    std::optional<int> opt_open_interest;

    // Greeks
    std::optional<double> opt_delta;
    std::optional<double> opt_gamma;
    std::optional<double> opt_vega;
    std::optional<double> opt_theta;
    std::optional<double> opt_iv;

    // Metadata
    std::chrono::system_clock::time_point timestamp;
    std::string source; // "polymarket" or "ibkr"
};

} // namespace polyquant
