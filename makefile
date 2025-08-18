SHELL := /bin/bash

# Export the project root so Python can import your packages
PYTHONPATH := $(CURDIR)
export PYTHONPATH

.PHONY: test test-fast test-all test-ganache test-rag test-new test-coverage

test-fast:
	pytest -q -m "not ganache"

test-ganache:
	GANACHE_OK=1 pytest -q -m ganache

test-rag:
	pytest -q -m ragheavy

test-all:
	GANACHE_OK=1 pytest -q

test-new:
	pytest tests/test_contract_logging.py tests/test_agent_market_reaction.py

test-coverage:
	coverage run -m pytest
	coverage report -m
	coverage html

test: test-fast