"""
data_pull.py
Fetches ETF prices (yfinance) and FRED macro series, caches to parquet.
Cache logic: reuse parquet files while they are fresh, otherwise refresh.
If refresh fails, fall back to any existing cached files.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from config import (
    DATA_DIR, ETF_PARQUET, FRED_PARQUET,
    DATA_FRESHNESS_MINUTES, FRED_SERIES, LAYERS, RATIO_EXTRAS, START_DATE,
)

load_dotenv()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_etf_tickers() -> list[str]:
    """Deduplicated union of all layer tickers + ratio extras."""
    tickers = set()
    for members in LAYERS.values():
        tickers.update(members)
    tickers.update(RATIO_EXTRAS)
    return sorted(tickers)


def _is_cache_fresh(filepath: str, freshness_minutes: int) -> bool:
    path = Path(filepath)
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    max_age = timedelta(minutes=freshness_minutes)
    return datetime.now() - mtime <= max_age


def _cache_timestamp(filepath: str) -> Optional[datetime]:
    path = Path(filepath)
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime)


def _load_cached_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_parquet(ETF_PARQUET), pd.read_parquet(FRED_PARQUET)


def _build_data_status(source: str, detail: str = "", error: str = "") -> dict[str, object]:
    etf_ts = _cache_timestamp(ETF_PARQUET)
    fred_ts = _cache_timestamp(FRED_PARQUET)
    return {
        "source": source,
        "detail": detail,
        "error": error,
        "freshness_minutes": DATA_FRESHNESS_MINUTES,
        "etf_timestamp": etf_ts.isoformat() if etf_ts else None,
        "fred_timestamp": fred_ts.isoformat() if fred_ts else None,
    }


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def fetch_etf_prices(tickers: list[str], start: str) -> pd.DataFrame:
    """
    Returns a DataFrame of adjusted close prices.
    Index: DatetimeIndex (business days)
    Columns: ticker symbols
    Tickers with no data for the full window (e.g. CRAK launched 2015) will
    simply have NaN before their inception date.
    """
    print(f"[data_pull] Downloading {len(tickers)} ETFs from yfinance (start={start})...")
    raw = yf.download(
        tickers,
        start=start,
        auto_adjust=True,
        progress=True,
        threads=True,
    )
    # yf returns MultiIndex columns when >1 ticker; flatten to just Close
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]]
        prices.columns = tickers

    prices.index = pd.to_datetime(prices.index)
    prices.index.name = "date"
    if prices.empty or prices.dropna(how="all").empty:
        raise ValueError("ETF download returned no usable price history.")
    print(f"[data_pull] ETF data shape: {prices.shape}")
    return prices


def fetch_fred_data(series_dict: dict[str, str], start: str) -> pd.DataFrame:
    """
    Returns a DataFrame of FRED macro series via direct REST API calls.
    Index: DatetimeIndex
    Columns: human-readable names from series_dict values
    """
    import requests

    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "FRED_API_KEY not set. Add it to your .env file. "
            "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
        )

    frames = {}
    for fred_id, col_name in series_dict.items():
        print(f"[data_pull] Fetching FRED series: {fred_id} → {col_name}")
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id":        fred_id,
                "api_key":          api_key,
                "file_type":        "json",
                "observation_start": start,
            },
        )
        r.raise_for_status()
        observations = r.json()["observations"]
        s = pd.Series(
            {obs["date"]: pd.to_numeric(obs["value"], errors="coerce")
             for obs in observations},
            name=col_name,
        )
        s.index = pd.to_datetime(s.index)
        frames[col_name] = s

    df = pd.DataFrame(frames)
    df.index.name = "date"
    print(f"[data_pull] FRED data shape: {df.shape}")
    return df


# ---------------------------------------------------------------------------
# Cache-aware loader
# ---------------------------------------------------------------------------

def load_or_pull(force_refresh: bool = False) -> dict[str, pd.DataFrame]:
    """
    Returns:
        {
            "etf_prices": pd.DataFrame,  # adj close, all tickers
            "fred_data":  pd.DataFrame,  # FRED macro series
        }

    Uses fresh cache when available. Otherwise hits the APIs and saves to disk.
    If refresh fails but cached files exist, falls back to stale cache.
    """
    Path(DATA_DIR).mkdir(exist_ok=True)

    etf_cached = _is_cache_fresh(ETF_PARQUET, DATA_FRESHNESS_MINUTES)
    fred_cached = _is_cache_fresh(FRED_PARQUET, DATA_FRESHNESS_MINUTES)
    cache_available = Path(ETF_PARQUET).exists() and Path(FRED_PARQUET).exists()

    if not force_refresh and etf_cached and fred_cached:
        print("[data_pull] Fresh cache available. Loading from disk...")
        etf_prices, fred_data = _load_cached_data()
        data_status = _build_data_status("cache_fresh", "Loaded fresh cached market and macro data.")
        return {"etf_prices": etf_prices, "fred_data": fred_data, "data_status": data_status}

    try:
        tickers = _all_etf_tickers()
        etf_prices = fetch_etf_prices(tickers, START_DATE)
        fred_data = fetch_fred_data(FRED_SERIES, START_DATE)

        etf_prices.to_parquet(ETF_PARQUET)
        fred_data.to_parquet(FRED_PARQUET)
        print(f"[data_pull] Saved → {ETF_PARQUET}, {FRED_PARQUET}")
        detail = "Forced refresh from APIs." if force_refresh else "Cache was stale. Refreshed from APIs."
        data_status = _build_data_status("live_refresh", detail)
        return {"etf_prices": etf_prices, "fred_data": fred_data, "data_status": data_status}
    except Exception as exc:
        if not cache_available:
            raise
        print(f"[data_pull] Refresh failed. Falling back to cached files. Error: {exc}")
        etf_prices, fred_data = _load_cached_data()
        data_status = _build_data_status(
            "stale_cache_fallback",
            "Live refresh failed. Using cached market and macro data.",
            error=str(exc),
        )
        return {"etf_prices": etf_prices, "fred_data": fred_data, "data_status": data_status}
