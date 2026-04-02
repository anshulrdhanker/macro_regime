"""
snapshot.py
Builds a compact dashboard snapshot from live market and macro inputs, and
optionally turns that snapshot into short dashboard copy via OpenAI.
"""

import json
import os
from typing import Any, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel

from config import (
    MOMENTUM_WINDOW,
    OPENAI_SUMMARY_MAX_TOKENS,
    OPENAI_SUMMARY_MODEL,
    OPENAI_SUMMARY_REASONING_EFFORT,
    OPENAI_SUMMARY_VERBOSITY,
    STATE_THRESHOLD,
    VOTE_THRESHOLD,
)
from constants import LAYER_META, LAYER_SIGNS, build_macro_summary, direction_info, regime_label


class DashboardCopySchema(BaseModel):
    bottom_line: str
    what_changed: str
    confirmation: str
    watch: str


def _layer_state_label(z_value: float) -> str:
    if z_value > STATE_THRESHOLD:
        return "Improving"
    if z_value < -STATE_THRESHOLD:
        return "Weakening"
    return "Neutral"


def _latest_point(series: pd.Series) -> tuple[Optional[pd.Timestamp], Optional[float]]:
    clean = series.dropna()
    if clean.empty:
        return None, None
    return pd.Timestamp(clean.index[-1]), float(clean.iloc[-1])


def _series_trend(series: pd.Series, periods: int = 3, tolerance: float = 0.01) -> str:
    clean = series.dropna()
    if len(clean) <= periods:
        return "flat"
    latest = float(clean.iloc[-1])
    prior = float(clean.iloc[-1 - periods])
    if prior == 0:
        delta = latest - prior
    else:
        delta = (latest / prior) - 1
    if delta > tolerance:
        return "rising"
    if delta < -tolerance:
        return "softening"
    return "flat"


def _build_macro_context(fred_data: pd.DataFrame) -> dict[str, Any]:
    context: dict[str, Any] = {}

    ts, latest = _latest_point(fred_data["yield_2yr"])
    if latest is not None:
        monthly_delta = fred_data["yield_2yr"].diff(21).dropna()
        delta_bps = float(monthly_delta.iloc[-1] * 100) if not monthly_delta.empty else None
        context["yield_2yr"] = {
            "date": ts.date().isoformat() if ts is not None else None,
            "latest": round(latest, 2),
            "change_1m_bps": round(delta_bps, 1) if delta_bps is not None else None,
            "trend": "rising" if (delta_bps or 0) > 5 else ("falling" if (delta_bps or 0) < -5 else "flat"),
        }

    for column in ["housing_starts", "industrial_production", "cpi"]:
        monthly = fred_data[column].dropna().resample("ME").last()
        ts, latest = _latest_point(monthly)
        yoy = monthly.pct_change(12, fill_method=None).dropna()
        latest_yoy = float(yoy.iloc[-1] * 100) if not yoy.empty else None
        context[column] = {
            "date": ts.date().isoformat() if ts is not None else None,
            "latest": round(latest, 2) if latest is not None else None,
            "yoy_pct": round(latest_yoy, 1) if latest_yoy is not None else None,
            "trend": _series_trend(monthly, periods=3, tolerance=0.01),
        }

    return context


def _market_vs_macro_status(composite_score: int, macro_context: dict[str, Any]) -> dict[str, str]:
    growth_softening = 0
    growth_firming = 0
    for key in ["housing_starts", "industrial_production"]:
        trend = macro_context.get(key, {}).get("trend")
        if trend == "softening":
            growth_softening += 1
        elif trend == "rising":
            growth_firming += 1

    if composite_score < 0:
        if growth_softening >= 1:
            return {"status": "confirming", "note": "Official macro data is starting to confirm the weaker market signal."}
        return {"status": "lagging", "note": "Official macro data still looks firmer than the equity tape."}
    if composite_score > 0:
        if growth_firming >= 1:
            return {"status": "confirming", "note": "Official macro data is starting to confirm the stronger market signal."}
        return {"status": "lagging", "note": "Official macro data has not fully caught up with the stronger market signal yet."}
    return {"status": "mixed", "note": "Official macro data is mixed, matching the market's transitional tone."}


