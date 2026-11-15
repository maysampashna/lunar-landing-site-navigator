"""Mission Control — pick a landing window, scrub to any second, see which stations are available."""
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

ui.setup_page("Lunar Landing Site Navigator · Mission Control", "🚀")
sites = ui.sites_df()
srows = sites.set_index("site_id")
names = ui.names()
DEFAULT_SITES = [s for s in ["malapert_massif", "de_gerlache_rim_2", "mons_mouton", "nobile_rim_2"] if s in names]

# ------------------------------------------------------------------ sidebar: mission setup + advanced box
with st.sidebar:
    st.markdown("### 🚀 Mission setup")
    chosen = st.multiselect("📍 Candidate landing sites", list(names), default=DEFAULT_SITES or list(names)[:4],
                            format_func=names.get)
    c1, c2 = st.columns(2)
    landing_date = c1.date_input("🛬 Landing (UTC)", pd.Timestamp("2027-08-16").date(),
                                 min_value=pd.Timestamp("2026-01-02").date(),
                                 max_value=pd.Timestamp("2031-02-10").date())
    landing_hour = c2.number_input("Hour (UTC)", 0, 23, 12)
    dur_days = st.slider("🗓️ Surface stay (days)", 1.0, 14.0, 6.0, 0.5)

    with st.expander("🛠️ Advanced mission control", expanded=False):
        st.markdown("**Communication**")
        require_dsn = st.toggle("Require a DSN complex to see the Moon", True,
                                help="Direct-to-Earth contact needs Earth above the site's terrain AND the Moon above "
                                     "the elevation mask at Goldstone, Madrid or Canberra.")
        dsn_mask = st.slider("DSN elevation mask (°)", 0.0, 20.0, 10.0, 1.0)
        mask = st.slider("Earth clearance above terrain (°)", 0.0, 10.0, 0.0, 0.5)
        st.markdown("**Power**")
        thr = st.slider("Sunlit if ≥ this fraction of the solar disc is visible", 0.05, 1.0, 0.5, 0.05)
        area = st.number_input("Solar array area (m²)", 1.0, 200.0, 10.0)
        eff = st.slider("Array efficiency", 0.1, 0.4, 0.30)
        load = st.number_input("Constant station load (W)", 50.0, 20000.0, 1000.0, 50.0)
        st.markdown("**Schedule risk & timing**")
        extra = st.multiselect("Arrival-slip scenarios (h)", [24, 48, 72], default=[24, 48])
        step_min = st.select_slider("Time resolution", [5, 10, 15, 30, 60], value=10, format_func=lambda m: f"{m} min")
        st.markdown("**Ranking preferences**")
        w = ui.weights_sidebar(expander=False)

shifts = sorted({0, *extra})
start = pd.Timestamp(landing_date).tz_localize("UTC") + pd.Timedelta(hours=int(landing_hour))
end_mission = start + pd.Timedelta(days=dur_days)
st.session_state["mission"] = {"sites": chosen, "start": start, "dur_days": dur_days}

# ------------------------------------------------------------------ header
v = ui.validation_report()
badge = (f'<span class="lln-badge">✔ Ephemeris validated vs JPL Horizons · max error '
         f'{v["overall_max_error_deg"]:.5f}°</span>' if v else "")
st.markdown(f'<div class="lln-hero"><h1>🌘 Lunar Landing Site Navigator</h1>{badge}</div>'
            '<div class="lln-sub">Mission control for the lunar south pole: sunlight for power, Earth + Deep Space '
            'Network for communication, at any second of your mission · Artemis III candidate regions (crewed landing '
            'now planned for Artemis IV) · representative points, not NASA-designated landing sites</div>',
            unsafe_allow_html=True)
if not chosen:
    st.info("Pick at least one landing site in the sidebar.")
    st.stop()
banners = ui.data_banners(chosen)
if not live.kernels_available():
    st.error("Ephemeris kernels are missing from this deployment.")
    st.stop()

power = PowerParams(array_area_m2=area, efficiency=eff, load_w=load)
params = visibility.VisParams(sunlit_threshold=thr, earth_mask_deg=mask, power=power, require_dsn=require_dsn)
end_all = start + pd.Timedelta(hours=dur_days * 24 + max(shifts))


