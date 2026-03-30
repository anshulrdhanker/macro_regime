START_DATE = "2010-01-01"

LAYERS = {
    "L1_rates_liquidity": ["HYG", "JNK", "SGOV", "BIL", "SHV", "KRE", "KBE"],
    "L2_global_growth":   ["COPX", "FCX", "SOXX", "SMH", "IYT", "JETS", "EEM", "VWO"],
    "L3_domestic_cycle":  ["XHB", "ITB", "IWM", "IJR", "XLY", "XLP", "WOOD", "CUT"],
    "L4_risk_appetite":   ["XLF", "XLU", "HYG", "ITA", "XAR", "PPA", "EEM", "IVE", "IVW"],
    "L5_inflation_commodities": ["XLE", "VDE", "CRAK", "MOO", "DBA", "SOIL", "XLB", "GLD"],
    "L6_stress_dislocation":    ["KRE", "XLF", "IWM", "SPY", "HYG", "JNK", "XLU", "TLT"],
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
    "NAPM":     "ism_manufacturing",
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
