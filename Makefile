# ruleIQ Test Execution Makefile
# Provides convenient shortcuts for running tests in different modes

.PHONY: help test-fast test-integration test-performance test-full test-ci test-ai test-security test-e2e test-parallel test-sequential install-test-deps test-groups test-groups-parallel test-groups-list test-group-unit test-group-ai test-group-api test-group-endpoints test-group-advanced test-group-e2e

# Default target
help:
	@echo "ruleIQ Test Execution Commands"
	@echo "==============================="
	@echo ""
	@echo "🎯 NEW: Independent Test Groups (100% Functionality):"
	@echo "  make test-groups         - Run all 6 groups sequentially"
	@echo "  make test-groups-parallel- Run all 6 groups in parallel (fastest)"
	@echo "  make test-groups-list    - List all test groups"
	@echo "  make test-group-unit     - Unit tests (2-3 min)"
	@echo "  make test-group-ai       - AI core tests (3-4 min)"
	@echo "  make test-group-api      - Basic API tests (4-5 min)"
	@echo "  make test-group-endpoints- AI endpoints (5-6 min)"
	@echo "  make test-group-advanced - Advanced features (3-4 min)"
	@echo "  make test-group-e2e      - End-to-end tests (6-8 min)"
	@echo ""
	@echo "Legacy Test Modes:"
	@echo "  make test-fast        - Fast unit tests only (high parallelism)"
	@echo "  make test-integration - Integration tests (medium parallelism)"
	@echo "  make test-performance - Performance tests (sequential)"
	@echo "  make test-ai          - AI and compliance tests"
	@echo "  make test-security    - Security and auth tests"
	@echo "  make test-e2e         - End-to-end workflow tests"
	@echo ""
	@echo "Comprehensive Modes:"
	@echo "  make test-full        - Complete test suite (optimized chunks)"
	@echo "  make test-ci          - CI/CD optimized execution"
	@echo ""
	@echo "Traditional Modes:"
	@echo "  make test-parallel    - All tests with pytest-xdist"
	@echo "  make test-sequential  - All tests sequentially"
	@echo ""
	@echo "Utilities:"
	@echo "  make install-test-deps - Install test dependencies"
	@echo "  make list-test-modes   - List all available test modes"
	@echo "  make test-info         - Show system info for test optimization"

# Install test dependencies
install-test-deps:
	pip install pytest-xdist pytest-parallel pytest-benchmark pytest-timeout pytest-asyncio

# Chunked test execution modes
test-fast:
	@echo "🚀 Running fast unit tests..."
	@. .venv/bin/activate && python scripts/run_tests_chunked.py --mode fast

test-integration:
	@echo "🔗 Running integration tests..."
	@. .venv/bin/activate && python scripts/run_tests_chunked.py --mode integration

test-performance:
	@echo "⚡ Running performance tests..."
	@. .venv/bin/activate && python scripts/run_tests_chunked.py --mode performance

test-ai:
	@echo "🤖 Running AI and compliance tests..."
	@. .venv/bin/activate && python scripts/run_tests_chunked.py --mode ai

test-security:
	@echo "🔒 Running security tests..."
	@. .venv/bin/activate && python scripts/run_tests_chunked.py --mode security

test-e2e:
	@echo "🎯 Running end-to-end tests..."
	@. .venv/bin/activate && python scripts/run_tests_chunked.py --mode e2e

test-full:
	@echo "🎪 Running complete test suite..."
	@. .venv/bin/activate && python scripts/run_tests_chunked.py --mode full

test-ci:
	@echo "🏗️ Running CI-optimized tests..."
	@. .venv/bin/activate && python scripts/run_tests_chunked.py --mode ci

# Traditional pytest execution
test-parallel:
	@echo "⚡ Running all tests with pytest-xdist..."
	python -m pytest -n auto --dist=worksteal --tb=short --maxfail=5

test-sequential:
	@echo "📝 Running all tests sequentially..."
	python -m pytest --tb=short --maxfail=5

# Utility commands
list-test-modes:
	python scripts/run_tests_chunked.py --list-modes

test-info:
	@echo "System Information for Test Optimization:"
	@python -c "import psutil; print(f'CPUs: {psutil.cpu_count()}, Memory: {psutil.virtual_memory().total/(1024**3):.1f}GB, Available: {psutil.virtual_memory().available/(1024**3):.1f}GB')"

