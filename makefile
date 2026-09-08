PYTHON ?= .venv/bin/python
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: test test-fast test-all test-ganache test-rag test-market-reaction test-behavior test-critical test-rag-effect test-prophet-signals test-coverage run benchmark run-experiments

test: test-fast
test-fast:
	$(PYTHON) -m pytest -m "not ganache and not ragheavy and not forecast and not blockchain and not llm and not embeddings"
test-all:
	$(PYTHON) -m pytest -m "not ganache and not llm and not embeddings"
test-ganache:
	$(PYTHON) -m pytest -m ganache
test-rag:
	$(PYTHON) -m pytest tests/test_rag_memory.py
test-market-reaction:
	$(PYTHON) -m pytest tests/test_market_service.py tests/test_contract_logging.py
test-behavior:
	$(PYTHON) -m pytest tests/test_negotiation_behavior.py
test-critical:
	$(PYTHON) -m pytest tests/test_critical_edge_cases.py
test-rag-effect:
	$(PYTHON) -m pytest tests/test_rag_effect_on_negotiation.py
test-prophet-signals:
	$(PYTHON) -m pytest -m forecast
test-coverage:
	$(PYTHON) -m coverage run -m pytest -m "not ganache and not llm and not embeddings"
	$(PYTHON) -m coverage report -m
run:
	$(PYTHON) -m streamlit run ui_app.py
benchmark:
	$(PYTHON) -m experiments.benchmark
experiments-loop-metrics-analysis:
	$(PYTHON) -m experiments.loop_metrics_analysis
experiments-performance-profile:
	$(PYTHON) -m experiments.performance_profile
experiments-prophet-performance-profile:
	$(PYTHON) -m experiments.prophet_performance_profile
run-experiments: benchmark
