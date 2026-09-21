# market/service.py
from __future__ import annotations

from typing import Iterable, Optional, List, Dict
from datetime import datetime, timedelta
import math
import random
import hashlib
import logging

import pandas as pd
from .forecaster import fit_and_forecast, ProphetUnavailable


# ---- helper data holders ----
class ServiceSignal:
    __slots__ = ("name", "trend", "last_price", "price_scalar")
    def __init__(self, name: str, trend: str, last_price: float, price_scalar: float):
        self.name = name
        self.trend = trend            # 'up' | 'down' | 'stable'
        self.last_price = last_price  # float
        self.price_scalar = price_scalar  # e.g., 0.90 .. 1.10


class MarketContext:
    """
    Return type of _MARKET.context(services):
      - by_service: dict[name] -> ServiceSignal
      - pretty __str__ and .lines convenience for SYSTEM messages
    """
    def __init__(self, by_service: dict[str, ServiceSignal]):
        self.by_service = by_service

    def __str__(self) -> str:
        if not self.by_service:
            return "Market forecast — (none)."
        parts = []
        for s in self.by_service.values():
            parts.append(f"{s.name}: {s.trend} (last≈{s.last_price:.2f})")
        return "Market forecast — " + "; ".join(parts) + "."

    @property
    def lines(self) -> list[str]:
        return [
            f"SYSTEM: Forecast indicates '{s.name}' market is trending {s.trend}."
            for s in self.by_service.values()
        ]

    def for_prompt(self) -> str:
        return str(self)

    @property
    def text(self) -> str:
        return str(self)


