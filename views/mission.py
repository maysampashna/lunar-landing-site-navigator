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

# map click → focus site (applied before the focus selector is drawn)
sel = st.session_state.get("db_map")
pts = (sel or {}).get("selection", {}).get("points", []) if isinstance(sel, dict) else \
    (getattr(getattr(sel, "selection", None), "points", None) or [])
if pts:
    clicked = pts[0].get("customdata")
    clicked = clicked[0] if isinstance(clicked, (list, tuple)) else clicked
    if clicked in st.session_state["m_sites"] and st.session_state.get("_db_last_click") != clicked:
        st.session_state["m_site"] = clicked
    st.session_state["_db_last_click"] = clicked
if st.session_state["m_sites"] and st.session_state.get("m_site") not in st.session_state["m_sites"]:
    st.session_state["m_site"] = st.session_state["m_sites"][0]

ui.banner("space_dashboard", "Mission Dashboard",
          "One control panel for sites, landing time and stay — every view below updates together.")

col_vis, col_ctl = st.columns([3.1, 1], gap="medium")

# ================================================================== the single control panel
with col_ctl:
    with st.container(key="card_ctl"):
        ui.card_title("tune", "Mission controls")
        chosen = st.multiselect("Candidate sites", list(names), format_func=names.get, key="m_sites")
        if not chosen:
            st.info("Pick at least one site.")
            st.stop()
        focus = st.selectbox("Site shown in 3D", chosen, format_func=names.get, key="m_site")
        a_, b_ = st.columns([1.5, 1])
        a_.date_input("Landing (UTC)", min_value=pd.Timestamp("2026-01-02").date(),
                      max_value=pd.Timestamp("2031-02-10").date(), key="m_date")
        b_.number_input("Hour", 0, 23, key="m_hour")
        dur_days = st.slider("Surface stay (days)", 1.0, 14.0, step=0.5, key="m_dur")
        time_slot = st.container()
        with st.expander("Advanced", icon=":material/settings:"):
            require_dsn = st.toggle("Require a DSN complex to see the Moon", True)
            dsn_mask = st.slider("DSN elevation mask (°)", 0.0, 20.0, 10.0, 1.0)
            mask = st.slider("Earth clearance above terrain (°)", 0.0, 10.0, 0.0, 0.5)
            thr = st.slider("Sunlit if ≥ this fraction of the Sun's disc is visible", 0.05, 1.0, 0.5, 0.05)
            area = st.number_input("Solar array area (m²)", 1.0, 200.0, 10.0)
            eff = st.slider("Array efficiency", 0.1, 0.4, 0.30)
            load = st.number_input("Constant load (W)", 50.0, 20000.0, 1000.0, 50.0)
            extra = st.multiselect("Landing-delay scenarios (h)", [24, 48, 72], default=[24, 48])
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


def next_events_for(sid, t_from):
    w_ = vis[sid]
    tt = pd.DatetimeIndex(w_.time_utc)
    ic = int(tt.searchsorted(t_from, side="right")) - 1
    out = []
    for colname, on_txt, off_txt in (("sunlit", "Sunrise", "Sunset"), ("dte_visible", "AOS", "LOS")):
        vals = w_[colname].to_numpy(bool)
        if 0 <= ic < len(vals) - 1:
            idx_ = np.flatnonzero(vals[ic + 1:] != vals[ic])
            if len(idx_):
                out.append((tt[ic + 1 + idx_[0]], off_txt if vals[ic] else on_txt))
    return out