@st.cache_data(show_spinner="Computing Sun, Earth and DSN geometry…")
def window_data(chosen_t, start_, end_, step_, thr_, mask_, area_, eff_, load_, req_, dsn_mask_):
    p = visibility.VisParams(sunlit_threshold=thr_, earth_mask_deg=mask_, require_dsn=req_,
                             power=PowerParams(array_area_m2=area_, efficiency=eff_, load_w=load_))
    dsn = live.dsn_series(start_, end_, step_, dsn_mask_)
    vis_ = {s: live.fine_visibility(srows.loc[s], ui.horizon(s), start_, end_, p, step_min=step_, dsn=dsn)
            for s in chosen_t}
    return vis_, dsn


vis, dsn = window_data(tuple(chosen), start, end_all, step_min, thr, mask, area, eff, load, require_dsn, dsn_mask)

# ------------------------------------------------------------------ row 1: map | mission clock
col_map, col_clock = st.columns([1.05, 1])
with col_clock:
    with st.container(border=True):
        st.markdown("**🕐 Mission clock** · UTC, NASA day-of-year format")
        mode = st.radio("Time source", ["Mission timeline", "Exact time", "Live (UTC now)"], horizontal=True,
                        label_visibility="collapsed")
        if mode == "Mission timeline":
            t_sel = st.slider("Scrub through the mission", min_value=start.to_pydatetime(),
                              max_value=end_mission.to_pydatetime(), value=start.to_pydatetime(),
                              step=timedelta(minutes=step_min), format="MMM DD, HH:mm")
            t_sel = pd.Timestamp(t_sel)
        elif mode == "Exact time":
            txt = st.text_input("Exact UTC time (to the second)", ui.doy(start),
                                help="Formats: 2027-228T18:30:15Z (day-of-year) or 2027-08-16 18:30:15")
            try:
                t_sel = (pd.Timestamp(pd.to_datetime(txt.strip().rstrip("Z"), format="%Y-%jT%H:%M:%S"))
                         if "T" in txt and len(txt.split("T")[0]) == 8 else pd.Timestamp(txt.strip().rstrip("Z")))
            except (ValueError, TypeError):
                st.error("Could not read that time — use 2027-228T18:30:15Z or 2027-08-16 18:30:15")
                t_sel = start
        else:
            t_sel = pd.Timestamp.now(tz="UTC").floor("s")
            st.caption("Live clock — refresh the page to update.")
        t_sel = t_sel.tz_localize("UTC") if t_sel.tz is None else t_sel.tz_convert("UTC")
        houston = t_sel.tz_convert("America/Chicago")
        st.markdown(f'<div class="lln-clock">{ui.doy(t_sel)}</div>'
                    f'<div class="lln-clock-sub">UTC {t_sel:%Y-%m-%d %H:%M:%S} · MET {ui.met(t_sel, start)} · '
                    f'Houston {houston:%H:%M %Z}</div>', unsafe_allow_html=True)

        # exact-second state of every site
        now_state = {s: live.at_time(srows.loc[s], ui.horizon(s), t_sel, params, dsn_mask) for s in chosen}
        status = {s: ui.status_of(bool(r.sunlit), bool(r.dte_visible)) for s, r in now_state.items()}
        n_av = sum(v_ == "available" for v_ in status.values())
        r0 = next(iter(now_state.values()))
        best_dsn = r0.dsn_best or "none"
        st.markdown(
            '<div style="display:flex;gap:10px;margin-top:12px">'
            + ui.kpi("Stations available", f"{n_av} / {len(chosen)}", "power + communication now",
                     "#3DDC97" if n_av else "#FF6B8B")
            + ui.kpi("Prime DSN complex", best_dsn, f"Moon {r0.dsn_best_el:.0f}° above horizon" if r0.dsn_best
                     else "Moon below every mask", ui.EARTH if r0.dsn_best else "#FF6B8B")
            + "</div>", unsafe_allow_html=True)

        # upcoming events (NASA terms: AOS/LOS = acquisition/loss of signal)
        events = []
        for sid in chosen:
            w_ = vis[sid]
            tt = pd.DatetimeIndex(w_.time_utc)
            ic = int(tt.searchsorted(t_sel, side="right")) - 1          # sample at/before the selected time
            for colname, on_txt, off_txt in (("sunlit", "sunrise ☀️", "sunset 🌑"), ("dte_visible", "AOS 📡", "LOS 📡")):
                vals = w_[colname].to_numpy(bool)
                if 0 <= ic < len(vals) - 1:
                    idx = np.flatnonzero(vals[ic + 1:] != vals[ic])
                    if len(idx):
                        events.append((tt[ic + 1 + idx[0]], f"{names[sid]} — {off_txt if vals[ic] else on_txt}"))
        dd = dsn[dsn.time_utc >= t_sel]
        if len(dd) > 1:
            ch = np.flatnonzero(dd.dsn_best.to_numpy()[1:] != dd.dsn_best.to_numpy()[:-1])
            if len(ch):
                a, b = dd.dsn_best.iloc[ch[0]], dd.dsn_best.iloc[ch[0] + 1]
                txt_ = (f"DSN handover {a} → {b}" if a and b else f"DSN coverage gap begins (after {a})" if a
                        else f"DSN coverage resumes ({b})")
                events.append((dd.time_utc.iloc[ch[0] + 1], txt_))
        ec = vis[chosen[0]]
        ecl = ec.eclipse_frac.to_numpy() > 0
        tt = pd.DatetimeIndex(ec.time_utc)
        ic = int(tt.searchsorted(t_sel, side="right")) - 1
        if 0 <= ic < len(ecl) - 1:
            idx = np.flatnonzero(ecl[ic + 1:] != ecl[ic])
            if len(idx):
                events.append((tt[ic + 1 + idx[0]], "Lunar eclipse " + ("ends" if ecl[ic] else "begins") + " 🌒"))
        events.sort(key=lambda e: e[0])
        if events:
            st.markdown("**⏭️ Upcoming events**")
            st.markdown("".join(f'<div class="lln-ev"><span class="tm">{ui.met(e[0], t_sel).replace("T+", "T−")}</span>'
                                f'<span class="tm">{e[0]:%j/%H:%M}Z</span><span>{e[1]}</span></div>'
                                for e in events[:7]), unsafe_allow_html=True)

