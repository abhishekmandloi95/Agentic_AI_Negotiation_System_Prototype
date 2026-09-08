import pytest
import pandas as pd
from market.forecaster import fit_and_forecast

@pytest.mark.forecast
def test_real_forecast_returns_horizon():
    pytest.importorskip("prophet")
    history = pd.DataFrame({"ds": pd.date_range("2025-01-01", periods=30), "y": range(100, 130)})
    result = fit_and_forecast(history, 5)
    assert len(result) == 5
    assert result["ds"].min() > history["ds"].max()
    assert result["yhat"].notna().all()
