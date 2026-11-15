"""Date Finder — best surface-start dates per site + calendar heatmap (hourly data)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import finder
from engine.power import PowerParams
import ui_common as ui

st.set_page_config(page_title="Date Finder · Lunar Navigator", page_icon="📅", layout="wide")
names = ui.names()

with st.sidebar:
    st.header("Search setup")
    chosen = st.multiselect("Sites", list(names), default=list(names)[:3], format_func=names.get)
    dur_days = st.number_input("Surface stay (days)", 1.0, 14.0, 6.0, 0.5)
    first, last = finder.valid_start_range(ui.ephem(list(names)[0]), dur_days * 24, 48)
    rng = st.date_input("Search start dates between (UTC)",
                        (pd.Timestamp("2027-01-01").date(), pd.Timestamp("2027-12-31").date()),
                        min_value=first.date(), max_value=last.date())
    n_best = st.slider("Windows per site", 1, 10, 5)
    thr = st.slider("Sunlit threshold (fraction of solar disc)", 0.05, 1.0, 0.5, 0.05)
    mask = st.slider("Earth elevation mask (°)", 0.0, 10.0, 0.0, 0.5)
    w = ui.weights_sidebar()

st.title("📅 Landing-date finder")
st.caption("Ranks surface-start dates by score for the chosen stay length. Uses the precomputed HOURLY data "
           "(approximate: may miss short shadows); open a date in the Decision Report for a 10-minute check. "
           "Start dates are limited so that the stay plus a 48 h shift stays inside the data.")
if not chosen or not isinstance(rng, tuple) or len(rng) != 2:
    st.info("Pick sites and a start/end date.")
    st.stop()
ui.data_banners(chosen)

power = PowerParams()
results = []
for s in chosen:
    vis = ui.hourly_vis(s, thr, mask, power.array_area_m2, power.efficiency, power.load_w)
    try:
        bw = finder.best_windows(vis, pd.Timestamp(rng[0]), pd.Timestamp(rng[1]), duration_h=dur_days * 24,
                                 n_best=n_best, weights=w, power=power, max_shift_h=48)
    except finder.DateRangeError as e:
        st.error(f"{names[s]}: {e}")
        continue
    bw.insert(0, "site", names[s])
    bw["terrain"] = ui.terrain_status(s)
    results.append(bw)

if results:
    res = pd.concat(results, ignore_index=True)
    res["start (UTC)"] = pd.to_datetime(res.start_utc).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(res[["site", "start (UTC)", "score", "pct_sunlit", "pct_dte", "pct_both", "longest_dark_h",
                      "longest_no_dte_h", "required_nameplate_kwh", "pct_uncertain", "terrain"]].round(1),
                 width="stretch", hide_index=True)

st.markdown("#### Calendar heatmap (daily fraction of hours)")
metric = st.radio("Metric", ["sunlit", "dte_visible", "both"], horizontal=True,
                  format_func={"sunlit": "☀️ Sunlit", "dte_visible": "🌍 Potential DTE", "both": "Both"}.get)
rows, z = [], []
for s in chosen:
    vis = ui.hourly_vis(s, thr, mask, power.array_area_m2, power.efficiency, power.load_w)
    d = finder.daily_heatmap(vis, metric)
    d = d[(d.index >= pd.Timestamp(rng[0], tz="UTC")) & (d.index <= pd.Timestamp(rng[1], tz="UTC"))]
    rows.append(names[s])
    z.append(d.values)
    x = d.index
if rows:
    hm = go.Figure(go.Heatmap(z=z, x=x, y=rows, zmin=0, zmax=1, colorscale="Cividis",
                              colorbar=dict(title="fraction")))
    hm.update_layout(height=120 + 40 * len(rows), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(hm, width="stretch")

st.caption(ui.LIMITATIONS)
