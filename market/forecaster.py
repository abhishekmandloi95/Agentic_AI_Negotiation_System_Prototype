import pandas as pd

class ProphetUnavailable(Exception):
    pass

def _import_prophet():
    try:
        from prophet import Prophet
        return Prophet
    except Exception as e:
        raise ProphetUnavailable(
            "Prophet not installed. pip install prophet (and possibly 'cmdstanpy')."
        ) from e

def fit_and_forecast(history: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    """
    history: DataFrame with columns ['ds','y'] (or commonly ['date','price']).
             'ds' should be datetime-like (daily cadence ideal).
    Returns: DataFrame with ['ds','yhat','yhat_lower','yhat_upper'] for the forecast horizon.
    """
    if history is None or history.empty:
        raise ProphetUnavailable("No history provided for Prophet.")

    df = history.copy()

    # Accept common alternative column names and coerce types
    if "ds" not in df.columns or "y" not in df.columns:
        rename_map = {}
        if "date" in df.columns: rename_map["date"] = "ds"
        if "timestamp" in df.columns: rename_map["timestamp"] = "ds"
        if "price" in df.columns: rename_map["price"] = "y"
        if rename_map:
            df = df.rename(columns=rename_map)

    if "ds" not in df.columns or "y" not in df.columns:
        raise ProphetUnavailable("History must have 'ds' and 'y' columns.")

    # Clean
    df = df[["ds", "y"]].dropna()
    df["ds"] = pd.to_datetime(df["ds"], errors="coerce", utc=True)
    df = df.dropna(subset=["ds", "y"])
    # Prophet prefers tz-naive datetimes
    df["ds"] = df["ds"].dt.tz_localize(None)
    df = df.sort_values("ds").drop_duplicates(subset="ds")

    # Guardrail: need a few points for Prophet to fit meaningfully
    if len(df) < 5:
        raise ProphetUnavailable("Insufficient history for Prophet (need >= 5 rows).")

    # Horizon guardrails
    horizon = int(max(1, horizon_days))

    Prophet = _import_prophet()
    m = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
    m.fit(df)
    future = m.make_future_dataframe(periods=horizon, freq="D", include_history=True)
    fc = m.predict(future)[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    # Return only the forecast horizon (exclude history rows)
    return fc.tail(horizon).reset_index(drop=True)
