"""Date Finder — rank mission start windows by power, communication and combined score."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import finder, live, visibility
from engine.power import PowerParams
import ui_common as ui

ui.setup_page()
names = ui.names()
ui.banner("calendar_month", "Date Finder",
          "Rank mission start windows by sunlight, Earth communication (with DSN coverage) and combined score.")

col_ctl, col_main = st.columns([0.9, 3.1])
with col_ctl:
    with st.container(key="card_search"):
        ui.card_title("tune", "Search Setup")
        msites = [x for x in st.session_state.get("mission", {}).get("sites", []) if x in names]
        chosen = st.multiselect("Sites", list(names), default=msites or
                                [s for s in ["malapert_massif", "de_gerlache_rim_2", "mons_mouton", "nobile_rim_2"]
                                 if s in names], format_func=names.get)
        dur_days = st.number_input("Surface Stay (days)", 1.0, 14.0, 6.0, 0.5)
        first, last = finder.valid_start_range(ui.ephem(list(names)[0]), dur_days * 24, 48)
        rng = st.date_input("Search Start Range (UTC)",
                            (pd.Timestamp("2027-01-01").date(), pd.Timestamp("2027-12-31").date()),
                            min_value=first.date(), max_value=last.date())
        n_best = st.slider("Windows per Site", 1, 10, 5)
        thr = st.slider("Sunlit Threshold (fraction)", 0.05, 1.0, 0.5, 0.05)
        mask = st.slider("Earth Elevation Mask (°)", 0.0, 10.0, 0.0, 0.5)
        req = st.toggle("Require DSN coverage", True)
        with st.expander("Score Weights", icon=":material/balance:"):
            w = ui.weights_sidebar(expander=False)

if not chosen or not isinstance(rng, tuple) or len(rng) != 2:
    with col_main:
        st.info("Pick sites and a start/end date.")
    st.stop()


@st.cache_data(show_spinner="Computing DSN coverage of the Moon…")
def dsn_all():
    e = ui.ephem(list(names)[0])
    from engine.dsn import coverage, moon_elevations
    return coverage(moon_elevations(live.sky(), pd.DatetimeIndex(e.time_utc)), 10.0)


@st.cache_data(show_spinner="Scanning landing windows…")
def site_vis(sid, thr_, mask_, req_):
    p = visibility.VisParams(sunlit_threshold=thr_, earth_mask_deg=mask_, require_dsn=req_)
    dsn_any = dsn_all()["dsn_any"].to_numpy() if req_ and live.kernels_available() else None
    return visibility.compute(ui.ephem(sid), ui.horizon(sid), p, dsn_any=dsn_any)


power = PowerParams()
results = []
for s in chosen:
    try:
        bw = finder.best_windows(site_vis(s, thr, mask, req), pd.Timestamp(rng[0]), pd.Timestamp(rng[1]),
                                 duration_h=dur_days * 24, n_best=n_best, weights=w, power=power, max_shift_h=48)
    except finder.DateRangeError as e:
        st.error(f"{names[s]}: {e}")
        continue
    bw.insert(0, "site_id", s)
    results.append(bw)

with col_main:
    if not results:
        st.warning("No windows found.")
        st.stop()
    res = pd.concat(results, ignore_index=True)
    res = res.sort_values(["score", "pct_both", "start_utc"], ascending=[False, False, True]).reset_index(drop=True)
    top = res.iloc[0]
    by_site = res.groupby("site_id").agg(score=("score", "mean"), sun=("pct_sunlit", "mean"), dte=("pct_dte", "mean"))
    robust = by_site.sort_values(["score", "sun"], ascending=False).index[0]
    lo = res.sort_values(["required_nameplate_kwh", "score"], ascending=[True, False]).iloc[0]
    n_zero = int((res.required_nameplate_kwh < 0.5).sum())
    k = st.columns(3)
    k[0].markdown(ui.kcard("emoji_events", "Best Overall Window", f"{pd.Timestamp(top.start_utc):%Y-%m-%d %H:%M} UTC",
                           f"{names[top.site_id]} · Score {top.score:.0f}", ui.TEAL), unsafe_allow_html=True)
    k[1].markdown(ui.kcard("layers", "Most Robust Site", names[robust],
                           f"Avg. score {by_site.loc[robust, 'score']:.0f} · Sun {by_site.loc[robust, 'sun']:.0f}% · "
                           f"Earth {by_site.loc[robust, 'dte']:.0f}%", ui.TEAL), unsafe_allow_html=True)
    k[2].markdown(ui.kcard("battery_charging_full", "Lowest Storage Need", f"{lo.required_nameplate_kwh:.0f} kWh",
                           f"{n_zero} of {len(res)} windows need no battery" if n_zero else
                           f"{names[lo.site_id]} · {pd.Timestamp(lo.start_utc):%Y-%m-%d}", ui.AMBER, amber=True),
                  unsafe_allow_html=True)
    st.write("")

    with st.container(key="card_ranked"):
        ui.card_title("format_list_numbered", "Ranked Landing Windows",
                      f"hourly scan · {dur_days:g}-day stays · {'DSN-confirmed ' if req else ''}Earth contact")
        rows = []
        for i, r in res.head(12).iterrows():
            terr = ui.terrain_status(r.site_id)
            tc = ui.BOTH if terr == "real" else "#FF6B8B"
            rows.append(
                f'<tr class="{"top" if i == 0 else ""}"><td>{i + 1}</td><td>{names[r.site_id]}</td>'
                f'<td>{pd.Timestamp(r.start_utc):%Y-%m-%d %H:%M}</td>'
                f'<td><span class="lln-bar" style="width:{max(4, r.score):.0f}px"></span>&nbsp; {r.score:.0f}</td>'
                f'<td><span class="lln-pv">{r.pct_sunlit:.0f}</span></td><td><span class="lln-pv">{r.pct_dte:.0f}</span></td>'
                f'<td><span class="lln-pv">{r.pct_both:.0f}</span></td><td>{r.longest_dark_h:.0f} h</td>'
                f'<td>{r.longest_no_dte_h:.0f} h</td><td>{r.required_nameplate_kwh:.0f} kWh</td>'
                f'<td>{ui.chip(terr.title(), tc)}</td></tr>')
        st.markdown('<table class="lln-table"><tr><th>#</th><th>Site</th><th>Start UTC</th><th>Score</th>'
                    '<th>Sun %</th><th>Earth %</th><th>Both %</th><th>Longest Dark</th><th>Longest No-Earth</th>'
                    '<th>Storage</th><th>Terrain</th></tr>' + "".join(rows) + "</table>", unsafe_allow_html=True)
        st.caption("Hourly samples (approximate) — open a window in Mission Overview for a 10-minute check. Start "
                   "dates are limited so the stay plus a 48 h slip stays inside the data.")
    st.write("")

    with st.container(key="card_heatmap"):
        a, b = st.columns([1.6, 1])
        with a:
            ui.card_title("grid_view", "Calendar Heatmap", "daily fraction of hours")
        with b:
            metric = st.segmented_control("Metric", ["sunlit", "dte_visible", "both"], default="sunlit",
                                          format_func={"sunlit": "☀️ Sunlit", "dte_visible": "📡 Potential DTE",
                                                       "both": "◐ Both"}.get, label_visibility="collapsed")
        z, ys = [], []
        for s in chosen:
            d = finder.daily_heatmap(site_vis(s, thr, mask, req), metric or "sunlit")
            d = d[(d.index >= pd.Timestamp(rng[0], tz="UTC")) & (d.index <= pd.Timestamp(rng[1], tz="UTC"))]
            z.append(d.values)
            ys.append(names[s])
            x = d.index
        hm = go.Figure(go.Heatmap(z=z, x=x, y=ys, zmin=0, zmax=1, colorscale="Cividis",
                                  colorbar=dict(title=dict(text="Fraction"), thickness=14)))
        st.plotly_chart(ui.style_fig(hm, 140 + 52 * len(ys)), width="stretch", config={"displayModeBar": False})

ui.footer()
