"""Mission Dashboard — one control panel; 3D/panorama/sky views, map, clock, decision summary and analysis."""
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
from engine.dsn import DSN_COMPLEXES
from engine.power import PowerParams
import ui_common as ui

ui.setup_page()
srows = ui.sites_df().set_index("site_id")
names = ui.names()
if not live.kernels_available():
    st.error("Ephemeris kernels are missing from this deployment.")
    st.stop()

if st.session_state["m_sites"] and st.session_state.get("m_site") not in st.session_state["m_sites"]:
    st.session_state["m_site"] = st.session_state["m_sites"][0]

ui.banner("space_dashboard", "Mission Dashboard",
          "One control panel for sites, landing time and stay — every view below updates together.")

# ================================================================== the single control panel (horizontal)
with st.container(key="card_ctl"):
    ui.card_title("tune", "Mission controls")
    st.markdown("""<style>
.st-key-sites_box {background:rgba(45,212,191,0.06); border:1px solid rgba(45,212,191,0.35); border-radius:12px;
   padding:10px 14px 12px 14px !important;}
.st-key-sites_box [data-testid="stWidgetLabel"] p {color:#7FF0DD; font-weight:700; font-size:0.9rem;}
.st-key-sites_box button[aria-pressed="false"] {background:rgba(255,255,255,0.03) !important; border:1px solid #2A4555 !important;}
.st-key-sites_box button[aria-pressed="false"] * {color:#9FB4C0 !important;}
.st-key-sites_box button[aria-pressed="false"]:hover {border-color:#2DD4BF; color:#E6F1F5;}
.st-key-sites_box button[aria-pressed="true"] {background:#2DD4BF !important; border:1px solid #2DD4BF !important; color:#04161F;
   font-weight:700; box-shadow:0 0 10px rgba(45,212,191,0.45);}
.st-key-sites_box button[aria-pressed="true"] * {color:#04161F !important; font-weight:700;}
</style>""", unsafe_allow_html=True)
    with st.container(key="sites_box"):
        chosen = st.pills("Candidate sites  ·  click to add or remove", list(names), selection_mode="multi",
                          format_func=names.get, key="m_sites")
    if not chosen:
        st.info("Pick at least one site.")
        st.stop()
    chosen = [x for x in names if x in chosen]                         # stable, map order
    c = st.columns([1.5, 1.1, 0.6, 1.5, 1.0], vertical_alignment="bottom")
    focus = c[0].selectbox("Site shown in 3D", chosen, format_func=names.get, key="m_site")
    c[1].date_input("Landing (UTC)", min_value=pd.Timestamp("2026-01-02").date(),
                    max_value=pd.Timestamp("2031-02-10").date(), key="m_date")
    c[2].number_input("Hour", 0, 23, key="m_hour")
    dur_days = c[3].slider("Surface stay (days)", 1.0, 14.0, step=0.5, key="m_dur")
    adv = c[4].popover("Advanced", icon=":material/settings:", width="stretch")
    time_slot = st.container()
    with adv:
        def grp(icon, title):
            st.markdown(f'<div class="lln-ct" style="font-size:0.98rem;margin:6px 0 2px 0;border-bottom:1px solid '
                        f'#1C3A4A;padding-bottom:4px">{ui.mi(icon, 20)}<span>{title}</span></div>',
                        unsafe_allow_html=True)
        st.markdown('<div style="background:rgba(45,212,191,0.08);border:1px solid rgba(45,212,191,0.35);'
                    'border-radius:10px;padding:10px 12px;font-size:0.86rem;color:#DCE9EF;line-height:1.45">'
                    '<b style="color:#7FF0DD">Why these settings?</b> The defaults describe a typical small lander '
                    'and are fine for most comparisons. Change them only to ask <i>"what if?"</i> — for a different '
                    'spacecraft, a stricter mission rule, or different priorities — and watch the ranking update. '
                    'Hover the <b>?</b> next to any setting for details.</div>', unsafe_allow_html=True)

        def when(text):
            st.markdown(f'<div style="color:#8FA4B0;font-size:0.8rem;margin:-2px 0 4px 0">When to change: {text}</div>',
                        unsafe_allow_html=True)
        grp("cell_tower", "Communication (Earth contact)")
        when("your mission has its own rules for when Earth contact counts, or uses a relay instead of the DSN.")
        require_dsn = st.toggle("Require a NASA DSN antenna to see the Moon", True, help="On: Earth contact also needs one of NASA's Deep Space Network dishes (California, Spain, Australia) to see the Moon. Off: Earth above the hills is enough.")
        dsn_mask = st.slider("DSN minimum elevation (°)", 0.0, 20.0, 10.0, 1.0, help="How high the Moon must be in the sky at a DSN dish before it can be used. 10° is a typical value.")
        mask = st.slider("Earth clearance above terrain (°)", 0.0, 10.0, 0.0, 0.5, help="Extra safety margin: how far Earth must rise above the hills before contact counts. 0 = just above the skyline.")
        grp("wb_sunny", "Power (sunlight and battery)")
        when("your lander has different solar panels or uses more or less power — this changes the battery needed.")
        thr = st.slider("Sunlit when this fraction of the Sun's disc is visible", 0.05, 1.0, 0.5, 0.05, help="The Sun often peeks over the hills. 0.5 = the site counts as sunlit when at least half of the Sun is visible.")
        p1, p2 = st.columns(2)
        area = p1.number_input("Solar array (m²)", 1.0, 200.0, 10.0, help="Size of the solar panels. Used only for the battery estimate.")
        eff = p2.slider("Array efficiency", 0.1, 0.4, 0.30, help="Share of sunlight the panels turn into electricity (0.30 = 30 %).")
        load = st.number_input("Constant power load (W)", 50.0, 20000.0, 1000.0, 50.0, help="Power the lander uses all the time. Sets how big the battery must be to get through dark periods.")
        grp("leaderboard", "Ranking")
        when("your mission cares more about power than communication (or the reverse), or expects longer delays.")
        extra = st.multiselect("Landing-delay scenarios (h)", [24, 48, 72], default=[24, 48], help="Landings often slip. The tool re-checks each site as if landing 24 or 48 hours late; Score if delayed is the worst of these.")
        w = ui.weights_sidebar(expander=False)

