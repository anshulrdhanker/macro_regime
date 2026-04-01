"""
main.py
Orchestrator. Run this to load/pull data and compute all analysis.

Usage (terminal):
    python main.py              # uses cache if available today
    python main.py --refresh    # force re-pull from APIs

Usage (Jupyter):
    from main import load
    data, analysis = load()

    data["etf_prices"]           # raw adj close prices
    data["fred_data"]            # FRED macro series
    analysis["layer_scores_20d"] # per-layer composite z-scores
    analysis["ratios"]           # XLY/XLP, HYG/LQD, etc.
    analysis["zscore_20d"]       # rolling z-score per ticker
    analysis["pct_rank_252d"]    # 252-day percentile rank per ticker
"""

import argparse

from analysis import run_dashboard_analysis, run_full_analysis
from data_pull import load_or_pull


def load(force_refresh: bool = False, analysis_mode: str = "full") -> tuple[dict, dict]:
    data = load_or_pull(force_refresh=force_refresh)
    if analysis_mode == "dashboard":
        analysis = run_dashboard_analysis(data["etf_prices"])
    elif analysis_mode == "full":
        analysis = run_full_analysis(data["etf_prices"])
    else:
        raise ValueError(f"Unknown analysis_mode: {analysis_mode}")
    return data, analysis


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Force re-pull from APIs")
    args = parser.parse_args()

    data, analysis = load(force_refresh=args.refresh, analysis_mode="full")

    print("\n=== Data Summary ===")
    print(f"ETF prices:  {data['etf_prices'].shape}  ({data['etf_prices'].index[0].date()} → {data['etf_prices'].index[-1].date()})")
    print(f"FRED data:   {data['fred_data'].shape}")

    print("\n=== Analysis Outputs ===")
    for key, df in analysis.items():
        print(f"  {key:25s}  shape={str(df.shape):15s}  columns={list(df.columns[:4])}{'...' if len(df.columns) > 4 else ''}")

    print("\nReady. Import via: from main import load")
