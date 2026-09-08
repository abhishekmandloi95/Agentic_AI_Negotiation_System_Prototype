import importlib
from datetime import datetime
import pandas as pd
from unittest.mock import Mock

def test_forecast_cache_toggle_and_history_invalidation(market, monkeypatch):
    module = importlib.import_module("market.service")
    forecast = Mock(return_value=pd.DataFrame({"yhat": [100, 110]}))
    monkeypatch.setattr(module, "fit_and_forecast", forecast)
    market.history["x"] = pd.DataFrame({"ds": pd.date_range("2025-01-01", periods=3), "y": [100, 90, 80]})
    market.set_use_prophet(True)
    assert market.context(["x"]).by_service["x"].trend == "up"
    market.context(["x"])
    assert forecast.call_count == 1
    market.set_use_prophet(False)
    assert market.context(["x"]).by_service["x"].trend == "down"
    assert market.get_forecast("x") is None
    assert forecast.call_count == 1
    market.set_use_prophet(True)
    market.context(["x"])
    assert forecast.call_count == 2
    market.history["x"].loc[2, "y"] = 200
    market.context(["x"])
    assert forecast.call_count == 3

def test_unavailable_prophet_falls_back(market, monkeypatch):
    module = importlib.import_module("market.service")
    def missing(*a, **k): raise module.ProphetUnavailable("test")
    monkeypatch.setattr(module, "fit_and_forecast", missing)
    market.history["x"] = pd.DataFrame({"y": [100, 110]})
    market.set_use_prophet(True)
    assert market.context(["x"]).by_service["x"].price_scalar == 1.05

def test_seed_is_reproducible():
    from market.service import MarketInsightsService
    a = MarketInsightsService(seed=7, as_of=datetime(2025,1,1))
    b = MarketInsightsService(seed=7, as_of=datetime(2025,1,1))
    for s in (a, b):
        s.configure(["x", "y"])
        s.update_market()
    pd.testing.assert_frame_equal(a.history["x"], b.history["x"])

def test_missing_market_is_neutral(market):
    assert market.context(["absent"]).by_service["absent"].price_scalar == 1
