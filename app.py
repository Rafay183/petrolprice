"""
Pakistan Live Fuel Prices — Streamlit App
Data source: AutoOnes Fuel Prices API (https://autoones.com/fuel-prices-api)
  - GET https://api2.autoones.com/api/fuel-prices          (current prices)
  - GET https://api2.autoones.com/api/fuel-prices/history  (?fuel=&view=&limit=)
No API key required. Prices are set by OGRA and change at most once a day.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
BASE_URL = "https://api2.autoones.com/api/fuel-prices"
HISTORY_URL = f"{BASE_URL}/history"
TIMEOUT = 15
HEADERS = {"User-Agent": "PK-Fuel-Streamlit/1.0", "Accept": "application/json"}

FUELS = {"petrol": "Petrol", "diesel": "Diesel (HSD)"}
COLORS = {"petrol": "#E4572E", "diesel": "#2E86AB"}

st.set_page_config(
    page_title="Pakistan Fuel Prices — Live",
    page_icon="⛽",
    layout="wide",
)


# ----------------------------------------------------------------------------
# API layer (cached — the API asks callers to cache; prices change daily)
# ----------------------------------------------------------------------------
class APIError(Exception):
    pass


def _get(url: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout as e:
        raise APIError("The fuel price API timed out. Please try again.") from e
    except requests.exceptions.HTTPError as e:
        raise APIError(f"API returned HTTP {r.status_code}.") from e
    except requests.exceptions.RequestException as e:
        raise APIError(f"Could not reach the API: {e}") from e
    except ValueError as e:
        raise APIError("API returned an invalid (non-JSON) response.") from e


def _num(x):
    """History endpoint returns numbers as strings — coerce safely."""
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=300, show_spinner=False)  # matches API's 5-min cache
def fetch_current() -> dict:
    return _get(BASE_URL)


@st.cache_data(ttl=600, show_spinner=False)  # matches API's 10-min cache
def fetch_history(fuel: str, view: str, limit: int) -> pd.DataFrame:
    data = _get(HISTORY_URL, {"fuel": fuel, "view": view, "limit": limit})
    rows = data.get("rows") or []
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Coerce every price-like column to float
    for col in df.columns:
        if col.endswith("_pkr"):
            df[col] = df[col].map(_num)

    # Normalise the time axis
    if "effective_date" in df.columns:
        df["date"] = pd.to_datetime(df["effective_date"], errors="coerce")
    elif "period" in df.columns:
        df["date"] = pd.to_datetime(df["period"].astype(str), errors="coerce")
    elif "year" in df.columns:
        df["date"] = pd.to_datetime(df["year"].astype(str), format="%Y", errors="coerce")

    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)
    return df


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def fmt_pkr(v) -> str:
    return "—" if v is None else f"Rs {v:,.2f}"


def main_price_col(df: pd.DataFrame) -> str | None:
    for c in ("price_pkr", "close_pkr", "avg_pkr"):
        if c in df.columns:
            return c
    return None


def price_card(item: dict):
    slug = item.get("slug", "")
    price = _num(item.get("price_pkr"))
    change = _num(item.get("change_pkr"))
    eff = item.get("effective_date", "—")
    delta = None if change is None else f"{change:+,.2f} PKR"
    st.metric(
        label=f"⛽ {item.get('fuel', slug.title())} (per litre)",
        value=fmt_pkr(price),
        delta=delta,
        delta_color="inverse",  # price rise = red, cut = green
    )
    st.caption(f"Effective from **{eff}**")


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")
    view = st.radio("History view", ["daily", "monthly", "yearly"], horizontal=True)
    limit_default = {"daily": 90, "monthly": 24, "yearly": 10}[view]
    limit = st.slider("Number of records", 1, 400, limit_default)
    fuels_sel = st.multiselect(
        "Fuels", list(FUELS), default=list(FUELS), format_func=lambda s: FUELS[s]
    )

    st.divider()
    st.subheader("🧮 Fuel cost calculator")
    calc_fuel = st.selectbox("Fuel", list(FUELS), format_func=lambda s: FUELS[s])
    calc_mode = st.radio("Calculate by", ["Litres", "Distance"], horizontal=True)
    if calc_mode == "Litres":
        litres = st.number_input("Litres", 0.0, 1000.0, 10.0, 1.0)
    else:
        km = st.number_input("Distance (km)", 0.0, 10000.0, 100.0, 10.0)
        kmpl = st.number_input("Mileage (km/litre)", 1.0, 100.0, 12.0, 0.5)
        litres = km / kmpl

    st.divider()
    if st.button("🔄 Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ----------------------------------------------------------------------------
# Header + current prices
# ----------------------------------------------------------------------------
st.title("⛽ Pakistan Petrol & Diesel Prices — Live")
st.caption(
    "Official OGRA-notified retail prices via the free AutoOnes API · "
    f"Last fetched {datetime.now():%d %b %Y, %I:%M %p}"
)

try:
    with st.spinner("Fetching latest prices…"):
        current = fetch_current()
except APIError as e:
    st.error(f"❌ {e}")
    st.stop()

prices = current.get("prices") or []
by_slug = {p.get("slug"): p for p in prices}

if not prices:
    st.warning("The API returned no current prices.")
else:
    cols = st.columns(len(prices) + 1)
    for col, item in zip(cols, prices):
        with col:
            price_card(item)

    # Calculator result in the last column
    with cols[-1]:
        p = _num(by_slug.get(calc_fuel, {}).get("price_pkr"))
        cost = None if p is None else p * litres
        st.metric(f"🧮 Cost of {litres:,.2f} L {FUELS[calc_fuel]}", fmt_pkr(cost))
        st.caption("Set inputs in the sidebar")

    # Petrol vs diesel gap
    pp = _num(by_slug.get("petrol", {}).get("price_pkr"))
    dp = _num(by_slug.get("diesel", {}).get("price_pkr"))
    if pp is not None and dp is not None:
        gap = dp - pp
        st.info(
            f"Diesel is **Rs {abs(gap):,.2f}** "
            f"{'more' if gap > 0 else 'less'} than petrol per litre."
        )

    upd = [p.get("price_updated_at") for p in prices if p.get("price_updated_at")]
    if upd:
        st.caption(
            f"Source: {current.get('source', 'OGRA')} · Unit: {current.get('unit', 'PKR/litre')} · "
            f"Price record updated: {max(upd)} · Prices stay frozen on weekends/holidays."
        )

st.divider()

# ----------------------------------------------------------------------------
# History
# ----------------------------------------------------------------------------
st.subheader(f"📈 Price history — {view} view")

if not fuels_sel:
    st.info("Select at least one fuel in the sidebar.")
    st.stop()

histories: dict[str, pd.DataFrame] = {}
errors = []
with st.spinner("Loading history…"):
    for f in fuels_sel:
        try:
            histories[f] = fetch_history(f, view, limit)
        except APIError as e:
            errors.append(f"{FUELS[f]}: {e}")
for e in errors:
    st.error(e)

histories = {k: v for k, v in histories.items() if not v.empty and "date" in v.columns}
if not histories:
    st.warning("No history data available for this selection.")
    st.stop()

# --- Chart ---
fig = go.Figure()
for f, df in histories.items():
    col = main_price_col(df)
    if col is None:
        continue
    # Band for min/max in monthly/yearly views
    if {"min_pkr", "max_pkr"} <= set(df.columns):
        fig.add_trace(go.Scatter(
            x=pd.concat([df["date"], df["date"][::-1]]),
            y=pd.concat([df["max_pkr"], df["min_pkr"][::-1]]),
            fill="toself", fillcolor=COLORS[f], opacity=0.15,
            line=dict(width=0), hoverinfo="skip", showlegend=False,
        ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df[col], name=FUELS[f],
        mode="lines+markers" if len(df) < 60 else "lines",
        line=dict(color=COLORS[f], width=2.5, shape="hv" if view == "daily" else "linear"),
        hovertemplate="%{x|%d %b %Y}<br>Rs %{y:,.2f}<extra>" + FUELS[f] + "</extra>",
    ))
fig.update_layout(
    height=450, hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10),
    yaxis_title="PKR per litre", xaxis_title=None,
    legend=dict(orientation="h", y=1.08, x=0),
)
st.plotly_chart(fig, use_container_width=True)

# --- Summary stats ---
stat_cols = st.columns(len(histories))
for sc, (f, df) in zip(stat_cols, histories.items()):
    col = main_price_col(df)
    s = df[col].dropna()
    if s.empty:
        continue
    with sc:
        st.markdown(f"**{FUELS[f]}** — over {len(df)} records")
        a, b, c = st.columns(3)
        a.metric("Lowest", fmt_pkr(s.min()))
        b.metric("Highest", fmt_pkr(s.max()))
        first, last = s.iloc[0], s.iloc[-1]
        pct = (last - first) / first * 100 if first else 0
        c.metric("Net change", fmt_pkr(last - first), f"{pct:+.1f}%", delta_color="inverse")

# --- Change log (daily view) ---
if view == "daily":
    st.subheader("🗓️ Recent price revisions")
    for f, df in histories.items():
        if "change_pkr" not in df.columns:
            continue
        rev = df[df["change_pkr"].fillna(0) != 0][["date", "price_pkr", "change_pkr"]]
        if rev.empty:
            continue
        rev = rev.sort_values("date", ascending=False).head(10).copy()
        rev["date"] = rev["date"].dt.strftime("%d %b %Y")
        rev["direction"] = rev["change_pkr"].map(lambda x: "🔺 Increase" if x > 0 else "🔻 Cut")
        st.markdown(f"**{FUELS[f]}**")
        st.dataframe(
            rev.rename(columns={"date": "Effective date", "price_pkr": "Price (PKR)",
                                "change_pkr": "Change (PKR)", "direction": "Direction"}),
            hide_index=True, use_container_width=True,
        )

# --- Raw data + download ---
with st.expander("📄 Raw data & download"):
    for f, df in histories.items():
        st.markdown(f"**{FUELS[f]}**")
        out = df.copy()
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(out, hide_index=True, use_container_width=True)
        st.download_button(
            f"⬇️ Download {FUELS[f]} CSV",
            out.to_csv(index=False).encode(),
            file_name=f"pk_{f}_{view}_prices.csv",
            mime="text/csv",
            key=f"dl_{f}",
        )

st.divider()
st.caption(
    "Data: [AutoOnes Fuel Prices API](https://autoones.com/fuel-prices-api) · "
    "Prices per OGRA notifications. Verify with the official OGRA notification "
    "before relying on them for financial decisions."
)
