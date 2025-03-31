#!/bin/bash
# Script to run all tests with proper reporting

set -e

ECHO_PREFIX="[test runner]"

# Determine if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "$ECHO_PREFIX Not in a virtual environment, activating if available..."
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "$ECHO_PREFIX No virtual environment found. Creating one..."
        ./scripts/make_venv.sh
        source venv/bin/activate
    fi
fi

# Ensure dependencies are installed
echo "$ECHO_PREFIX Ensuring dependencies are installed..."
pip install -e ".[dev]"

# Function to run a specific test file or directory
run_test() {
    local test_path=$1
    local test_name=$(basename "$test_path")
    
    echo "$ECHO_PREFIX Running test: $test_name"
    PYTHONPATH=. pytest -v "$test_path"
    
    if [ $? -eq 0 ]; then
        echo "$ECHO_PREFIX ✅ Test $test_name completed successfully"
    else
        echo "$ECHO_PREFIX ❌ Test $test_name failed"
        FAILED_TESTS+=("$test_name")
    fi
    echo
}

# Parse command line arguments
if [ "$#" -gt 0 ]; then
    # Run specific test(s)
    for test_path in "$@"; do
        run_test "$test_path"
    done
else
    # Run all tests
    echo "$ECHO_PREFIX Running all tests..."
    
    # Array to track failed tests
    FAILED_TESTS=()
    
    # Run each test file separately for better reporting
    for test_file in tests/test_*.py; do
        run_test "$test_file"
    done
    
    # Report results
    echo "$ECHO_PREFIX Test run completed."
    if [ ${#FAILED_TESTS[@]} -eq 0 ]; then
        echo "$ECHO_PREFIX All tests passed! 🎉"
    else
        echo "$ECHO_PREFIX The following tests failed:"
        for test in "${FAILED_TESTS[@]}"; do
            echo "  - $test"
        done
        echo "$ECHO_PREFIX Please fix the failing tests."
        exit 1
    fi
fi