shifts = sorted({0, *extra})
step_min = 10
start = ui.mission_start()
end_mission = start + pd.Timedelta(days=dur_days)
end_all = start + pd.Timedelta(hours=dur_days * 24 + max(shifts))
power = PowerParams(array_area_m2=area, efficiency=eff, load_w=load)
params = visibility.VisParams(sunlit_threshold=thr, earth_mask_deg=mask, power=power, require_dsn=require_dsn)


@st.cache_data(show_spinner="Computing Sun, Earth and DSN geometry…")
def window_data(chosen_t, start_, end_, step_, thr_, mask_, area_, eff_, load_, req_, dsn_mask_):
    p = visibility.VisParams(sunlit_threshold=thr_, earth_mask_deg=mask_, require_dsn=req_,
                             power=PowerParams(array_area_m2=area_, efficiency=eff_, load_w=load_))
    dsn_ = live.dsn_series(start_, end_, step_, dsn_mask_)
    vis_ = {s: live.fine_visibility(srows.loc[s], ui.horizon(s), start_, end_, p, step_min=step_, dsn=dsn_)
            for s in chosen_t}
    return vis_, dsn_


vis, dsn = window_data(tuple(chosen), start, end_all, step_min, thr, mask, area, eff, load, require_dsn, dsn_mask)
try:
    table, best = finder.shift_compare(vis, start, duration_h=dur_days * 24, shifts_h=tuple(shifts), weights=w,
                                       power=power,
                                       terrain_real={s: ui.terrain_status(s) == "real" for s in chosen})
except finder.DateRangeError as e:
    st.error(f"Choose an earlier landing or a shorter stay. {e}")
    st.stop()
worst = table.groupby("site_id")["worst_case_score"].first()
base = table[table.shift_h == 0].set_index("site_id")
conf = table.groupby("site_id")["confident"].first()
order = sorted(chosen, key=lambda s: (-round(worst[s]), -base.loc[s, "pct_both"],
                                      base.loc[s, "required_nameplate_kwh"], names[s].casefold()))
