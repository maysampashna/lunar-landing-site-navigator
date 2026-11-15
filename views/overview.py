"""Mission Overview — setup, map and clock first; then the decision summary; then detailed analysis in tabs."""
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

ui.banner("rocket_launch", "Mission Overview",
          "Compare candidate south-pole sites for a modeled surface stay: sunlight for power and potential "
          "direct-to-Earth (DTE) communication.",
          f'<span class="lln-pill amber">{ui.mi("satellite_alt", 18)} Mission Control Mode</span> '
          + ui.validated_pill())
if not live.kernels_available():
    st.error("Ephemeris kernels are missing from this deployment.")
    st.stop()

col_setup, col_map, col_clock = st.columns([0.8, 1.3, 1.1])

# ================================================================== LEVEL 1 — setup, map, clock
with col_setup:
    with st.container(key="card_setup"):
        ui.card_title("tune", "Mission Setup")
        chosen = st.multiselect("Candidate sites", list(names), format_func=names.get, key="m_sites")
        a, b = st.columns([1.35, 1])
        a.date_input("Surface start (UTC)", min_value=pd.Timestamp("2026-01-02").date(),
                     max_value=pd.Timestamp("2031-02-10").date(), key="m_date")
        b.number_input("Hour (UTC)", 0, 23, key="m_hour")
        dur_days = st.slider("Surface stay (days)", 1.0, 14.0, step=0.5, key="m_dur")
        with st.expander("Advanced controls", icon=":material/settings:"):
            st.caption("Communication")
            require_dsn = st.toggle("Require a DSN complex to see the Moon", True,
                                    help="Potential DTE needs Earth above the site's terrain AND the Moon above the "
                                         "elevation mask at Goldstone, Madrid or Canberra (geometry only).")
            dsn_mask = st.slider("DSN elevation mask (°)", 0.0, 20.0, 10.0, 1.0)
            mask = st.slider("Earth clearance above terrain (°)", 0.0, 10.0, 0.0, 0.5)
            st.caption("Power (illustrative)")
            thr = st.slider("Sunlit if ≥ this fraction of the Sun's disc is visible", 0.05, 1.0, 0.5, 0.05)
            area = st.number_input("Solar array area (m²)", 1.0, 200.0, 10.0)
            eff = st.slider("Array efficiency", 0.1, 0.4, 0.30)
            load = st.number_input("Constant load (W)", 50.0, 20000.0, 1000.0, 50.0)
            st.caption("Schedule risk and time step")
            extra = st.multiselect("Surface-start shifts (h)", [24, 48, 72], default=[24, 48])
            step_min = st.select_slider("Time resolution", [5, 10, 15, 30, 60], value=10,
                                        format_func=lambda m: f"{m} min")
            st.caption("Ranking preferences")
            w = ui.weights_sidebar(expander=False)

if not chosen:
    st.info("Pick at least one candidate site.")
    st.stop()
shifts = sorted({0, *extra})
start = ui.mission_start()
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
try:
    table, best = finder.shift_compare(vis, start, duration_h=dur_days * 24, shifts_h=tuple(shifts), weights=w,
                                       power=power,
                                       terrain_real={s: ui.terrain_status(s) == "real" for s in chosen})
except finder.DateRangeError as e:
    st.error(f"Choose an earlier start or a shorter stay. {e}")
    st.stop()
worst = table.groupby("site_id")["worst_case_score"].first()
base = table[table.shift_h == 0].set_index("site_id")
conf = table.groupby("site_id")["confident"].first()
# deterministic order: worst-case score, then Sun+DTE %, then storage, then name (ties stay ties in the labels)
order = sorted(chosen, key=lambda s: (-round(worst[s]), -base.loc[s, "pct_both"],
                                      base.loc[s, "required_nameplate_kwh"], names[s].casefold()))
pool = [s for s in order if conf[s]] or order
top_score = round(worst[pool[0]])
winners = [s for s in pool if round(worst[s]) == top_score]
top = winners[0]