class MarketInsightsService:
    """
    Keeps simple daily price history per resource and provides Prophet-based
    trends (with a graceful fallback). Designed to be drop-in compatible with:
      - MarketInsightsService.from_config({...})
      - _MARKET.context(services)  -> object with .by_service[svc].price_scalar
    """
    def __init__(self, seed=0, as_of=None):
        self.seed = seed
        self.as_of = as_of or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._rng = random.Random(seed)
        self._forecast_cache = {}
        self.history: Dict[str, pd.DataFrame] = {}
        self.resources: List[str] = []
        self._cache: Dict[tuple[str, int], str] = {}
        self._use_prophet = True

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "MarketInsightsService":
        """
        Accepts:
          - {"resources": ["DevOps", "Analytics", ...]}  OR
          - {"services": {"DevOps": {...}, "Analytics": {...}, ...}}
        """
        inst = cls()
        resources: list[str] = []
        if cfg:
            if isinstance(cfg.get("resources"), (list, tuple, set)):
                resources = list(cfg["resources"])
            elif isinstance(cfg.get("services"), dict):
                resources = list(cfg["services"].keys())
        inst.configure(resources)
        return inst

    def _init_history_if_missing(self, resource: str, days: int = 30) -> None:
        """Create a simple daily random-walk history ending today."""
        if resource in self.history and not self.history[resource].empty:
            return

        base = 80.0 + (int.from_bytes(hashlib.sha256(resource.encode()).digest()[:4], "big") % 40)  
        mu = 0.05
        sigma = 0.30
        dt = 1.0 / 365.0
        sqrt_dt = math.sqrt(dt)

        prices = [float(base)]
        rnd = random.Random(f"{self.seed}:{resource}")

        for _ in range(days - 1):
            z = rnd.gauss(0.0, 1.0)
            next_price = prices[-1] * math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * sqrt_dt * z)
            prices.append(max(next_price, 1e-9))

        today = self.as_of
        dates = [today - timedelta(days=(days - 1 - i)) for i in range(days)]
        self.history[resource] = pd.DataFrame({"ds": dates, "y": prices})

    def configure(self, resources: Iterable[str]) -> None:
        unique = sorted({r for r in resources if r})
        self.resources = unique
        for r in unique:
            self._init_history_if_missing(r)

    def update_market(self) -> None:
        """Advance each resource by one day using a GBM-style step."""
        mu = 0.05
        sigma = 0.20
        dt = 1.0 / 365.0
        sqrt_dt = math.sqrt(dt)

        for r, df in self.history.items():
            last_price = float(df["y"].iloc[-1])
            z = self._rng.gauss(0.0, 1.0)
            next_price = last_price * math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * sqrt_dt * z)
            next_price = max(next_price, 1e-9)

            last_ds = pd.to_datetime(df["ds"].iloc[-1])
            new_ds = (last_ds.to_pydatetime() + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            self.history[r] = pd.concat(
                [df, pd.DataFrame({"ds": [new_ds], "y": [next_price]})],
                ignore_index=True,
            )

        self._cache.clear()
        self._forecast_cache.clear()

    def _recent_trend(self, df) -> str:
        recent = df.tail(min(7, len(df)))
        if len(recent) < 2:
            return "stable"
        start, end = float(recent["y"].iloc[0]), float(recent["y"].iloc[-1])
        if end > start * 1.02:
            return "up"
        elif end < start * 0.98:
            return "down"
        else:
            return "stable"

    def get_trend(self, resource: str, days_ahead: int = 5) -> str:
        """Return 'up' | 'down' | 'stable' using Prophet forecast or a simple fallback."""
        key = self._history_key(resource, days_ahead)
        if key in self._cache:
            return self._cache[key]

        df = self.history.get(resource)
        if df is None or df.empty:
            self._cache[key] = "stable"
            return "stable"

        if not self._use_prophet:
            self._cache[key] = self._recent_trend(df)
            return self._cache[key]

        try:
            fc = self._forecast(resource, days_ahead)
            if fc is None or fc.empty:
                self._cache[key] = "stable"
                return "stable"
            first = float(fc["yhat"].iloc[0])
            last = float(fc["yhat"].iloc[-1])
            if last > first * 1.05:
                self._cache[key] = "up"
            elif last < first * 0.95:
                self._cache[key] = "down"
            else:
                self._cache[key] = "stable"
            return self._cache[key]
        except ProphetUnavailable:
            self._cache[key] = self._recent_trend(df)
            return self._cache[key]
        except Exception:
            logging.getLogger(__name__).exception("Forecast failed for %s", resource)
            self._cache[key] = "stable"
            return "stable"

    def _history_key(self, resource, days_ahead):
        df = self.history.get(resource)
        fingerprint = None if df is None else hashlib.sha256(
            pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()
        return resource, max(1, int(days_ahead)), fingerprint, self._use_prophet

    def _forecast(self, resource, days_ahead):
        key = self._history_key(resource, days_ahead)
        if key not in self._forecast_cache:
            
            self._forecast_cache = {k: v for k, v in self._forecast_cache.items()
                                    if k[:2] != key[:2]}
            try:
                self._forecast_cache[key] = fit_and_forecast(self.history[resource], horizon_days=key[1])
            except Exception as exc:
                self._forecast_cache[key] = exc
        result = self._forecast_cache[key]
        if isinstance(result, Exception):
            raise result
        return result.copy() if result is not None else None

    def get_forecast(self, resource: str, days_ahead: int = 5) -> Optional[pd.DataFrame]:
        
        if not self._use_prophet:
            return None
        df = self.history.get(resource)
        if df is None or df.empty:
            return None
        try:
            return self._forecast(resource, days_ahead)
        except Exception:
            return None

    def context(self, services, days_ahead: int = 5) -> MarketContext:
        """
        Returns a MarketContext with .by_service[svc].price_scalar etc.
        `services` can be an iterable of names or a dict whose keys are names.
        """
        # normalize names
        if not services:
            names: list[str] = []
        elif isinstance(services, dict):
            names = list(services.keys())
        else:
            try:
                names = list(services)
            except TypeError:
                names = [str(services)]

        by_service: dict[str, ServiceSignal] = {}

        for res in names:
            res = str(res)
            trend = self.get_trend(res, days_ahead=days_ahead)

            # last observed price (if any)
            df = self.history.get(res)
            last_price = float(df["y"].iloc[-1]) if (df is not None and not df.empty) else float("nan")

            # prefer Prophet slope → derive scalar; else coarse trend mapping
            price_scalar = 1.0
            fc = self.get_forecast(res, days_ahead=days_ahead)
            try:
                if fc is not None and len(fc) >= 2:
                    first_hat = float(fc["yhat"].iloc[0])
                    last_hat = float(fc["yhat"].iloc[-1])
                    if first_hat > 0:
                        pct = (last_hat / first_hat) - 1.0
                        pct = max(-0.10, min(0.10, pct))  # clamp ±10%
                        price_scalar = 1.0 + pct
                else:
                    price_scalar = 1.05 if trend == "up" else (0.95 if trend == "down" else 1.0)
            except Exception:
                price_scalar = 1.05 if trend == "up" else (0.95 if trend == "down" else 1.0)

            by_service[res] = ServiceSignal(
                name=res, trend=trend, last_price=last_price, price_scalar=price_scalar
            )

        return MarketContext(by_service)

    def context_lines(self, services, days_ahead: int = 5) -> list[str]:
        """One SYSTEM line per service (helper)."""
        return self.context(services, days_ahead=days_ahead).lines

    def set_use_prophet(self, value: bool):
        if self._use_prophet != value:
            self._use_prophet = value
            self._cache.clear()
            self._forecast_cache.clear()

    def get_use_prophet(self) -> bool:
        return self._use_prophet

# Shared singleton
service = MarketInsightsService()