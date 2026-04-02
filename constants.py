"""
constants.py
All display metadata, signs, commentary, and pure helper functions.
No framework dependencies — works with Streamlit, Dash, or plain Python.
"""

# ── Layer metadata ────────────────────────────────────────────────────────────

LAYER_META = {
    "L1_rates_liquidity": {
        "name":      "Credit & Funding Conditions",
        "short":     "Credit",
        "card_label": "Credit",
        "card_desc":  "High yield credit and bank sensitivity.",
        "card_icon": "payments",
        "score_tag_map": {
            "negative": "Deflationary",
            "neutral": "Balanced",
            "positive": "Expansionary",
        },
        "message_map": {
            "negative": "Softer Credit Conditions",
            "neutral": "No Strong Credit Signal",
            "positive": "Easier Credit Conditions",
        },
        "lead":      "3–6 months",
        "lead_desc": "leads credit spreads and Fed policy",
        "etfs":      "HYG · JNK · KRE · KBE",
    },
    "L2_global_growth": {
        "name":      "Global Demand",
        "short":     "Global",
        "card_label": "Global Growth",
        "card_desc":  "Copper, chips, transports, and EM demand.",
        "card_icon": "trending_up",
        "score_tag_map": {
            "negative": "Below Trend",
            "neutral": "Stable",
            "positive": "Above Trend",
        },
        "message_map": {
            "negative": "Weaker Global Demand",
            "neutral": "No Strong Global Signal",
            "positive": "Improving Global Demand",
        },
        "lead":      "6–9 months",
        "lead_desc": "leads global PMI",
        "etfs":      "COPX · FCX · SOXX · SMH · IYT · JETS · EEM · VWO",
    },
    "L3_domestic_cycle": {
        "name":      "US Consumer & Housing",
        "short":     "US",
        "card_label": "Consumer & Housing",
        "card_desc":  "Homebuilders, small caps, and consumer demand.",
        "card_icon": "home",
        "score_tag_map": {
            "negative": "Slowing",
            "neutral": "Stable",
            "positive": "Expansionary",
        },
        "message_map": {
            "negative": "Softer Domestic Demand",
            "neutral": "No Strong Domestic Signal",
            "positive": "Improving Domestic Demand",
        },
        "lead":      "6–12 months",
        "lead_desc": "leads US GDP",
        "etfs":      "XHB · ITB · IWM · IJR · XLY · XLP · WOOD · CUT",
    },
    "L4_risk_appetite": {
        "name":      "Risk Appetite",
        "short":     "Risk",
        "card_label": "Risk Appetite",
        "card_desc":  "Cyclicals vs defensives across the tape.",
        "card_icon": "monitoring",
        "score_tag_map": {
            "negative": "Risk Off",
            "neutral": "Mixed",
            "positive": "Risk On",
        },
        "message_map": {
            "negative": "Risk Appetite Is Fading",
            "neutral": "Risk Appetite Is Mixed",
            "positive": "Risk Appetite Is Improving",
        },
        "lead":      "3–6 months",
        "lead_desc": "leads earnings revisions",
        "etfs":      "XLF · XLU · HYG · ITA · XAR · PPA · EEM · IVE · IVW",
    },
    "L5_inflation_commodities": {
        "name":      "Inflation Pressure",
        "short":     "Inflation",
        "card_label": "Inflation",
        "card_desc":  "Energy, materials, metals, and ags.",
        "card_icon": "show_chart",
        "score_tag_map": {
            "negative": "Disinflation",
            "neutral": "Stable",
            "positive": "Inflationary",
        },
        "message_map": {
            "negative": "Inflation Pressure Is Easing",
            "neutral": "No Strong Inflation Signal",
            "positive": "Inflation Pressure Is Building",
        },
        "lead":      "9–12 months",
        "lead_desc": "leads CPI",
        "etfs":      "XLE · VDE · CRAK · MOO · DBA · SOIL · XLB · GLD",
    },
    "L6_stress_dislocation": {
        "name":      "Stress & Fragility",
        "short":     "Stress",
        "card_label": "System Stress",
        "card_desc":  "Bonds, gold, and defensives as safety trades.",
        "card_icon": "bolt",
        "score_tag_map": {
            "negative": "Fragile",
            "neutral": "Stable",
            "positive": "Orderly",
        },
        "message_map": {
            "negative": "Stress Is Building",
            "neutral": "Stress Is Contained",
            "positive": "Stress Is Easing",
        },
        "lead":      "1–3 months",
        "lead_desc": "early warning on systemic risk",
        "etfs":      "XLU · TLT · GLD",
    },
}