pool = [s for s in order if conf[s]] or order
top_score = round(worst[pool[0]])
winners = [s for s in pool if round(worst[s]) == top_score]

# one selected time for every view
hours = pd.date_range(start, end_mission, freq="1h")
with time_slot:
    t_sel = st.select_slider("Selected time (UTC)", options=list(hours), value=hours[0],
                             format_func=lambda x: f"{x:%b %d %H:%M}")
t_sel = pd.Timestamp(t_sel)
now_state = {s: live.at_time(srows.loc[s], ui.horizon(s), t_sel, params, dsn_mask) for s in chosen}
status = {s: ui.status_of(bool(r.sunlit), bool(r.dte_visible)) for s, r in now_state.items()}
f0 = now_state[focus]
hp = ui.horizon(focus)


# ================================================================== station ranking
st.markdown(f'<div class="lln-sec">{ui.mi("leaderboard")}Station ranking<span class="lln-tag">over the full stay</span>'
            '</div>', unsafe_allow_html=True)
with st.container():
    late = "/".join(f"+{h}" for h in shifts if h) + " h" if len(shifts) > 1 else "none"
    rows = []
    for sid in order:
        r = base.loc[sid]
        lab, col = ui.rating(r.worst_case_score)
        rank = 1 + sum(round(worst[s]) > round(worst[sid]) for s in order)
        tied = sum(round(worst[s]) == round(worst[sid]) for s in order) > 1
        rows.append(f'<tr class="{"top" if sid in winners else ""}"><td>{rank}{"=" if tied else ""}</td>'
                    f'<td><b>{names[sid]}</b></td>'
                    f'<td class="n">{r.pct_sunlit:.0f}</td><td class="n">{r.pct_dte:.0f}</td>'
                    f'<td class="n">{r.longest_dark_h:.0f}</td><td class="n">{r.longest_no_dte_h:.0f}</td>'
                    f'<td class="n">{r.required_nameplate_kwh:.0f}</td>'
                    f'<td class="n">{r.score:.0f}</td><td class="n"><b>{r.worst_case_score:.0f}</b></td>'
                    f'<td>{ui.chip(lab, col)}</td><td>{ui.chip(*ui.STATUS[status[sid]])}</td></tr>')
    st.markdown(
        '<table class="lln-table"><tr>'
        '<th data-tip="Rank of the site. 1= means two or more sites share the same score.">#</th>'
        '<th data-tip="NASA Artemis III candidate region, shown at one representative point.">Site</th>'
        '<th class="n" data-tip="Percent of the stay when the Sun is above the hills around the site, so solar '
        'panels can make power.">Sunlight %</th>'
        '<th class="n" data-tip="Percent of the stay when Earth is above the hills AND a NASA Deep Space Network '
        'antenna can see the Moon, so the site can talk directly to Earth.">Earth contact %</th>'
        '<th class="n" data-tip="Longest stretch, in hours, with no sunlight. The lander must survive this on '
        'batteries.">Longest dark (h)</th>'
        '<th class="n" data-tip="Longest stretch, in hours, with no direct contact with Earth.">Longest Earth gap (h)</th>'
        '<th class="n" data-tip="Rough battery size needed to keep a 1 kW lander running through the dark '
        'periods. 0 = never dark. Illustrative, not a flight design.">Battery needed (kWh)</th>'
        '<th class="n" data-tip="Overall 0–100 score if the landing happens exactly as planned. Higher = more '
        'sunlight and Earth contact, shorter gaps.">Score on time</th>'
        f'<th class="n" data-tip="Lowest score if the landing slips by {late}. Sites are ranked by this, so a '
        'site that only works on schedule ranks lower.">Score if delayed</th>'
        '<th data-tip="Excellent ≥ 90, Good 70–89, Fair 40–69, Poor below 40 (based on Score if delayed).">Rating</th>'
        '<th class="tip-r" data-tip="Is the Sun and/or Earth visible at the moment chosen on the Selected time '
        'slider?">At selected time</th></tr>'
        + "".join(rows) + "</table>", unsafe_allow_html=True)
    st.caption(f"Columns describe a landing at the planned time. Sites are ranked by **Score if delayed** — the lowest "
               f"score if the landing slips ({late}) — so a site that only works on schedule ranks lower. "
               "Equal scores share a rank (1=). Hover any column header for its definition.")
