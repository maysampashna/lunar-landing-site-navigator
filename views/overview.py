"""Mission Overview — mission setup, south-pole map, mission clock, station availability, DSN and ranking."""
from __future__ import annotations

import sys
from datetime import timedelta
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
sites = ui.sites_df()
srows = sites.set_index("site_id")
names = ui.names()
DEFAULT_SITES = [s for s in ["malapert_massif", "de_gerlache_rim_2", "mons_mouton", "nobile_rim_2"] if s in names]

ui.banner("rocket_launch", "Mission Overview",
          "Compare lunar south-pole landing sites at any second of the mission — power from the Sun, communication "
          "through Earth and NASA's Deep Space Network.",
          f'<span class="lln-pill amber">{ui.mi("satellite_alt", 18)} Mission Control Mode</span> '
          + ui.validated_pill())
if not live.kernels_available():
    st.error("Ephemeris kernels are missing from this deployment.")
    st.stop()

col_setup, col_map, col_clock = st.columns([0.95, 1.15, 1.05])

# ------------------------------------------------------------------ mission setup panel
with col_setup:
    with st.container(key="card_setup"):
        ui.card_title("rocket_launch", "Mission Setup")
        chosen = st.multiselect(f"Candidate sites ({len(names)} available)", list(names),
                                default=DEFAULT_SITES or list(names)[:4], format_func=names.get)
        a, b = st.columns([1.3, 1])
        landing_date = a.date_input("Landing date (UTC)", pd.Timestamp("2027-08-16").date(),
                                    min_value=pd.Timestamp("2026-01-02").date(),
                                    max_value=pd.Timestamp("2031-02-10").date())
        landing_hour = b.number_input("UTC hour", 0, 23, 12)
        dur_days = st.slider("Surface stay (days)", 1.0, 14.0, 6.0, 0.5)
        with st.expander("Advanced Controls", icon=":material/tune:"):
            st.markdown("**Communication**")
            require_dsn = st.toggle("Require a DSN complex to see the Moon", True,
                                    help="Direct-to-Earth contact needs Earth above the site's terrain AND the Moon "
                                         "above the elevation mask at Goldstone, Madrid or Canberra.")
            dsn_mask = st.slider("DSN elevation mask (°)", 0.0, 20.0, 10.0, 1.0)
            mask = st.slider("Earth clearance above terrain (°)", 0.0, 10.0, 0.0, 0.5)
            st.markdown("**Power**")
            thr = st.slider("Sunlit if ≥ this fraction of the solar disc is visible", 0.05, 1.0, 0.5, 0.05)
            area = st.number_input("Solar array area (m²)", 1.0, 200.0, 10.0)
            eff = st.slider("Array efficiency", 0.1, 0.4, 0.30)
            load = st.number_input("Constant station load (W)", 50.0, 20000.0, 1000.0, 50.0)
            st.markdown("**Schedule risk & timing**")
            extra = st.multiselect("Arrival-slip scenarios (h)", [24, 48, 72], default=[24, 48])
            step_min = st.select_slider("Time resolution", [5, 10, 15, 30, 60], value=10,
                                        format_func=lambda m: f"{m} min")
            st.markdown("**Ranking preferences**")
            w = ui.weights_sidebar(expander=False)

if not chosen:
    st.info("Pick at least one landing site.")
    st.stop()
shifts = sorted({0, *extra})
start = pd.Timestamp(landing_date).tz_localize("UTC") + pd.Timedelta(hours=int(landing_hour))
end_mission = start + pd.Timedelta(days=dur_days)
end_all = start + pd.Timedelta(hours=dur_days * 24 + max(shifts))
st.session_state["mission"] = {"sites": chosen, "start": start, "dur_days": dur_days}
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
table, best = finder.shift_compare(vis, start, duration_h=dur_days * 24, shifts_h=tuple(shifts), weights=w,
                                   power=power, terrain_real={s: ui.terrain_status(s) == "real" for s in chosen})
