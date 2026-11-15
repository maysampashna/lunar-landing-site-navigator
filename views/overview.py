"""Lunar Landing Site Navigator — Mission Overview (main page).

Run:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from engine import finder, live, visibility
from engine.power import PowerParams
import ui_common as ui

ui.setup_page("Lunar Landing Site Navigator")
sites = ui.sites_df()
names = ui.names()
DEFAULT_SITES = [s for s in ["malapert_massif", "de_gerlache_rim_2", "mons_mouton", "nobile_rim_2"] if s in names]

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### 🚀 Mission setup")
    chosen = st.multiselect("📍 Candidate sites", list(names), default=DEFAULT_SITES or list(names)[:4],
                            format_func=names.get)
    dur_days = st.number_input("🗓️ Surface stay (days)", 1.0, 14.0, 6.0, 0.5)
    extra = st.multiselect("⏱️ Arrival-slip scenarios (h)", [24, 48, 72], default=[24, 48])
    shifts = sorted({0, *extra})
    earliest, latest = finder.valid_start_range(ui.ephem(list(names)[0]), dur_days * 24, max(shifts))
    start_date = st.date_input("🛬 Surface start (UTC)", pd.Timestamp("2027-08-16").date(),
                               min_value=earliest.date(), max_value=latest.date())
    start_hour = st.slider("Start hour (UTC)", 0, 23, 12)
    with st.expander("👁️ Visibility assumptions"):
        thr = st.slider("Sunlit if ≥ this fraction of the Sun's disc is visible", 0.05, 1.0, 0.5, 0.05)
        mask = st.slider("Earth elevation mask above terrain (°)", 0.0, 10.0, 0.0, 0.5)
    with st.expander("🔋 Illustrative power model"):
        area = st.number_input("Array area (m²)", 1.0, 200.0, 10.0)
        eff = st.slider("Array efficiency", 0.1, 0.4, 0.30)
        load = st.number_input("Constant load (W)", 50.0, 20000.0, 1000.0, 50.0)
    w = ui.weights_sidebar()

start = pd.Timestamp(start_date).tz_localize("UTC") + pd.Timedelta(hours=start_hour)
st.session_state["mission"] = {"sites": chosen, "start": start, "dur_days": dur_days}

# ------------------------------------------------------------------ header
v = ui.validation_report()
badge = (f'<span class="lln-badge">✔ Ephemeris validated vs JPL Horizons · max error '
         f'{v["overall_max_error_deg"]:.5f}°</span>' if v else "")
st.markdown(f'<div class="lln-hero"><h1>🌘 Lunar Landing Site Navigator</h1>{badge}</div>'
            '<div class="lln-sub">Which south-pole site gives the best sunlight and Earth contact for your mission — '
            'and does the answer survive a schedule slip? · Artemis III candidate regions (crewed landing now planned '
            'for Artemis IV) · representative points, not NASA-designated landing sites</div>', unsafe_allow_html=True)

if not chosen:
    st.info("Pick at least one site in the sidebar.")
    st.stop()
banners = ui.data_banners(chosen)

power = PowerParams(array_area_m2=area, efficiency=eff, load_w=load)
params = visibility.VisParams(sunlit_threshold=thr, earth_mask_deg=mask, power=power)
if live.kernels_available():
    end = start + pd.Timedelta(hours=dur_days * 24 + max(shifts))
    srows = sites.set_index("site_id")
    vis = {s: live.fine_visibility(srows.loc[s], ui.horizon(s), start, end, params, step_min=10) for s in chosen}
    resolution_note = "10-minute resolution"
else:
    vis = {s: ui.hourly_vis(s, thr, mask, area, eff, load) for s in chosen}
    resolution_note = "hourly (approximate)"

try:
    table, best = finder.shift_compare(vis, start, duration_h=dur_days * 24, shifts_h=tuple(shifts),
                                       weights=w, power=power,
                                       terrain_real={s: ui.terrain_status(s) == "real" for s in chosen})
except finder.DateRangeError as e:
    st.error(str(e))
    st.stop()

base = table[table.shift_h == 0].set_index("site_id")
worst = table.groupby("site_id")["worst_case_score"].first()
order = list(worst.sort_values(ascending=False).index)
top = best or order[0]
scores = worst.to_dict()

# ------------------------------------------------------------------ KPI row
k = st.columns(4)
k[0].markdown(ui.kpi("Mission window", f"{dur_days:g} days", f"from {start:%d %b %Y, %H:%M} UTC"), unsafe_allow_html=True)
k[1].markdown(ui.kpi("Sites compared", f"{len(chosen)}", f"{len(shifts)} timing scenarios · {resolution_note}"),
              unsafe_allow_html=True)
lab, col = ui.rating(worst[top])
k[2].markdown(ui.kpi("Best worst-case score", f"{worst[top]:.0f}/100", f"{names[top]} · {lab}", col),
              unsafe_allow_html=True)
k[3].markdown(ui.kpi("Ephemeris error vs JPL", f"{v['overall_max_error_deg']:.5f}°" if v else "—",
                     "Sun & Earth positions, 8 sites", ui.BOTH if v else "#E6EAF2"), unsafe_allow_html=True)
st.write("")

# ------------------------------------------------------------------ map + comparison
left, right = st.columns([1.05, 1])
with left:
    with st.container(border=True):
        st.markdown("**🗺️ South-pole candidate sites** · real LOLA terrain shading · colour = rating")
        st.plotly_chart(ui.south_pole_map(chosen, scores, height=520, highlight=top), width="stretch",
                        config={"displayModeBar": False, "scrollZoom": False})

with right:
    rows = []
    for sid in order:
        r = base.loc[sid]
        lab, col = ui.rating(r.worst_case_score)
        rows.append(f'<tr><td><span class="lln-dot" style="background:{col}"></span>{names[sid]}</td>'
                    f'<td>{r.pct_sunlit:.0f}%</td><td>{r.pct_dte:.0f}%</td><td>{r.pct_both:.0f}%</td>'
                    f'<td>{r.longest_dark_h:.0f} h</td><td><b>{r.worst_case_score:.0f}</b></td>'
                    f'<td>{ui.chip(lab, col)}</td></tr>')
    st.markdown('<div class="lln-card"><h4>📊 Landing site comparison</h4><table class="lln-table">'
                '<tr><th>Site</th><th>☀️ Sun</th><th>🌍 Earth</th><th>Both</th><th>Longest dark</th>'
                '<th>Worst-case</th><th>Rating</th></tr>' + "".join(rows) + "</table></div>", unsafe_allow_html=True)
    st.write("")

    # recommendation
    fragile = []
    for sid in chosen:
        sc = table[table.site_id == sid].set_index("shift_h")["score"]
        if sc.loc[0] - sc.min() >= 5:
            fragile.append(f"<b>{names[sid]}</b> drops from {sc.loc[0]:.0f} to {sc.min():.0f} "
                           f"if arrival slips {int(sc.idxmin())} h")
    if best is not None:
        r = base.loc[best]
        runner = [s for s in order if s != best]
        txt = (f"<b>{names[best]}</b> is the best modeled location for a {dur_days:g}-day stay starting "
               f"{start:%d %b %Y}: {r.pct_sunlit:.0f}% sunlight and {r.pct_dte:.0f}% potential Earth contact, "
               f"with a worst-case score of {worst[best]:.0f} across "
               f"{', '.join(f'+{s} h' for s in shifts)} arrival scenarios.")
        if runner:
            txt += f" Runner-up: {names[runner[0]]} ({worst[runner[0]]:.0f})."
        if fragile:
            txt += "<br>⚠️ Timing risk: " + "; ".join(fragile) + "."
        st.markdown(f'<div class="lln-rec"><h4>✅ Recommendation</h4>{txt}<br>'
                    '<span style="color:#9AA4B8;font-size:0.8rem">Best modeled location under your selected '
                    'criteria — not a landing-safety assessment.</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="lln-warn"><h4>Demonstration ranking</h4>Top: <b>{names[top]}</b> '
                    f'(worst-case {worst[top]:.0f}). No confident recommendation: terrain data is synthetic, missing '
                    'or incomplete for these sites.</div>', unsafe_allow_html=True)
    if table.pct_eclipsed.max() > 0:
        st.info("🌑 A lunar eclipse (Earth passing in front of the Sun, as seen from the Moon) falls inside this "
                "window; it is included in sunlight and power.")

# ------------------------------------------------------------------ visibility timeline
st.write("")
st.markdown("#### 🕒 Visibility timeline — when each site has sunlight and Earth in view")
segs = []
for sid in order:
    w0 = finder.window(vis[sid], start, dur_days * 24)
    t = pd.DatetimeIndex(w0.time_utc)
    dt = t[1] - t[0]
    for kind, colname in (("☀️ Sunlight", "sunlit"), ("🌍 Earth in view", "dte_visible")):
        m = w0[colname].to_numpy(bool)
        edges = np.flatnonzero(np.diff(np.concatenate([[0], m.astype(int), [0]])))
        for a, b in zip(edges[0::2], edges[1::2]):
            segs.append({"Site": names[sid], "Kind": kind, "Start": t[a], "Finish": t[b - 1] + dt})
if segs:
    sdf = pd.DataFrame(segs)
    sdf["Row"] = sdf.Site + (" · " + sdf.Kind.str.split(" ").str[0])
    fig = px.timeline(sdf, x_start="Start", x_end="Finish", y="Row", color="Kind", opacity=0.92,
                      color_discrete_map={"☀️ Sunlight": ui.SUN, "🌍 Earth in view": ui.EARTH})
    cats = [f"{names[s]} · {e}" for s in order for e in ("☀️", "🌍")]
    fig.update_yaxes(categoryorder="array", categoryarray=cats[::-1], title=None)
    fig.update_xaxes(title=None)
    fig.update_layout(legend_title_text="")
    st.plotly_chart(ui.style_fig(fig, height=110 + 44 * len(order)), width="stretch")
else:
    st.caption("No sunlight or Earth visibility at any selected site in this window.")

# ------------------------------------------------------------------ sensitivity + storage
c1, c2 = st.columns(2)
with c1:
    fig = go.Figure()
    for sid in order:
        sc = table[table.site_id == sid].sort_values("shift_h")
        fig.add_trace(go.Scatter(x=[f"+{h} h" for h in sc.shift_h], y=sc.score, mode="lines+markers",
                                 name=names[sid], line=dict(color=ui.site_color(sid), width=3), marker=dict(size=9)))
    fig.update_yaxes(range=[-3, 103], title="Score")
    st.plotly_chart(ui.style_fig(fig, 340, "⏱️ Timing sensitivity — score if arrival slips"), width="stretch")
with c2:
    fig = go.Figure(go.Bar(x=[names[s] for s in order], y=[base.loc[s, "required_nameplate_kwh"] for s in order],
                           marker_color=[ui.site_color(s) for s in order],
                           text=[f"{base.loc[s, 'required_nameplate_kwh']:.0f} kWh" for s in order],
                           textposition="outside"))
    fig.update_yaxes(title="Battery (kWh, nameplate)")
    st.plotly_chart(ui.style_fig(fig, 340, f"🔋 Illustrative storage to ride through darkness ({load:.0f} W load)"),
                    width="stretch")

with st.expander("📋 All metrics (every site × arrival scenario)"):
    show = table[["site_id", "shift_h", "pct_sunlit", "pct_dte", "pct_both", "longest_dark_h", "longest_no_dte_h",
                  "mean_solar_w", "required_nameplate_kwh", "soc_end", "pct_uncertain", "pct_eclipsed", "score",
                  "worst_case_score", "terrain_real", "confident"]].copy()
    show["site_id"] = show.site_id.map(names)
    st.dataframe(show.round(2), width="stretch", hide_index=True)

st.caption("➡️ Open **Sky View** in the sidebar to watch the Sun and Earth move over the real horizon at any site.")
ui.footer()
