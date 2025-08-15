from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict
import os
import pandas as pd

from .schemas import MarketConfig, MarketSignal, PriceForecast  # PricePoint not used
from .forecaster import fit_and_forecast, ProphetUnavailable
from . import simulator as sim

_EPS = 1e-9

class MarketInsights:
    """
    Orchestrates: load data -> forecast (Prophet) or simulate -> expose tiny API.
    """
    def __init__(self, config: MarketConfig):
        self.config = config
        self._last_prices: Dict[str, float] = {}
        self._cache: Dict[tuple, MarketSignal] = {}  # (resource, horizon)->signal

    def _load_history(self, resource: str) -> Optional[pd.DataFrame]:
        src = self.config.resource_sources.get(resource)
        if not src:
            return None

        # CSV path only for now
        if not (os.path.exists(src) and src.lower().endswith(".csv")):
            return None

        df = pd.read_csv(src)

        # Accept common alternative column names
        rename = {}
        if "ds" not in df.columns:
            if "date" in df.columns: rename["date"] = "ds"
            elif "timestamp" in df.columns: rename["timestamp"] = "ds"
        if "y" not in df.columns and "price" in df.columns:
            rename["price"] = "y"
        if rename:
            df = df.rename(columns=rename)

        if not {"ds", "y"}.issubset(df.columns):
            return None

        # Clean & normalize
        df = df[["ds", "y"]].dropna()
        df["ds"] = pd.to_datetime(df["ds"], errors="coerce", utc=True)
        df = df.dropna(subset=["ds", "y"])
        df["ds"] = df["ds"].dt.tz_localize(None)  # Prophet prefers tz-naive
        df = df.sort_values("ds").drop_duplicates(subset="ds").reset_index(drop=True)

        if not df.empty:
            self._last_prices[resource] = float(df["y"].iloc[-1])

        return df if not df.empty else None

    def _last_price(self, resource: str, fallback: float = 1.0) -> float:
        return self._last_prices.get(resource, fallback)

    def get_signal(self, resource: str, horizon_days: Optional[int] = None) -> MarketSignal:
        h = horizon_days or self.config.default_horizon_days
        key = (resource, h)
        if key in self._cache:
            return self._cache[key]

        history = self._load_history(resource)
        generated_at = datetime.utcnow()

        if history is not None:
            try:
                fc = fit_and_forecast(history, h)
                last = float(history["y"].iloc[-1])
                # take last day of horizon
                row = fc.iloc[-1]
                forecast_price = float(row["yhat"])
                low = float(row["yhat_lower"])
                high = float(row["yhat_upper"])
                # robust relative change
                denom = max(_EPS, abs(last))
                trend = (forecast_price - last) / denom
            except ProphetUnavailable:
                last = float(history["y"].iloc[-1])
                sim_pts = sim.gbm_series(max(_EPS, last), h)
                forecast_price = sim_pts[-1].price
                low = min(p.price for p in sim_pts)
                high = max(p.price for p in sim_pts)
                denom = max(_EPS, abs(last))
                trend = (forecast_price - last) / denom
        else:
            # no history at all -> pure simulate from nominal last
            last = self._last_price(resource, fallback=1.0)
            sim_pts = sim.gbm_series(max(_EPS, last), h)
            forecast_price = sim_pts[-1].price
            low = min(p.price for p in sim_pts)
            high = max(p.price for p in sim_pts)
            denom = max(_EPS, abs(last))
            trend = (forecast_price - last) / denom

        pf = PriceForecast(
            resource=resource,
            horizon_days=h,
            forecast_price=forecast_price,
            trend=trend,
            confidence_low=low,
            confidence_high=high,
            generated_at=generated_at,
        )

        # Derived signals
        volatility = max(0.0, min(1.0, (high - low) / max(_EPS, abs(forecast_price))))
        demand_index = max(0.0, min(1.0, 0.5 + trend))  # simple mapping

        note = (
            f"{resource}: {trend:+.1%} over {h}d; "
            f"forecast≈{forecast_price:.2f} "
            f"[{low:.2f}–{high:.2f}], vol≈{volatility:.2f}"
        )

        signal = MarketSignal(
            resource=resource,
            horizon_days=h,
            forecast=pf,
            demand_index=demand_index,
            volatility=volatility,
            notes=note,
        )
        self._cache[key] = signal
        return signal

    # ===== Helpers for strategy/prompt =====
    def adjust_value(
        self,
        base_value: float,
        resource: str,
        role: str = "buyer",
        horizon_days: Optional[int] = None,
        cap: float = 0.25,
    ) -> float:
        """
        Adjust a reservation value using forecast trend. cap limits the impact to ±25% by default.
        Buyers pay a bit more on up-trend; sellers accept a bit less on down-trend.
        """
        s = self.get_signal(resource, horizon_days)
        adj = max(-cap, min(cap, s.forecast.trend))
        if role.lower().startswith("buy"):
            return base_value * (1.0 + adj)
        else:
            return base_value * (1.0 - max(-adj, 0.0))  # sellers resist drops less aggressively

    def context_line(self, resource: str, horizon_days: Optional[int] = None) -> str:
        return self.get_signal(resource, horizon_days).notes
