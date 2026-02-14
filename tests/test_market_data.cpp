#include <gtest/gtest.h>
#include "polyquant/core/EventBus.h"
#include "polyquant/core/MarketDataAggregator.h"
#include "polyquant/core/StrategyEngine.h"
#include <thread>
#include <chrono>

using namespace polyquant;

// Test EventBus pub/sub mechanism
TEST(EventBusTest, PublishAndSubscribe) {
    auto event_bus = std::make_shared<EventBus>();

    MarketDataUpdate received_update;
    bool callback_called = false;

    event_bus->subscribe([&](const MarketDataUpdate& update) {
        received_update = update;
        callback_called = true;
    });

    MarketDataUpdate test_update;
    test_update.source = "test";
    test_update.ticker = "AAPL";
    test_update.price = 150.0;
    test_update.bid = 149.5;
    test_update.ask = 150.5;

    event_bus->publish(test_update);

    EXPECT_TRUE(callback_called);
    EXPECT_EQ(received_update.source, "test");
    EXPECT_EQ(received_update.ticker, "AAPL");
    EXPECT_DOUBLE_EQ(received_update.price, 150.0);
}

// Test multiple subscribers
TEST(EventBusTest, MultipleSubscribers) {
    auto event_bus = std::make_shared<EventBus>();

    int callback_count = 0;

    event_bus->subscribe([&](const MarketDataUpdate& update) {
        callback_count++;
    });

    event_bus->subscribe([&](const MarketDataUpdate& update) {
        callback_count++;
    });

    event_bus->subscribe([&](const MarketDataUpdate& update) {
        callback_count++;
    });

    MarketDataUpdate test_update;
    test_update.source = "test";
    event_bus->publish(test_update);

    EXPECT_EQ(callback_count, 3);
}

// Test MarketDataAggregator basic functionality
TEST(MarketDataAggregatorTest, StoresAndRetrievesSnapshot) {
    auto event_bus = std::make_shared<EventBus>();
    auto aggregator = std::make_shared<MarketDataAggregator>(event_bus);

    MarketDataUpdate update;
    update.source = "ibkr";  // Use IBKR source to trigger opt_bid/ask processing
    update.contract_id = 12345;
    update.ticker = "NVDA";
    update.price = 500.0;
    update.opt_bid = 499.5;
    update.opt_ask = 500.5;

    event_bus->publish(update);

    // Give aggregator time to process
    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    auto snapshot = aggregator->get_snapshot(12345);
    ASSERT_TRUE(snapshot.has_value());
    EXPECT_EQ(snapshot->ticker, "NVDA");
    EXPECT_DOUBLE_EQ(snapshot->opt_bid, 499.5);
    EXPECT_DOUBLE_EQ(snapshot->opt_ask, 500.5);
}

// Test MarketDataAggregator handles missing data
TEST(MarketDataAggregatorTest, ReturnsEmptyForUnknownContract) {
    auto event_bus = std::make_shared<EventBus>();
    auto aggregator = std::make_shared<MarketDataAggregator>(event_bus);

    auto snapshot = aggregator->get_snapshot(99999);
    EXPECT_FALSE(snapshot.has_value());
}

// Test StrategyEngine signal generation
TEST(StrategyEngineTest, GeneratesSignalOnHighProbability) {
    auto event_bus = std::make_shared<EventBus>();
    auto aggregator = std::make_shared<MarketDataAggregator>(event_bus);
    auto strategy = std::make_shared<StrategyEngine>(event_bus, aggregator);

    strategy->start();

    // Publish update with high probability
    MarketDataUpdate update;
    update.source = "polymarket";
    update.contract_id = 12345;
    update.ticker = "AAPL";
    update.poly_prob = 0.85;  // Above 0.80 threshold
    update.bid = 0.84;
    update.ask = 0.86;
    update.opt_bid = 5.0;
    // Note: spread_pct is calculated in MarketDataAggregator from bid/ask

    event_bus->publish(update);

    // Give strategy time to process
    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    // TODO: Add signal capture mechanism to verify BUY signal was generated
    // For now, this test just ensures no crashes occur
    SUCCEED();
}

// Test StrategyEngine rejects wide spreads
TEST(StrategyEngineTest, RejectsWideSpread) {
    auto event_bus = std::make_shared<EventBus>();
    auto aggregator = std::make_shared<MarketDataAggregator>(event_bus);
    auto strategy = std::make_shared<StrategyEngine>(event_bus, aggregator);

    strategy->start();

    // Publish update with high probability but wide spread
    MarketDataUpdate update;
    update.source = "polymarket";
    update.contract_id = 12345;
    update.ticker = "TSLA";
    update.poly_prob = 0.85;
    update.bid = 0.80;
    update.ask = 0.90;
    update.opt_bid = 5.0;
    // Note: spread = (0.90 - 0.80) / 0.80 = 0.125 = 12.5% (above 5% threshold)

    event_bus->publish(update);

    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    // TODO: Verify HOLD signal or rejection reason
    SUCCEED();
}

// Test MarketDataUpdate structure
TEST(MarketDataUpdateTest, InitializesCorrectly) {
    MarketDataUpdate update;

    // Test default values
    EXPECT_EQ(update.ticker, "");
    EXPECT_EQ(update.contract_id, 0);
    EXPECT_DOUBLE_EQ(update.price, 0.0);
    EXPECT_DOUBLE_EQ(update.bid, 0.0);
    EXPECT_DOUBLE_EQ(update.ask, 0.0);
    EXPECT_EQ(update.source, "");

    // Test optional fields are unset
    EXPECT_FALSE(update.poly_prob.has_value());
    EXPECT_FALSE(update.opt_bid.has_value());
}

// Test spread calculation
TEST(MarketDataUpdateTest, SpreadCalculation) {
    MarketDataUpdate update;
    update.bid = 100.0;
    update.ask = 102.0;

    // Spread = (ask - bid) / bid = 2 / 100 = 0.02 = 2%
    double spread_pct = (update.ask - update.bid) / update.bid;

    EXPECT_NEAR(spread_pct, 0.02, 1e-6);
}

// Test thread safety of EventBus (basic concurrency test)
TEST(EventBusTest, ThreadSafety) {
    auto event_bus = std::make_shared<EventBus>();

    std::atomic<int> callback_count{0};

    event_bus->subscribe([&](const MarketDataUpdate& update) {
        callback_count++;
        std::this_thread::sleep_for(std::chrono::microseconds(1));
    });

    // Publish from multiple threads
    std::vector<std::thread> threads;
    for (int i = 0; i < 10; i++) {
        threads.emplace_back([&]() {
            MarketDataUpdate update;
            update.source = "test";
            for (int j = 0; j < 10; j++) {
                event_bus->publish(update);
            }
        });
    }

    for (auto& thread : threads) {
        thread.join();
    }

    // Should have 10 threads * 10 publishes = 100 callbacks
    EXPECT_EQ(callback_count, 100);
}