with col_ctl:
    with st.container(key="card_now"):
        ui.card_title("visibility", "At selected time")
        ev = next_events_for(focus, t_sel)
        nxt = f"{min(ev)[1]} in {(min(ev)[0] - t_sel).total_seconds() / 3600:.1f} h" if ev else "none before stay ends"

        def yes(on, color):
            return f'<b style="color:{color if on else ui.GREY}">{"YES" if on else "NO"}</b>'

        st.markdown(
            '<div class="lln-st" style="border:none;background:none;padding:0;margin:0">'
            f'<div style="color:{ui.AMBER};font-weight:700;margin-bottom:4px">{names[focus]}</div>'
            f'<div class="rw"><span>{ui.mi("wb_sunny", 18, ui.SUN)}Sunlight (power)</span>{yes(f0.sunlit, ui.SUN)}</div>'
            f'<div class="rw"><span>{ui.mi("public", 18, ui.EARTH)}Earth contact (DTE)</span>'
            f'{yes(f0.dte_visible, ui.EARTH)}</div>'
            f'<div class="rw"><span>{ui.mi("event", 18, ui.GREY)}Next change</span><b>{nxt}</b></div>'
            f'<div class="mut">Sun El {f0.sun_el_deg:+.2f}° (clears terrain {f0.sun_el_deg - f0.horizon_at_sun_deg:+.2f}°) · '
            f'Earth El {f0.earth_el_deg:+.2f}° (clears {f0.earth_el_deg - f0.horizon_at_earth_deg:+.2f}°)</div></div>',
            unsafe_allow_html=True)

# ================================================================== LAYER 1 — 3D / panorama / sky chart
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


with col_vis:
    with st.container(key="card_vis"):
        tab3d, tabpan, tabsky = st.tabs([":material/view_in_ar: 3D Observer View", ":material/panorama: Panorama",
                                         ":material/radar: Sky Chart"])
        with tab3d:
            fig3 = ui.observer_3d(focus, f0, hp, exag=2.0, height=610)
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

# ================================================================== LAYER 2 — map + mission clock
col_map, col_clock = st.columns([1.45, 1], gap="medium")
with col_map:
    with st.container(key="card_map"):
        v_, c_ = st.columns([0.7, 1.6], vertical_alignment="center")
        view = v_.segmented_control("View", ["2D", "3D"], default="2D", label_visibility="collapsed") or "2D"
        color_by = c_.segmented_control("Colour", ["At selected time", "Mission rating"], default="At selected time",
                                        label_visibility="collapsed")
        stat_ = status if color_by != "Mission rating" else None
        if view == "3D" and ui.terrain3d() is not None:
            st.plotly_chart(ui.region_3d(chosen, status=stat_, scores=worst.to_dict(), highlight=focus),
                            width="stretch", config={"displaylogo": False, "scrollZoom": True,
                                                     "modeBarButtonsToRemove": ["toImage"]})
        else:
            st.plotly_chart(ui.south_pole_map(chosen, worst.to_dict(), height=470, highlight=focus, status=stat_),
                            width="stretch", config=ui.MAP_CONFIG, on_select="rerun", selection_mode="points",
                            key="db_map")
        legend = (" ".join(ui.chip(l_, c2) for l_, c2 in ui.STATUS.values()) if stat_ is not None else
                  " ".join(ui.chip(f"{l_} {r_}", c2) for l_, r_, c2 in
                           [("Excellent", "≥90", "#3DDC97"), ("Good", "70–89", "#4C8DFF"),
                            ("Fair", "40–69", "#FFB02E"), ("Poor", "<40", "#FF6B8B")]))
        st.markdown(legend + '<div style="color:#8FA4B0;font-size:0.8rem;margin-top:4px">'
                    + ("Drag to rotate, scroll to zoom · NASA LOLA relief, heights ×4" if view == "3D" else
                       "Click a site to show it in 3D · drag to move, +/− to zoom") + '</div>', unsafe_allow_html=True)