with col_map:
    with st.container(border=True):
        color_by = st.radio("Map colour", ["Status at selected time", "Mission rating"], horizontal=True,
                            label_visibility="collapsed")
        st.markdown("**🗺️ South-pole landing sites** · real LOLA terrain shading")
        table, best = finder.shift_compare(vis, start, duration_h=dur_days * 24, shifts_h=tuple(shifts),
                                           weights=w, power=power,
                                           terrain_real={s: ui.terrain_status(s) == "real" for s in chosen})
        worst = table.groupby("site_id")["worst_case_score"].first()
        st.plotly_chart(ui.south_pole_map(chosen, worst.to_dict(), height=470, highlight=best,
                                          status=status if color_by.startswith("Status") else None),
                        width="stretch", config={"displayModeBar": False, "scrollZoom": False})
        if color_by.startswith("Status"):
            st.markdown(" ".join(ui.chip(l_, c_) for l_, c_ in ui.STATUS.values()), unsafe_allow_html=True)
        else:
            st.markdown(" ".join(ui.chip(f"{l_} {r_}", c_) for l_, r_, c_ in
                                 [("Excellent", "≥90", "#3DDC97"), ("Good", "70–89", "#4C8DFF"),
                                  ("Fair", "40–69", "#FFB02E"), ("Poor", "<40", "#FF6B8B")]), unsafe_allow_html=True)

# ------------------------------------------------------------------ row 2: station availability board
st.markdown(f'<div class="lln-sec">📡 Station availability<span>at {ui.doy(t_sel)} · power = Sun on the array · '
            f'communication = Earth above terrain{" + DSN in view" if require_dsn else ""}</span></div>',
            unsafe_allow_html=True)


def next_change(sid, col):
    w_ = vis[sid]
    t = pd.DatetimeIndex(w_.time_utc)
    if t_sel < t[0] or t_sel > t[-1]:
        return "outside window"
    i = int(t.searchsorted(t_sel))
    vals = w_[col].to_numpy(bool)
    if i >= len(vals):
        return "—"
    cur = vals[i]
    idx = np.flatnonzero(vals[i:] != cur)
    if not len(idx):
        return f"{'stays on' if cur else 'stays off'} to end of window"
    hrs = (t[i + idx[0]] - t_sel).total_seconds() / 3600
    return f"{'ends' if cur else 'starts'} in {hrs:.1f} h ({t[i + idx[0]]:%j/%H:%M})"


