"""
app.py — Equity-Implied Macro Barometer
Run with: python app.py
"""

import os

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html

from config import (
    CHART_LOOKBACK,
    STATE_THRESHOLD,
)
from constants import LAYER_META, border_color, score_color
from main import load
from snapshot import build_dashboard_copy, build_dashboard_snapshot


print("[app] Loading data...")
data, analysis = load(analysis_mode="dashboard")
snapshot = build_dashboard_snapshot(data, analysis)
dashboard_copy = build_dashboard_copy(snapshot)

composite_discrete = snapshot["composite_series"]
today_date = pd.Timestamp(snapshot["as_of_date"])
regime_text = snapshot["regime"]
regime_color = snapshot["regime_color"]
dir_arrow = snapshot["direction_arrow"]
dir_word = snapshot["direction"]
dir_color = snapshot["direction_color"]


def data_status_label() -> str:
    status = snapshot.get("data_status", {})
    source = status.get("source")
    source_map = {
        "cache_fresh": "Using fresh cache",
        "live_refresh": "Refreshed live",
        "stale_cache_fallback": "Using stale cache",
    }
    label = source_map.get(source, "Status unknown")
    etf_ts = status.get("etf_timestamp")
    fred_ts = status.get("fred_timestamp")
    if etf_ts and fred_ts:
        return f"{label} · Market {pd.to_datetime(etf_ts).strftime('%b %d %H:%M')} · Macro {pd.to_datetime(fred_ts).strftime('%b %d %H:%M')}"
    return label


def layer_state_label(z_value: float) -> str:
    if z_value > STATE_THRESHOLD:
        return "Improving"
    if z_value < -STATE_THRESHOLD:
        return "Weakening"
    return "Neutral"


def layer_message(layer_key: str, z_value: float) -> str:
    message_map = LAYER_META[layer_key].get("message_map", {})
    if z_value > STATE_THRESHOLD:
        return message_map.get("positive", "Improving")
    if z_value < -STATE_THRESHOLD:
        return message_map.get("negative", "Weakening")
    return message_map.get("neutral", "Neutral")


def make_timeline_fig(series: pd.Series, lookback: int = CHART_LOOKBACK) -> go.Figure:
    s = series.iloc[-lookback:]
    fig = go.Figure()
    fig.add_hline(y=0, line_color="#222222", line_width=1)
    fig.add_trace(
        go.Scatter(
            x=s.index,
            y=s.values,
            mode="lines",
            line=dict(color="#c8c8c8", width=2),
            fill="tozeroy",
            fillcolor="rgba(180,180,180,0.08)",
            hovertemplate="%{x|%b %d, %Y}<br>Score: %{y:+d}<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[s.index[-1]],
            y=[s.values[-1]],
            mode="markers",
            marker=dict(size=9, color=score_color(float(s.iloc[-1]))),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=240,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10, color="#5a5a5a")),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, range=[-7, 7]),
        hovermode="x unified",
    )
    return fig


def build_signal_cards() -> html.Div:
    cards = []
    for layer in snapshot["layers"]:
        z_value = float(layer["z_score"])
        layer_meta = LAYER_META[layer["key"]]
        message = layer_message(layer["key"], z_value)
        etf_pills = [
            html.Span(ticker.strip(), className="signal-card-etf-pill")
            for ticker in layer_meta["etfs"].split(" · ")
            if ticker.strip()
        ]
        cards.append(
            html.Div(
                [
                    html.Div(layer_meta.get("card_label", layer["short"]), className="signal-card-title"),
                    html.Div(message, className="signal-card-message", style={"color": score_color(z_value)}),
                    html.Div(f"{z_value:+.1f}σ", className="signal-card-score"),
                    html.Div(layer_meta.get("card_desc", ""), className="signal-card-note"),
                    html.Details(
                        [
                            html.Summary("View ETFs", className="signal-card-toggle"),
                            html.Div(etf_pills, className="signal-card-etfs"),
                        ],
                        className="signal-card-details",
                    ),
                ],
                className="signal-card",
                style={"borderLeftColor": border_color(z_value)},
            )
        )
    return html.Div(cards, className="signals-grid")


app = Dash(__name__, title="Equity-Implied Macro Barometer")
server = app.server

app.layout = html.Div(
    [
        html.Div(
            [
                html.Div("What Equities Are Pricing", className="hero-title"),
                html.Div(
                    "Equities lead macro data, so to get an understanding of what equities are implying, I pulled ETF data (bucketed into areas of the economy), and extrapolated its behaviour relative to history.",
                    className="hero-subtitle",
                ),
                html.Div(
                    [
                        html.Span(regime_text, className="summary-pill", style={"color": regime_color}),
                        html.Span(snapshot["breadth"], className="summary-pill"),
                        html.Span(data_status_label(), className="summary-pill"),
                    ],
                    className="summary-row",
                ),
            ],
            className="hero-block",
        ),
        html.Div(build_signal_cards(), className="section-block"),
        html.Div(
            [
                html.Div(
                    [
                        html.Div("What Changed", className="mini-section-title"),
                        html.Div(dashboard_copy["what_changed"], className="mini-section-copy"),
                    ],
                    className="mini-panel",
                ),
                html.Div(
                    [
                        html.Div("What Is Confirming", className="mini-section-title"),
                        html.Div(dashboard_copy["confirmation"], className="mini-section-copy"),
                    ],
                    className="mini-panel",
                ),
                html.Div(
                    [
                        html.Div("What To Watch", className="mini-section-title"),
                        html.Div(dashboard_copy["watch"], className="mini-section-copy"),
                    ],
                    className="mini-panel",
                ),
            ],
            className="mini-grid",
        ),
        html.Div(
            [
                html.Div("Six Market Bucket Signals Over Time", className="mini-section-title"),
                dcc.Graph(
                    figure=make_timeline_fig(composite_discrete),
                    config={"displayModeBar": False},
                ),
            ],
            className="chart-block",
        ),
        html.Div(
            f"{today_date.strftime('%B %d, %Y')} · Copy source: {dashboard_copy['source']}",
            className="footer",
        ),
    ],
    id="app-root",
)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8050"))
    host = os.getenv("HOST", "0.0.0.0")
    app.run(debug=False, host=host, port=port)