with col_clock:
    with st.container(key="card_clock"):
        ui.card_title("timer", "Mission Clock", "simulated mission time")
        now_real = pd.Timestamp.now(tz="UTC")
        st.markdown(f'<div class="lln-clock">{ui.doy(t_sel)}</div><div class="lln-clock-sub">Selected time · '
                    f'MET {ui.met(t_sel, start)}<br>Houston {t_sel.tz_convert("America/Chicago"):%H:%M %Z} · '
                    f'Actual now: {now_real:%Y-%j}T{now_real:%H:%M}Z</div>', unsafe_allow_html=True)
        r0 = f0
        n_earth = sum(bool(r.earth_in_view) for r in now_state.values())
        dsn_up = bool(r0.dsn_any)
        st.markdown(
            '<div style="display:flex;gap:10px;margin:10px 0 6px 0">'
            + ui.kcard("cell_tower", "DSN geometry", "Moon in view" if dsn_up else "No complex",
                       f"{r0.dsn_best} · Moon {r0.dsn_best_el:.0f}°" if dsn_up else "Moon below every mask",
                       ui.EARTH if dsn_up else ui.GREY, small=True)
            + ui.kcard("public", "Earth visible", f"{n_earth} / {len(chosen)} sites", "above terrain",
                       ui.EARTH if n_earth else ui.GREY, small=True)
            + "</div>", unsafe_allow_html=True)
        events = []
        for sid in chosen:
            for t_, lab_ in next_events_for(sid, t_sel):
                events.append((t_, f"{names[sid]} – {lab_}", ui.SUN if lab_ in ("Sunrise", "Sunset") else ui.EARTH))
        dd = dsn[dsn.time_utc >= t_sel]
        if len(dd) > 1:
            ch = np.flatnonzero(dd.dsn_best.to_numpy()[1:] != dd.dsn_best.to_numpy()[:-1])
            if len(ch):
                a1, b1 = dd.dsn_best.iloc[ch[0]], dd.dsn_best.iloc[ch[0] + 1]
                events.append((dd.time_utc.iloc[ch[0] + 1], f"DSN {a1} → {b1}" if a1 and b1 else
                               f"DSN gap begins ({a1})" if a1 else f"DSN resumes ({b1})", ui.GREY))
        events.sort(key=lambda e: e[0])
        st.markdown('<div class="lln-ct" style="font-size:0.98rem;margin-top:4px">'
                    f'{ui.mi("format_list_bulleted")}<span>Upcoming events</span></div>'
                    + "".join(f'<div class="lln-ev"><span class="d" style="background:{c}"></span>'
                              f'<span class="tm">{ui.tminus(t, t_sel)}</span><span>{lab}</span></div>'
                              for t, lab, c in events[:5])
                    + ("" if events else '<div class="lln-ev">No changes before the end of the stay</div>'),
                    unsafe_allow_html=True)

# ================================================================== LAYER 3 — decision summary
fragile = []
for sid in order:
    sc = table[table.site_id == sid].set_index("shift_h")["score"]
    if sc.loc[0] - sc.min() >= 5:
        fragile.append(f"{names[sid]} drops from {sc.loc[0]:.0f} to {sc.min():.0f} at +{int(sc.idxmin())} h")


def vals(col, fmt="{:.0f}"):
    v = [fmt.format(base.loc[s, col]) for s in winners]
    return v[0] if len(set(v)) == 1 else " / ".join(v)


shift_txt = " | ".join(("0 h" if h == 0 else f"+{h} h") + " " + " / ".join(dict.fromkeys(
    f"{table[(table.site_id == s) & (table.shift_h == h)].score.iloc[0]:.0f}" for s in winners)) for h in shifts)
tie = len(winners) > 1
wb = base.loc[winners[0]]
reason = ("Sunlight and Earth contact are available for the whole stay" if wb.pct_sunlit >= 99.5 and wb.pct_dte >= 99.5
          else f"Highest combined sunlight ({vals('pct_sunlit')}%) and Earth contact ({vals('pct_dte')}%)")
reason += (", and the score holds if the landing slips." if all(worst[s] >= base.loc[s, "score"] - 0.5 for s in winners)
           else ", with the smallest loss if the landing slips.")
if tie:
    reason = f"{len(winners)} sites tie in every scenario. " + reason
if fragile:
    reason += f"<br>Schedule risk: {'; '.join(fragile)}."
