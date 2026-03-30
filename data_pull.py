"""
data_pull.py
Fetches ETF prices (yfinance) and FRED macro series, caches to parquet.
Cache logic: if the parquet file was written today, load from disk.
             Otherwise, hit the APIs and overwrite.
"""

import os
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from fredapi import Fred

from config import (
    DATA_DIR, ETF_PARQUET, FRED_PARQUET,
    FRED_SERIES, LAYERS, RATIO_EXTRAS, START_DATE,
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


def _is_cached_today(filepath: str) -> bool:
    path = Path(filepath)
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime).date()
    return mtime == date.today()


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
    print(f"[data_pull] ETF data shape: {prices.shape}")
    return prices


def fetch_fred_data(series_dict: dict[str, str], start: str) -> pd.DataFrame:
    """
    Returns a DataFrame of FRED macro series.
    Index: DatetimeIndex
    Columns: human-readable names from series_dict values
    """
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "FRED_API_KEY not set. Add it to your .env file. "
            "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
        )

    fred = Fred(api_key=api_key)
    frames = {}
    for fred_id, col_name in series_dict.items():
        print(f"[data_pull] Fetching FRED series: {fred_id} → {col_name}")
        s = fred.get_series(fred_id, observation_start=start)
        frames[col_name] = s

    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
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

    If both parquet files were written today and force_refresh=False,
    loads from disk. Otherwise hits the APIs and saves to disk.
    """
    Path(DATA_DIR).mkdir(exist_ok=True)

    etf_cached  = _is_cached_today(ETF_PARQUET)
    fred_cached = _is_cached_today(FRED_PARQUET)

    if not force_refresh and etf_cached and fred_cached:
        print("[data_pull] Cache is current. Loading from disk...")
        etf_prices = pd.read_parquet(ETF_PARQUET)
        fred_data  = pd.read_parquet(FRED_PARQUET)
    else:
        tickers    = _all_etf_tickers()
        etf_prices = fetch_etf_prices(tickers, START_DATE)
        fred_data  = fetch_fred_data(FRED_SERIES, START_DATE)

        etf_prices.to_parquet(ETF_PARQUET)
        fred_data.to_parquet(FRED_PARQUET)
        print(f"[data_pull] Saved → {ETF_PARQUET}, {FRED_PARQUET}")

    return {"etf_prices": etf_prices, "fred_data": fred_data}