st.write("")

# ------------------------------------------------------------------ data for the station views
w_f = live.fine_visibility(srows.loc[focus], hp, start, end_mission, params, step_min=60).reset_index(drop=True)
tt_f = pd.DatetimeIndex(w_f.time_utc)
idx = int(np.clip(tt_f.searchsorted(t_sel), 0, len(tt_f) - 1))
az = np.concatenate([hp.az_deg, [360.0]])
hz = np.concatenate([hp.horizon_el_deg, hp.horizon_el_deg[:1]])
ymin = float(min(np.nanmin(hz), w_f.sun_el_deg.min(), w_f.earth_el_deg.min())) - 2
ymax = float(max(np.nanmax(hz), w_f.sun_el_deg.max(), w_f.earth_el_deg.max())) + 3


def sun_marker(row):
    if row.sun_frac <= 0:
        return dict(size=16, symbol="circle-open", color=ui.SUN, line=dict(width=2.5))
    return dict(size=16, symbol="circle", color="#FFD36E", line=dict(color="white", width=1),
                opacity=1.0 if row.sunlit else 0.5)


def earth_marker(row):
    if not row.earth_in_view:
        return dict(size=20, symbol="circle-open", color=ui.EARTH, line=dict(width=2.5))
    return dict(size=20, symbol="circle", color=ui.EARTH, line=dict(color="white", width=1.5))


