"""
analysis.py
Computes returns, rolling z-scores, percentile ranks, ratio series,
and per-layer composite scores from the master price DataFrame.

All functions are pure (no side effects) and return DataFrames so they
compose cleanly in Jupyter notebooks.
"""

import numpy as np
import pandas as pd

from config import LAYERS, RATIOS, WINDOWS


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------

def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Multi-period returns for every ticker.
    Returns a DataFrame with MultiIndex columns: (ticker, period).
    Periods: '1d', '5d', '20d', '60d'
    """
    periods = {"1d": 1, "5d": 5, "20d": 20, "60d": 60}
    frames = {}
    for label, n in periods.items():
        frames[label] = prices.pct_change(n)

    return pd.concat(frames, axis=1).swaplevel(axis=1).sort_index(axis=1)
    # columns: MultiIndex (ticker, period)


# ---------------------------------------------------------------------------
# Rolling z-score
# ---------------------------------------------------------------------------

def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    roll = series.rolling(window, min_periods=window // 2)
    return (series - roll.mean()) / roll.std()


def compute_rolling_zscores(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Returns z-scores of 1-day returns over two rolling windows.
        {
            "zscore_20d":  DataFrame (date × ticker),
            "zscore_60d":  DataFrame (date × ticker),
        }
    daily_returns are used as the input series so z-score = how extreme
    today's move is relative to the trailing window's distribution.
    """
    daily_returns = prices.pct_change(1)
    short_w  = WINDOWS["short"]   # 20
    medium_w = WINDOWS["medium"]  # 60

    zscore_20 = daily_returns.apply(_rolling_zscore, window=short_w)
    zscore_60 = daily_returns.apply(_rolling_zscore, window=medium_w)

    return {"zscore_20d": zscore_20, "zscore_60d": zscore_60}


# ---------------------------------------------------------------------------
# Percentile rank (252-day rolling)
# ---------------------------------------------------------------------------

def compute_percentile_ranks(prices: pd.DataFrame) -> pd.DataFrame:
    """
    For each ticker, rolling 252-day percentile rank of the 1-day return.
    Interpretation: 0.9 means today's return is in the 90th percentile
    of the past year — useful for spotting extreme moves in context.

    Note: .apply() with a 252-window is slow for 40+ tickers × 15 years.
    Expect ~30s on first run. Result is cached in main.py.
    """
    window = WINDOWS["long"]  # 252
    daily_returns = prices.pct_change(1)

    def _pct_rank(x: np.ndarray) -> float:
        return pd.Series(x).rank(pct=True).iloc[-1]

    print("[analysis] Computing 252-day percentile ranks (slow, one-time)...")
    ranks = daily_returns.rolling(window, min_periods=window // 2).apply(
        _pct_rank, raw=False
    )
    return ranks


# ---------------------------------------------------------------------------
# Ratio series
# ---------------------------------------------------------------------------

def compute_ratios(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Computes A/B price ratios for each pair in RATIOS.
    Columns named 'A_B' (e.g. 'XLY_XLP').
    """
    frames = {}
    for a, b in RATIOS:
        if a not in prices.columns or b not in prices.columns:
            print(f"[analysis] Warning: {a} or {b} missing from prices, skipping ratio.")
            continue
        col_name = f"{a}_{b}"
        frames[col_name] = prices[a] / prices[b]

    return pd.DataFrame(frames)


def compute_ratio_zscores(ratio_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Z-scores of ratio daily returns, same 20d/60d windows as tickers."""
    daily = ratio_df.pct_change(1)
    short_w  = WINDOWS["short"]
    medium_w = WINDOWS["medium"]

    return {
        "ratio_zscore_20d": daily.apply(_rolling_zscore, window=short_w),
        "ratio_zscore_60d": daily.apply(_rolling_zscore, window=medium_w),
    }


# ---------------------------------------------------------------------------
# Layer composite scores
# ---------------------------------------------------------------------------

def compute_layer_scores(zscore_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each layer, equal-weight average of member z-scores → single score per day.
    Positive = layer is risk-on; Negative = risk-off / stressed.

    Input: zscore_df with columns = ticker symbols (e.g. zscore_20d output).
    Returns: DataFrame with columns = layer names.
    """
    scores = {}
    for layer_name, members in LAYERS.items():
        available = [t for t in members if t in zscore_df.columns]
        if not available:
            continue
        scores[layer_name] = zscore_df[available].mean(axis=1)

    return pd.DataFrame(scores)


# ---------------------------------------------------------------------------
# Master entry point
# ---------------------------------------------------------------------------

def run_full_analysis(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Runs all computations and returns a dict of clean DataFrames.

    Keys:
        returns          — MultiIndex (ticker, period), all return windows
        zscore_20d       — 20-day rolling z-score of daily returns
        zscore_60d       — 60-day rolling z-score of daily returns
        pct_rank_252d    — 252-day rolling percentile rank of daily returns
        ratios           — price ratios (A/B)
        ratio_zscore_20d — z-score of ratio daily returns, 20d window
        ratio_zscore_60d — z-score of ratio daily returns, 60d window
        layer_scores_20d — per-layer composite z-score (20d)
        layer_scores_60d — per-layer composite z-score (60d)
    """
    print("[analysis] Running full analysis pipeline...")

    returns    = compute_returns(prices)
    zscores    = compute_rolling_zscores(prices)
    pct_ranks  = compute_percentile_ranks(prices)
    ratios     = compute_ratios(prices)
    ratio_z    = compute_ratio_zscores(ratios)
    layer_20   = compute_layer_scores(zscores["zscore_20d"])
    layer_60   = compute_layer_scores(zscores["zscore_60d"])

    print("[analysis] Done.")

    return {
        "returns":           returns,
        "zscore_20d":        zscores["zscore_20d"],
        "zscore_60d":        zscores["zscore_60d"],
        "pct_rank_252d":     pct_ranks,
        "ratios":            ratios,
        "ratio_zscore_20d":  ratio_z["ratio_zscore_20d"],
        "ratio_zscore_60d":  ratio_z["ratio_zscore_60d"],
        "layer_scores_20d":  layer_20,
        "layer_scores_60d":  layer_60,
    }