LAYER_SIGNS = {
    "L1_rates_liquidity":       +1,
    "L2_global_growth":         +1,
    "L3_domestic_cycle":        +1,
    "L4_risk_appetite":         +1,
    "L5_inflation_commodities": +1,
    "L6_stress_dislocation":    -1,
}


# ── Pure helper functions ─────────────────────────────────────────────────────

def score_color(v: float) -> str:
    if v >= 2:    return "#00d48a"
    if v >= 0.5:  return "#4a9e6e"
    if v >= -0.5: return "#505050"
    if v >= -2:   return "#d85c5c"
    return "#ef4444"


def border_color(v: float) -> str:
    if v >= 0.5:  return "#1a4a2e"
    if v >= -0.5: return "#1e1e1e"
    return "#5a1c1c"


def regime_label(d: int) -> tuple[str, str]:
    if d >= 3:  return "Expansion",          "#00d48a"
    if d >= 1:  return "Mild Expansion",     "#4a9e6e"
    if d >= -1: return "Transitional",       "#505050"
    if d >= -3: return "Contraction",        "#d85c5c"
    return "Severe Contraction", "#ef4444"


def direction_info(delta: int) -> tuple[str, str, str]:
    """Returns (arrow, word, color)."""
    if delta >= 3:  return "↑↑", "accelerating higher",   "#00d48a"
    if delta >= 1:  return "↑",  "improving",             "#4a9e6e"
    if delta == 0:  return "→",  "unchanged",             "#606060"
    if delta >= -2: return "↓",  "deteriorating",         "#d85c5c"
    return "↓↓", "sharply deteriorating", "#ef4444"


