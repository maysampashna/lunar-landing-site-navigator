"""Shared UI helpers: theme, cards, ratings, data loaders, south-pole map."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

from engine import data, visibility
from engine.metrics import ScoreWeights

ROOT = Path(__file__).resolve().parent
SUN, EARTH, BOTH, GREY = "#FFB02E", "#4C8DFF", "#3DDC97", "#8A93A6"
BG, PANEL, BORDER = "#0A0F1E", "#121A2E", "#243049"
SITE_COLORS = ["#B57BFF", "#4C8DFF", "#3DDC97", "#FFB02E", "#FF6B8B", "#4FD1C5", "#F6E05E", "#A0AEC0"]
DEFAULT_WEIGHTS = ScoreWeights()
R_MOON_KM = 1737.4

LIMITATIONS = ("Geometric line of sight only. Not assessed: landing hazards, slopes, thermal environment, RF link "
               "budget, antenna scheduling. Power/storage values are illustrative estimates, not a flight design. "
               "Surface-start shifts assume arrival moves by exactly the shift (sensitivity analysis, not a "
               "trajectory model). Sites are representative points, not NASA-designated landing sites. 8 of the 9 "
               "Artemis III regions are included: the USGS download for Mons Mouton Plateau failed during the event.")

CSS = f"""
<style>
.block-container {{padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1500px;}}
h1, h2, h3 {{letter-spacing: -0.01em;}}
.lln-hero {{display:flex; align-items:center; gap:14px; margin-bottom:4px;}}
.lln-hero h1 {{margin:0; font-size:2.0rem;}}
.lln-sub {{color:#9AA4B8; font-size:0.92rem; margin-bottom:14px;}}
.lln-card {{background:{PANEL}; border:1px solid {BORDER}; border-radius:14px; padding:16px 18px; height:100%;}}
.lln-card h4 {{margin:0 0 10px 0; font-size:1.02rem; color:#E6EAF2;}}
.lln-kpi {{background:{PANEL}; border:1px solid {BORDER}; border-radius:14px; padding:14px 16px;}}
.lln-kpi .lbl {{color:#9AA4B8; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.06em;}}
.lln-kpi .val {{font-size:1.55rem; font-weight:700; margin-top:2px;}}
.lln-kpi .sub {{color:#9AA4B8; font-size:0.8rem;}}
.lln-chip {{display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:700;}}
.lln-table {{width:100%; border-collapse:collapse; font-size:0.9rem;}}
.lln-table th {{text-align:left; color:#9AA4B8; font-weight:600; padding:6px 8px; border-bottom:1px solid {BORDER};}}
.lln-table td {{padding:7px 8px; border-bottom:1px solid #1B2440;}}
.lln-table td:first-child {{white-space:nowrap;}}
.lln-dot {{display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px;}}
.lln-rec {{background:linear-gradient(135deg, #0F2A22 0%, #10241E 100%); border:1px solid #2F7A5B; border-radius:14px;
           padding:16px 20px;}}
.lln-rec h4 {{margin:0 0 6px 0; color:#3DDC97;}}
.lln-warn {{background:#2A1F0F; border:1px solid #8A5A1F; border-radius:14px; padding:14px 18px;}}
.lln-demo {{background:#2A0F18; border:1px solid #8A1F3A; border-radius:14px; padding:14px 18px;}}
.lln-badge {{display:inline-flex; align-items:center; gap:6px; background:#0F2A22; border:1px solid #2F7A5B;
             color:#3DDC97; border-radius:999px; padding:3px 12px; font-size:0.8rem; font-weight:600;}}
.lln-foot {{color:#7D879C; font-size:0.78rem; margin-top:18px;}}
</style>
"""


def setup_page(title: str, icon: str = "🌘"):
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


def rating(score: float) -> tuple[str, str]:
    if score >= 90:
        return "Excellent", "#3DDC97"
    if score >= 70:
        return "Good", "#4C8DFF"
    if score >= 40:
        return "Fair", "#FFB02E"
    return "Poor", "#FF6B8B"


def chip(text: str, color: str) -> str:
    return f'<span class="lln-chip" style="background:{color}22;color:{color};border:1px solid {color}66">{text}</span>'


def kpi(label: str, value: str, sub: str = "", color: str = "#E6EAF2") -> str:
    return (f'<div class="lln-kpi"><div class="lbl">{label}</div>'
            f'<div class="val" style="color:{color}">{value}</div><div class="sub">{sub}</div></div>')


@st.cache_data
def sites_df() -> pd.DataFrame:
    return data.load_sites()


@st.cache_data
def ephem(site_id: str) -> pd.DataFrame:
    return data.load_ephem(site_id)


def horizon(site_id: str):
    return data.load_horizon(site_id)


def terrain_status(site_id: str) -> str:
    if data.load_horizon(site_id) is None:
        return "missing"
    return "synthetic" if data.is_synthetic(site_id) else "real"


def names() -> dict[str, str]:
    s = sites_df()
    return dict(zip(s.site_id, s.name))


def site_color(site_id: str) -> str:
    ids = list(sites_df().site_id)
    return SITE_COLORS[ids.index(site_id) % len(SITE_COLORS)] if site_id in ids else GREY


@st.cache_data
def hourly_vis(site_id: str, thr: float, mask: float, area: float, eff: float, load: float) -> pd.DataFrame:
    from engine.power import PowerParams
    p = visibility.VisParams(sunlit_threshold=thr, earth_mask_deg=mask,
                             power=PowerParams(array_area_m2=area, efficiency=eff, load_w=load))
    return visibility.compute(ephem(site_id), horizon(site_id), p)


def data_banners(site_ids) -> dict[str, list[str]]:
    nm = names()
    s = sites_df().set_index("site_id")
    out = {"synthetic": [], "missing": [], "provisional": []}
    for sid in site_ids:
        st_ = terrain_status(sid)
        if st_ != "real":
            out[st_].append(nm[sid])
        if str(s.loc[sid, "provisional"]).lower() == "true":
            out["provisional"].append(nm[sid])
    if out["synthetic"] or out["missing"]:
        st.markdown('<div class="lln-demo">🧪 <b>Demonstration results — not a recommendation.</b> '
                    + (f"Synthetic terrain: {', '.join(out['synthetic'])}. " if out["synthetic"] else "")
                    + (f"No terrain data: {', '.join(out['missing'])}. " if out["missing"] else "")
                    + "Confident rankings require real LOLA terrain horizons.</div>", unsafe_allow_html=True)
    if out["provisional"]:
        st.warning(f"Provisional site coordinates: {', '.join(out['provisional'])}")
    return out


def validation_report() -> dict | None:
    p = ROOT / "data" / "validation.json"
    return json.loads(p.read_text()) if p.exists() else None


def weights_sidebar() -> ScoreWeights:
    with st.expander("⚖️ Score weights (your preferences)"):
        w = ScoreWeights(st.slider("Sunlight", 0.0, 1.0, DEFAULT_WEIGHTS.w_sun),
                         st.slider("Earth visibility", 0.0, 1.0, DEFAULT_WEIGHTS.w_dte),
                         st.slider("Both at once", 0.0, 1.0, DEFAULT_WEIGHTS.w_both),
                         st.slider("Penalty: longest dark gap", 0.0, 0.5, DEFAULT_WEIGHTS.w_gap_dark),
                         st.slider("Penalty: longest no-Earth gap", 0.0, 0.5, DEFAULT_WEIGHTS.w_gap_dte))
        if not w.is_valid():
            st.warning("Sunlight, Earth visibility and Both cannot all be zero — using the default weights.")
            w = DEFAULT_WEIGHTS
        st.caption("Positive weights are rescaled to sum to 1. The score is a preference calculation, "
                   "not a safety rating.")
    return w


# ------------------------------------------------------------------ south-pole map
def polar_xy_km(lat_deg, lon_deg):
    """South-polar stereographic (true scale at the pole, R = 1737.4 km) — same projection as the LOLA DEMs."""
    rho = 2 * R_MOON_KM * np.tan(np.radians((90 + np.asarray(lat_deg, float)) / 2))
    lon = np.radians(np.asarray(lon_deg, float))
    return rho * np.sin(lon), rho * np.cos(lon)


@st.cache_data
def _basemap():
    meta = json.loads((ROOT / "data" / "basemap_hill.json").read_text())
    return Image.open(ROOT / "data" / "basemap_hill.png"), meta


def south_pole_map(site_ids, scores: dict | None = None, height: int = 520, highlight: str | None = None):
    img, m = _basemap()
    s = sites_df().set_index("site_id")
    fig = go.Figure()
    fig.add_layout_image(dict(source=img, xref="x", yref="y", x=m["x0_km"], y=m["y1_km"],
                              sizex=m["x1_km"] - m["x0_km"], sizey=m["y1_km"] - m["y0_km"],
                              sizing="stretch", layer="below", opacity=0.95))
    # latitude rings + meridians
    t = np.linspace(0, 2 * np.pi, 361)
    for lat in (-89, -88, -86, -84):
        rho = polar_xy_km(lat, 0)[1]
        fig.add_trace(go.Scatter(x=rho * np.sin(t), y=rho * np.cos(t), mode="lines", hoverinfo="skip",
                                 line=dict(color="rgba(255,255,255,0.45)", width=1.2, dash="dot"), showlegend=False))
        fig.add_annotation(x=rho * 0.7071, y=-rho * 0.7071, text=f"{abs(lat)}°S", showarrow=False,
                           font=dict(size=11, color="rgba(255,255,255,0.85)"), bgcolor="rgba(10,15,30,0.6)")
    for lon, lab in ((0, "0°"), (90, "90°E"), (180, "180°"), (-90, "90°W")):
        x, y = polar_xy_km(-83.2, lon)
        fig.add_trace(go.Scatter(x=[0, x], y=[0, y], mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color="rgba(255,255,255,0.15)", width=1)))
        fig.add_annotation(x=x * 1.03, y=y * 1.03, text=lab, showarrow=False, font=dict(size=10, color="#C9D1E3"))
    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers+text", text=["South Pole"], textposition="bottom center",
                             marker=dict(symbol="cross-thin", size=14, line=dict(color="white", width=2)),
                             textfont=dict(color="white", size=11), hoverinfo="skip", showlegend=False))
    ids = [i for i in site_ids if i in s.index]
    x, y = polar_xy_km(s.loc[ids, "lat_deg"].values, s.loc[ids, "lon_deg"].values)
    labels, colors, hover, sizes = [], [], [], []
    for sid in ids:
        r = s.loc[sid]
        sc = None if scores is None else scores.get(sid)
        lab, col = rating(sc) if sc is not None else ("", site_color(sid))
        labels.append(f"{r['name']}" + (f" · {sc:.0f}" if sc is not None else ""))
        colors.append(col)
        sizes.append(22 if sid == highlight else 15)
        hover.append(f"<b>{r['name']}</b><br>{abs(r.lat_deg):.2f}°S, {r.lon_deg:.2f}°E<br>"
                     f"surface {float(r.height_m)/1000:.2f} km" + (f"<br>score {sc:.0f} ({lab})" if sc is not None else ""))
    fig.add_trace(go.Scatter(x=x, y=y, mode="markers", hovertext=hover, hoverinfo="text",
                             marker=dict(size=sizes, color=colors, line=dict(color="white", width=2),
                                         symbol="diamond"), showlegend=False))
    for xi, yi, lab_, col_ in zip(x, y, labels, colors):
        fig.add_annotation(x=xi, y=yi, text=f"<b>{lab_}</b>", showarrow=False, yshift=20,
                           font=dict(color="white", size=13), bgcolor="rgba(10,15,30,0.78)",
                           bordercolor=col_, borderwidth=1.5, borderpad=3)
    pad = 45
    xr = [min(x.min(), 0) - pad, max(x.max(), 0) + pad]
    yr = [min(y.min(), 0) - pad, max(y.max(), 0) + pad]
    span = max(xr[1] - xr[0], yr[1] - yr[0])
    cx, cy = np.mean(xr), np.mean(yr)
    # scale bar 50 km
    bx, by = cx - span / 2 + 18, cy - span / 2 + 14
    fig.add_shape(type="line", x0=bx, x1=bx + 50, y0=by, y1=by, line=dict(color="white", width=3))
    fig.add_annotation(x=bx + 25, y=by, text="50 km", showarrow=False, yshift=10, font=dict(color="white", size=11))
    fig.update_xaxes(range=[cx - span / 2, cx + span / 2], visible=False)
    fig.update_yaxes(range=[cy - span / 2, cy + span / 2], visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=BG, plot_bgcolor="black",
                      dragmode="pan")
    return fig


def style_fig(fig, height=360, title=None):
    fig.update_layout(height=height, paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color="#C9D1E3"),
                      margin=dict(l=10, r=10, t=40 if title else 10, b=10), title=title,
                      legend=dict(orientation="h", yanchor="top", y=-0.12, x=0))
    if title:
        fig.update_layout(margin=dict(l=10, r=10, t=44, b=60))
    fig.update_xaxes(gridcolor="#1E2742", zerolinecolor="#2A3556")
    fig.update_yaxes(gridcolor="#1E2742", zerolinecolor="#2A3556")
    return fig


def footer():
    st.markdown(f'<div class="lln-foot">{LIMITATIONS}<br>Data: NASA/JPL NAIF SPICE · NASA GSFC LOLA DEMs · '
                'USGS Artemis III region grids · validated against JPL Horizons. Team Bulldogs Beyond Earth · '
                'NASA Space Apps 2026.</div>', unsafe_allow_html=True)
