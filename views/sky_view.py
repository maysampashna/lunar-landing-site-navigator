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

ui.setup_page()
names = ui.names()
sites = ui.sites_df().set_index("site_id")
ids = list(names)
if st.session_state.get("m_site") not in ids:
    st.session_state["m_site"] = ids[0]
st.session_state["sky_days"] = st.session_state.get("sky_days", int(min(14, np.ceil(st.session_state["m_dur"]))))

r = sites.loc[st.session_state["m_site"]]
ui.banner("satellite_alt", f"Sky View — {r['name']}",
          f"{abs(r.lat_deg):.2f}° S, {r.lon_deg:.2f}° E · observer 2 m above the surface · LOLA terrain horizon to "
          "150 km · NASA/JPL SPICE positions")
toolbar = st.container(key="card_skyctl")
with toolbar:
    c = st.columns([1.5, 1.15, 1.15, 0.75, 1.25], vertical_alignment="bottom")
    site = c[0].selectbox("Site", ids, format_func=names.get, key="m_site")
    mode = c[1].segmented_control("Mode", ["Mission replay", "Now (UTC)"], default="Mission replay")
    if mode != "Now (UTC)":
        c[2].date_input("Start (UTC)", min_value=pd.Timestamp("2026-01-02").date(),
                        max_value=pd.Timestamp("2031-02-10").date(), key="m_date")
        c[3].number_input("Hour", 0, 23, key="m_hour")
        days = c[4].slider("Replay length (days)", 1, 14, key="sky_days")
        start = ui.mission_start()
    else:
        start, days = pd.Timestamp.now(tz="UTC").floor("h"), 2
        c[2].markdown(f"<div style='color:#C9D8E0;padding-bottom:8px'>Next 48 h from<br><b>{ui.doy(start)}</b></div>",
                      unsafe_allow_html=True)

r = sites.loc[site]
hp = ui.horizon(site)
ui.data_banners([site])
if hp is None or not live.kernels_available():
    st.error("Terrain or ephemeris data missing for this site.")
    st.stop()
end = start + pd.Timedelta(days=days)
w = live.fine_visibility(r, hp, start, end, visibility.VisParams(), step_min=60).reset_index(drop=True)
t = pd.DatetimeIndex(w.time_utc)
with toolbar:
    t_pick = st.select_slider("Selected time (UTC)", options=list(range(len(t))), value=0,
                              format_func=lambda i: f"{t[i]:%b %d %H:%M}")
idx = int(t_pick)
f0 = w.iloc[idx]


def next_change(col):
    v = w[col].to_numpy(bool)
    j = np.flatnonzero(v[idx:] != v[idx])
    if not len(j):
        return "No change before replay end"
    hrs = (t[idx + j[0]] - t[idx]).total_seconds() / 3600
    return f"{'Ends' if v[idx] else 'Starts'} in {hrs:.0f} h"


k = st.columns(4)
k[0].markdown(ui.kcard("wb_sunny", "Sun disc above terrain", f"{f0.sun_frac * 100:.0f}%",
                       f"El {f0.sun_el_deg:+.2f}° · terrain {f0.horizon_at_sun_deg:+.2f}°", ui.SUN),
              unsafe_allow_html=True)
k[1].markdown(ui.kcard("public", "Earth", "In view" if f0.earth_in_view else "Behind terrain",
                       f"El {f0.earth_el_deg:+.2f}° · terrain {f0.horizon_at_earth_deg:+.2f}°",
                       ui.EARTH if f0.earth_in_view else ui.GREY), unsafe_allow_html=True)
k[2].markdown(ui.kcard("light_mode", "Sunlight (power)", "ON" if f0.sunlit else "OFF", next_change("sunlit"),
                       ui.SUN if f0.sunlit else ui.GREY), unsafe_allow_html=True)
k[3].markdown(ui.kcard("cell_tower", "Potential DTE (geometric)", "ON" if f0.earth_in_view else "OFF",
                       next_change("earth_in_view"), ui.EARTH if f0.earth_in_view else ui.GREY), unsafe_allow_html=True)
st.markdown(f'<div style="color:#8FA4B0;font-size:0.82rem;margin:4px 0 8px 2px">At selected time '
            f'{ui.doy(t[idx])}. Move the time slider above, or press ▶ Play in the Panorama tab.</div>',
            unsafe_allow_html=True)

az = np.concatenate([hp.az_deg, [360.0]])
hz = np.concatenate([hp.horizon_el_deg, hp.horizon_el_deg[:1]])
ymin = float(min(np.nanmin(hz), w.sun_el_deg.min(), w.earth_el_deg.min())) - 2
ymax = float(max(np.nanmax(hz), w.sun_el_deg.max(), w.earth_el_deg.max())) + 3


def label(i):
    row = w.iloc[i]
    return (f"{t[i]:%Y-%m-%d %H:%M} UTC   ·   ☀️ {row.sun_frac * 100:.0f}% of Sun visible   ·   "
            f"🌍 Earth {'in view' if row.dte_visible else 'hidden'}")


