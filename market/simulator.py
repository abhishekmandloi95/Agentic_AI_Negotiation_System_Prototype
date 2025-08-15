from datetime import datetime, timedelta
import math
from typing import List
from .schemas import PricePoint
import random

def gbm_series(last_price: float, days: int, mu: float = 0.05, sigma: float = 0.2) -> List[PricePoint]:

    random.seed(42)
    """
    Generate a simple geometric Brownian motion price path.
    - Step size assumes trading days (dt = 1/252).
    - Returns `days` forward points starting at now+1d, ..., now+days.
    """
    if days <= 0:
        return []

    dt = 1.0 / 365.0
    # keep prices positive & finite
    eps = 1e-9
    try:
        price = float(last_price)
    except Exception:
        price = 1.0
    if not math.isfinite(price) or price <= 0.0:
        price = 1.0

    out: List[PricePoint] = []
    now = datetime.utcnow()

    sqrt_dt = math.sqrt(dt)
    drift = (mu - 0.5 * sigma * sigma) * dt

    for i in range(1, days + 1):
        z = random.gauss(0.0, 1.0)
        price *= math.exp(drift + sigma * sqrt_dt * z)
        # clamp just in case of numerical weirdness
        if not math.isfinite(price) or price <= 0.0:
            price = eps
        out.append(PricePoint(ts=now + timedelta(days=i), price=price))

    return out