cols = st.columns(min(4, len(chosen)))
for k, sid in enumerate(chosen):
    r = now_state[sid]
    lab, col = ui.STATUS[status[sid]]
    clear_s = r.sun_el_deg - r.horizon_at_sun_deg
    clear_e = r.earth_el_deg - r.horizon_at_earth_deg
    dsn_txt = (f"{r.dsn_best} · Moon {r.dsn_best_el:.0f}°" if r.dsn_best else "no complex above mask")
    with cols[k % len(cols)]:
        st.markdown(
            f'<div class="lln-st" style="border-top:3px solid {col}">'
            f'<div class="hd"><span class="nm">{names[sid]}</span>{ui.chip(lab, col)}</div>'
            f'<div class="ln">☀️ Sun <b>{r.sun_frac * 100:.0f}%</b> visible · el {r.sun_el_deg:+.2f}° '
            f'(clearance {clear_s:+.2f}°)</div>'
            f'<div class="ln">⚡ Solar power <b>{r.p_solar_w / 1000:.2f} kW</b>'
            + (f' · 🌑 eclipse {r.eclipse_frac * 100:.0f}%' if r.eclipse_frac > 0 else "") + '</div>'
            f'<div class="ln">🌍 Earth el {r.earth_el_deg:+.2f}° (clearance <b>{clear_e:+.2f}°</b>)</div>'
            f'<div class="ln">📡 DSN {dsn_txt}</div>'
            f'<div class="mut">☀️ sunlight {next_change(sid, "sunlit")}<br>'
            f'📡 comm {next_change(sid, "dte_visible")}</div></div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ row 3: DSN panel
st.markdown('<div class="lln-sec">🛰️ NASA Deep Space Network<span>Moon elevation at each complex · a station can '
            'talk to Earth only when Earth is above its horizon and a complex sees the Moon</span></div>',
            unsafe_allow_html=True)
dcol = st.columns(3)
for k, (name, (lat, lon, _)) in enumerate(DSN_COMPLEXES.items()):
    el = r0[f"dsn_{name.lower()}_el"]
    up = el >= dsn_mask
    prime = name == r0.dsn_best
    colr = ui.EARTH if up else ui.GREY
    dcol[k].markdown(ui.kpi(("★ PRIME · " if prime else "") + name, f"{el:+.1f}°",
                            ("Moon in view" if up else "below mask") + f" · {abs(lat):.1f}°{'N' if lat > 0 else 'S'}",
                            "#3DDC97" if prime else colr), unsafe_allow_html=True)
fig = go.Figure()
for name, c in zip(DSN_COMPLEXES, ["#FFB02E", "#B57BFF", "#3DDC97"]):
    fig.add_trace(go.Scatter(x=dsn.time_utc, y=dsn[f"dsn_{name.lower()}_el"], name=name, mode="lines",
                             line=dict(color=c, width=2.2)))
fig.add_hline(y=dsn_mask, line=dict(color="#FF6B8B", dash="dash", width=1),
              annotation_text=f"mask {dsn_mask:.0f}°", annotation_font_color="#FF6B8B")
fig.add_shape(type="line", x0=t_sel, x1=t_sel, y0=-90, y1=90, line=dict(color="white", width=1.5, dash="dot"))
fig.update_yaxes(range=[-5, 90], title="Moon elevation (°)")
fig.update_xaxes(range=[start, end_mission])
fig = ui.style_fig(fig, 300, "Moon elevation at the DSN complexes — dotted line = selected time")
fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"))
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ------------------------------------------------------------------ row 4: mission ranking
st.markdown(f'<div class="lln-sec">🏆 Best landing site for this window<span>{dur_days:g}-day stay from '
            f'{ui.doy(start)} · ranked by worst case over {", ".join(f"+{s} h" for s in shifts)} arrival slips</span>'
            '</div>', unsafe_allow_html=True)
base = table[table.shift_h == 0].set_index("site_id")
order = list(worst.sort_values(ascending=False).index)
top = best or order[0]
left, right = st.columns([1.45, 1])
with left:
    rows = []
    for sid in order:
        r = base.loc[sid]
        lab, col = ui.rating(r.worst_case_score)
        rows.append(f'<tr><td><span class="lln-dot" style="background:{col}"></span>{names[sid]}</td>'
                    f'<td>{r.pct_sunlit:.0f}%</td><td>{r.pct_dte:.0f}%</td><td>{r.pct_both:.0f}%</td>'
                    f'<td>{r.longest_dark_h:.0f} h</td><td>{r.longest_no_dte_h:.0f} h</td>'
                    f'<td>{r.required_nameplate_kwh:.0f} kWh</td><td><b>{r.worst_case_score:.0f}</b></td>'
                    f'<td>{ui.chip(lab, col)}</td></tr>')
    st.markdown('<div class="lln-card"><table class="lln-table"><tr><th>Site</th><th>☀️ Power</th><th>📡 Comm</th>'
                '<th>Both</th><th>Longest dark</th><th>Longest no-comm</th><th>Battery</th><th>Worst-case</th>'
                '<th>Rating</th></tr>' + "".join(rows) + "</table></div>", unsafe_allow_html=True)
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
        st.markdown(f'<div class="lln-rec"><h4>✅ Recommendation</h4>{txt}<br><span style="color:#9AA4B8;'
                    'font-size:0.8rem">Best modeled location under your selected criteria — not a landing-safety '
                    'assessment.</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="lln-warn"><h4>Demonstration ranking</h4>Top: <b>{names[top]}</b> '
                    f'(worst-case {worst[top]:.0f}). No confident recommendation: terrain data is synthetic, missing '
                    'or incomplete for these sites.</div>', unsafe_allow_html=True)
    if table.pct_eclipsed.max() > 0:
        st.info("🌑 A lunar eclipse (Earth passing in front of the Sun, as seen from the Moon) falls inside this "
                "window; it is included in sunlight and power.")

# timeline with selected-time marker
segs = []
for sid in order:
    w0 = finder.window(vis[sid], start, dur_days * 24)
    t = pd.DatetimeIndex(w0.time_utc)
    dt = t[1] - t[0]
    for kind, colname in (("☀️ Power (sunlit)", "sunlit"), ("📡 Communication", "dte_visible")):
        m = w0[colname].to_numpy(bool)
        edges = np.flatnonzero(np.diff(np.concatenate([[0], m.astype(int), [0]])))
        for a, b in zip(edges[0::2], edges[1::2]):
            segs.append({"Row": f"{names[sid]} · {kind.split(' ')[0]}", "Kind": kind, "Start": t[a],
                         "Finish": t[b - 1] + dt})
if segs:
    sdf = pd.DataFrame(segs)
    fig = px.timeline(sdf, x_start="Start", x_end="Finish", y="Row", color="Kind", opacity=0.92,
                      color_discrete_map={"☀️ Power (sunlit)": ui.SUN, "📡 Communication": ui.EARTH})
    cats = [f"{names[s]} · {e}" for s in order for e in ("☀️", "📡")]
    fig.update_yaxes(categoryorder="array", categoryarray=cats[::-1], title=None)
    fig.update_xaxes(title=None, range=[start, end_mission])
    fig.add_shape(type="line", x0=t_sel, x1=t_sel, y0=0, y1=1, yref="paper",
                  line=dict(color="white", width=2, dash="dot"))
    fig = ui.style_fig(fig, 120 + 44 * len(order), "🕒 Visibility timeline — dotted line = selected time")
    fig.update_layout(legend_title_text="", legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1,
                                                        xanchor="right"))
    st.plotly_chart(fig, width="stretch")