def _format_layer_list(layer_names: list[str]) -> str:
    labels = [LAYER_META.get(name, {}).get("name", name) for name in layer_names]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def build_macro_summary(
    composite_score: int,
    delta: int,
    layer_votes: dict[str, int],
    signed_scores: dict[str, float],
    layer_delta: dict[str, float],
) -> dict[str, object]:
    risk_off_count = sum(1 for vote in layer_votes.values() if vote == -1)
    neutral_count = sum(1 for vote in layer_votes.values() if vote == 0)
    risk_on_count = sum(1 for vote in layer_votes.values() if vote == 1)

    strongest_neg = [
        name for name, score in sorted(signed_scores.items(), key=lambda item: item[1])
        if score < -0.5
    ][:2]
    strongest_pos = [
        name for name, score in sorted(signed_scores.items(), key=lambda item: item[1], reverse=True)
        if score > 0.5
    ][:2]
    divergence = bool(strongest_neg and strongest_pos)

    if divergence:
        confirmation = "Split tape"
    elif max(risk_off_count, risk_on_count) >= 5:
        confirmation = "Broad confirmation"
    elif max(risk_off_count, risk_on_count) >= 4 and neutral_count <= 1:
        confirmation = "Good confirmation"
    else:
        confirmation = "Narrow confirmation"

    if strongest_neg and strongest_pos:
        balance_text = (
            f"Weakness is concentrated in {_format_layer_list(strongest_neg)}, while "
            f"{_format_layer_list(strongest_pos)} is the main offset."
        )
    elif strongest_neg:
        balance_text = f"The main drag is {_format_layer_list(strongest_neg)}."
    elif strongest_pos:
        balance_text = f"Leadership is concentrated in {_format_layer_list(strongest_pos)}."
    else:
        balance_text = "No layer is giving a strong directional message yet."

    stress_vote = layer_votes.get("L6_stress_dislocation", 0)
    inflation_vote = layer_votes.get("L5_inflation_commodities", 0)
    credit_vote = layer_votes.get("L1_rates_liquidity", 0)
    risk_vote = layer_votes.get("L4_risk_appetite", 0)

    biggest_improve = max(layer_delta, key=layer_delta.get)
    biggest_deterioration = min(layer_delta, key=layer_delta.get)

    if composite_score <= -4:
        bottom_line = (
            f"Equities are pricing a contraction led by {_format_layer_list(strongest_neg or list(layer_votes.keys())[:2])}."
        )
    elif composite_score <= -2:
        bottom_line = (
            f"Equities are pricing a slowdown led by {_format_layer_list(strongest_neg or list(layer_votes.keys())[:2])}."
        )
    elif composite_score >= 4:
        bottom_line = (
            f"Equities are pricing an expansion with leadership from {_format_layer_list(strongest_pos or list(layer_votes.keys())[:2])}."
        )
    elif composite_score >= 2:
        bottom_line = (
            f"Equities are leaning toward expansion, with leadership strongest in {_format_layer_list(strongest_pos or list(layer_votes.keys())[:2])}."
        )
    else:
        bottom_line = "Equities are pricing a transitional macro backdrop with no broad regime dominance yet."

    if composite_score < 0 and stress_vote == 1:
        bottom_line += " Stress has not fully confirmed the slowdown yet."
    elif composite_score < 0 and stress_vote == -1:
        bottom_line += " Defensive assets are now confirming the move."
    elif composite_score > 0 and credit_vote == 1 and risk_vote == 1:
        bottom_line += " Credit and risk appetite are confirming the move."

    if delta <= -3:
        change_text = (
            f"The barometer has deteriorated sharply over the last month, with the biggest rollover in "
            f"{LAYER_META[biggest_deterioration]['name']}."
        )
    elif delta < 0:
        change_text = (
            f"The barometer is weakening versus one month ago, led lower by "
            f"{LAYER_META[biggest_deterioration]['name']}."
        )
    elif delta >= 3:
        change_text = (
            f"The barometer has improved sharply over the last month, led by "
            f"{LAYER_META[biggest_improve]['name']}."
        )
    elif delta > 0:
        change_text = (
            f"The barometer is improving modestly versus one month ago, with the best follow-through in "
            f"{LAYER_META[biggest_improve]['name']}."
        )
    else:
        change_text = "The barometer is little changed over the last month. Leadership has not materially broadened."

    if inflation_vote == 1 and composite_score < 0:
        watch = "Inflation-sensitive assets are not rolling over with growth. Watch for a stagflation-style split."
    elif stress_vote == 1 and composite_score < 0:
        watch = "Watch whether stress indicators start joining the slowdown. That would make the signal materially more severe."
    elif credit_vote == 1 and composite_score > 0:
        watch = "Watch credit first. If it keeps confirming, the expansion signal should broaden."
    else:
        watch = "Watch credit and risk appetite first. They should confirm the next regime move."

    drivers = [
        f"{LAYER_META[name]['short']} {signed_scores[name]:+.1f}σ"
        for name in strongest_neg + strongest_pos
    ]

    return {
        "signal_balance": confirmation,
        "breadth": f"{risk_off_count} risk-off / {risk_on_count} risk-on / {neutral_count} neutral",
        "bottom_line": bottom_line,
        "confirmation": balance_text,
        "what_changed": change_text,
        "watch": watch,
        "biggest_positive": LAYER_META[biggest_improve]["name"],
        "biggest_negative": LAYER_META[biggest_deterioration]["name"],
        "drivers": drivers,
    }


def hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