# map click → focused site (applied before the focus selector is drawn)
sel = st.session_state.get("ov_map")
pts = (sel or {}).get("selection", {}).get("points", []) if isinstance(sel, dict) else \
    (getattr(getattr(sel, "selection", None), "points", None) or [])
if pts:
    sid_clicked = pts[0].get("customdata")
    sid_clicked = sid_clicked[0] if isinstance(sid_clicked, (list, tuple)) else sid_clicked
    if sid_clicked in chosen and st.session_state.get("_ov_last_click") != sid_clicked:
        st.session_state["m_site"] = sid_clicked
    st.session_state["_ov_last_click"] = sid_clicked
if st.session_state.get("m_site") not in chosen:
    st.session_state["m_site"] = top


def next_events_for(sid, t_sel):
    """[(time, label)] next change of power and of potential DTE after t_sel."""
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


with col_clock:
    with st.container(key="card_clock"):
        ui.card_title("timer", "Mission Clock", "simulated mission time")
        mode = st.segmented_control("Time source", ["Timeline", "Exact time", "Now (UTC)"], default="Timeline",
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
        elif mode == "Now (UTC)":
            t_sel = pd.Timestamp.now(tz="UTC").floor("s")
        else:
            t_sel = pd.Timestamp(st.slider("Mission time", min_value=start.to_pydatetime(),
                                           max_value=end_mission.to_pydatetime(), value=start.to_pydatetime(),
                                           step=timedelta(minutes=step_min), format="MMM DD HH:mm",
                                           label_visibility="collapsed"))
        t_sel = t_sel.tz_localize("UTC") if t_sel.tz is None else t_sel.tz_convert("UTC")
        if not (vis[chosen[0]].time_utc.min() <= t_sel <= vis[chosen[0]].time_utc.max()):
            st.warning("That time is outside the selected stay; showing the surface start instead.")
            t_sel = start
        now_real = pd.Timestamp.now(tz="UTC")
        st.markdown(f'<div class="lln-clock">{ui.doy(t_sel)}</div><div class="lln-clock-sub">Selected time · '
                    f'MET {ui.met(t_sel, start)}<br>Houston {t_sel.tz_convert("America/Chicago"):%H:%M %Z} · '
                    f'Actual now: {now_real:%Y-%j}T{now_real:%H:%M}Z</div>', unsafe_allow_html=True)

        now_state = {s: live.at_time(srows.loc[s], ui.horizon(s), t_sel, params, dsn_mask) for s in chosen}
        status = {s: ui.status_of(bool(r.sunlit), bool(r.dte_visible)) for s, r in now_state.items()}
        r0 = next(iter(now_state.values()))
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
                a_, b_ = dd.dsn_best.iloc[ch[0]], dd.dsn_best.iloc[ch[0] + 1]
                events.append((dd.time_utc.iloc[ch[0] + 1],
                               f"DSN {a_} → {b_}" if a_ and b_ else f"DSN gap begins ({a_})" if a_
                               else f"DSN resumes ({b_})", ui.GREY))
        ec = vis[chosen[0]]
        ecl = ec.eclipse_frac.to_numpy() > 0
        tt = pd.DatetimeIndex(ec.time_utc)
        ic = int(tt.searchsorted(t_sel, side="right")) - 1
        if 0 <= ic < len(ecl) - 1:
            idx = np.flatnonzero(ecl[ic + 1:] != ecl[ic])
            if len(idx):
                events.append((tt[ic + 1 + idx[0]], "Lunar eclipse " + ("ends" if ecl[ic] else "begins"), "#C9D8E0"))
        events.sort(key=lambda e: e[0])
        st.markdown('<div class="lln-ct" style="font-size:0.98rem;margin-top:4px">'
                    f'{ui.mi("format_list_bulleted")}<span>Upcoming events</span></div>'
                    + "".join(f'<div class="lln-ev"><span class="d" style="background:{c}"></span>'
                              f'<span class="tm">{ui.tminus(t, t_sel)}</span><span>{lab}</span></div>'
                              for t, lab, c in events[:5])
                    + ("" if events else '<div class="lln-ev">No changes before the end of the stay</div>'),
                    unsafe_allow_html=True)

with col_map:
    with st.container(key="card_map"):
        a, b = st.columns([1.15, 1], vertical_alignment="center")
        color_by = a.segmented_control("Map colour", ["At selected time", "Mission rating"],
                                       default="At selected time", label_visibility="collapsed")
        focus = b.selectbox("Focus site", chosen, format_func=names.get, key="m_site", label_visibility="collapsed")
        st.plotly_chart(ui.south_pole_map(chosen, worst.to_dict(), height=470, highlight=focus,
                                          status=status if color_by != "Mission rating" else None),
                        width="stretch", config={"displayModeBar": False, "scrollZoom": False},
                        on_select="rerun", selection_mode="points", key="ov_map")
        if color_by != "Mission rating":
            legend = " ".join(ui.chip(l_, c_) for l_, c_ in ui.STATUS.values())
        else:
            legend = " ".join(ui.chip(f"{l_} {r_}", c_) for l_, r_, c_ in
                              [("Excellent", "≥90", "#3DDC97"), ("Good", "70–89", "#4C8DFF"),
                               ("Fair", "40–69", "#FFB02E"), ("Poor", "<40", "#FF6B8B")])
        c1, c2 = st.columns([1.6, 1], vertical_alignment="center")
        c1.markdown(legend + '<div style="color:#8FA4B0;font-size:0.8rem;margin-top:4px">Click a site to focus it.'
                    '</div>', unsafe_allow_html=True)
        c2.page_link("views/sky_view.py", label=f"Sky View: {names[focus]}", icon=":material/satellite_alt:")

# ================================================================== LEVEL 2 — Mission Decision Summary
fragile = []
for sid in order:
    sc = table[table.site_id == sid].set_index("shift_h")["score"]
    if sc.loc[0] - sc.min() >= 5:
        fragile.append(f"{names[sid]} drops from {sc.loc[0]:.0f} to {sc.min():.0f} at +{int(sc.idxmin())} h")


def vals(col, fmt="{:.0f}"):
    v = [fmt.format(base.loc[s, col]) for s in winners]
    return v[0] if len(set(v)) == 1 else " / ".join(v)


shift_txt = " | ".join(
    ("0 h" if h == 0 else f"+{h} h") + " " + " / ".join(dict.fromkeys(
        f"{table[(table.site_id == s) & (table.shift_h == h)].score.iloc[0]:.0f}" for s in winners))
    for h in shifts)
tie = len(winners) > 1
wb = base.loc[top]
if wb.pct_sunlit >= 99.5 and wb.pct_dte >= 99.5:
    reason = "Sunlight and potential DTE are available for the whole stay"
else:
    reason = (f"Highest combined sunlight ({vals('pct_sunlit')}%) and potential DTE ({vals('pct_dte')}%) "
              "among the selected sites")
reason += (", and the score does not drop when the surface start shifts." if all(
    worst[s] >= base.loc[s, "score"] - 0.5 for s in winners) else ", with the smallest loss when the start shifts.")
if tie:
    reason = (f"{len(winners)} sites tie on every scenario. " + reason +
              " Pick between them on factors this tool does not model (terrain hazards, slopes, operations).")
if fragile:
    reason += f"<br>Schedule risk: {'; '.join(fragile)}."
if table.pct_eclipsed.max() > 0:
    reason += "<br>A lunar eclipse falls inside this stay and is included in sunlight and power."
head = ("Tie · best modeled sites" if tie else "Best modeled site") if best is not None else "Demonstration ranking"
st.markdown(
    '<div class="lln-dec">'
    f'<div class="site"><div class="lb">{ui.mi("flag", 18, ui.AMBER)} {head}</div>'
    f'<div class="nm">{" &amp; ".join(names[s] for s in winners)}</div>'
    f'<div style="color:#B5C7D1;font-size:0.82rem;margin-top:2px">{dur_days:g}-day stay from {ui.doy(start)}</div></div>'
    f'<div class="score"><div class="lb">Worst-case score</div><div class="vl">{top_score}</div>'
    f'<div style="color:#8FA4B0;font-size:0.8rem">of 100</div></div>'
    '<div class="mt">'
    f'<span>{ui.mi("wb_sunny", 17, ui.SUN)} Sunlight over stay</span><b>{vals("pct_sunlit")}%</b>'
    f'<span>{ui.mi("public", 17, ui.EARTH)} Potential DTE over stay</span><b>{vals("pct_dte")}%</b>'
    f'<span>{ui.mi("battery_charging_full", 17, ui.SUN)} Estimated storage</span>'
    f'<b>{vals("required_nameplate_kwh")} kWh</b>'
    f'<span>{ui.mi("schedule", 17, ui.TEAL)} Score by start shift</span><b>{shift_txt}</b></div>'
    f'<div class="why"><b>Why:</b> {reason}<div class="nt">Modeled site comparison under the selected criteria — '
    'not a complete landing-safety recommendation.</div></div>'
    '</div>', unsafe_allow_html=True)
if best is None:
    st.warning("No confident ranking: terrain data is missing or incomplete for these sites.")

# ================================================================== site status at the selected time
st.markdown(f'<div class="lln-sec">{ui.mi("radar")}Site status<span class="lln-tag">at selected time</span>'
            f'<span style="color:#8FA4B0;font-weight:500;font-size:0.86rem;margin-left:8px">{ui.doy(t_sel)}</span></div>',
            unsafe_allow_html=True)
cols = st.columns(min(4, len(chosen)))
for k, sid in enumerate(order):
    r = now_state[sid]
    lab, col = ui.STATUS[status[sid]]
    ev = next_events_for(sid, t_sel)
    nxt = f"{min(ev)[1]} in {(min(ev)[0] - t_sel).total_seconds() / 3600:.1f} h" if ev else "none in stay"
    dsn_txt = f"{r.dsn_best} · {r.dsn_best_el:.0f}°" if r.dsn_best else "none"
    with cols[k % len(cols)]:
        st.markdown(
            f'<div class="lln-st{" focus" if sid == focus else ""}"><div class="hd"><div class="ib">'
            f'{ui.mi("landscape", 24)}</div><div><div class="nm">{names[sid]}</div>{ui.chip(lab, col)}</div></div>'
            f'<div class="rw"><span>{ui.mi("wb_sunny", 18, ui.SUN)}Sun disc visible</span><b>{r.sun_frac * 100:.0f}%</b></div>'
            f'<div class="rw"><span>{ui.mi("public", 18, ui.EARTH)}Earth disc visible</span><b>{r.earth_frac * 100:.0f}%</b></div>'
            f'<div class="rw"><span>{ui.mi("bolt", 18, ui.SUN)}Solar power</span><b>{r.p_solar_w / 1000:.2f} kW</b></div>'
            f'<div class="rw"><span>{ui.mi("cell_tower", 18, ui.EARTH)}DSN geometry</span><b>{dsn_txt}</b></div>'
            f'<div class="rw"><span>{ui.mi("event", 18, ui.GREY)}Next change</span><b>{nxt}</b></div>'
            f'<div class="mut">Clearance above terrain: Sun {r.sun_el_deg - r.horizon_at_sun_deg:+.2f}° · '
            f'Earth {r.earth_el_deg - r.horizon_at_earth_deg:+.2f}°</div></div>', unsafe_allow_html=True)

# ================================================================== LEVEL 3 — detailed analysis
st.markdown(f'<div class="lln-sec">{ui.mi("analytics")}Detailed analysis<span class="lln-tag">over the full stay</span>'
            '</div>', unsafe_allow_html=True)
tabs = st.tabs([":material/table_chart: Site Comparison", ":material/cell_tower: DSN Geometry",
                ":material/timeline: Visibility Timeline", ":material/schedule: Schedule Risk",
                ":material/battery_charging_full: Battery & Power"])

with tabs[0]:
    rows = []
    for sid in order:
        r = base.loc[sid]
        lab, col = ui.rating(r.worst_case_score)
        rank = 1 + sum(round(worst[s]) > round(worst[sid]) for s in order)
        tied = sum(round(worst[s]) == round(worst[sid]) for s in order) > 1
        rows.append(f'<tr class="{"top" if sid in winners else ""}"><td>{rank}{"=" if tied else ""}</td>'
                    f'<td><b>{names[sid]}</b></td><td class="n">{r.pct_sunlit:.0f}</td><td class="n">{r.pct_dte:.0f}</td>'
                    f'<td class="n">{r.pct_both:.0f}</td><td class="n">{r.longest_dark_h:.0f}</td>'
                    f'<td class="n">{r.longest_no_dte_h:.0f}</td><td class="n">{r.required_nameplate_kwh:.0f}</td>'
                    f'<td class="n">{r.score:.0f}</td><td class="n"><b>{r.worst_case_score:.0f}</b></td>'
                    f'<td>{ui.chip(lab, col)}</td></tr>')
    st.markdown(
        '<table class="lln-table"><tr><th>#</th><th>Site</th>'
        '<th class="n" title="Share of the stay with at least the chosen fraction of the Sun disc above terrain">Sun %</th>'
        '<th class="n" title="Share of the stay with Earth above terrain + mask (and a DSN complex seeing the Moon, if required)">DTE %</th>'
        '<th class="n" title="Sunlit and potential DTE at the same time">Both %</th>'
        '<th class="n" title="Longest continuous period without sunlight">Longest dark (h)</th>'
        '<th class="n" title="Longest continuous period without potential DTE">Longest no-DTE (h)</th>'
        '<th class="n" title="Illustrative battery nameplate needed to carry the load through darkness">Storage (kWh)</th>'
        '<th class="n" title="Score for the planned surface start">Score</th>'
        '<th class="n" title="Lowest score across the surface-start shifts">Worst case</th><th>Rating</th></tr>'
        + "".join(rows) + "</table>", unsafe_allow_html=True)
    st.caption("Ties share a rank (shown as 1=). Rows are then listed by Both %, storage and name for a stable order.")
    with st.expander("All metrics (every site × start shift)", icon=":material/table:"):
        show = table[["site_id", "shift_h", "pct_sunlit", "pct_dte", "pct_both", "longest_dark_h", "longest_no_dte_h",
                      "mean_solar_w", "required_nameplate_kwh", "soc_end", "pct_uncertain", "pct_eclipsed", "score",
                      "worst_case_score", "terrain_real", "confident"]].copy()
        show["site_id"] = show.site_id.map(names)
        st.dataframe(show.round(2), width="stretch", hide_index=True)

with tabs[1]:
    st.caption("Potential geometric access: the Moon is above the elevation mask at a complex. This is not "
               "scheduled antenna time and does not confirm DSN service.")
    dcol = st.columns([1, 1, 1, 3.2])
    for k, (name, _) in enumerate(DSN_COMPLEXES.items()):
        el = r0[f"dsn_{name.lower()}_el"]
        up = el >= dsn_mask
        with dcol[k]:
            st.markdown(ui.kcard("cell_tower", name, f"{el:+.1f}°",
                                 ("Moon in view" if up else "Below mask") + (" · highest" if name == r0.dsn_best else ""),
                                 ui.EARTH if up else ui.GREY, small=True), unsafe_allow_html=True)
    with dcol[3]:
        fig = go.Figure()
        for name, c in zip(DSN_COMPLEXES, ["#FFB02E", "#B57BFF", "#3DDC97"]):
            fig.add_trace(go.Scatter(x=dsn.time_utc, y=dsn[f"dsn_{name.lower()}_el"], name=name, mode="lines",
                                     line=dict(color=c, width=2)))
        fig.add_hline(y=dsn_mask, line=dict(color="#FF6B8B", dash="dash", width=1),
                      annotation_text=f"mask {dsn_mask:.0f}°", annotation_position="bottom right")
        fig.add_shape(type="line", x0=t_sel, x1=t_sel, y0=-90, y1=90, line=dict(color="white", width=1.5, dash="dot"))
        fig.update_yaxes(range=[-5, 90], title="Moon elevation (°)")
        fig.update_xaxes(range=[start, end_mission], title="UTC")
        fig = ui.style_fig(fig, 240)
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"),
                          margin=dict(l=10, r=10, t=26, b=10))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Values at the selected time; the dotted line marks it on the chart.")