c1, c2 = st.columns(2)
with c1:
    fig = go.Figure()
    for sid in order:
        sc = table[table.site_id == sid].sort_values("shift_h")
        fig.add_trace(go.Scatter(x=[f"+{h} h" for h in sc.shift_h], y=sc.score, mode="lines+markers",
                                 name=names[sid], line=dict(color=ui.site_color(sid), width=3), marker=dict(size=9)))
    fig.update_yaxes(range=[-3, 103], title="Score")
    st.plotly_chart(ui.style_fig(fig, 340, "⏱️ Schedule risk — score if arrival slips"), width="stretch")
with c2:
    fig = go.Figure(go.Bar(x=[names[s] for s in order], y=[base.loc[s, "required_nameplate_kwh"] for s in order],
                           marker_color=[ui.site_color(s) for s in order],
                           text=[f"{base.loc[s, 'required_nameplate_kwh']:.0f} kWh" for s in order],
                           textposition="outside"))
    fig.update_yaxes(title="Battery (kWh, nameplate)")
    st.plotly_chart(ui.style_fig(fig, 340, f"🔋 Battery needed to ride through darkness ({load:.0f} W)"),
                    width="stretch")

with st.expander("📋 All metrics (every site × arrival scenario)"):
    show = table[["site_id", "shift_h", "pct_sunlit", "pct_dte", "pct_both", "longest_dark_h", "longest_no_dte_h",
                  "mean_solar_w", "required_nameplate_kwh", "soc_end", "pct_uncertain", "pct_eclipsed", "score",
                  "worst_case_score", "terrain_real", "confident"]].copy()
    show["site_id"] = show.site_id.map(names)
    st.dataframe(show.round(2), width="stretch", hide_index=True)

st.caption("➡️ **Sky View** (sidebar) shows the Sun and Earth moving over the real horizon at any site.")
ui.footer()
