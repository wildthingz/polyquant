#include <iostream>
#include <spdlog/spdlog.h>
#include <pqxx/pqxx>
#include <cstdlib>
#include <thread>
#include <chrono>

int main() {
    spdlog::info("PolyQuant Engine Starting...");

    // Basic Database Connection Test
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
                return 1;
            }
        } else {
            spdlog::warn("Database environment variables not set, skipping connection test.");
        }
    } catch (const std::exception &e) {
        spdlog::error("Database connection error: {}", e.what());
        // Don't exit yet, just log error for now as we are setting up
    }

    spdlog::info("System initialized. Waiting for events...");

    // Keep alive for Docker
    while(true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    return 0;
}
