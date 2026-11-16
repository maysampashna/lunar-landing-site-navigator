"""Date Finder — rank surface-start windows by sunlight, potential DTE and combined score."""
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
if st.session_state.pop("_goto_overview", False):
    st.switch_page("views/overview.py")
names = ui.names()
ui.banner("calendar_month", "Date Finder",
          "Find the surface-start dates that give the most sunlight and potential direct-to-Earth contact.")

col_ctl, col_main = st.columns([0.85, 3.15])
with col_ctl:
    with st.container(key="card_search"):
        ui.card_title("tune", "Search Setup")
        st.caption("Location")
        chosen = st.multiselect("Sites", list(names), format_func=names.get, key="m_sites")
        st.caption("Stay and date range")
        dur_days = st.number_input("Surface stay (days)", 1.0, 14.0, step=0.5, key="m_dur")
        first, last = finder.valid_start_range(ui.ephem(list(names)[0]), dur_days * 24, 48)
        rng = st.date_input("Search starts between (UTC)",
                            (pd.Timestamp("2027-01-01").date(), pd.Timestamp("2027-12-31").date()),
                            min_value=first.date(), max_value=last.date())
        st.caption("Visibility thresholds")
        thr = st.slider("Sunlit if ≥ this fraction of the Sun's disc is visible", 0.05, 1.0, 0.5, 0.05)
        mask = st.slider("Earth clearance above terrain (°)", 0.0, 10.0, 0.0, 0.5)
        req = st.toggle("Require DSN geometry", True,
                        help="Count DTE only when a DSN complex also sees the Moon above 10° (geometry only).")
        with st.expander("Advanced scoring", icon=":material/settings:"):
            n_best = st.slider("Windows kept per site", 1, 10, 5)
            w = ui.weights_sidebar(expander=False)

if not chosen or not isinstance(rng, tuple) or len(rng) != 2:
    with col_main:
        st.info("Pick sites and a start/end date.")
    st.stop()


site_vis = ui.site_vis_hourly


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


def open_in_overview(sid, t0, dur):
    """Button callback: copy the window into the shared mission selections, then switch page."""
    t0 = pd.Timestamp(t0)
    t0 = min(t0, pd.Timestamp("2031-02-10 23:00", tz="UTC"))
    if sid not in st.session_state["m_sites"]:
        st.session_state["m_sites"] = list(st.session_state["m_sites"]) + [sid]
    st.session_state.update(m_date=t0.date(), m_hour=int(t0.hour), m_dur=float(dur), m_site=sid,
                            _goto_overview=True)