# Development shortcuts
test-quick: test-fast
test-dev: test-integration
test-all: test-full

# Specific test categories with markers
test-unit:
	python -m pytest -m unit -n auto --dist=worksteal

test-api:
	python -m pytest -m api -n 2 --dist=worksteal

test-database:
	python -m pytest -m database -n 1

test-slow:
	python -m pytest -m slow -n 1

test-smoke:
	python -m pytest -m smoke -n auto --dist=worksteal

# Coverage reports
test-coverage:
	python -m pytest --cov=. --cov-report=html --cov-report=term-missing --cov-fail-under=70 --cov-branch

test-coverage-fast:
	python -m pytest tests/unit/ -m unit --cov=. --cov-report=html --cov-report=term-missing --cov-fail-under=70 --cov-branch

# Benchmark specific tests
test-benchmark:
	python -m pytest tests/performance/ --benchmark-only --benchmark-sort=mean

# Clean up test artifacts
clean-test:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -f coverage.xml coverage.json
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Watch mode for development (requires pytest-watch)
test-watch:
	ptw --runner "python -m pytest -n auto --dist=worksteal"

# Profile test execution
test-profile:
	python -m pytest --profile --profile-svg

# Test with different Python versions (if available)
test-py311:
	python3.11 -m pytest -n auto --dist worksteal

test-py312:
	python3.12 -m pytest -n auto --dist worksteal

test-py313:
	python3.13 -m pytest -n auto --dist worksteal

# Memory profiling
test-memory:
	python -m pytest -m memory --tb=short

# Stress testing
test-stress:
	for i in {1..5}; do echo "Stress run $$i"; make test-fast || exit 1; done

# Test specific files or patterns
test-file:
	@echo "Usage: make test-file FILE=path/to/test_file.py"
	@if [ -z "$(FILE)" ]; then echo "Please specify FILE=path/to/test_file.py"; exit 1; fi
	python -m pytest $(FILE) -v

test-pattern:
	@echo "Usage: make test-pattern PATTERN=test_name_pattern"
	@if [ -z "$(PATTERN)" ]; then echo "Please specify PATTERN=test_name_pattern"; exit 1; fi
	python -m pytest -k "$(PATTERN)" -v

# Docker-based testing (if Docker is available)
test-docker:
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Generate test report
test-report:
	python scripts/run_tests_chunked.py --mode full > test_report.txt 2>&1
	@echo "Test report generated: test_report.txt"

# Continuous testing for development
test-continuous:
	@echo "Starting continuous testing (Ctrl+C to stop)..."
	@while true; do \
		echo "Running fast tests..."; \
		make test-fast; \
		echo "Waiting 30 seconds..."; \
		sleep 30; \
	done

# NEW: Independent Test Groups (100% Functionality)
test-groups:
	@echo "🎯 Running all test groups sequentially..."
	python test_groups.py all

test-groups-parallel:
	@echo "⚡ Running all test groups in parallel..."
	python test_groups.py parallel

test-groups-list:
	@echo "📋 Listing all test groups..."
	python test_groups.py list

test-group-unit:
	@echo "🔧 Running unit tests..."
	python test_groups.py group1_unit

test-group-ai:
	@echo "🤖 Running AI core tests..."
	python test_groups.py group2_ai_core

test-group-api:
	@echo "🌐 Running basic API tests..."
	python test_groups.py group3_api_basic

test-group-endpoints:
	@echo "🚀 Running AI endpoints tests..."
	python test_groups.py group4_ai_endpoints

test-group-advanced:
	@echo "⚙️ Running advanced features tests..."
	python test_groups.py group5_advanced

test-group-e2e:
	@echo "🎯 Running end-to-end tests..."
	python test_groups.py group6_e2e

# Quick combinations for development
test-quick-groups:
	@echo "⚡ Running quick test groups (Unit + AI)..."
	python test_groups.py group1_unit && python test_groups.py group2_ai_core

test-core-groups:
	@echo "🎯 Running core test groups (Unit + AI + API)..."
	python test_groups.py group1_unit && python test_groups.py group2_ai_core && python test_groups.py group3_api_basic
