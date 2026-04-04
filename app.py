"""
app.py — Equity-Implied Macro Barometer
Run with: python app.py
"""

import os

import pandas as pd
import plotly.graph_objects as go
from dash import ALL, Dash, Input, Output, State, callback, ctx, dcc, html

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


def card_accent_color(z_value: float) -> str:
    if z_value > STATE_THRESHOLD:
        return "#d2d8e0" if z_value < 1.25 else "#4a9e6e"
    if z_value < -STATE_THRESHOLD:
        return "#bb5551"
    return "#d2d8e0"


def card_signal_color(z_value: float) -> str:
    if z_value > STATE_THRESHOLD:
        return score_color(z_value)
    if z_value < -STATE_THRESHOLD:
        return score_color(z_value)
    return "#d2d8e0"


def score_tag(layer_key: str, z_value: float) -> str:
    tag_map = LAYER_META[layer_key].get("score_tag_map", {})
    if z_value > STATE_THRESHOLD:
        return tag_map.get("positive", "Positive")
    if z_value < -STATE_THRESHOLD:
        return tag_map.get("negative", "Negative")
    return tag_map.get("neutral", "Neutral")


def hero_tail(delta: int) -> str:
    if delta >= 2:
        return " but the tape has improved over the past month."
    if delta >= 1:
        return " but the tape has started to improve over the past month."
    if delta == 0:
        return "and the tape has not improved over the past month."
    if delta <= -2:
        return " and the tape has deteriorated over the past month."
    return " and the tape is still weakening at the margin."


def signal_strength_meta() -> str:
    total_layers = max(len(snapshot["layers"]), 1)
    risk_off = sum(1 for vote in snapshot["layer_votes"].values() if vote == -1)
    risk_on = sum(1 for vote in snapshot["layer_votes"].values() if vote == 1)
    neutral = total_layers - risk_off - risk_on
    if risk_off > risk_on:
        return (
            f"{risk_off}/{total_layers} buckets are ",
            "risk off",
            regime_color,
        )
    if risk_on > risk_off:
        return (
            f"{risk_on}/{total_layers} buckets are ",
            "risk on",
            "#4a9e6e",
        )
    return (
        f"{neutral}/{total_layers} buckets are ",
        "neutral",
        "#d2d8e0",
    )


def build_note_items(title: str, text: str) -> list[html.Li]:
    sentences = [part.strip() for part in text.replace("?", ".").split(".") if part.strip()]
    if not sentences:
        sentences = [text.strip()]
    items = []
    for sentence in sentences[:2]:
        headline, _, rest = sentence.partition(",")
        headline = headline.strip().rstrip(":")
        body = rest.strip() if rest else ""
        children = [html.Div(headline, className="note-item-head")]
        if body:
            children.append(html.Div(body, className="note-item-body"))
        items.append(
            html.Li(
                children,
                className="note-item",
            )
        )
    return items


def build_drawer_content(layer_key: str) -> list[html.Div]:
    layer = next((item for item in snapshot["layers"] if item["key"] == layer_key), None)
    if layer is None:
        return []
    z_value = float(layer["z_score"])
    layer_meta = LAYER_META[layer_key]
    message = layer_message(layer_key, z_value)
    tag = score_tag(layer_key, z_value)
    etf_pills = [
        html.Span(ticker.strip(), className="drawer-etf-pill")
        for ticker in layer_meta["etfs"].split(" · ")
        if ticker.strip()
    ]
    return [
        html.Div(layer_meta.get("card_label", layer["short"]), className="drawer-kicker"),
        html.Div(message, className="drawer-title", style={"color": card_signal_color(z_value)}),
        html.Div(
            [
                html.Span(f"{z_value:+.1f}σ", className="drawer-score"),
                html.Span(tag, className="drawer-tag", style={"color": card_signal_color(z_value)}),
            ],
            className="drawer-score-row",
        ),
        html.Div(layer_meta.get("card_desc", ""), className="drawer-copy"),
        html.Div("ETF Basket", className="drawer-section-label"),
        html.Div(etf_pills, className="drawer-etfs"),
    ]


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
        tag = score_tag(layer["key"], z_value)
        cards.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(layer_meta.get("card_label", layer["short"]), className="signal-card-title"),
                            html.Span(layer_meta.get("card_icon", "insights"), className="material-symbols-outlined signal-card-icon"),
                        ],
                        className="signal-card-header",
                    ),
                    html.Div(message, className="signal-card-message", style={"color": card_signal_color(z_value)}),
                    html.Div(
                        [
                            html.Span(f"{z_value:+.1f}σ", className="signal-card-score"),
                            html.Span(tag, className="signal-card-tag", style={"color": card_signal_color(z_value)}),
                        ],
                        className="signal-card-score-row",
                    ),
                    html.Div(layer_meta.get("card_desc", ""), className="signal-card-note"),
                    html.Button(
                        [
                            html.Span("View ETFs"),
                            html.Span("chevron_right", className="material-symbols-outlined signal-card-chevron"),
                        ],
                        id={"type": "etf-open", "index": layer["key"]},
                        className="signal-card-toggle",
                    ),
                ],
                className="signal-card",
                style={"--card-accent": card_accent_color(z_value)},
            )
        )
    return html.Div(cards, className="signals-grid")


