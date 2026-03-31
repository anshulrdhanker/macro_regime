"""
app.py — Macro Barometer Dashboard
Run with: streamlit run app.py
"""

import json
import os

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from config import LAYERS
from main import load

load_dotenv()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Macro Barometer",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Metadata — plain English names, descriptions, lead times
# ---------------------------------------------------------------------------
LAYER_META = {
    "L1_rates_liquidity": {
        "name":        "Credit & Banking",
        "etfs":        "HYG · JNK · KRE · KBE",
        "what_it_is":  "High yield bonds and regional bank stocks.",
        "why_it_leads":"When credit spreads tighten and banks rally, capital is cheap and flowing freely — the economy expands. When they break down, lending dries up 3–6 months before it shows in GDP.",
        "lead":        "3–6 months",
        "inverted":    False,
    },
    "L2_global_growth": {
        "name":        "Global Manufacturing & Trade",
        "etfs":        "COPX · FCX · SOXX · SMH · IYT · JETS · EEM · VWO",
        "what_it_is":  "Copper miners, semiconductors, transport, airlines, emerging markets.",
        "why_it_leads":"Copper goes into everything — construction, EVs, factories. When miners rally, someone big is ordering material. Chips lead tech capex. Together they price global GDP 6–9 months out.",
        "lead":        "6–9 months",
        "inverted":    False,
    },
    "L3_domestic_cycle": {
        "name":        "Domestic Economy",
        "etfs":        "XHB · ITB · IWM · IJR · XLY · XLP · WOOD · CUT",
        "what_it_is":  "Homebuilders, small caps, consumer discretionary, timber.",
        "why_it_leads":"Homebuilders price in mortgage demand before permits are filed. Small caps live and die by domestic credit — they have no offshore revenue to hide behind. Leads housing starts by 6–12 months.",
        "lead":        "6–12 months",
        "inverted":    False,
    },
    "L4_risk_appetite": {
        "name":        "Risk Appetite",
        "etfs":        "XLF · XLU · HYG · ITA · XAR · PPA · EEM · IVE · IVW",
        "what_it_is":  "Financials vs. defensives, growth vs. value, defense sector.",
        "why_it_leads":"When financials outperform utilities and growth beats value, institutions are reaching for return. When that reverses, they're reducing exposure — usually before the data confirms it.",
        "lead":        "3–6 months",
        "inverted":    False,
    },
    "L5_inflation_commodities": {
        "name":        "Inflation & Real Assets",
        "etfs":        "XLE · VDE · CRAK · MOO · DBA · SOIL · XLB · GLD",
        "what_it_is":  "Energy, refiners, agriculture, fertilizers, materials, gold.",
        "why_it_leads":"Hard assets rally when inflation expectations rise or when supply shocks hit. If commodities are strong while growth weakens, that's stagflation — the worst macro environment for equities.",
        "lead":        "3–9 months",
        "inverted":    False,
    },
    "L6_stress_dislocation": {
        "name":        "Flight to Safety",
        "etfs":        "XLU · TLT · GLD",
        "what_it_is":  "Utilities, long-duration Treasury bonds, gold.",
        "why_it_leads":"When these three rally together, capital is running from risk — not rotating, fleeing. It's the oldest signal in markets. A sustained bid in all three simultaneously is a stress indicator, not a sector call.",
        "lead":        "1–3 months",
        "inverted":    True,
    },
}

