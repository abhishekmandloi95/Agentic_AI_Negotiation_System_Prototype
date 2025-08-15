# tests/test_market_service.py
import pandas as pd
import pytest
import importlib, sys, types

def _market_service_module():
    # Robustly import the submodule even if package exports `service` attribute
    mod = sys.modules.get("market.service")
    if not isinstance(mod, types.ModuleType):
        mod = importlib.import_module("market.service")
    return mod

def test_context_returns_object_and_scalars():
    svc_mod = _market_service_module()
    service = svc_mod.service

    service.configure(['X', 'Y'])
    service.update_market()

    ctx = service.context({'X': {}, 'Y': {}})
    assert hasattr(ctx, 'by_service')
    assert set(ctx.by_service.keys()) == {'X', 'Y'}
    for sig in ctx.by_service.values():
        assert hasattr(sig, 'price_scalar')
        assert 0.9 <= float(sig.price_scalar) <= 1.1

def test_trend_uses_prophet_when_available(monkeypatch):
    svc_mod = _market_service_module()
    service = svc_mod.service

    def fake_fc(df, horizon_days):
        ds = pd.date_range(df['ds'].iloc[-1], periods=horizon_days+1, freq='D')[1:]
        yhat = pd.Series([1.0 + 0.02 * i for i in range(horizon_days)])  # rising
        return pd.DataFrame({
            'ds': ds, 'yhat': yhat, 'yhat_lower': yhat * 0.95, 'yhat_upper': yhat * 1.05
        })

    # Patch the function IN THE MODULE WHERE get_trend LOOKS IT UP
    monkeypatch.setattr(svc_mod, 'fit_and_forecast', fake_fc, raising=True)

    service.configure(['Z'])
    service.update_market()
    assert service.get_trend('Z', days_ahead=5) == 'up'

def test_trend_fallback_path(monkeypatch):
    svc_mod = _market_service_module()
    service = svc_mod.service
    ProphetUnavailable = svc_mod.ProphetUnavailable

    def raise_unavailable(df, horizon_days):
        raise ProphetUnavailable("no prophet in test")

    monkeypatch.setattr(svc_mod, 'fit_and_forecast', raise_unavailable, raising=True)

    service.configure(['W'])
    # bias recent history downward so fallback tends to say 'down'
    for _ in range(5):
        df = service.history['W']
        df.loc[df.index[-1], 'y'] = float(df['y'].iloc[-1]) * 0.98
        service.update_market()

    trend = service.get_trend('W', days_ahead=5)
    assert trend in {'down', 'stable'}