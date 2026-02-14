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

# ONNX Runtime (Manual include since it doesn't always have a CMake config)
set(ONNXRUNTIME_ROOT /usr/local)
include_directories(${ONNXRUNTIME_ROOT}/include)
link_directories(${ONNXRUNTIME_ROOT}/lib)

# Include directories
include_directories(src/cpp)

# Add subdirectories
add_subdirectory(src/cpp)

# Tests
enable_testing()
file(GLOB_RECURSE TEST_SOURCES "tests/*.cpp")

if(TEST_SOURCES)
    # We need to link against the implementation files for tests
    # In a larger project, we'd make a static library for core logic
    add_executable(polyquant_tests
        ${TEST_SOURCES}
        src/cpp/pricing/BlackScholes.cpp
    )

    target_link_libraries(polyquant_tests PRIVATE
        GTest::gtest
        GTest::gtest_main
        ${Boost_LIBRARIES}
        pqxx
        onnxruntime
        Threads::Threads
        spdlog::spdlog
    )

    add_test(NAME AllTests COMMAND polyquant_tests)
endif()
