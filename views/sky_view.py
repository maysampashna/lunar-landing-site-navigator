"""Sky View — what an observer standing at the site would see: Sun and Earth over the real terrain horizon."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import live, visibility
import ui_common as ui

ui.setup_page("Sky View · Lunar Navigator", "🔭")
names = ui.names()
sites = ui.sites_df().set_index("site_id")
mission = st.session_state.get("mission", {})

with st.sidebar:
    st.markdown("### 🔭 Sky View")
    default_site = (mission.get("sites") or ["de_gerlache_rim_2"])[0]
    ids = list(names)
    site = st.selectbox("📍 Site", ids, index=ids.index(default_site) if default_site in ids else 0,
                        format_func=names.get)
    mode = st.radio("Mode", ["🎬 Mission replay", "🔴 Live now"], horizontal=False)
    if mode.startswith("🎬"):
        d0 = mission.get("start", pd.Timestamp("2027-08-16 12:00", tz="UTC"))
        day = st.date_input("Start (UTC)", d0.date(), min_value=pd.Timestamp("2026-01-02").date(),
                            max_value=pd.Timestamp("2031-02-10").date())
        hour = st.slider("Start hour (UTC)", 0, 23, int(d0.hour))
        days = st.slider("Replay length (days)", 1, 14, int(min(14, mission.get("dur_days", 6))))
        start = pd.Timestamp(day).tz_localize("UTC") + pd.Timedelta(hours=hour)
    else:
        now = pd.Timestamp.now(tz="UTC").floor("h")
        start, days = now, 2
        st.caption(f"Showing the next 48 h from **{now:%Y-%m-%d %H:%M} UTC** (frame 1 = now).")
    st.caption("Animation step: 1 hour. Positions from NASA/JPL SPICE kernels; terrain from LOLA.")

hp = ui.horizon(site)
r = sites.loc[site]
st.markdown(f'<div class="lln-hero"><h1>🔭 Sky from {r["name"]}</h1></div>'
            f'<div class="lln-sub">{abs(r.lat_deg):.2f}°S, {r.lon_deg:.2f}°E · surface {float(r.height_m)/1000:.2f} km · '
            'observer 2 m above ground · real LOLA terrain horizon to 150 km · azimuth measured from local north</div>',
            unsafe_allow_html=True)
ui.data_banners([site])
if hp is None:
    st.error("No terrain horizon available for this site.")
    st.stop()
if not live.kernels_available():
    st.error("Ephemeris kernels are not available in this deployment.")
    st.stop()

end = start + pd.Timedelta(days=days)
w = live.fine_visibility(r, hp, start, end, visibility.VisParams(), step_min=60).reset_index(drop=True)
t = pd.DatetimeIndex(w.time_utc)

# ------------------------------------------------------------------ status tiles (frame 1)
f0 = w.iloc[0]
c = st.columns(4)
c[0].markdown(ui.kpi("☀️ Sun", f"{f0.sun_frac * 100:.0f}% visible",
                     f"el {f0.sun_el_deg:+.2f}° · az {f0.sun_az_deg:.1f}° · terrain {f0.horizon_at_sun_deg:+.2f}°",
                     ui.SUN), unsafe_allow_html=True)
c[1].markdown(ui.kpi("🌍 Earth", "in view" if f0.dte_visible else "hidden",
                     f"el {f0.earth_el_deg:+.2f}° · az {f0.earth_az_deg:.1f}° · terrain {f0.horizon_at_earth_deg:+.2f}°",
                     ui.EARTH if f0.dte_visible else ui.GREY), unsafe_allow_html=True)


def next_change(col):
    v = w[col].to_numpy(bool)
    idx = np.flatnonzero(v != v[0])
    if not len(idx):
        return f"no change in {days} d"
    hrs = (t[idx[0]] - t[0]).total_seconds() / 3600
    return f"{'ends' if v[0] else 'starts'} in {hrs:.0f} h"


c[2].markdown(ui.kpi("Sunlight", "ON" if f0.sunlit else "OFF", next_change("sunlit"),
                     ui.SUN if f0.sunlit else ui.GREY), unsafe_allow_html=True)
c[3].markdown(ui.kpi("Earth contact (geometric)", "ON" if f0.dte_visible else "OFF", next_change("dte_visible"),
                     ui.EARTH if f0.dte_visible else ui.GREY), unsafe_allow_html=True)
st.write("")

az = np.concatenate([hp.az_deg, [360.0]])
hz = np.concatenate([hp.horizon_el_deg, hp.horizon_el_deg[:1]])
ymin = float(min(np.nanmin(hz), w.sun_el_deg.min(), w.earth_el_deg.min())) - 2
ymax = float(max(np.nanmax(hz), w.sun_el_deg.max(), w.earth_el_deg.max())) + 3


def label(i):
    row = w.iloc[i]
    return (f"{t[i]:%Y-%m-%d %H:%M} UTC   ·   ☀️ {row.sun_frac * 100:.0f}% of Sun visible   ·   "
            f"🌍 Earth {'in view' if row.dte_visible else 'hidden'}")


def play_controls(n, ms=110):
    steps = [dict(method="animate", args=[[str(i)], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                                         transition=dict(duration=0))],
                  label=f"{t[i]:%d %b %Hh}") for i in range(n)]
    return dict(
        updatemenus=[dict(type="buttons", showactive=False, x=0, y=-0.09, xanchor="left", yanchor="top", direction="left",
                          bgcolor=ui.PANEL, bordercolor=ui.BORDER, font=dict(color="#E6EAF2"),
                          buttons=[dict(label="▶ Play", method="animate",
                                        args=[None, dict(frame=dict(duration=ms, redraw=True), fromcurrent=True,
                                                         transition=dict(duration=0))]),
                                   dict(label="⏸ Pause", method="animate",
                                        args=[[None], dict(frame=dict(duration=0), mode="immediate")])])],
        sliders=[dict(active=0, steps=steps, x=0.16, len=0.84, y=-0.05, pad=dict(t=0),
                      currentvalue=dict(visible=False), font=dict(color="#9AA4B8", size=9),
                      bgcolor=ui.BORDER, activebgcolor=ui.EARTH, tickcolor=ui.BORDER)])


tab1, tab2, tab3 = st.tabs(["🎬 Panorama replay", "🔭 Telescope close-up (true size)", "🧭 All-sky horizon chart"])

# ------------------------------------------------------------------ 1. panorama animation
with tab1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=az, y=hz, fill="tozeroy", mode="lines", name="Terrain (LOLA)",
                             line=dict(color="#9AA4B8", width=1.5), fillcolor="#2B3142", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[0, 360], y=[ymin, ymin], fill="tonexty", mode="lines", line=dict(width=0),
                             fillcolor="#2B3142", showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=w.sun_az_deg, y=w.sun_el_deg, mode="markers", name="Sun path",
                             marker=dict(size=3, color=ui.SUN, opacity=0.35), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=w.earth_az_deg, y=w.earth_el_deg, mode="markers", name="Earth path",
                             marker=dict(size=3, color=ui.EARTH, opacity=0.45), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[f0.sun_az_deg], y=[f0.sun_el_deg], mode="markers", name="Sun",
                             marker=dict(size=30, color="rgba(255,176,46,0.25)", line=dict(width=0)),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[f0.sun_az_deg], y=[f0.sun_el_deg], mode="markers", name="☀️ Sun",
                             marker=dict(size=16, color="#FFD36E", line=dict(color="white", width=1))))
    fig.add_trace(go.Scatter(x=[f0.earth_az_deg], y=[f0.earth_el_deg], mode="markers", name="🌍 Earth",
                             marker=dict(size=20, color=ui.EARTH, line=dict(color="white", width=1.5))))
    frames = []
    for i in range(len(w)):
        row = w.iloc[i]
        frames.append(go.Frame(name=str(i), traces=[4, 5, 6], data=[
            go.Scatter(x=[row.sun_az_deg], y=[row.sun_el_deg]),
            go.Scatter(x=[row.sun_az_deg], y=[row.sun_el_deg]),
            go.Scatter(x=[row.earth_az_deg], y=[row.earth_el_deg])],
            layout=dict(title=dict(text=label(i)))))
    fig.frames = frames
    fig.update_xaxes(range=[0, 360], tickvals=[0, 45, 90, 135, 180, 225, 270, 315, 360],
                     ticktext=["N 0°", "NE", "E 90°", "SE", "S 180°", "SW", "W 270°", "NW", "N"], title=None)
    fig.update_yaxes(range=[ymin, ymax], title="Elevation (°)")
    fig = ui.style_fig(fig, 540)
    fig.update_layout(title=dict(text=label(0), font=dict(size=13, color="#E6EAF2")), **play_controls(len(w)),
                      plot_bgcolor="#03050C", margin=dict(l=10, r=10, t=50, b=95),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"))
    st.plotly_chart(fig, width="stretch")
    st.caption("Press ▶ Play to watch the Sun circle the horizon (one lunar day ≈ 29.5 Earth days) while Earth "
               "rocks with libration. Symbols are enlarged for visibility — see the telescope tab for true sizes. "
               "Vertical scale is exaggerated: south-polar sun angles are only a few degrees.")

# ------------------------------------------------------------------ 2. telescope close-up (true size)
with tab2:
    body = st.radio("Track", ["🌍 Earth", "☀️ Sun"], horizontal=True)
    key = "earth" if body.startswith("🌍") else "sun"
    col = ui.EARTH if key == "earth" else "#FFD36E"
    fov = 6.0 if key == "earth" else 4.0
    th = np.linspace(0, 2 * np.pi, 72)

    def disc(i):
        row = w.iloc[i]
        rad = row[f"{key}_radius_deg"]
        el = row[f"{key}_el_deg"]
        return row[f"{key}_az_deg"] + rad * np.cos(th) / np.cos(np.radians(el)), el + rad * np.sin(th)

    def terrain_window(center):
        a = np.arange(center - 3 * fov, center + 3 * fov, 0.1)
        return a, hp.at(a % 360)

    fig = go.Figure()
    ax_, hz_ = terrain_window(w.iloc[0][f"{key}_az_deg"])
    fig.add_trace(go.Scatter(x=ax_, y=hz_, fill="tozeroy", mode="lines", line=dict(color="#9AA4B8"),
                             fillcolor="#2B3142", name="Terrain", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=ax_, y=np.full_like(ax_, -30), fill="tonexty", mode="lines", line=dict(width=0),
                             fillcolor="#2B3142", showlegend=False, hoverinfo="skip"))
    dx, dy = disc(0)
    fig.add_trace(go.Scatter(x=dx, y=dy, fill="toself", mode="lines", fillcolor=col, line=dict(color="white", width=1),
                             name=f"{body} (true angular size)"))
    frames = []
    for i in range(len(w)):
        cz = w.iloc[i][f"{key}_az_deg"]
        ax_, hz_ = terrain_window(cz)
        dx, dy = disc(i)
        ce = w.iloc[i][f"{key}_el_deg"]
        frames.append(go.Frame(name=str(i), traces=[0, 1, 2], data=[
            go.Scatter(x=ax_, y=hz_), go.Scatter(x=ax_, y=np.full_like(ax_, -30)), go.Scatter(x=dx, y=dy)],
            layout=dict(title=dict(text=label(i)), xaxis=dict(range=[cz - fov, cz + fov]),
                        yaxis=dict(range=[ce - fov * 0.55, ce + fov * 0.55]))))
    fig.frames = frames
    cz, ce = w.iloc[0][f"{key}_az_deg"], w.iloc[0][f"{key}_el_deg"]
    fig.update_xaxes(range=[cz - fov, cz + fov], title="Azimuth (°)")
    fig.update_yaxes(range=[ce - fov * 0.55, ce + fov * 0.55], title="Elevation (°)", scaleanchor="x", scaleratio=1)
    fig = ui.style_fig(fig, 560)
    fig.update_layout(title=dict(text=label(0), font=dict(size=13, color="#E6EAF2")), **play_controls(len(w), 140),
                      plot_bgcolor="#03050C", margin=dict(l=10, r=10, t=50, b=95),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"A {2 * fov:.0f}°-wide telescope view that follows the {key.title()} with equal scale on both axes. "
               "The disc is drawn at its true apparent size (Earth ≈ 1.9°, Sun ≈ 0.53°) so you can see exactly how "
               "much of it clears the real mountain skyline.")

# ------------------------------------------------------------------ 3. all-sky horizon chart
with tab3:
    top = float(np.ceil(max(ymax, 12)))
    rr = lambda el: top - np.asarray(el, float)       # noqa: E731  centre = high elevation, rim = low
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(theta=az, r=rr(hz), mode="lines", fill="toself", fillcolor="rgba(43,49,66,0)",
                                  line=dict(color="#9AA4B8", width=2), name="Terrain horizon", hoverinfo="skip"))
    fig.add_trace(go.Scatterpolar(theta=np.concatenate([az, az[::-1]]),
                                  r=np.concatenate([rr(hz), np.full_like(az, top - ymin + 1)]), fill="toself",
                                  fillcolor="#2B3142", line=dict(width=0), name="Ground", hoverinfo="skip"))
    hrs = (t - t[0]).total_seconds() / 3600
    fig.add_trace(go.Scatterpolar(theta=w.sun_az_deg, r=rr(w.sun_el_deg), mode="markers", name="☀️ Sun track",
                                  marker=dict(size=5, color=hrs, colorscale="YlOrBr", showscale=False),
                                  text=[f"{x:%d %b %H:%M}" for x in t], hovertemplate="Sun %{text}<extra></extra>"))
    fig.add_trace(go.Scatterpolar(theta=w.earth_az_deg, r=rr(w.earth_el_deg), mode="markers", name="🌍 Earth track",
                                  marker=dict(size=5, color=hrs, colorscale="Blues", showscale=False),
                                  text=[f"{x:%d %b %H:%M}" for x in t], hovertemplate="Earth %{text}<extra></extra>"))
    ticks = [e for e in range(int(np.floor(ymin)), int(top) + 1) if e % 2 == 0]
    fig.update_layout(polar=dict(bgcolor="#03050C",
                                 angularaxis=dict(rotation=90, direction="clockwise", gridcolor="#1E2742",
                                                  tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                                                  ticktext=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                                                  color="#C9D1E3"),
                                 radialaxis=dict(range=[0, top - ymin + 1], tickvals=[rr(e) for e in ticks],
                                                 ticktext=[f"{e}°" for e in ticks], gridcolor="#1E2742",
                                                 color="#7D879C", angle=90, tickfont=dict(size=9))))
    fig = ui.style_fig(fig, 600)
    st.plotly_chart(fig, width="stretch")
    st.caption("All-sky view looking straight up: compass directions around the edge, elevation increasing toward "
               "the centre. The grey band is the real terrain; tracks are coloured from light (start) to dark (end).")

ui.footer()