# ================================================================== station views (full width)
with st.container():
    with st.container(key="card_vis"):
        tab3d, tabpan, tabsky = st.tabs([":material/view_in_ar: 3D Observer View", ":material/panorama: Panorama",
                                         ":material/radar: Sky Chart"])
        with tab3d:
            fig3 = ui.observer_3d(focus, f0, hp, exag=2.0, height=680)
            if fig3 is None:
                st.info("3D terrain tile not available for this site.")
            else:
                st.plotly_chart(fig3, width="stretch", config={"displaylogo": False, "scrollZoom": True,
                                                               "modeBarButtonsToRemove": ["toImage"]})
                st.caption("NASA LOLA terrain (~96 km around the station), lit by the Sun at the selected time; "
                           "heights ×2. Drag to rotate, scroll to zoom. Solid line = in view, dashed = behind terrain.")
        with tabpan:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=az, y=hz, fill="tozeroy", mode="lines", showlegend=False, hoverinfo="skip",
                                     line=dict(color="#9AA4B8", width=1.5), fillcolor="#2B3142"))
            fig.add_trace(go.Scatter(x=[0, 360], y=[ymin, ymin], fill="tonexty", mode="lines", line=dict(width=0),
                                     fillcolor="#2B3142", showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=w_f.sun_az_deg, y=w_f.sun_el_deg, mode="markers", showlegend=False,
                                     marker=dict(size=3, color=ui.SUN, opacity=0.35), hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=w_f.earth_az_deg, y=w_f.earth_el_deg, mode="markers", showlegend=False,
                                     marker=dict(size=3, color=ui.EARTH, opacity=0.45), hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=[f0.sun_az_deg], y=[f0.sun_el_deg], mode="markers", name="Sun",
                                     marker=sun_marker(f0)))
            fig.add_trace(go.Scatter(x=[f0.earth_az_deg], y=[f0.earth_el_deg], mode="markers", name="Earth",
                                     marker=earth_marker(f0)))
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="Hollow = behind terrain",
                                     marker=dict(size=14, symbol="circle-open", color="#C9D8E0", line=dict(width=2))))
            fig.update_xaxes(range=[0, 360], tickvals=[0, 45, 90, 135, 180, 225, 270, 315, 360],
                             ticktext=["N 0°", "NE", "E 90°", "SE", "S 180°", "SW", "W 270°", "NW", "N"], title=None)
            fig.update_yaxes(range=[ymin, ymax], title="Elevation (°)")
            fig = ui.style_fig(fig, 560)
            fig.update_layout(plot_bgcolor="#03050C", margin=dict(l=10, r=10, t=40, b=10),
                              legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.caption("Full 360° skyline from LOLA terrain to 150 km (vertical scale exaggerated). Faint dots = paths "
                       "over the stay; markers = selected time.")
        with tabsky:
            topr = float(np.ceil(max(ymax, 12)))
            rr = lambda el: topr - np.asarray(el, float)      # noqa: E731  centre = high elevation, rim = low
            hrs = (tt_f - tt_f[0]).total_seconds() / 3600
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(theta=np.concatenate([az, az[::-1]]),
                                          r=np.concatenate([rr(hz), np.full_like(az, topr - ymin + 1)]), fill="toself",
                                          fillcolor="#2B3142", line=dict(width=0), name="Ground", hoverinfo="skip"))
            fig.add_trace(go.Scatterpolar(theta=az, r=rr(hz), mode="lines", line=dict(color="#9AA4B8", width=2),
                                          name="Terrain horizon", hoverinfo="skip"))
            fig.add_trace(go.Scatterpolar(theta=w_f.sun_az_deg, r=rr(w_f.sun_el_deg), mode="markers", name="Sun track",
                                          marker=dict(size=5, color=hrs, colorscale="YlOrBr", showscale=False),
                                          text=[f"{x:%d %b %H:%M}" for x in tt_f],
                                          hovertemplate="Sun %{text}<extra></extra>"))
            fig.add_trace(go.Scatterpolar(theta=w_f.earth_az_deg, r=rr(w_f.earth_el_deg), mode="markers",
                                          name="Earth track",
                                          marker=dict(size=5, color=hrs, colorscale="Blues", showscale=False),
                                          text=[f"{x:%d %b %H:%M}" for x in tt_f],
                                          hovertemplate="Earth %{text}<extra></extra>"))
            ticks = [e for e in range(int(np.floor(ymin)), int(topr) + 1) if e % 2 == 0]
            fig.update_layout(polar=dict(bgcolor="#03050C",
                                         angularaxis=dict(rotation=90, direction="clockwise", gridcolor="#1E2742",
                                                          tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                                                          ticktext=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                                                          color="#C9D1E3"),
                                         radialaxis=dict(range=[0, topr - ymin + 1], tickvals=[rr(e) for e in ticks],
                                                         ticktext=[f"{e}°" for e in ticks], gridcolor="#1E2742",
                                                         color="#7D879C", angle=90, tickfont=dict(size=9))))
            st.plotly_chart(ui.style_fig(fig, 560), width="stretch", config={"displayModeBar": False})
            st.caption("Looking straight up: elevation increases toward the centre; tracks fade light → dark over the stay.")

# ================================================================== analysis, one section after another
st.markdown(f'<div class="lln-sec">{ui.mi("timeline")}Visibility Timeline<span class="lln-tag">sunlight and Earth contact</span></div>',
            unsafe_allow_html=True)
