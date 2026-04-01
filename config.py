START_DATE = "2010-01-01"

# Dashboard / signal settings
VOTE_THRESHOLD = 0.5
STATE_THRESHOLD = 0.5
DELTA_THRESHOLD = 0.25
MOMENTUM_WINDOW = 20          # trading days, used for "1M change"
CHART_LOOKBACK = 252          # trading days, used for composite trend
DATA_FRESHNESS_MINUTES = 60   # cache TTL for pulled market / macro data
OPENAI_SUMMARY_MODEL = "gpt-5.4-mini"
OPENAI_SUMMARY_MAX_TOKENS = 500
OPENAI_SUMMARY_REASONING_EFFORT = "none"
OPENAI_SUMMARY_VERBOSITY = "low"

LAYERS = {
    "L1_rates_liquidity": ["HYG", "JNK", "KRE", "KBE"],
    "L2_global_growth":   ["COPX", "FCX", "SOXX", "SMH", "IYT", "JETS", "EEM", "VWO"],
    "L3_domestic_cycle":  ["XHB", "ITB", "IWM", "IJR", "XLY", "XLP", "WOOD", "CUT"],
    "L4_risk_appetite":   ["XLF", "XLU", "HYG", "ITA", "XAR", "PPA", "EEM", "IVE", "IVW"],
    "L5_inflation_commodities": ["XLE", "VDE", "CRAK", "MOO", "DBA", "SOIL", "XLB", "GLD"],
    "L6_stress_dislocation":    ["XLU", "TLT", "GLD"],
}

# Extra tickers needed for ratios but not in any layer
RATIO_EXTRAS = ["SPY", "TLT", "LQD", "SOXX"]

RATIOS = [
    ("XLY", "XLP"),
    ("XLF", "XLU"),
    ("IWM", "SPY"),
    ("SOXX", "SPY"),
    ("IVE", "IVW"),
    ("EEM", "SPY"),
    ("HYG", "LQD"),
]

# FRED series: key = FRED ID, value = column name in output DataFrame
# DGS2 now, macro validation series ready for later
FRED_SERIES = {
    "DGS2":     "yield_2yr",
    "HOUST":    "housing_starts",
    "INDPRO":   "industrial_production",
    "CPIAUCSL": "cpi",
}

# Rolling windows used throughout analysis.py
WINDOWS = {
    "short":  20,   # ~1 month
    "medium": 60,   # ~1 quarter
    "long":   252,  # ~1 year — used for percentile rank
}

DATA_DIR = "data"
ETF_PARQUET  = "data/master_etf_prices.parquet"
FRED_PARQUET = "data/fred_data.parquet"