worst = table.groupby("site_id")["worst_case_score"].first()
base = table[table.shift_h == 0].set_index("site_id")
order = list(worst.sort_values(ascending=False).index)
top = best or order[0]


def next_events_for(sid, t_sel):
    """[(time, label)] next change of power and of communication after t_sel."""
    w_ = vis[sid]
    tt = pd.DatetimeIndex(w_.time_utc)
    ic = int(tt.searchsorted(t_sel, side="right")) - 1
    out = []
    for colname, on_txt, off_txt in (("sunlit", "Sunrise", "Sunset"), ("dte_visible", "AOS", "LOS")):
        vals = w_[colname].to_numpy(bool)
        if 0 <= ic < len(vals) - 1:
            idx = np.flatnonzero(vals[ic + 1:] != vals[ic])
            if len(idx):
                out.append((tt[ic + 1 + idx[0]], off_txt if vals[ic] else on_txt))
    return out


# ------------------------------------------------------------------ mission clock panel
with col_clock:
    with st.container(key="card_clock"):
        ui.card_title("timer", "Mission Clock", "UTC · NASA day-of-year")
        mode = st.segmented_control("Time source", ["Timeline", "Exact time", "Live UTC"], default="Timeline",
                                    label_visibility="collapsed")
        if mode == "Exact time":
            txt = st.text_input("Exact UTC time (to the second)", ui.doy(start), label_visibility="collapsed",
                                help="2027-228T18:30:15Z (day-of-year) or 2027-08-16 18:30:15")
            try:
                t_sel = (pd.Timestamp(pd.to_datetime(txt.strip().rstrip("Z"), format="%Y-%jT%H:%M:%S"))
                         if "T" in txt and len(txt.split("T")[0]) == 8 else pd.Timestamp(txt.strip().rstrip("Z")))
            except (ValueError, TypeError):
                st.error("Use 2027-228T18:30:15Z or 2027-08-16 18:30:15")
                t_sel = start
        elif mode == "Live UTC":
            t_sel = pd.Timestamp.now(tz="UTC").floor("s")
        else:
            t_sel = pd.Timestamp(st.slider("Mission time", min_value=start.to_pydatetime(),
                                           max_value=end_mission.to_pydatetime(), value=start.to_pydatetime(),
                                           step=timedelta(minutes=step_min), format="MMM DD HH:mm",
                                           label_visibility="collapsed"))
        t_sel = t_sel.tz_localize("UTC") if t_sel.tz is None else t_sel.tz_convert("UTC")
        st.markdown(f'<div class="lln-clock">{ui.doy(t_sel)}</div><div class="lln-clock-sub">UTC '
                    f'{t_sel:%Y-%m-%d %H:%M:%S} · MET {ui.met(t_sel, start)} · Houston '
                    f'{t_sel.tz_convert("America/Chicago"):%H:%M %Z}</div>', unsafe_allow_html=True)

        now_state = {s: live.at_time(srows.loc[s], ui.horizon(s), t_sel, params, dsn_mask) for s in chosen}
        status = {s: ui.status_of(bool(r.sunlit), bool(r.dte_visible)) for s, r in now_state.items()}
        r0 = next(iter(now_state.values()))
        n_earth = sum(bool(r.earth_in_view) for r in now_state.values())
        dsn_up = bool(r0.dsn_any)
        st.markdown(
            '<div style="display:flex;gap:10px;margin:12px 0 8px 0">'
            + ui.kcard("cell_tower", "DSN Coverage", "In View" if dsn_up else "No Coverage",
                       f"{r0.dsn_best} · Moon {r0.dsn_best_el:.0f}°" if dsn_up else "Moon below every mask",
                       ui.BOTH if dsn_up else "#FF6B8B", small=True)
            + ui.kcard("public", "Earth Visibility", "In View" if n_earth else "Hidden",
                       f"{n_earth} of {len(chosen)} sites", ui.BOTH if n_earth else "#FF6B8B", small=True)
            + "</div>", unsafe_allow_html=True)

        events = []
        for sid in chosen:
            for t_, lab_ in next_events_for(sid, t_sel):
                events.append((t_, f"{names[sid]} – {lab_}", ui.SUN if lab_ in ("Sunrise", "Sunset") else ui.EARTH,
                               "wb_sunny" if lab_ in ("Sunrise", "Sunset") else "cell_tower"))
        dd = dsn[dsn.time_utc >= t_sel]
        if len(dd) > 1:
            ch = np.flatnonzero(dd.dsn_best.to_numpy()[1:] != dd.dsn_best.to_numpy()[:-1])
            if len(ch):
                a_, b_ = dd.dsn_best.iloc[ch[0]], dd.dsn_best.iloc[ch[0] + 1]
                events.append((dd.time_utc.iloc[ch[0] + 1],
                               f"DSN {a_} → {b_}" if a_ and b_ else f"DSN gap begins ({a_})" if a_
                               else f"DSN resumes ({b_})", "#B57BFF", "satellite_alt"))
        ec = vis[chosen[0]]
        ecl = ec.eclipse_frac.to_numpy() > 0
        tt = pd.DatetimeIndex(ec.time_utc)
        ic = int(tt.searchsorted(t_sel, side="right")) - 1
        if 0 <= ic < len(ecl) - 1:
            idx = np.flatnonzero(ecl[ic + 1:] != ecl[ic])
            if len(idx):
                events.append((tt[ic + 1 + idx[0]], "Lunar eclipse " + ("ends" if ecl[ic] else "begins"), "#C9D8E0",
                               "dark_mode"))
        events.sort(key=lambda e: e[0])
        st.markdown(f'<div class="lln-ct" style="font-size:1.02rem;margin-top:6px">{ui.mi("format_list_bulleted")}'
                    f'<span>Upcoming Events</span><small style="margin-left:auto">Next {min(5, len(events))}</small></div>'
                    + "".join(f'<div class="lln-ev"><span class="d" style="background:{c}"></span>'
                              f'<span class="tm">{ui.tminus(t, t_sel)}</span><span>{lab}</span>'
                              f'<span class="tg">{ui.mi(ic_, 18)}</span></div>' for t, lab, c, ic_ in events[:5])
                    + ("" if events else '<div class="lln-ev">No changes before the end of the window</div>'),
                    unsafe_allow_html=True)