def halo(row):
    return dict(size=30 if row.sunlit else 0, color="rgba(255,176,46,0.25)", line=dict(width=0))


def sun_marker(row):
    """Filled when sunlit, faded when only a sliver shows, hollow when fully behind terrain."""
    if row.sun_frac <= 0:
        return dict(size=16, symbol="circle-open", color=ui.SUN, line=dict(width=2.5), opacity=0.9)
    return dict(size=16, symbol="circle", color="#FFD36E", line=dict(color="white", width=1),
                opacity=1.0 if row.sunlit else 0.5)


def earth_marker(row):
    if not row.earth_in_view:
        return dict(size=20, symbol="circle-open", color=ui.EARTH, line=dict(width=2.5), opacity=0.9)
    return dict(size=20, symbol="circle", color=ui.EARTH, line=dict(color="white", width=1.5), opacity=1.0)


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
        sliders=[dict(active=idx, steps=steps, x=0.16, len=0.84, y=-0.05, pad=dict(t=0),
                      currentvalue=dict(visible=False), font=dict(color="#9AA4B8", size=9),
                      bgcolor=ui.BORDER, activebgcolor=ui.EARTH, tickcolor=ui.BORDER)])


col_plot, col_geo = st.columns([3.3, 1])
with col_plot:
    tab0, tab1, tab2, tab3 = st.tabs([":material/view_in_ar: 3D Observer View", ":material/play_circle: Panorama Replay",
                                      ":material/center_focus_strong: Telescope Close-Up",
                                      ":material/radar: All-Sky Chart"])

    # ------------------------------------------------------------------ 0. 3D observer view (real LOLA terrain)
    with tab0:
        exag = 3
        fig3 = ui.observer_3d(site, f0, hp, exag=float(exag), height=600)
        if fig3 is None:
            st.info("3D terrain tile not available for this site.")
        else:
            st.plotly_chart(fig3, width="stretch", config={"displaylogo": False, "scrollZoom": True,
                                                           "modeBarButtonsToRemove": ["toImage"]})
            st.caption("Drag to rotate, scroll to zoom. Real NASA LOLA terrain for 40 km around the station (heights ×3 "
                       "so the relief is visible). Lines point to the Sun and Earth at the selected time: solid = in "
                       "view, dashed grey = behind terrain. Visibility is computed with all terrain out to 150 km.")

    # ------------------------------------------------------------------ 1. panorama animation
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=az, y=hz, fill="tozeroy", mode="lines", name="Terrain (LOLA)", showlegend=False,
                                 line=dict(color="#9AA4B8", width=1.5), fillcolor="#2B3142", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[0, 360], y=[ymin, ymin], fill="tonexty", mode="lines", line=dict(width=0),
                                 fillcolor="#2B3142", showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=w.sun_az_deg, y=w.sun_el_deg, mode="markers", name="Sun path",
                                 marker=dict(size=3, color=ui.SUN, opacity=0.35), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=w.earth_az_deg, y=w.earth_el_deg, mode="markers", name="Earth path",
                                 marker=dict(size=3, color=ui.EARTH, opacity=0.45), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=[f0.sun_az_deg], y=[f0.sun_el_deg], mode="markers", name="Sun",
                                 marker=halo(f0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[f0.sun_az_deg], y=[f0.sun_el_deg], mode="markers", name="Sun",
                                 marker=sun_marker(f0)))
        fig.add_trace(go.Scatter(x=[f0.earth_az_deg], y=[f0.earth_el_deg], mode="markers", name="Earth",
                                 marker=earth_marker(f0)))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="Hollow = behind terrain",
                                 marker=dict(size=14, symbol="circle-open", color="#C9D8E0", line=dict(width=2))))
        frames = []
        for i in range(len(w)):
            row = w.iloc[i]
            frames.append(go.Frame(name=str(i), traces=[4, 5, 6], data=[
                go.Scatter(x=[row.sun_az_deg], y=[row.sun_el_deg], marker=halo(row)),
                go.Scatter(x=[row.sun_az_deg], y=[row.sun_el_deg], marker=sun_marker(row)),
                go.Scatter(x=[row.earth_az_deg], y=[row.earth_el_deg], marker=earth_marker(row))],
                layout=dict(title=dict(text=label(i)))))
        fig.frames = frames
        fig.update_xaxes(range=[0, 360], tickvals=[0, 45, 90, 135, 180, 225, 270, 315, 360],
                         ticktext=["N 0°", "NE", "E 90°", "SE", "S 180°", "SW", "W 270°", "NW", "N"], title=None)
        fig.update_yaxes(range=[ymin, ymax], title="Elevation (°)")
        fig = ui.style_fig(fig, 580)
        fig.update_layout(title=dict(text=label(idx), font=dict(size=13, color="#E6EAF2")), **play_controls(len(w)),
                          plot_bgcolor="#03050C", margin=dict(l=10, r=10, t=78, b=95),
                          legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"))
        fig.update_layout(title=dict(y=0.985, yref="container", x=0.01, xanchor="left"))
        st.plotly_chart(fig, width="stretch")

    # ------------------------------------------------------------------ 2. telescope close-up (true size)
    with tab2:
        body = st.segmented_control("Track", ["Earth", "Sun"], default="Earth", label_visibility="collapsed") or "Earth"
        key = "earth" if body == "Earth" else "sun"
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
        dx, dy = disc(idx)
        fig.add_trace(go.Scatter(x=dx, y=dy, fill="toself", mode="lines", fillcolor=col, line=dict(color="white", width=1),
                                 name=f"{body.split(' ')[-1]} (true angular size)"))
        ax_, hz_ = terrain_window(w.iloc[idx][f"{key}_az_deg"])
        fig.add_trace(go.Scatter(x=ax_, y=np.full_like(ax_, -30), mode="lines", line=dict(width=0),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=ax_, y=hz_, fill="tonexty", mode="lines", line=dict(color="#9AA4B8"),
                                 fillcolor="#2B3142", name="Terrain (drawn in front)", hoverinfo="skip"))
        frames = []
        for i in range(len(w)):
            cz = w.iloc[i][f"{key}_az_deg"]
            ax_, hz_ = terrain_window(cz)
            dx, dy = disc(i)
            ce = w.iloc[i][f"{key}_el_deg"]
            frames.append(go.Frame(name=str(i), traces=[0, 1, 2], data=[
                go.Scatter(x=dx, y=dy), go.Scatter(x=ax_, y=np.full_like(ax_, -30)), go.Scatter(x=ax_, y=hz_)],
                layout=dict(title=dict(text=label(i)), xaxis=dict(range=[cz - fov, cz + fov]),
                            yaxis=dict(range=[ce - fov * 0.55, ce + fov * 0.55]))))
        fig.frames = frames
        cz, ce = w.iloc[idx][f"{key}_az_deg"], w.iloc[idx][f"{key}_el_deg"]
        fig.update_xaxes(range=[cz - fov, cz + fov], title="Azimuth (°)")
        fig.update_yaxes(range=[ce - fov * 0.55, ce + fov * 0.55], title="Elevation (°)", scaleanchor="x", scaleratio=1)
        fig = ui.style_fig(fig, 580)
        fig.update_layout(title=dict(text=label(idx), font=dict(size=13, color="#E6EAF2")), **play_controls(len(w), 140),
                          plot_bgcolor="#03050C", margin=dict(l=10, r=10, t=78, b=95),
                          legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"))
        fig.update_layout(title=dict(y=0.985, yref="container", x=0.01, xanchor="left"))
        st.plotly_chart(fig, width="stretch")

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


with col_geo:
    with st.container(key="card_geo"):
        ui.card_title("explore", "Geometry", "at selected time")

        def row(icon, color, lab, val):
            return (f'<div class="rw"><span>{ui.mi(icon, 18, color)}{lab}</span><b>{val}</b></div>')

        crossing = next_change("sunlit").replace("Ends", "Sunset").replace("Starts", "Sunrise")
        st.markdown(
            '<div class="lln-st" style="border:none;background:none;padding:0">'
            + row("wb_sunny", ui.SUN, "Sun azimuth", f"{f0.sun_az_deg:.1f}°")
            + row("wb_sunny", ui.SUN, "Sun elevation", f"{f0.sun_el_deg:+.2f}°")
            + row("terrain", ui.SUN, "Sun clearance", f"{f0.sun_el_deg - f0.horizon_at_sun_deg:+.2f}°")
            + row("public", ui.EARTH, "Earth azimuth", f"{f0.earth_az_deg:.1f}°")
            + row("public", ui.EARTH, "Earth elevation", f"{f0.earth_el_deg:+.2f}°")
            + row("terrain", ui.EARTH, "Earth clearance", f"{f0.earth_el_deg - f0.horizon_at_earth_deg:+.2f}°")
            + row("event", ui.GREY, "Next Sun crossing", crossing.replace("No change", "None"))
            + '<div class="mut">Clearance = elevation above the terrain skyline in that direction. '
              'Negative = hidden.</div></div>', unsafe_allow_html=True)
    with st.expander("How to read this view", icon=":material/help:"):
        st.markdown("- **3D Observer View**: real LOLA terrain for 40 km around the station. Heights are shown ×3, and the Sun/Earth directions are scaled the same way, so the picture stays geometrically consistent.\n- **Panorama**: the full 360° skyline from LOLA terrain. Azimuth 0° = geographic north. "
                    "Symbols are enlarged; vertical scale is exaggerated (polar Sun angles are only a few degrees).\n"
                    "- **Telescope**: follows one body at its true angular size (Earth ≈ 1.9°, Sun ≈ 0.53°), with "
                    "terrain drawn in front, so you see exactly how much clears the skyline.\n"
                    "- **All-sky**: looking straight up; elevation increases toward the centre, tracks fade light → dark "
                    "over time.\n- Potential DTE here is geometric (Earth above terrain); DSN geometry is in "
                    "Mission Overview.")

ui.footer()