with tabs[2]:
    segs = []
    for sid in order:
        w0 = finder.window(vis[sid], start, dur_days * 24)
        t = pd.DatetimeIndex(w0.time_utc)
        dt = t[1] - t[0]
        for kind, colname, lane in (("Sunlit (power)", "sunlit", "Sun"), ("Potential DTE", "dte_visible", "DTE")):
            m = w0[colname].to_numpy(bool)
            edges = np.flatnonzero(np.diff(np.concatenate([[0], m.astype(int), [0]])))
            for a_, b_ in zip(edges[0::2], edges[1::2]):
                segs.append({"Lane": f"{names[sid]} — {lane}", "Kind": kind, "Start": t[a_],
                             "Finish": t[b_ - 1] + dt})
    if segs:
        sdf = pd.DataFrame(segs)
        fig = px.timeline(sdf, x_start="Start", x_end="Finish", y="Lane", color="Kind", opacity=0.95,
                          color_discrete_map={"Sunlit (power)": ui.SUN, "Potential DTE": ui.EARTH})
        lanes = [f"{names[s]} — {e}" for s in order for e in ("Sun", "DTE")]
        fig.update_yaxes(categoryorder="array", categoryarray=lanes[::-1], title=None)
        fig.update_xaxes(title="UTC", range=[start, end_mission], tickformat="%b %d\n%H:%M")
        fig.add_shape(type="line", x0=t_sel, x1=t_sel, y0=0, y1=1, yref="paper",
                      line=dict(color="white", width=1.5, dash="dot"))
        for k in range(1, len(order)):
            fig.add_hline(y=2 * k - 0.5, line=dict(color="#2A4555", width=1))
        fig = ui.style_fig(fig, 110 + 34 * len(lanes))
        fig.update_layout(legend_title_text="", bargap=0.35,
                          legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"),
                          margin=dict(l=10, r=10, t=26, b=10))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Filled bars = available. Gaps = Sun or Earth behind terrain (or no DSN geometry when required). "
               "Dotted line = selected time.")