# ------------------------------------------------------------------ map panel
with col_map:
    with st.container(key="card_map"):
        color_by = st.segmented_control("Map colour", ["Status now", "Mission rating"], default="Status now",
                                        label_visibility="collapsed")
        st.plotly_chart(ui.south_pole_map(chosen, worst.to_dict(), height=440, highlight=top,
                                          status=status if color_by != "Mission rating" else None),
                        width="stretch", config={"displayModeBar": False, "scrollZoom": False})
        if color_by != "Mission rating":
            st.markdown(" ".join(ui.chip(l_.split(" ·")[0], c_) for l_, c_ in ui.STATUS.values()),
                        unsafe_allow_html=True)
        else:
            st.markdown(" ".join(ui.chip(f"{l_} {r_}", c_) for l_, r_, c_ in
                                 [("Excellent", "≥90", "#3DDC97"), ("Good", "70–89", "#4C8DFF"),
                                  ("Fair", "40–69", "#FFB02E"), ("Poor", "<40", "#FF6B8B")]), unsafe_allow_html=True)

# ------------------------------------------------------------------ station cards
cols = st.columns(min(4, len(chosen)))
for k, sid in enumerate(chosen):
    r = now_state[sid]
    lab, col = ui.STATUS[status[sid]]
    ev = next_events_for(sid, t_sel)
    nxt = (f"{min(ev)[1]} in {(min(ev)[0] - t_sel).total_seconds() / 3600:.1f} h" if ev else "no change in window")
    dsn_txt = f"{r.dsn_best} · {r.dsn_best_el:.0f}°" if r.dsn_best else "none"
    with cols[k % len(cols)]:
        st.markdown(
            f'<div class="lln-st" style="border-color:{col}88"><div class="hd"><div class="ib">{ui.mi("landscape", 28)}</div>'
            f'<div><div class="nm">{names[sid]}</div>{ui.chip(lab, col)}</div></div>'
            f'<div class="rw"><span>{ui.mi("wb_sunny", 19, ui.SUN)}Sun visible</span><b>{r.sun_frac * 100:.0f}%</b></div>'
            f'<div class="rw"><span>{ui.mi("public", 19, ui.EARTH)}Earth visibility</span><b>{r.earth_frac * 100:.0f}%</b></div>'
            f'<div class="rw"><span>{ui.mi("bolt", 19, "#F6E05E")}Solar power</span><b>{r.p_solar_w / 1000:.2f} kW</b></div>'
            f'<div class="rw"><span>{ui.mi("cell_tower", 19, "#B57BFF")}DSN link</span><b>{dsn_txt}</b></div>'
            f'<div class="rw"><span>{ui.mi("event", 19, "#C9D8E0")}Next event</span><b>{nxt}</b></div>'
            f'<div class="mut">Sun el {r.sun_el_deg:+.2f}° (clearance {r.sun_el_deg - r.horizon_at_sun_deg:+.2f}°) · '
            f'Earth el {r.earth_el_deg:+.2f}° (clearance {r.earth_el_deg - r.horizon_at_earth_deg:+.2f}°)</div></div>',
            unsafe_allow_html=True)