head = ("Tie · best modeled sites" if tie else "Best modeled site") if best is not None else "Demonstration ranking"
st.markdown(
    '<div class="lln-dec">'
    f'<div class="site"><div class="lb">{ui.mi("flag", 18, ui.AMBER)} {head}</div>'
    f'<div class="nm">{" &amp; ".join(names[s] for s in winners)}</div>'
    f'<div style="color:#B5C7D1;font-size:0.82rem;margin-top:2px">{dur_days:g}-day stay from {ui.doy(start)}</div></div>'
    f'<div class="score"><div class="lb">Worst-case score</div><div class="vl">{top_score}</div>'
    '<div style="color:#8FA4B0;font-size:0.8rem">of 100</div></div><div class="mt">'
    f'<span>{ui.mi("wb_sunny", 17, ui.SUN)} Sunlight over stay</span><b>{vals("pct_sunlit")}%</b>'
    f'<span>{ui.mi("public", 17, ui.EARTH)} Earth contact over stay</span><b>{vals("pct_dte")}%</b>'
    f'<span>{ui.mi("battery_charging_full", 17, ui.SUN)} Estimated storage</span><b>{vals("required_nameplate_kwh")} kWh</b>'
    f'<span>{ui.mi("schedule", 17, ui.TEAL)} Score if landing slips</span><b>{shift_txt}</b></div>'
    f'<div class="why"><b>Why:</b> {reason}<div class="nt">Modeled comparison under the selected criteria — '
    'not a landing-safety recommendation.</div></div></div>', unsafe_allow_html=True)

# ================================================================== LAYER 4 — analysis (compact tabs)
tabs = st.tabs([":material/table_chart: Site Comparison", ":material/schedule: Landing-Delay Risk",
                ":material/battery_charging_full: Battery & Power", ":material/cell_tower: DSN Geometry",
                ":material/timeline: Visibility Timeline"])
with tabs[0]:
    rows = []
    for sid in order:
        r = base.loc[sid]
        lab, col = ui.rating(r.worst_case_score)
        rank = 1 + sum(round(worst[s]) > round(worst[sid]) for s in order)
        tied = sum(round(worst[s]) == round(worst[sid]) for s in order) > 1
        rows.append(f'<tr class="{"top" if sid in winners else ""}"><td>{rank}{"=" if tied else ""}</td>'
                    f'<td><b>{names[sid]}</b></td><td>{ui.chip(*ui.STATUS[status[sid]])}</td>'
                    f'<td class="n">{r.pct_sunlit:.0f}</td><td class="n">{r.pct_dte:.0f}</td>'
                    f'<td class="n">{r.pct_both:.0f}</td><td class="n">{r.longest_dark_h:.0f}</td>'
                    f'<td class="n">{r.required_nameplate_kwh:.0f}</td><td class="n"><b>{r.worst_case_score:.0f}</b></td>'
                    f'<td>{ui.chip(lab, col)}</td></tr>')
    st.markdown(
        '<table class="lln-table"><tr><th>#</th><th>Site</th><th title="Sun / Earth at the selected time">Now</th>'
        '<th class="n" title="Share of the stay with sunlight">Sun %</th>'
        '<th class="n" title="Share of the stay with Earth contact (Earth above terrain + DSN geometry)">Earth %</th>'
        '<th class="n" title="Sunlight and Earth contact at the same time">Both %</th>'
        '<th class="n" title="Longest continuous period without sunlight">Longest dark (h)</th>'
        '<th class="n" title="Illustrative battery nameplate for the constant load">Storage (kWh)</th>'
        '<th class="n" title="Lowest score across the landing-delay scenarios">Worst-case score</th>'
        '<th>Rating</th></tr>' + "".join(rows) + "</table>", unsafe_allow_html=True)
    st.caption("Equal scores share a rank (1=).")
with tabs[1]:
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
with tabs[2]:
    kwh = [base.loc[s, "required_nameplate_kwh"] for s in order]
    fig = go.Figure(go.Bar(x=[names[s] for s in order], y=kwh, marker_color=ui.SUN, opacity=0.9,
                           text=[f"{v:.0f} kWh" for v in kwh], textposition="outside", width=0.5))
    fig.update_yaxes(title="Estimated storage (kWh)", range=[0, max(10, max(kwh)) * 1.2])
    st.plotly_chart(ui.style_fig(fig, 280), width="stretch", config={"displayModeBar": False})
    st.caption(f"Illustrative: constant {load:.0f} W load, {area:g} m² Sun-tracking array at {eff:.0%}, 95 % "
               "charge/discharge efficiency, 80 % depth of discharge. Not a flight design.")
with tabs[3]:
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
with tabs[4]:
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

ui.footer()
