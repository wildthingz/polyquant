# src/cpp/CMakeLists.txt

# Define source files
set(SOURCES
    main.cpp
    pricing/BlackScholes.cpp
    feed/PolymarketClient.cpp
    feed/IBKRClient.cpp
    core/MarketDataAggregator.cpp
    core/StrategyEngine.cpp
)

# Create the executable
# We include TWS_SOURCES here which we defined in the root CMakeLists.txt
add_executable(polyquant_engine ${SOURCES} ${TWS_SOURCES})

# Link libraries
target_link_libraries(polyquant_engine PRIVATE
    ${Boost_LIBRARIES}
    ${PostgreSQL_LIBRARIES}
    pqxx
    onnxruntime
    Threads::Threads
    spdlog::spdlog
    OpenSSL::SSL
    OpenSSL::Crypto
)

# Include directories
target_include_directories(polyquant_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/include
)
