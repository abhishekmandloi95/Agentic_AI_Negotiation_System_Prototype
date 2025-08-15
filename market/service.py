# market/service.py
from __future__ import annotations

from typing import Iterable, Optional, List, Dict
from datetime import datetime, timedelta
import math
import random

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
    def __init__(self):
        self.history: Dict[str, pd.DataFrame] = {}
        self.resources: List[str] = []
        self._cache: Dict[tuple[str, int], str] = {}

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

        base = 80.0 + (hash(resource) % 40)  # deterministic 80..119
        mu = 0.05
        sigma = 0.30
        dt = 1.0 / 365.0
        sqrt_dt = math.sqrt(dt)

        prices = [float(base)]
        rnd = random.Random(hash(resource) & 0xFFFFFFFF)

        for _ in range(days - 1):
            z = rnd.gauss(0.0, 1.0)
            next_price = prices[-1] * math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * sqrt_dt * z)
            prices.append(max(next_price, 1e-9))

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
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
            z = random.gauss(0.0, 1.0)
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

    def get_trend(self, resource: str, days_ahead: int = 5) -> str:
        """Return 'up' | 'down' | 'stable' using Prophet forecast or a simple fallback."""
        key = (resource, int(days_ahead))
        if key in self._cache:
            return self._cache[key]

        df = self.history.get(resource)
        if df is None or df.empty:
            self._cache[key] = "stable"
            return "stable"

        try:
            fc = fit_and_forecast(df, horizon_days=days_ahead)
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
            recent = df.tail(min(7, len(df)))
            if len(recent) < 2:
                self._cache[key] = "stable"
                return "stable"
            start, end = float(recent["y"].iloc[0]), float(recent["y"].iloc[-1])
            if end > start * 1.02:
                self._cache[key] = "up"
            elif end < start * 0.98:
                self._cache[key] = "down"
            else:
                self._cache[key] = "stable"
            return self._cache[key]
        except Exception:
            self._cache[key] = "stable"
            return "stable"

    def get_forecast(self, resource: str, days_ahead: int = 5) -> Optional[pd.DataFrame]:
        """Convenience accessor to the full Prophet forecast frame."""
        df = self.history.get(resource)
        if df is None or df.empty:
            return None
        try:
            return fit_and_forecast(df, horizon_days=days_ahead)
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


# Shared singleton
service = MarketInsightsService()