RATIO_META = {
    "XLY_XLP": {
        "name":   "Consumer Discretionary vs. Staples",
        "signal": "Are consumers spending on wants or needs?",
        "high":   "Investors expect consumers to keep spending — expansion.",
        "low":    "Rotation to necessities — consumers pulling back.",
    },
    "XLF_XLU": {
        "name":   "Financials vs. Utilities",
        "signal": "Is credit expanding or contracting?",
        "high":   "Banks outperforming — credit is flowing, economy accelerating.",
        "low":    "Utilities winning — safety trade, credit stress ahead.",
    },
    "IWM_SPY": {
        "name":   "Small Caps vs. S&P 500",
        "signal": "Domestic growth confidence vs. large-cap safety.",
        "high":   "Small caps leading — domestic economy healthy.",
        "low":    "Flight to large-cap quality — domestic stress signal.",
    },
    "SOXX_SPY": {
        "name":   "Semiconductors vs. Broad Market",
        "signal": "Tech capex cycle — leads 6–12 months.",
        "high":   "Chips outperforming — corporate capex expanding ahead.",
        "low":    "Chips lagging — tech spending contraction coming.",
    },
    "IVE_IVW": {
        "name":   "Value vs. Growth",
        "signal": "Where is institutional money rotating?",
        "high":   "Value winning — defensive rotation, late-cycle behavior.",
        "low":    "Growth winning — risk-on, early-to-mid cycle.",
    },
    "EEM_SPY": {
        "name":   "Emerging Markets vs. US",
        "signal": "Global growth optimism vs. US safety trade.",
        "high":   "EM outperforming — global expansion, dollar weakening.",
        "low":    "Capital repatriating to US — global stress or dollar strength.",
    },
    "HYG_LQD": {
        "name":   "High Yield vs. Investment Grade",
        "signal": "Credit spread proxy — the market's stress gauge.",
        "high":   "Spreads tight — risk appetite healthy, no credit stress.",
        "low":    "Spreads widening — credit stress, tightening ahead.",
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

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp { background-color: #080808; color: #d8d8d8; }
    .block-container { padding: 2rem 3rem; max-width: 1440px; }
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Zone 1: Hero ── */
    .hero {
        background: #0d0d0d;
        border: 1px solid #181818;
        border-radius: 20px;
        padding: 2.75rem 3rem;
        margin-bottom: 2.5rem;
        display: flex;
        align-items: center;
        gap: 4rem;
    }
    .hero-left { min-width: 160px; }
    .hero-eyebrow {
        font-size: 0.6rem;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #383838;
        margin-bottom: 0.3rem;
    }
    .hero-score {
        font-size: 7.5rem;
        font-weight: 700;
        line-height: 0.9;
        letter-spacing: -5px;
    }
    .hero-denom {
        font-size: 0.6rem;
        letter-spacing: 0.12em;
        color: #2a2a2a;
        margin-top: 0.5rem;
        text-transform: uppercase;
    }
    .hero-regime {
        font-size: 1.75rem;
        font-weight: 600;
        letter-spacing: -0.3px;
        margin-bottom: 0.65rem;
    }
    .hero-summary {
        font-size: 0.98rem;
        color: #787878;
        line-height: 1.7;
        max-width: 700px;
        font-weight: 300;
    }
    .hero-meta {
        font-size: 0.65rem;
        color: #242424;
        margin-top: 1.2rem;
        letter-spacing: 0.06em;
    }

    /* ── Section label ── */
    .section-label {
        font-size: 0.58rem;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #2c2c2c;
        margin: 0 0 1.25rem 0;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid #131313;
    }

    /* ── Zone 2: Layer cards ── */
    .layer-card {
        background: #0d0d0d;
        border: 1px solid #181818;
        border-left: 3px solid #222;
        border-radius: 16px;
        padding: 1.6rem 1.75rem 1.4rem;
        margin-bottom: 1rem;
    }
    .layer-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.2rem;
    }
    .layer-name {
        font-size: 0.9rem;
        font-weight: 600;
        color: #c0c0c0;
        letter-spacing: -0.2px;
    }
    .layer-z {
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        line-height: 1;
    }
    .layer-etfs {
        font-size: 0.6rem;
        color: #2e2e2e;
        letter-spacing: 0.06em;
        margin-bottom: 0.9rem;
    }
    .layer-sentence {
        font-size: 0.82rem;
        color: #686868;
        line-height: 1.6;
        font-weight: 300;
        margin-bottom: 0.9rem;
    }
    /* Center-anchored Z-bar */
    .zbar-track {
        height: 2px;
        background: #181818;
        border-radius: 2px;
        position: relative;
    }
    .zbar-tick {
        position: absolute;
        left: 50%;
        top: -3px;
        width: 1px;
        height: 8px;
        background: #2a2a2a;
        transform: translateX(-50%);
    }
    .zbar-fill {
        position: absolute;
        top: 0;
        height: 100%;
        border-radius: 2px;
    }

    /* ── Zone 3: Ratio cards ── */
    .ratio-card {
        background: #0d0d0d;
        border: 1px solid #181818;
        border-radius: 14px;
        padding: 1.3rem 1.4rem 1.1rem;
        margin-bottom: 0.75rem;
    }
    .ratio-name {
        font-size: 0.75rem;
        font-weight: 500;
        color: #a0a0a0;
        margin-bottom: 0.15rem;
    }
    .ratio-signal-q {
        font-size: 0.65rem;
        color: #333;
        margin-bottom: 0.8rem;
        font-style: italic;
    }
    .ratio-val-row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 0.5rem;
    }
    .ratio-val {
        font-size: 1.3rem;
        font-weight: 600;
        letter-spacing: -0.3px;
    }
    .ratio-z-badge {
        font-size: 0.65rem;
        font-weight: 500;
        letter-spacing: 0.04em;
    }
    /* Percentile track */
    .pct-track {
        height: 2px;
        background: #181818;
        border-radius: 2px;
        position: relative;
        margin-bottom: 0.35rem;
    }
    .pct-dot {
        position: absolute;
        top: 50%;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        transform: translate(-50%, -50%);
    }
    .ratio-interp {
        font-size: 0.65rem;
        color: #383838;
        line-height: 1.5;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def score_color(v: float) -> str:
    if v >= 2:    return "#00d48a"
    if v >= 0.5:  return "#4a9e6e"
    if v >= -0.5: return "#505050"
    if v >= -2:   return "#c07050"
    return "#e04040"


def border_color(v: float) -> str:
    if v >= 0.5:  return "#00d48a"
    if v >= -0.5: return "#1e1e1e"
    return "#e04040"


def regime_label(d: int) -> tuple[str, str]:
    if d >= 3:  return "Expansion",           "#00d48a"
    if d >= 1:  return "Mild Expansion",      "#4a9e6e"
    if d >= -1: return "Transitional",        "#505050"
    if d >= -3: return "Contraction",         "#c07050"
    return "Severe Contraction", "#e04040"


def zbar_html(z: float, color: str) -> str:
    """Center-anchored bar: fills left (negative) or right (positive) from center."""
    fill_pct = min(abs(z) / 3.0 * 50, 50)
    if z >= 0:
        style = f"left:50%;width:{fill_pct:.1f}%;background:{color};"
    else:
        style = f"right:50%;width:{fill_pct:.1f}%;background:{color};"
    return f"""
    <div class="zbar-track">
        <div class="zbar-tick"></div>
        <div class="zbar-fill" style="{style}"></div>
    </div>"""


@st.cache_data(ttl=3600, show_spinner=False)
def get_ai_content(snapshot_json: str) -> dict:
    """
    Single OpenAI call returning:
      - summary: one sentence for Zone 1
      - layers: dict of layer_name -> one sentence
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"summary": "", "layers": {}}

    snapshot = json.loads(snapshot_json)

    layer_lines = []
    for layer_name, meta in LAYER_META.items():
        z = snapshot["layers"][layer_name]
        layer_lines.append(
            f"- {meta['name']} ({meta['etfs']}): Z={z:+.2f}. "
            f"Lead time {meta['lead']}. "
            f"Context: {meta['why_it_leads']}"
        )

    ratio_lines = []
    for col, z in snapshot["ratios"].items():
        meta = RATIO_META.get(col, {})
        ratio_lines.append(f"- {meta.get('name', col)}: Z={z:+.2f}")

    prompt = f"""You are a senior macro strategist briefing a portfolio manager.

Today's macro snapshot:
Composite regime score: {snapshot['composite']}/6

Layer signals:
{chr(10).join(layer_lines)}

Key ratio Z-scores:
{chr(10).join(ratio_lines)}

Return a JSON object with exactly these keys:
1. "summary": ONE sentence (max 30 words) summarizing the macro regime. Name specific stressed layers. No hedging.
2. "layers": an object where each key is a layer name and the value is ONE sentence (max 20 words) explaining what the current reading means for the economy — not the number, the implication. Be specific. Present tense.

Layer name keys must be exactly: L1_rates_liquidity, L2_global_growth, L3_domestic_cycle, L4_risk_appetite, L5_inflation_commodities, L6_stress_dislocation

Return only valid JSON, no markdown."""

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"summary": "", "layers": {}}


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    return load()


with st.spinner(""):
    data, analysis = load_data()

layer_60      = analysis["layer_scores_60d"]
zscore_regime = analysis["zscore_regime"]
ratios        = analysis["ratios"]
ratio_z60     = analysis["ratio_zscore_60d"]

signed = layer_60.copy()
for col, sign in LAYER_SIGNS.items():
    signed[col] = signed[col] * sign

THRESHOLD = 0.5
discrete_signals = signed.apply(
    lambda col: np.where(col > THRESHOLD, 1, np.where(col < -THRESHOLD, -1, 0))
)
composite_discrete = pd.Series(discrete_signals.sum(axis=1), index=layer_60.index)

today_date    = layer_60.index[-1]
today_layers  = layer_60.iloc[-1]
today_disc    = int(composite_discrete.iloc[-1])
today_ratios  = ratios.iloc[-1]
today_ratio_z = ratio_z60.iloc[-1]

regime_text, regime_color = regime_label(today_disc)

# Build snapshot for OpenAI (serializable)
snapshot = {
    "composite": today_disc,
    "layers":    {k: round(float(today_layers[k]), 3) for k in layer_60.columns},
    "ratios":    {k: round(float(today_ratio_z[k]), 3) for k in ratio_z60.columns},
}
ai = get_ai_content(json.dumps(snapshot))
layer_sentences = ai.get("layers", {})
summary         = ai.get("summary", "")

# ---------------------------------------------------------------------------
# Zone 1 — Hero
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="hero">
    <div class="hero-left">
        <div class="hero-eyebrow">Macro Climate Score</div>
        <div class="hero-score" style="color:{regime_color};">{today_disc:+d}</div>
        <div class="hero-denom">out of ±6</div>
    </div>
    <div>
        <div class="hero-regime" style="color:{regime_color};">{regime_text}</div>
        <div class="hero-summary">{summary or "Loading market intelligence..."}</div>
        <div class="hero-meta">
            {today_date.strftime("%B %d, %Y")}
            &nbsp;·&nbsp;
            Derived from {len(layer_60):,} trading days of market price data (2010–present)
            &nbsp;·&nbsp;
            Market prices lead economic data by 3–12 months
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Zone 2 — Six layer cards (2 columns)
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Six Layers of the Economy — What Markets Are Pricing In</div>',
            unsafe_allow_html=True)

left_col, right_col = st.columns(2)
layer_items = list(layer_60.columns)

for i, layer_name in enumerate(layer_items):
    z         = float(today_layers[layer_name])
    sign_adj  = z * LAYER_SIGNS.get(layer_name, 1)
    meta      = LAYER_META[layer_name]
    color     = score_color(sign_adj)
    border    = border_color(sign_adj)
    sentence  = layer_sentences.get(layer_name, meta["what_it_is"])
    bar_html  = zbar_html(sign_adj, color)

    card_html = f"""
    <div class="layer-card" style="border-left-color:{border};">
        <div class="layer-header">
            <div>
                <div class="layer-name">{meta['name']}</div>
                <div class="layer-etfs">{meta['etfs']}</div>
            </div>
            <div class="layer-z" style="color:{color};">{z:+.2f}σ</div>
        </div>
        <div class="layer-sentence">{sentence}</div>
        {bar_html}
    </div>"""

    with (left_col if i % 2 == 0 else right_col):
        st.markdown(card_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Zone 3 — Ratio gauges (2 columns)
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label" style="margin-top:0.5rem;">Key Market Ratios — Risk Appetite Gauges</div>',
            unsafe_allow_html=True)

r_left, r_right = st.columns(2)
ratio_items = list(ratios.columns)

for i, col_name in enumerate(ratio_items):
    meta         = RATIO_META.get(col_name, {"name": col_name, "signal": "", "high": "", "low": ""})
    val          = float(today_ratios[col_name])
    z            = float(today_ratio_z[col_name])
    color        = score_color(z)

    ratio_series = ratios[col_name].dropna()
    pct_rank     = float((ratio_series < val).mean() * 100)
    dot_left     = f"{pct_rank:.1f}%"

    # Dot color: high pct = green (ratio elevated), low pct = red
    if pct_rank >= 60:   dot_color = "#00d48a"
    elif pct_rank >= 40: dot_color = "#505050"
    else:                dot_color = "#e04040"

    # Plain-English interpretation based on percentile
    if pct_rank >= 55:
        interp = meta.get("high", "")
    elif pct_rank <= 45:
        interp = meta.get("low", "")
    else:
        interp = meta.get("signal", "")

    card_html = f"""
    <div class="ratio-card">
        <div class="ratio-name">{meta['name']}</div>
        <div class="ratio-signal-q">{meta.get('signal','')}</div>
        <div class="ratio-val-row">
            <div class="ratio-val" style="color:{color};">{val:.3f}</div>
            <div class="ratio-z-badge" style="color:{color};">z = {z:+.2f}σ &nbsp;·&nbsp; {pct_rank:.0f}th pct</div>
        </div>
        <div class="pct-track">
            <div class="pct-dot" style="left:{dot_left};background:{dot_color};"></div>
        </div>
        <div class="ratio-interp">{interp}</div>
    </div>"""

    with (r_left if i % 2 == 0 else r_right):
        st.markdown(card_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("""
<div style="text-align:center;color:#1a1a1a;font-size:0.6rem;
            margin-top:3rem;letter-spacing:0.1em;text-transform:uppercase;">
    Macro Barometer &nbsp;·&nbsp; Market prices lead economic data by 3–12 months
</div>
""", unsafe_allow_html=True)
