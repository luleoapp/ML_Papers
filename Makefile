.PHONY: venv install test lint format clean docker

# Default target
all: venv install

# Create and setup virtual environment
venv:
	@bash scripts/make_venv.sh

# Install the package in development mode
install:
	@if [ -d "venv" ]; then \
		source venv/bin/activate && pip install -e . && pip install -e ".[dev]"; \
	else \
		pip install -e . && pip install -e ".[dev]"; \
	fi

# Run tests
test:
	@./scripts/run_tests.sh

# Run specific tests
test-engine:
	@./scripts/run_tests.sh tests/test_engine.py

test-date-utils:
	@./scripts/run_tests.sh tests/test_date_utils.py

test-cloud-store:
	@./scripts/run_tests.sh tests/test_cloud_store.py tests/test_cloud_integration.py

test-trade-metrics:
	@./scripts/run_tests.sh tests/test_trade_metrics.py tests/test_data_integration.py

test-versioning:
	@./scripts/run_tests.sh tests/test_versioning.py tests/test_engine_versioning.py

# Run linting
lint:
	@if [ -d "venv" ]; then \
		source venv/bin/activate && flake8 backtest_simulator/ && mypy backtest_simulator/; \
	else \
		flake8 backtest_simulator/ && mypy backtest_simulator/; \
	fi

# Format code
format:
	@if [ -d "venv" ]; then \
		source venv/bin/activate && black backtest_simulator/ && isort backtest_simulator/; \
	else \
		black backtest_simulator/ && isort backtest_simulator/; \
	fi

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf **/__pycache__/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf .mypy_cache/

# Build Docker image
docker:
	docker build -t backtest_simulator .

# Run example in Docker
docker-run:
	docker run -v $(PWD)/results:/app/results backtest_simulator run --start-date 2023-01-01 --end-date 2023-01-31 --universe AAPL MSFT GOOGL AMZN META