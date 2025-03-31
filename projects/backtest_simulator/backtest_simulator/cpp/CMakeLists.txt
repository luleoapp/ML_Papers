cmake_minimum_required(VERSION 3.12)
project(backtest_engine LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Find Python
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Find pybind11
find_package(pybind11 CONFIG REQUIRED)
if(NOT pybind11_FOUND)
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -m pip install pybind11
        RESULT_VARIABLE pip_result
    )
    find_package(pybind11 CONFIG REQUIRED)
endif()

# Add source files
set(SOURCES
    src/backtest_engine.cpp
    src/order_book.cpp
    src/tick_processor.cpp
    src/trade_marker.cpp
    src/pybind_module.cpp
)

# Create the extension module
pybind11_add_module(backtest_engine ${SOURCES})

# Include directories
target_include_directories(backtest_engine PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)

# Link libraries if needed
# target_link_libraries(backtest_engine PRIVATE some_library)

# Install rules
install(TARGETS backtest_engine DESTINATION .)