# ------------------------------------------------------------------ summary bar (real values)
best_sun = base.pct_sunlit.max()
sun_sites = [names[s] for s in order if base.loc[s, "pct_sunlit"] == best_sun]
best_comm = base.pct_dte.max()
comm_sites = [names[s] for s in order if base.loc[s, "pct_dte"] == best_comm]
lab_top, col_top = ui.rating(worst[top])


def who(lst):
    return lst[0] + (" (tie)" if len(lst) == 2 else f" +{len(lst) - 1}" if len(lst) > 2 else "")


st.markdown(
    '<div class="lln-sum">'
    f'<div>{ui.mi("wb_sunny")}<div><div class="lb">Best sunlight</div><div class="vl">{best_sun:.0f}%</div>'
    f'<div class="sb">{who(sun_sites)}</div></div></div>'
    f'<div>{ui.mi("public")}<div><div class="lb">Best Earth communication</div><div class="vl">{best_comm:.0f}%</div>'
    f'<div class="sb">{"all selected sites" if len(comm_sites) == len(chosen) else who(comm_sites)}</div></div></div>'
    f'<div>{ui.mi("shield")}<div><div class="lb">Best robustness (worst case)</div>'
    f'<div class="vl">{worst[top]:.0f}/100</div><div class="sb">{names[top]} · {lab_top}</div></div></div>'
    f'<div>{ui.mi("flag")}<div><div class="lb">Recommended prime site</div>'
    f'<div class="vl" style="color:{ui.AMBER}">{names[top] if best else "—"}</div>'
    f'<div class="sb">{"best modeled under your criteria" if best else "no confident recommendation"}</div></div></div>'
    '</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ DSN panel
st.markdown(f'<div class="lln-sec">{ui.mi("satellite_alt")}NASA Deep Space Network<span class="s">Moon elevation '
            'at each complex · contact needs Earth above the site horizon and a complex that sees the Moon</span></div>',
            unsafe_allow_html=True)
dcol = st.columns([1, 1, 1, 3])
for k, (name, (lat, lon, _)) in enumerate(DSN_COMPLEXES.items()):
    el = r0[f"dsn_{name.lower()}_el"]
    up = el >= dsn_mask
    prime = name == r0.dsn_best
    with dcol[k]:
        st.markdown(ui.kcard("cell_tower", ("★ " if prime else "") + name, f"{el:+.1f}°",
                             ("PRIME · " if prime else "") + ("Moon in view" if up else "below mask"),
                             ui.BOTH if prime else ui.EARTH if up else ui.GREY, amber=prime), unsafe_allow_html=True)
with dcol[3]:
    fig = go.Figure()
    for name, c in zip(DSN_COMPLEXES, ["#FFB02E", "#B57BFF", "#3DDC97"]):
        fig.add_trace(go.Scatter(x=dsn.time_utc, y=dsn[f"dsn_{name.lower()}_el"], name=name, mode="lines",
                                 line=dict(color=c, width=2.2)))
    fig.add_hline(y=dsn_mask, line=dict(color="#FF6B8B", dash="dash", width=1))
    fig.add_shape(type="line", x0=t_sel, x1=t_sel, y0=-90, y1=90, line=dict(color="white", width=1.5, dash="dot"))
    fig.update_yaxes(range=[-5, 90], title="Moon el (°)")
    fig.update_xaxes(range=[start, end_mission])
    fig = ui.style_fig(fig, 190)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"),
                      margin=dict(l=10, r=10, t=24, b=10))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------------------------------ ranking + recommendation
