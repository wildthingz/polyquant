#pragma once

#include "MarketData.h"
#include <functional>
#include <vector>
#include <mutex>
#include <memory>

namespace polyquant {

class EventBus {
public:
    using MarketDataCallback = std::function<void(const MarketDataUpdate&)>;

    void subscribe(MarketDataCallback callback) {
        std::lock_guard<std::mutex> lock(mutex_);
        subscribers_.push_back(callback);
    }

    void publish(const MarketDataUpdate& update) {
        std::lock_guard<std::mutex> lock(mutex_);
        for (const auto& callback : subscribers_) {
            callback(update);
        }
    }

private:
    std::vector<MarketDataCallback> subscribers_;
    std::mutex mutex_;
};

} // namespace polyquant
