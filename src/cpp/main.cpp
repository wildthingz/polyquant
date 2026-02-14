#include <iostream>
#include <fstream>
#include <sstream>
#include <spdlog/spdlog.h>
#include <pqxx/pqxx>
#include <cstdlib>
#include <thread>
#include <chrono>
#include <filesystem>
#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>
#include "polyquant/core/EventBus.h"
#include "polyquant/core/MarketDataAggregator.h"
#include "polyquant/core/StrategyEngine.h"
#include "polyquant/feed/PolymarketClient.h"
#include "polyquant/feed/IBKRClient.h"

namespace fs = std::filesystem;

// Helper to load .env file
void load_env_file(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        spdlog::warn("Could not open env file: {}", path);
        return;
    }

    int count = 0;
    std::string line;
    while (std::getline(file, line)) {
        if (line.empty() || line[0] == '#') continue;

        size_t delimiter_pos = line.find('=');
        if (delimiter_pos != std::string::npos) {
            std::string key = line.substr(0, delimiter_pos);
            std::string value = line.substr(delimiter_pos + 1);

            // Remove trailing \r if present
            if (!value.empty() && value.back() == '\r') {
                value.pop_back();
            }

            // Only set if not already in environment
            if (std::getenv(key.c_str()) == nullptr) {
                setenv(key.c_str(), value.c_str(), 1);
                count++;
            }
        }
    }
    spdlog::info("Loaded {} environment variables from {}", count, path);
}

int main() {
    spdlog::info("PolyQuant Engine Starting...");

    // Environment variables are set by docker-compose.yml or .env file
    // Try to load .env only if it exists in the working directory (optional)
    if (fs::exists(".env")) {
        load_env_file(".env");
        spdlog::info("Loaded .env from working directory");
    } else if (fs::exists("/app/.env")) {
        load_env_file("/app/.env");
        spdlog::info("Loaded .env from /app");
    } else {
        spdlog::info("No .env file found, using container environment variables");
    }

    // 1. Initialize Event Bus
    auto event_bus = std::make_shared<polyquant::EventBus>();

    // 2. Initialize Market Data Aggregator
    auto aggregator = std::make_shared<polyquant::MarketDataAggregator>(event_bus);

    // 3. Initialize Strategy Engine
    auto strategy = std::make_shared<polyquant::StrategyEngine>(event_bus, aggregator);
    strategy->start();

    // 4. Initialize Database Connection
    try {
        const char* db_host = std::getenv("DB_HOST");
        const char* db_port = std::getenv("DB_PORT");
        const char* db_name = std::getenv("DB_NAME");
        const char* db_user = std::getenv("DB_USER");
        const char* db_pass = std::getenv("DB_PASSWORD");

        if (db_host && db_port && db_name && db_user && db_pass) {
            std::string db_conn_str = "host=" + std::string(db_host) +
                                      " port=" + std::string(db_port) +
                                      " dbname=" + std::string(db_name) +
                                      " user=" + std::string(db_user) +
                                      " password=" + std::string(db_pass);

            pqxx::connection c(db_conn_str);
            if (c.is_open()) {
                spdlog::info("Connected to database successfully: {}", c.dbname());
            } else {
                spdlog::error("Failed to connect to database");
            }
        } else {
            spdlog::warn("Database environment variables not set, skipping connection test.");
        }
    } catch (const std::exception &e) {
        spdlog::error("Database connection error: {}", e.what());
    }

    // 5. Initialize IBKR Client
    auto ibkr_client = std::make_shared<polyquant::feed::IBKRClient>(event_bus);

    const char* ibkr_host_env = std::getenv("IBKR_HOST");
    std::string ibkr_host = ibkr_host_env ? ibkr_host_env : "ib_gateway";
    int ibkr_port = 4002;
    int client_id = 123;

    // Connect to IB Gateway
    std::thread ibkr_thread([ibkr_client, ibkr_host, ibkr_port, client_id]() {
        // Retry logic
        for(int i=0; i<10; ++i) {
            spdlog::info("Attempting to connect to IBKR at {}:{} (Client ID: {})", ibkr_host, ibkr_port, client_id);
            if(ibkr_client->connect(ibkr_host, ibkr_port, client_id)) {
                break;
            }
            std::this_thread::sleep_for(std::chrono::seconds(5));
        }
    });
    ibkr_thread.detach();

    // 6. Initialize Polymarket Client
    boost::asio::io_context ioc;
    boost::asio::ssl::context ctx(boost::asio::ssl::context::tlsv12_client);
    ctx.set_default_verify_paths();

    auto poly_client = std::make_shared<polyquant::feed::PolymarketClient>(ioc, ctx, event_bus);
    poly_client->run("ws-subscriptions-clob.polymarket.com", "443");

    spdlog::info("System initialized. Starting event loop...");

    // 7. Run Event Loop
    try {
        ioc.run();
    } catch (const std::exception& e) {
        spdlog::error("Event loop error: {}", e.what());
    }

    return 0;
}