with col_main:
    if not results:
        st.warning("No windows found.")
        st.stop()
    res = pd.concat(results, ignore_index=True)
    res = res.sort_values(["score", "pct_both", "start_utc"], ascending=[False, False, True]).reset_index(drop=True)
    res["rs"] = res.score.round().astype(int)
    res["rank"] = res.rs.rank(method="min", ascending=False).astype(int)
    top = res.iloc[0]
    n_top = int((res.rs == res.rs.iloc[0]).sum())
    by_site = res.groupby("site_id").agg(score=("score", "mean"), sun=("pct_sunlit", "mean"), dte=("pct_dte", "mean"))
    robust = by_site.sort_values(["score", "sun"], ascending=False).index[0]
    lo = res.sort_values(["required_nameplate_kwh", "score"], ascending=[True, False]).iloc[0]
    n_zero = int((res.required_nameplate_kwh < 0.5).sum())
    k = st.columns(3)
    k[0].markdown(ui.kcard("emoji_events", "Top score", f"{top.rs} / 100",
                           f"{n_top} windows tie · earliest: {names[top.site_id]}, "
                           f"{pd.Timestamp(top.start_utc):%Y-%m-%d %H:%M}" if n_top > 1 else
                           f"{names[top.site_id]} · {pd.Timestamp(top.start_utc):%Y-%m-%d %H:%M} UTC", ui.TEAL),
                  unsafe_allow_html=True)
    k[1].markdown(ui.kcard("layers", "Most consistent site", names[robust],
                           f"Mean of its top windows: score {by_site.loc[robust, 'score']:.0f} · Sun "
                           f"{by_site.loc[robust, 'sun']:.0f}% · DTE {by_site.loc[robust, 'dte']:.0f}%", ui.TEAL),
                  unsafe_allow_html=True)
    k[2].markdown(ui.kcard("battery_charging_full", "Lowest storage need", f"{lo.required_nameplate_kwh:.0f} kWh",
                           f"{n_zero} of {len(res)} windows need none (illustrative 1 kW load)" if n_zero else
                           f"{names[lo.site_id]} · {pd.Timestamp(lo.start_utc):%Y-%m-%d}", ui.SUN),
                  unsafe_allow_html=True)
    st.write("")

    with st.container(key="card_ranked"):
        ui.card_title("format_list_numbered", "Ranked landing windows",
                      f"{dur_days:g}-day stays · hourly scan · {'DSN geometry required' if req else 'Earth above terrain'}")
        shown = res.head(12)
        all_lola = all(ui.terrain_status(x) == "real" for x in shown.site_id)
        rows = []
        for i, r in shown.iterrows():
            terr = ui.terrain_status(r.site_id)
            tied = int((res.rs == r.rs).sum()) > 1
            rows.append(
                f'<tr class="{"top" if r.rs == top.rs else ""}"><td>{r["rank"]}{"=" if tied else ""}</td>'
                f'<td><b>{names[r.site_id]}</b></td><td>{pd.Timestamp(r.start_utc):%Y-%m-%d %H:%M}</td>'
                f'<td class="n"><span class="lln-bar" style="width:{max(3, 0.6 * r.score):.0f}px;'
                f'background:{ui.TEAL}"></span>&nbsp;<b>{r.rs}</b></td>'
                f'<td class="n">{r.pct_sunlit:.0f}</td><td class="n">{r.pct_dte:.0f}</td><td class="n">{r.pct_both:.0f}</td>'
                f'<td class="n">{r.longest_dark_h:.0f}</td><td class="n">{r.longest_no_dte_h:.0f}</td>'
                f'<td class="n">{r.required_nameplate_kwh:.0f}</td>'
                + ("" if all_lola else f'<td>{"LOLA" if terr == "real" else ui.chip(terr.title(), "#FF6B8B")}</td>')
                + '</tr>')
        st.markdown(
            '<table class="lln-table"><tr><th>#</th><th>Site</th><th>Start (UTC)</th>'
            '<th class="n" title="User-weighted preference score, 0–100 (not a safety rating)">Score</th>'
            '<th class="n" title="Share of the stay with the Sun sufficiently above terrain">Sun %</th>'
            '<th class="n" title="Share of the stay with potential direct-to-Earth line of sight">DTE %</th>'
            '<th class="n" title="Sunlit and potential DTE at the same time">Both %</th>'
            '<th class="n" title="Longest continuous period without sunlight">Longest dark (h)</th>'
            '<th class="n" title="Longest continuous period without potential DTE">Longest no-DTE (h)</th>'
            '<th class="n" title="Illustrative battery nameplate for a constant 1 kW load">Storage (kWh)</th>'
            + ("" if all_lola else '<th title="Terrain source for the horizon">Terrain</th>') + '</tr>'
            + "".join(rows) + "</table>",
            unsafe_allow_html=True)
        st.caption("All horizons from NASA LOLA terrain. Equal scores share a rank (1=) and are equally good under these criteria; they are listed by "
                   "Both %, then earliest start. Score is for the planned start (hourly samples); Mission Overview re-checks it at 10 minutes and with +24/+48 h start shifts.")
        a, b = st.columns([3, 1.2], vertical_alignment="bottom")
        pick = a.selectbox("Open a window in Mission Overview", list(shown.index),
                           format_func=lambda i: f"#{shown.loc[i, 'rank']}  {names[shown.loc[i, 'site_id']]} · "
                                                 f"{pd.Timestamp(shown.loc[i, 'start_utc']):%Y-%m-%d %H:%M} UTC · "
                                                 f"score {shown.loc[i, 'rs']}")
        b.button("Open in Mission Overview", icon=":material/arrow_forward:", type="primary", width="stretch",
                 on_click=open_in_overview,
                 args=(shown.loc[pick, "site_id"], shown.loc[pick, "start_utc"], dur_days))
    st.write("")

    with st.container(key="card_heatmap"):
        a, b = st.columns([1.5, 1], vertical_alignment="center")
        with a:
            ui.card_title("grid_view", "Calendar heatmap", "share of each day's hours")
        with b:
            metric = st.segmented_control("Metric", ["sunlit", "dte_visible", "both"], default="sunlit",
                                          format_func={"sunlit": "Sunlit", "dte_visible": "Potential DTE",
                                                       "both": "Both"}.get, label_visibility="collapsed") or "sunlit"
        hue = {"sunlit": ui.SUN, "dte_visible": ui.EARTH, "both": ui.BOTH}[metric]
        z, ys = [], []
        for s in chosen:
            d = finder.daily_heatmap(site_vis(s, thr, mask, req), metric)
            d = d[(d.index >= pd.Timestamp(rng[0], tz="UTC")) & (d.index <= pd.Timestamp(rng[1], tz="UTC"))]
            z.append(d.values)
            ys.append(names[s])
            x = d.index
        hm = go.Figure(go.Heatmap(z=z, x=x, y=ys, zmin=0, zmax=1, colorscale=[[0, "#0A1A26"], [1, hue]],
                                  xgap=0.5, ygap=3,
                                  hovertemplate="%{y}<br>%{x|%Y-%m-%d}<br>%{z:.0%} of hours<extra></extra>",
                                  colorbar=dict(title=dict(text="Share of<br>hours"), tickformat=".0%",
                                                thickness=12, len=0.9)))
        hm.update_xaxes(dtick="M1", tickformat="%b\n%Y", showgrid=False)
        hm.update_yaxes(showgrid=False, tickfont=dict(size=13))
        st.plotly_chart(ui.style_fig(hm, 120 + 46 * len(ys)), width="stretch", config={"displayModeBar": False})

ui.footer()