st.markdown(f'<div class="lln-sec">{ui.mi("emoji_events")}Best landing site for this window<span class="s">'
            f'{dur_days:g}-day stay from {ui.doy(start)} · ranked by worst case over '
            f'{", ".join(f"+{s} h" for s in shifts)} arrival slips</span></div>', unsafe_allow_html=True)
left, right = st.columns([1.45, 1])
with left:
    rows = []
    for i, sid in enumerate(order):
        r = base.loc[sid]
        lab, col = ui.rating(r.worst_case_score)
        rows.append(f'<tr class="{"top" if i == 0 else ""}"><td><span class="lln-dot" style="background:{col}"></span>'
                    f'{names[sid]}</td><td><span class="lln-pv">{r.pct_sunlit:.0f}</span></td>'
                    f'<td><span class="lln-pv">{r.pct_dte:.0f}</span></td><td><span class="lln-pv">{r.pct_both:.0f}</span></td>'
                    f'<td>{r.longest_dark_h:.0f} h</td><td>{r.longest_no_dte_h:.0f} h</td>'
                    f'<td>{r.required_nameplate_kwh:.0f} kWh</td><td><b>{r.worst_case_score:.0f}</b></td>'
                    f'<td>{ui.chip(lab, col)}</td></tr>')
    with st.container(key="card_rank"):
        st.markdown('<table class="lln-table"><tr><th>Site</th><th>Power %</th><th>Comm %</th><th>Both %</th>'
                    '<th>Longest dark</th><th>Longest no-comm</th><th>Battery</th><th>Worst-case</th><th>Rating</th>'
                    '</tr>' + "".join(rows) + "</table>", unsafe_allow_html=True)
with right:
    fragile = []
    for sid in chosen:
        sc = table[table.site_id == sid].set_index("shift_h")["score"]
        if sc.loc[0] - sc.min() >= 5:
            fragile.append(f"<b>{names[sid]}</b> drops from {sc.loc[0]:.0f} to {sc.min():.0f} "
                           f"if arrival slips {int(sc.idxmin())} h")
    if best is not None:
        r = base.loc[best]
        runner = [s for s in order if s != best]
        txt = (f"<b>{names[best]}</b> is the best modeled landing site: {r.pct_sunlit:.0f}% of the time with power, "
               f"{r.pct_dte:.0f}% with {'DSN-confirmed ' if require_dsn else ''}Earth communication, worst-case score "
               f"{worst[best]:.0f}/100.")
        if runner:
            txt += f" Runner-up: {names[runner[0]]} ({worst[runner[0]]:.0f})."
        if fragile:
            txt += "<br>⚠️ <b>Schedule risk:</b> " + "; ".join(fragile) + "."
        st.markdown(f'<div class="lln-rec"><h4>✅ Recommendation</h4>{txt}<br><span style="color:#9FB4C0;'
                    'font-size:0.8rem">Best modeled location under your selected criteria — not a landing-safety '
                    'assessment.</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="lln-warn"><h4>Demonstration ranking</h4>Top: <b>{names[top]}</b> '
                    f'(worst-case {worst[top]:.0f}). No confident recommendation: terrain data is synthetic, missing '
                    'or incomplete for these sites.</div>', unsafe_allow_html=True)
    if table.pct_eclipsed.max() > 0:
        st.info("A lunar eclipse (Earth passing in front of the Sun, as seen from the Moon) falls inside this "
                "window; it is included in sunlight and power.", icon=":material/dark_mode:")