def build_dashboard_snapshot(data: dict[str, Any], analysis: dict[str, pd.DataFrame]) -> dict[str, Any]:
    layer_60 = analysis["layer_scores_60d"]

    signed = layer_60.copy()
    for col, sign in LAYER_SIGNS.items():
        if col in signed.columns:
            signed[col] = signed[col] * sign

    disc_signals = signed.apply(
        lambda c: np.where(c > VOTE_THRESHOLD, 1, np.where(c < -VOTE_THRESHOLD, -1, 0))
    )
    composite_discrete = pd.Series(disc_signals.sum(axis=1), index=layer_60.index)

    today_disc = int(composite_discrete.iloc[-1])
    disc_20d_ago = (
        int(composite_discrete.iloc[-1 - MOMENTUM_WINDOW])
        if len(composite_discrete) > MOMENTUM_WINDOW
        else today_disc
    )
    comp_delta = today_disc - disc_20d_ago

    today_date = pd.Timestamp(layer_60.index[-1])
    today_signed = signed.iloc[-1]
    layer_delta: dict[str, float] = {}
    for layer_name in layer_60.columns:
        if len(signed) > MOMENTUM_WINDOW:
            layer_delta[layer_name] = float(signed[layer_name].iloc[-1]) - float(
                signed[layer_name].iloc[-1 - MOMENTUM_WINDOW]
            )
        else:
            layer_delta[layer_name] = 0.0

    layer_votes = {layer_name: int(disc_signals[layer_name].iloc[-1]) for layer_name in layer_60.columns}
    regime_text, regime_color = regime_label(today_disc)
    dir_arrow, dir_word, dir_color = direction_info(comp_delta)
    fallback_summary = build_macro_summary(
        today_disc,
        comp_delta,
        layer_votes,
        today_signed.to_dict(),
        layer_delta,
    )

    layers = []
    for layer_name in layer_60.columns:
        z_value = float(today_signed[layer_name])
        layers.append(
            {
                "key": layer_name,
                "name": LAYER_META[layer_name]["name"],
                "short": LAYER_META[layer_name]["short"],
                "state": _layer_state_label(z_value),
                "z_score": round(z_value, 3),
                "delta_1m": round(layer_delta[layer_name], 3),
                "vote": layer_votes[layer_name],
            }
        )

    macro_context = _build_macro_context(data["fred_data"])
    market_vs_macro = _market_vs_macro_status(today_disc, macro_context)

    snapshot = {
        "as_of_date": today_date.date().isoformat(),
        "regime": regime_text,
        "regime_color": regime_color,
        "direction": dir_word,
        "direction_arrow": dir_arrow,
        "direction_color": dir_color,
        "composite_score": today_disc,
        "composite_1m_change": comp_delta,
        "composite_series": composite_discrete,
        "breadth": fallback_summary["breadth"],
        "layers": layers,
        "layer_votes": layer_votes,
        "layer_delta": layer_delta,
        "signed_scores": today_signed.to_dict(),
        "fallback_summary": fallback_summary,
        "macro_context": macro_context,
        "market_vs_macro": market_vs_macro,
        "data_status": data.get("data_status", {}),
    }
    return snapshot


