from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime

@dataclass
class PricePoint:
    ts: datetime
    price: float

@dataclass
class PriceForecast:
    resource: str
    horizon_days: int
    forecast_price: float
    trend: float                 # % change vs last known price (e.g., +0.07 = +7%)
    confidence_low: float        # lower bound price
    confidence_high: float       # upper bound price
    generated_at: datetime

@dataclass
class MarketSignal:
    resource: str
    horizon_days: int
    forecast: PriceForecast
    demand_index: Optional[float] = None   # 0..1 if you compute demand
    volatility: Optional[float] = None     # e.g., rolling std
    notes: Optional[str] = None            # short text for prompts

@dataclass
class MarketConfig:
    # maps your negotiation 'service/resource' name -> data source identifier or file path
    resource_sources: Dict[str, str]
    default_horizon_days: int = 7