# ------------------------------------------------------------------ timeline + charts
segs = []
for sid in order:
    w0 = finder.window(vis[sid], start, dur_days * 24)
    t = pd.DatetimeIndex(w0.time_utc)
    dt = t[1] - t[0]
    for kind, colname in (("☀️ Power (sunlit)", "sunlit"), ("📡 Communication", "dte_visible")):
        m = w0[colname].to_numpy(bool)
        edges = np.flatnonzero(np.diff(np.concatenate([[0], m.astype(int), [0]])))
        for a_, b_ in zip(edges[0::2], edges[1::2]):
            segs.append({"Row": f"{names[sid]} · {kind.split(' ')[0]}", "Kind": kind, "Start": t[a_],
                         "Finish": t[b_ - 1] + dt})
with st.container(key="card_timeline"):
    ui.card_title("timeline", "Visibility timeline", "dotted line = selected time")
    if segs:
        sdf = pd.DataFrame(segs)
        fig = px.timeline(sdf, x_start="Start", x_end="Finish", y="Row", color="Kind", opacity=0.92,
                          color_discrete_map={"☀️ Power (sunlit)": ui.SUN, "📡 Communication": ui.EARTH})
        cats = [f"{names[s]} · {e}" for s in order for e in ("☀️", "📡")]
        fig.update_yaxes(categoryorder="array", categoryarray=cats[::-1], title=None)
        fig.update_xaxes(title=None, range=[start, end_mission])
        fig.add_shape(type="line", x0=t_sel, x1=t_sel, y0=0, y1=1, yref="paper",
                      line=dict(color="white", width=2, dash="dot"))
        fig = ui.style_fig(fig, 100 + 42 * len(order))
        fig.update_layout(legend_title_text="", legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1,
                                                            xanchor="right"), margin=dict(l=10, r=10, t=26, b=10))
        st.plotly_chart(fig, width="stretch")

c1, c2 = st.columns(2)
with c1:
    with st.container(key="card_risk"):
        ui.card_title("schedule", "Schedule risk", "score if arrival slips")
        fig = go.Figure()
        for sid in order:
            sc = table[table.site_id == sid].sort_values("shift_h")
            fig.add_trace(go.Scatter(x=[f"+{h} h" for h in sc.shift_h], y=sc.score, mode="lines+markers",
                                     name=names[sid], line=dict(color=ui.site_color(sid), width=3),
                                     marker=dict(size=9)))
        fig.update_yaxes(range=[-3, 103], title="Score")
        st.plotly_chart(ui.style_fig(fig, 300), width="stretch")
with c2:
    with st.container(key="card_battery"):
        ui.card_title("battery_charging_full", "Battery to ride through darkness", f"{load:.0f} W load, illustrative")
        fig = go.Figure(go.Bar(x=[names[s] for s in order], y=[base.loc[s, "required_nameplate_kwh"] for s in order],
                               marker_color=[ui.site_color(s) for s in order],
                               text=[f"{base.loc[s, 'required_nameplate_kwh']:.0f} kWh" for s in order],
                               textposition="outside"))
        fig.update_yaxes(title="kWh (nameplate)")
        st.plotly_chart(ui.style_fig(fig, 300), width="stretch")

with st.expander("All metrics (every site × arrival scenario)", icon=":material/table:"):
    show = table[["site_id", "shift_h", "pct_sunlit", "pct_dte", "pct_both", "longest_dark_h", "longest_no_dte_h",
                  "mean_solar_w", "required_nameplate_kwh", "soc_end", "pct_uncertain", "pct_eclipsed", "score",
                  "worst_case_score", "terrain_real", "confident"]].copy()
    show["site_id"] = show.site_id.map(names)
    st.dataframe(show.round(2), width="stretch", hide_index=True)

ui.footer()
