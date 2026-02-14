#include "polyquant/feed/PolymarketClient.h"
#include <spdlog/spdlog.h>
#include <iostream>

namespace polyquant {
namespace feed {

PolymarketClient::PolymarketClient(net::io_context& ioc, ssl::context& ctx, std::shared_ptr<EventBus> event_bus)
    : ioc_(ioc),
      resolver_(net::make_strand(ioc)),
      ws_(net::make_strand(ioc), ctx),
      event_bus_(event_bus) {}

void PolymarketClient::run(const std::string& host, const std::string& port) {
    host_ = host;
    resolver_.async_resolve(
        host,
        port,
        beast::bind_front_handler(&PolymarketClient::on_resolve, shared_from_this()));
}

void PolymarketClient::on_resolve(beast::error_code ec, tcp::resolver::results_type results) {
    if (ec) {
        spdlog::error("Polymarket resolve failed: {}", ec.message());
        return;
    }

    beast::get_lowest_layer(ws_).expires_after(std::chrono::seconds(30));
    beast::get_lowest_layer(ws_).async_connect(
        results,
        beast::bind_front_handler(&PolymarketClient::on_connect, shared_from_this()));
}

void PolymarketClient::on_connect(beast::error_code ec, tcp::resolver::results_type::endpoint_type ep) {
    if (ec) {
        spdlog::error("Polymarket connect failed: {}", ec.message());
        return;
    }

    beast::get_lowest_layer(ws_).expires_after(std::chrono::seconds(30));

    // Set SNI Hostname (required for SSL)
    if (!SSL_set_tlsext_host_name(ws_.next_layer().native_handle(), host_.c_str())) {
        ec = beast::error_code(static_cast<int>(::ERR_get_error()), net::error::get_ssl_category());
        spdlog::error("Polymarket SNI failed: {}", ec.message());
        return;
    }

    ws_.next_layer().async_handshake(
        ssl::stream_base::client,
        beast::bind_front_handler(&PolymarketClient::on_ssl_handshake, shared_from_this()));
}

void PolymarketClient::on_ssl_handshake(beast::error_code ec) {
    if (ec) {
        spdlog::error("Polymarket SSL handshake failed: {}", ec.message());
        return;
    }

    beast::get_lowest_layer(ws_).expires_never();
    ws_.set_option(websocket::stream_base::timeout::suggested(beast::role_type::client));
    ws_.set_option(websocket::stream_base::decorator([](websocket::request_type& req) {
        req.set(http::field::user_agent, std::string(BOOST_BEAST_VERSION_STRING) + " polyquant-client");
    }));

    ws_.async_handshake(host_, "/ws/market",
        beast::bind_front_handler(&PolymarketClient::on_handshake, shared_from_this()));
}

void PolymarketClient::on_handshake(beast::error_code ec) {
    if (ec) {
        spdlog::error("Polymarket handshake failed: {}", ec.message());
        return;
    }

    spdlog::info("Connected to Polymarket WebSocket");

    // Send subscription message using correct Polymarket CLOB format
    // Format: {"type": "market", "assets_ids": ["token1", "token2"]}
    // For testing, subscribe to a few high-volume token IDs
    json subscribe_msg = {
        {"type", "market"},
        {"assets_ids", json::array({
            "101676997363687199724245607342877036148401850938023978421879460310389391082353",  // Sample token from earlier
            "4153292802911610701832309484716814274802943278345248636922528170020319407796"
        })}
    };

    std::string msg_str = subscribe_msg.dump();
    spdlog::info("Sending subscription: {}", msg_str);

    ws_.async_write(
        net::buffer(msg_str),
        beast::bind_front_handler(&PolymarketClient::on_write, shared_from_this()));
}

void PolymarketClient::on_write(beast::error_code ec, std::size_t bytes_transferred) {
    if (ec) {
        spdlog::error("Polymarket write failed: {}", ec.message());
        return;
    }

    spdlog::info("Subscription sent, waiting for market data...");

    // Start reading responses
    ws_.async_read(buffer_,
        beast::bind_front_handler(&PolymarketClient::on_read, shared_from_this()));
}

void PolymarketClient::on_read(beast::error_code ec, std::size_t bytes_transferred) {
    if (ec) {
        spdlog::error("Polymarket read failed: {} - will attempt reconnect", ec.message());
        // TODO: Implement exponential backoff reconnection
        return;
    }

    std::string msg = beast::buffers_to_string(buffer_.data());
    process_message(msg);

    buffer_.consume(buffer_.size());

    // Continue reading
    ws_.async_read(buffer_,
        beast::bind_front_handler(&PolymarketClient::on_read, shared_from_this()));
}

void PolymarketClient::process_message(const std::string& message) {
    try {
        // Log raw message to see what we're actually receiving
        spdlog::info("Polymarket message ({} chars): {}", message.size(),
                    message.substr(0, std::min(size_t(300), message.size())));

        auto j = json::parse(message);

        // Check for various message types (not just event_type)
        if (j.contains("type")) {
            spdlog::info("Message type field: {}", j["type"].get<std::string>());
        }
        if (j.contains("event_type")) {
            spdlog::info("Event type field: {}", j["event_type"].get<std::string>());
        }

        if (!j.contains("event_type")) {
            spdlog::info("No event_type - might be subscription response or other message");
            return; // Ignore non-standard messages
        }

        std::string event_type = j["event_type"];

        if (event_type == "book") {
            // Full order book snapshot
            spdlog::debug("Book snapshot for market: {}", j.value("market", "unknown"));

            MarketDataUpdate update;
            update.source = "polymarket";
            update.timestamp = std::chrono::system_clock::now();
            update.asset_id = j.value("asset_id", "");
            update.market_id = j.value("market", "");

            if (j.contains("bids") && !j["bids"].empty()) {
                update.bid = std::stod(j["bids"][0]["price"].get<std::string>());
                update.bid_size = std::stod(j["bids"][0]["size"].get<std::string>());
            }
            if (j.contains("asks") && !j["asks"].empty()) {
                update.ask = std::stod(j["asks"][0]["price"].get<std::string>());
                update.ask_size = std::stod(j["asks"][0]["size"].get<std::string>());
            }

            event_bus_->publish(update);
            spdlog::info("Published book: market={} bid={:.4f} ask={:.4f}",
                        update.market_id, update.bid, update.ask);

        } else if (event_type == "price_change") {
            // Price update
            if (!j.contains("price_changes") || j["price_changes"].empty()) {
                return;
            }

            auto price_change = j["price_changes"][0];
            MarketDataUpdate update;
            update.source = "polymarket";
            update.timestamp = std::chrono::system_clock::now();
            update.asset_id = price_change.value("asset_id", "");
            update.market_id = j.value("market", "");
            update.price = std::stod(price_change.value("price", "0"));

            if (price_change.contains("best_bid")) {
                update.bid = std::stod(price_change["best_bid"].get<std::string>());
            }
            if (price_change.contains("best_ask")) {
                update.ask = std::stod(price_change["best_ask"].get<std::string>());
            }

            event_bus_->publish(update);
            spdlog::info("Published price_change: market={} price={:.4f}",
                        update.market_id, update.price);
        }

    } catch (const std::exception& e) {
        spdlog::warn("Failed to parse Polymarket message: {}", e.what());
    }
}

} // namespace feed
} // namespace polyquant
