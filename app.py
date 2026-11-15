"""Lunar Landing Site Navigator — Decision Report (main page).

Run:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import data, finder, live, visibility
from engine.power import PowerParams
import ui_common as ui

st.set_page_config(page_title="Lunar Landing Site Navigator", page_icon="🌘", layout="wide")

sites = ui.sites_df()
names = ui.names()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Mission setup")
    chosen = st.multiselect("Sites", list(names), default=["malapert_massif", "de_gerlache_rim_2", "mons_mouton", "nobile_rim_2"], format_func=names.get)
    dur_days = st.number_input("Surface stay (days)", 1.0, 14.0, 6.0, 0.5)
    extra = st.multiselect("Surface-start shifts (h)", [24, 48, 72], default=[24, 48])
    shifts = sorted({0, *extra})
    earliest, latest = finder.valid_start_range(ui.ephem(list(names)[0]), dur_days * 24, max(shifts))
    start_date = st.date_input("Surface start (UTC)", pd.Timestamp("2027-08-16").date(),
                               min_value=earliest.date(), max_value=latest.date())
    start_hour = st.slider("Start hour (UTC)", 0, 23, 12)
    with st.expander("Visibility assumptions"):
        thr = st.slider("Sunlit if ≥ this fraction of the Sun's disc is visible", 0.05, 1.0, 0.5, 0.05)
        mask = st.slider("Earth elevation mask above terrain (°)", 0.0, 10.0, 0.0, 0.5)
    with st.expander("Illustrative power model"):
        area = st.number_input("Array area (m²)", 1.0, 200.0, 10.0)
        eff = st.slider("Array efficiency", 0.1, 0.4, 0.30)
        load = st.number_input("Constant load (W)", 50.0, 20000.0, 1000.0, 50.0)
    w = ui.weights_sidebar()

st.title("Lunar Mission Decision Report")
st.caption("Artemis III candidate regions (crewed landing now planned for Artemis IV) · "
           "representative points, not NASA-designated landing sites")
if not chosen:
    st.info("Pick at least one site in the sidebar.")
    st.stop()

banners = ui.data_banners(chosen)
power = PowerParams(array_area_m2=area, efficiency=eff, load_w=load)
params = visibility.VisParams(sunlit_threshold=thr, earth_mask_deg=mask, power=power)
start = pd.Timestamp(start_date).tz_localize("UTC") + pd.Timedelta(hours=start_hour)

if live.kernels_available():
    end = start + pd.Timedelta(hours=dur_days * 24 + max(shifts))
    srows = sites.set_index("site_id")
    vis = {s: live.fine_visibility(srows.loc[s], ui.horizon(s), start, end, params, step_min=10) for s in chosen}
    resolution_note = "10-minute resolution (recomputed for this window)"
else:
    vis = {s: ui.hourly_vis(s, thr, mask, area, eff, load) for s in chosen}
    resolution_note = "approximate: hourly samples may miss short shadows or interruptions"

v = ui.validation_report()
if v:
    st.success(f"✅ Ephemeris validated vs JPL Horizons: max error {v['overall_max_error_deg']:.5f}° "
               "(positions only; see Validation & Sources)")
else:
    st.info("Ephemeris validation vs JPL Horizons not yet run (see Validation & Sources).")

try:
    table, best = finder.shift_compare(vis, start, duration_h=dur_days * 24, shifts_h=tuple(shifts),
                                       weights=w, power=power,
                                       terrain_real={s: ui.terrain_status(s) == "real" for s in chosen})
except finder.DateRangeError as e:
    st.error(str(e))
    st.stop()

worst = table.groupby("site_id")["worst_case_score"].first()
demo_top = worst.idxmax()
if best is not None:
    st.subheader(f"Best modeled location under the selected criteria: **{names[best]}**")
elif banners["synthetic"] or banners["missing"]:
    st.subheader(f"Demonstration ranking only — top: {names[demo_top]} (not a recommendation)")
else:
    st.subheader("No confident recommendation: missing terrain could change visibility at every site")
focus_default = best or demo_top
st.write(f"Ranked by worst-case score across surface-start shifts of {', '.join(f'+{s} h' for s in shifts)} "
         f"for a {dur_days:g}-day stay starting {start:%Y-%m-%d %H:%M} UTC · {resolution_note}. "
         "The score is a preference calculation using your weights.")
unconf_terrain = sorted(set(table.loc[table.terrain_real & ~table.confident, "site_id"]))
if unconf_terrain:
    st.warning("Excluded from confident ranking (missing terrain could change visibility): "
               + ", ".join(names[u] for u in unconf_terrain))
if table.pct_eclipsed.max() > 0:
    st.info("🌑 A lunar eclipse (Earth blocking the Sun) falls inside this window; it is included in sunlight and power.")

# ------------------------------------------------------------------ report cards
base = table[table.shift_h == 0].set_index("site_id")
order = sorted(chosen, key=lambda s: -base.loc[s, "worst_case_score"])
for c, s in zip(st.columns(len(chosen)), order):
    r = base.loc[s]
    with c:
        st.markdown(f"### {names[s]}")
        st.metric("Worst-case score", f"{r.worst_case_score:.0f} / 100")
        st.markdown(f"**☀️ Sunlight** {r.pct_sunlit:.0f}% · longest dark {r.longest_dark_h:.0f} h")
        st.markdown(f"**🌍 Potential DTE visibility** {r.pct_dte:.0f}% · longest gap {r.longest_no_dte_h:.0f} h")
        st.markdown(f"**🔋 Storage (illustrative)** {r.required_nameplate_kwh:.0f} kWh nameplate · "
                    f"end charge {100 * r.soc_end:.0f}%")
        status = ui.terrain_status(s)
        if status != "real":
            st.caption(f"🧪 {status} terrain — demonstration only")
        elif not r.confident:
            st.caption(f"⚠️ uncertain terrain {r.max_pct_uncertain:.0f}% of the time")

st.markdown("#### Timing sensitivity")
pivot = table.pivot(index="site_id", columns="shift_h", values="score").rename(index=names)
pivot.columns = [f"score +{c} h" for c in pivot.columns]
st.dataframe(pivot.round(1), width="stretch")

with st.expander("All metrics"):
    show = table[["site_id", "shift_h", "pct_sunlit", "pct_dte", "pct_both", "longest_dark_h", "longest_no_dte_h",
                  "mean_solar_w", "required_nameplate_kwh", "soc_end", "pct_uncertain", "pct_eclipsed", "score",
                  "worst_case_score", "terrain_real", "confident"]].copy()
    show["site_id"] = show.site_id.map(names)
    st.dataframe(show.round(2), width="stretch")

# ------------------------------------------------------------------ timeline + horizon for one site
st.markdown("---")
focus = st.selectbox("Inspect site", chosen, format_func=names.get, index=chosen.index(focus_default))
w0 = finder.window(vis[focus], start, dur_days * 24)

fig = go.Figure()
fig.add_trace(go.Scatter(x=w0.time_utc, y=w0.sun_el_deg, name="Sun elevation", line=dict(color=ui.SUN)))
fig.add_trace(go.Scatter(x=w0.time_utc, y=w0.horizon_at_sun_deg, name="Terrain under Sun",
                         line=dict(color=ui.SUN, dash="dot")))
fig.add_trace(go.Scatter(x=w0.time_utc, y=w0.earth_el_deg, name="Earth elevation", line=dict(color=ui.EARTH)))
fig.add_trace(go.Scatter(x=w0.time_utc, y=w0.horizon_at_earth_deg, name="Terrain under Earth",
                         line=dict(color=ui.EARTH, dash="dot")))
fig.update_layout(title=f"{names[focus]}: Sun and Earth vs terrain horizon", yaxis_title="Elevation (°)",
                  height=380, legend=dict(orientation="h"))
st.plotly_chart(fig, width="stretch")

hp = ui.horizon(focus)
if hp is not None:
    pan = go.Figure()
    pan.add_trace(go.Scatter(x=hp.az_deg, y=hp.horizon_el_deg, fill="tozeroy", name="Terrain horizon",
                             line=dict(color=ui.GREY)))
    pan.add_trace(go.Scatter(x=w0.sun_az_deg, y=w0.sun_el_deg, mode="markers", name="Sun track",
                             marker=dict(color=ui.SUN, size=4)))
    pan.add_trace(go.Scatter(x=w0.earth_az_deg, y=w0.earth_el_deg, mode="markers", name="Earth track",
                             marker=dict(color=ui.EARTH, size=4)))
    if hp.incomplete.any():
        pan.add_trace(go.Scatter(x=hp.az_deg[hp.incomplete], y=hp.horizon_el_deg[hp.incomplete], mode="markers",
                                 name="Terrain data incomplete", marker=dict(color="red", size=3)))
    pan.update_layout(title="360° horizon panorama (azimuth from local north)", xaxis_title="Azimuth (°)",
                      yaxis_title="Elevation (°)", height=380, legend=dict(orientation="h"))
    st.plotly_chart(pan, width="stretch")
else:
    st.warning("No terrain horizon for this site — plotted against a flat 0° horizon; all results uncertain.")

st.caption(ui.LIMITATIONS)