app = Dash(__name__, title="Equity-Implied Macro Barometer")
server = app.server

app.layout = html.Div(
    [
        dcc.Store(id="selected-layer-store", data=None),
        html.Div(
            [
                html.Header(
                    [
                        html.Div(
                            [
                                html.Span("Citrini Terminal", className="topbar-brand"),
                            ],
                            className="topbar-left",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [html.Span("notifications", className="material-symbols-outlined topbar-icon"), html.Span(className="topbar-dot")],
                                    className="topbar-icon-wrap",
                                ),
                                html.Span("settings", className="material-symbols-outlined topbar-icon"),
                                html.Div("A", className="topbar-avatar"),
                            ],
                            className="topbar-right",
                        ),
                    ],
                    className="topbar-shell",
                ),
                html.Main(
                    [
                        html.Section(
                            [
                                html.Div(
                                    [
                                        html.Div("Current Macro Regime", className="hero-kicker"),
                                        html.Div(
                                            [
                                                html.Span("Equities are in ", className="hero-sentence-base"),
                                                html.Span(regime_text.lower(), className="hero-sentence-regime", style={"color": regime_color}),
                                                html.Span(f" {hero_tail(snapshot['composite_1m_change'])}", className="hero-sentence-base"),
                                            ],
                                            className="hero-title",
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.Div("Last Updated", className="hero-meta-label"),
                                                        html.Div(pd.to_datetime(snapshot["as_of_date"]).strftime("%d %b %Y"), className="hero-meta-value"),
                                                    ],
                                                    className="hero-meta-block",
                                                ),
                                                html.Div(className="hero-meta-divider"),
                                                html.Div(
                                                    [
                                                        html.Div("Signal", className="hero-meta-label"),
                                                        html.Div(
                                                            [
                                                                html.Span(signal_strength_meta()[0], className="hero-meta-signal-prefix"),
                                                                html.Span(
                                                                    signal_strength_meta()[1],
                                                                    className="hero-meta-signal-word",
                                                                    style={"color": signal_strength_meta()[2]},
                                                                ),
                                                            ],
                                                            className="hero-meta-value hero-meta-signal",
                                                        ),
                                                    ],
                                                    className="hero-meta-block",
                                                ),
                                            ],
                                            className="hero-meta-row",
                                        ),
                                    ],
                                    className="hero-block",
                                ),
                            ],
                            className="content-section",
                        ),
                        html.Div(build_signal_cards(), className="section-block"),
                        html.Div(
                            [
                                html.Section(
                                    [
                                        html.Div(
                                            [
                                                html.Span(className="mini-section-dot mini-section-dot-primary"),
                                                html.Div("What Changed", className="mini-section-title"),
                                            ],
                                            className="mini-section-head",
                                        ),
                                        html.Ul(build_note_items("What Changed", dashboard_copy["what_changed"]), className="note-list"),
                                    ],
                                    className="mini-panel mini-panel-notes",
                                ),
                                html.Section(
                                    [
                                        html.Div(
                                            [
                                                html.Span(className="mini-section-dot mini-section-dot-neutral"),
                                                html.Div("What Is Confirming", className="mini-section-title"),
                                            ],
                                            className="mini-section-head",
                                        ),
                                        html.Ul(build_note_items("What Is Confirming", dashboard_copy["confirmation"]), className="note-list"),
                                    ],
                                    className="mini-panel mini-panel-notes",
                                ),
                                html.Section(
                                    [
                                        html.Div(
                                            [
                                                html.Span(className="mini-section-dot mini-section-dot-alert"),
                                                html.Div("What To Watch", className="mini-section-title"),
                                            ],
                                            className="mini-section-head",
                                        ),
                                        html.Ul(build_note_items("What To Watch", dashboard_copy["watch"]), className="note-list"),
                                    ],
                                    className="mini-panel mini-panel-notes",
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
                    className="main-shell",
                ),
                html.Div(
                    [
                        html.Button(
                            html.Span("close", className="material-symbols-outlined"),
                            id="etf-drawer-close",
                            className="drawer-close",
                        ),
                        html.Div(id="etf-drawer-content", className="drawer-content"),
                    ],
                    id="etf-drawer",
                    className="etf-drawer",
                ),
            ],
            className="workspace-shell",
        ),
    ],
    id="app-root",
)


@callback(
    Output("selected-layer-store", "data"),
    Input({"type": "etf-open", "index": ALL}, "n_clicks"),
    Input("etf-drawer-close", "n_clicks"),
    State("selected-layer-store", "data"),
    prevent_initial_call=True,
)
def toggle_etf_drawer(open_clicks, close_clicks, current_layer):
    triggered = ctx.triggered_id
    if triggered == "etf-drawer-close":
        return None
    if isinstance(triggered, dict):
        layer_key = triggered.get("index")
        if layer_key == current_layer:
            return None
        return layer_key
    return current_layer


@callback(
    Output("etf-drawer", "className"),
    Output("etf-drawer-content", "children"),
    Input("selected-layer-store", "data"),
)
def render_etf_drawer(layer_key):
    if not layer_key:
        return "etf-drawer", []
    return "etf-drawer etf-drawer-open", build_drawer_content(layer_key)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8050"))
    host = os.getenv("HOST", "0.0.0.0")
    app.run(debug=False, host=host, port=port)