def build_dashboard_copy(snapshot: dict[str, Any]) -> dict[str, str]:
    fallback = {
        "bottom_line": snapshot["fallback_summary"]["bottom_line"],
        "what_changed": snapshot["fallback_summary"]["what_changed"],
        "confirmation": snapshot["fallback_summary"]["confirmation"],
        "watch": snapshot["fallback_summary"]["watch"],
        "source": "rule_fallback",
        "copy_error": "",
    }

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        fallback["copy_error"] = "OPENAI_API_KEY missing"
        return fallback

    try:
        from openai import OpenAI
    except Exception as exc:
        fallback["copy_error"] = f"OpenAI import failed: {exc}"
        return fallback

    packet = {
        "as_of_date": snapshot["as_of_date"],
        "equity_implied": {
            "regime": snapshot["regime"],
            "composite_score": snapshot["composite_score"],
            "composite_1m_change": snapshot["composite_1m_change"],
            "direction": snapshot["direction"],
            "breadth": snapshot["breadth"],
            "layers": snapshot["layers"],
            "bottom_drivers": sorted(
                snapshot["layers"], key=lambda layer: layer["z_score"]
            )[:2],
            "offsets": sorted(
                snapshot["layers"], key=lambda layer: layer["z_score"], reverse=True
            )[:2],
        },
        "macro_context": snapshot["macro_context"],
        "market_vs_macro": snapshot["market_vs_macro"],
    }

    system_prompt = (
        "You write short dashboard copy for an equity-implied macro barometer used by a portfolio manager. "
        "Equity-implied signals come first. Official macro data is secondary context. "
        "Do not give portfolio advice. Do not invent facts. Use only the packet provided. "
        "Return exactly these fields: bottom_line, what_changed, confirmation, watch. "
        "Each field must be one sentence in plain English. "
        "Write like a concise PM morning note, not a dashboard tooltip. "
        "For bottom_line, use a short market-first sentence. Start with 'Equities are' or 'The tape is'. "
        "Do not mention the word 'barometer'. Do not mention the composite score number. "
        "Prefer direct regime language like contraction, stabilization, recovery, or mixed transition. "
        "For what_changed, say what worsened or improved over the past month and name the main drivers. "
        "For confirmation, say whether official macro data is confirming, lagging, or diverging from the market signal. "
        "For watch, say what to monitor next in one direct sentence."
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.parse(
            model=OPENAI_SUMMARY_MODEL,
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Write the dashboard copy from this snapshot:\n" + json.dumps(packet, default=str),
                },
            ],
            text_format=DashboardCopySchema,
            reasoning={"effort": OPENAI_SUMMARY_REASONING_EFFORT},
            text={"verbosity": OPENAI_SUMMARY_VERBOSITY},
            max_output_tokens=OPENAI_SUMMARY_MAX_TOKENS,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            output_text = getattr(response, "output_text", "")
            raw_output = getattr(response, "output", None)
            response_status = getattr(response, "status", None)
            incomplete_details = getattr(response, "incomplete_details", None)
            raw_output_preview = ""
            if raw_output is not None:
                try:
                    raw_output_preview = json.dumps(raw_output, default=str)[:500]
                except Exception:
                    raw_output_preview = str(raw_output)[:500]
            fallback["copy_error"] = (
                "OpenAI returned no parsed output"
                + (f" | status={response_status}" if response_status else "")
                + (f" | incomplete={incomplete_details}" if incomplete_details else "")
                + (f" | text={output_text[:180]}" if output_text else "")
                + (f" | raw={raw_output_preview}" if raw_output_preview else "")
            )
            print(f"[snapshot] OpenAI parse failed: {fallback['copy_error']}")
            return fallback

        payload = parsed.model_dump()
        required = ["bottom_line", "what_changed", "confirmation", "watch"]
        if any(not isinstance(payload.get(key), str) or not payload.get(key).strip() for key in required):
            fallback["copy_error"] = "OpenAI parsed output missing required fields"
            print(f"[snapshot] OpenAI parse failed: {fallback['copy_error']}")
            return fallback

        payload["source"] = "openai"
        payload["copy_error"] = ""
        return payload
    except Exception as exc:
        fallback["copy_error"] = f"{type(exc).__name__}: {exc}"
        print(f"[snapshot] OpenAI request failed: {fallback['copy_error']}")
        return fallback