with st.container(key="card_visibility"):
    segs = []
    for sid in order:
        w0 = finder.window(vis[sid], start, dur_days * 24)
        t = pd.DatetimeIndex(w0.time_utc)
        dt = t[1] - t[0]
        for kind, colname, lane in (("Sunlit (power)", "sunlit", "Sun"), ("Earth contact", "dte_visible", "Earth")):
            m = w0[colname].to_numpy(bool)
            edges = np.flatnonzero(np.diff(np.concatenate([[0], m.astype(int), [0]])))
            for a2, b2 in zip(edges[0::2], edges[1::2]):
                segs.append({"Lane": f"{names[sid]} — {lane}", "Kind": kind, "Start": t[a2], "Finish": t[b2 - 1] + dt})
    if segs:
        fig = px.timeline(pd.DataFrame(segs), x_start="Start", x_end="Finish", y="Lane", color="Kind",
                          color_discrete_map={"Sunlit (power)": ui.SUN, "Earth contact": ui.EARTH})
        lanes = [f"{names[s]} — {e}" for s in order for e in ("Sun", "Earth")]
        fig.update_yaxes(categoryorder="array", categoryarray=lanes[::-1], title=None)
        fig.update_xaxes(title=None, range=[start, end_mission], tickformat="%b %d\n%H:%M")
        fig.add_shape(type="line", x0=t_sel, x1=t_sel, y0=0, y1=1, yref="paper",
                      line=dict(color="white", width=1.5, dash="dot"))
        fig = ui.style_fig(fig, 110 + 30 * len(lanes))
        fig.update_layout(legend_title_text="", bargap=0.35, margin=dict(l=10, r=10, t=26, b=10),
                          legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

st.markdown(f'<div class="lln-sec">{ui.mi("cell_tower")}DSN Geometry<span class="lln-tag">Goldstone · Madrid · Canberra</span></div>',
            unsafe_allow_html=True)
with st.container(key="card_dsn"):
    fig = go.Figure()
    for name, c in zip(DSN_COMPLEXES, ["#FFB02E", "#B57BFF", "#3DDC97"]):
        fig.add_trace(go.Scatter(x=dsn.time_utc, y=dsn[f"dsn_{name.lower()}_el"], name=name, mode="lines",
                                 line=dict(color=c, width=2)))
    fig.add_hline(y=dsn_mask, line=dict(color="#FF6B8B", dash="dash", width=1),
                  annotation_text=f"mask {dsn_mask:.0f}°", annotation_position="bottom right")
    fig.add_shape(type="line", x0=t_sel, x1=t_sel, y0=-5, y1=90, line=dict(color="white", width=1.5, dash="dot"))
    fig.update_yaxes(range=[-5, 90], title="Moon elevation (°)")
    fig.update_xaxes(range=[start, end_mission])
    fig = ui.style_fig(fig, 260)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"),
                      margin=dict(l=10, r=10, t=26, b=10))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Moon elevation at Goldstone, Madrid and Canberra: potential geometric access, not scheduled antenna time.")

st.markdown(f'<div class="lln-sec">{ui.mi("battery_charging_full")}Battery &amp; Power<span class="lln-tag">illustrative</span></div>',
            unsafe_allow_html=True)
with st.container(key="card_battery"):
    kwh = [base.loc[s, "required_nameplate_kwh"] for s in order]
    fig = go.Figure(go.Bar(x=[names[s] for s in order], y=kwh, marker_color=ui.SUN, opacity=0.9,
                           text=[f"{v:.0f} kWh" for v in kwh], textposition="outside", width=0.5))
    fig.update_yaxes(title="Estimated storage (kWh)", range=[0, max(10, max(kwh)) * 1.2])
    st.plotly_chart(ui.style_fig(fig, 280), width="stretch", config={"displayModeBar": False})
    st.caption(f"Illustrative: constant {load:.0f} W load, {area:g} m² Sun-tracking array at {eff:.0%}, 95 % "
               "charge/discharge efficiency, 80 % depth of discharge. Not a flight design.")

st.markdown(f'<div class="lln-sec">{ui.mi("schedule")}Landing-Delay Risk<span class="lln-tag">score if the landing slips</span></div>',
            unsafe_allow_html=True)
with st.container(key="card_delay"):
    fig = go.Figure()
    xs = [("0 h" if h == 0 else f"+{h} h") for h in shifts]
    for sid in order:
        sc = table[table.site_id == sid].sort_values("shift_h")
        win = sid in winners
        fig.add_trace(go.Scatter(x=xs, y=sc.score, mode="lines+markers", name=names[sid] + ("  ★" if win else ""),
                                 line=dict(color=ui.site_color(sid), width=4 if win else 2),
                                 marker=dict(size=10 if win else 7), opacity=1 if win else 0.75))
    fig.update_yaxes(range=[-3, 105], title="Score")
    fig.update_xaxes(title="Landing delay")
    fig = ui.style_fig(fig, 300)
    fig.update_layout(legend=dict(orientation="v", yanchor="top", y=1, x=1.01, xanchor="left"),
                      margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"★ Highest worst-case score: {' & '.join(names[s] for s in winners)} ({top_score}).")

ui.footer()