with tabs[3]:
    fig = go.Figure()
    xs = [("0 h" if h == 0 else f"+{h} h") for h in shifts]
    for sid in order:
        sc = table[table.site_id == sid].sort_values("shift_h")
        win = sid in winners
        fig.add_trace(go.Scatter(x=xs, y=sc.score, mode="lines+markers", name=names[sid] + ("  ★" if win else ""),
                                 line=dict(color=ui.site_color(sid), width=4 if win else 2),
                                 marker=dict(size=10 if win else 7), opacity=1 if win else 0.75))
    fig.update_yaxes(range=[-3, 105], title="Score")
    fig.update_xaxes(title="Surface-start shift")
    fig = ui.style_fig(fig, 320)
    fig.update_layout(legend=dict(orientation="v", yanchor="top", y=1, x=1.01, xanchor="left"),
                      margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"★ Highest worst-case score: {' & '.join(names[s] for s in winners)} ({top_score}). "
               "A shift moves the whole stay later by that many hours (sensitivity check, not a trajectory model).")

with tabs[4]:
    vals_kwh = [base.loc[s, "required_nameplate_kwh"] for s in order]
    fig = go.Figure(go.Bar(x=[names[s] for s in order], y=vals_kwh, marker_color=ui.SUN, opacity=0.9,
                           text=[f"{v:.0f} kWh" for v in vals_kwh], textposition="outside", width=0.5))
    fig.update_yaxes(title="Estimated storage (kWh)", range=[0, max(10, max(vals_kwh)) * 1.2])
    st.plotly_chart(ui.style_fig(fig, 300), width="stretch", config={"displayModeBar": False})
    st.caption(f"Illustrative estimate: constant {load:.0f} W load, {area:g} m² Sun-tracking array at {eff:.0%} "
               "efficiency, 95 % charge/discharge efficiency, 80 % usable depth of discharge, planned start. "
               "Not a flight design.")

ui.footer()
