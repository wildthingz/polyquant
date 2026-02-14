# src/cpp/CMakeLists.txt

# Define source files
set(SOURCES
    main.cpp
    pricing/BlackScholes.cpp
)

# Create the executable
add_executable(polyquant_engine ${SOURCES})

# Link libraries
target_link_libraries(polyquant_engine PRIVATE
    ${Boost_LIBRARIES}
    ${PostgreSQL_LIBRARIES}
    pqxx
    onnxruntime
    Threads::Threads
    spdlog::spdlog
)

# Include directories
target_include_directories(polyquant_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src/cpp
)
