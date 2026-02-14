cmake_minimum_required(VERSION 3.20)
project(PolyQuant VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -O3")

# Dependencies
find_package(Boost 1.74 REQUIRED COMPONENTS system thread)
find_package(PostgreSQL REQUIRED)
find_package(GTest REQUIRED)
find_package(Threads REQUIRED)
find_package(spdlog REQUIRED)
find_package(OpenSSL REQUIRED)

# ONNX Runtime
set(ONNXRUNTIME_ROOT /usr/local)
include_directories(${ONNXRUNTIME_ROOT}/include)
link_directories(${ONNXRUNTIME_ROOT}/lib)

# IBKR TWS API
# We need to compile the TWS API source files
set(TWS_API_DIR /opt/twsapi)
if(EXISTS ${TWS_API_DIR})
    include_directories(${TWS_API_DIR})
    file(GLOB TWS_SOURCES "${TWS_API_DIR}/*.cpp")
    # Exclude the sample client if it exists (usually EClientSocket.cpp is what we need)
    # But TWS API folder is flat, so GLOB is fine.
else()
    message(WARNING "TWS API not found at ${TWS_API_DIR}. IBKR Client will fail to build.")
endif()

# Include directories
include_directories(include)
include_directories(src/cpp)

# Add subdirectories
add_subdirectory(src/cpp)

# Tests
enable_testing()
file(GLOB_RECURSE TEST_SOURCES "tests/*.cpp")

if(TEST_SOURCES)
    add_executable(polyquant_tests
        ${TEST_SOURCES}
        src/cpp/pricing/BlackScholes.cpp
        src/cpp/core/MarketDataAggregator.cpp
        src/cpp/core/StrategyEngine.cpp
        # We don't link IBKR/Polymarket clients in unit tests to avoid external dependencies
    )

    target_link_libraries(polyquant_tests PRIVATE
        GTest::gtest
        GTest::gtest_main
        ${Boost_LIBRARIES}
        pqxx
        onnxruntime
        Threads::Threads
        spdlog::spdlog
        OpenSSL::SSL
        OpenSSL::Crypto
    )

    add_test(NAME AllTests COMMAND polyquant_tests)
endif()
