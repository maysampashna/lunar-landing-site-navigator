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
    st.switch_page("views/mission.py")
names = ui.names()
ui.help_button()
ui.banner("event_available", "Best Date Finder",
          "Find the landing dates that give the most sunlight and Earth contact.")

st.markdown("""<style>
.st-key-df_sites {background:rgba(45,212,191,0.06); border:1px solid rgba(45,212,191,0.35); border-radius:12px;
   padding:10px 14px 12px 14px !important;}
.st-key-df_sites [data-testid="stWidgetLabel"] p {color:#7FF0DD; font-weight:700; font-size:0.9rem;}
.st-key-df_sites button[aria-pressed="false"] {background:rgba(255,255,255,0.03) !important; border:1px solid #2A4555 !important;}
.st-key-df_sites button[aria-pressed="false"] * {color:#9FB4C0 !important;}
.st-key-df_sites button[aria-pressed="true"] {background:#2DD4BF !important; border:1px solid #2DD4BF !important;
   box-shadow:0 0 10px rgba(45,212,191,0.45);}
.st-key-df_sites button[aria-pressed="true"] * {color:#04161F !important; font-weight:700;}
</style>""", unsafe_allow_html=True)
with st.container(key="card_search"):
    ui.card_title("tune", "Search setup")
    with st.container(key="df_sites"):
        chosen = st.pills("Candidate sites  ·  click to add or remove", list(names), selection_mode="multi",
                          format_func=names.get, key="m_sites")
    chosen = [x for x in names if x in (chosen or [])]
    c = st.columns([1.0, 2.0, 1.0], vertical_alignment="bottom")
    dur_days = c[0].number_input("Surface stay (days)", 1.0, 14.0, step=0.5, key="m_dur",
                                 help="How long the lander stays on the surface.")
    first, last = finder.valid_start_range(ui.ephem(list(names)[0]), dur_days * 24, 48)
    rng = c[1].date_input("Search landing dates between (UTC)",
                          (pd.Timestamp("2027-01-01").date(), pd.Timestamp("2027-12-31").date()),
                          min_value=first.date(), max_value=last.date(),
                          help="Every hour in this range is tried as a landing time.")
    with c[2].popover("Advanced", icon=":material/settings:", width="stretch",
                      help="Optional. Try your own rules or priorities; the defaults work for most uses."):
        req = st.toggle("Require a NASA DSN antenna to see the Moon", True,
                        help="On: Earth contact also needs a Deep Space Network dish to see the Moon.")
        thr = st.slider("Sunlit when this fraction of the Sun's disc is visible", 0.05, 1.0, 0.5, 0.05,
                        help="0.5 = sunlit when at least half of the Sun is above the hills.")
        mask = st.slider("Earth clearance above terrain (°)", 0.0, 10.0, 0.0, 0.5,
                         help="How far Earth must rise above the hills before contact counts.")
        n_best = st.slider("Best dates kept per site", 1, 10, 5, help="How many top dates to list for each site.")
        w = ui.weights_sidebar(expander=False)
st.write("")
col_main = st.container()

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
    with st.container(key="card_ranked"):
        ui.card_title("format_list_numbered", "Best landing dates", f"{dur_days:g}-day stay")
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
                f'<td class="n">{r.pct_sunlit:.0f}</td><td class="n">{r.pct_dte:.0f}</td>'
                f'<td class="n">{r.longest_dark_h:.0f}</td><td class="n">{r.longest_no_dte_h:.0f}</td>'
                f'<td class="n">{r.required_nameplate_kwh:.0f}</td>'
                + ("" if all_lola else f'<td>{"LOLA" if terr == "real" else ui.chip(terr.title(), "#FF6B8B")}</td>')
                + '</tr>')
        st.markdown(
            '<table class="lln-table"><tr><th data-tip="Rank. 1= means several dates share the same score.">#</th>'
            '<th>Site</th><th data-tip="Landing time to start the stay (UTC).">Landing (UTC)</th>'
            '<th class="n" data-tip="0–100. Higher = more sunlight and Earth contact, shorter gaps. A planning '
            'preference, not a safety rating.">Score</th>'
            '<th class="n" data-tip="Percent of the stay when the Sun is above the hills (power).">Sunlight %</th>'
            '<th class="n" data-tip="Percent of the stay when the lander can talk directly to Earth.">'
            'Earth contact %</th>'
            '<th class="n" data-tip="Longest stretch, in hours, with no sunlight.">Longest dark (h)</th>'
            '<th class="n" data-tip="Longest stretch, in hours, with no Earth contact.">Longest Earth gap (h)</th>'
            '<th class="n tip-r" data-tip="Rough battery size for a 1 kW lander to get through the dark periods. '
            'Illustrative.">Battery needed (kWh)</th>'
            + ("" if all_lola else '<th title="Terrain source for the horizon">Terrain</th>') + '</tr>'
            + "".join(rows) + "</table>",
            unsafe_allow_html=True)
        st.caption("Equal scores share a rank (1=). Open a date in the Mission Dashboard to check it in detail, "
                   "including landing delays.")
        a, b = st.columns([3, 1.2], vertical_alignment="bottom")
        pick = a.selectbox("Open a date in the Mission Dashboard", list(shown.index),
                           format_func=lambda i: f"#{shown.loc[i, 'rank']}  {names[shown.loc[i, 'site_id']]} · "
                                                 f"{pd.Timestamp(shown.loc[i, 'start_utc']):%Y-%m-%d %H:%M} UTC · "
                                                 f"score {shown.loc[i, 'rs']}")
        b.button("Open in Mission Dashboard", icon=":material/arrow_forward:", type="primary", width="stretch",
                 on_click=open_in_overview,
                 args=(shown.loc[pick, "site_id"], shown.loc[pick, "start_utc"], dur_days))
    st.write("")

    with st.container(key="card_heatmap"):
        a, b = st.columns([1.5, 1], vertical_alignment="center")
        with a:
            st.markdown(f'<div class="lln-ct">{ui.mi("grid_view")}<span>Calendar</span>'
                        '<span class="lln-help" data-tip="Each row is a site, each square a day. Brighter = more of '
                        'that day has sunlight (or Earth contact). Use it to spot good periods at a glance.">?</span>'
                        '</div>', unsafe_allow_html=True)
        with b:
            metric = st.segmented_control("Metric", ["sunlit", "dte_visible", "both"], default="sunlit",
                                          format_func={"sunlit": "Sunlight", "dte_visible": "Earth contact",
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
