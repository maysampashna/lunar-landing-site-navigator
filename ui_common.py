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
BG, PANEL, BORDER = "#06131F", "#0B1E2D", "#1C3A4A"
TEAL, AMBER = "#2DD4BF", "#F5A524"
SITE_COLORS = ["#B57BFF", "#4C8DFF", "#3DDC97", "#FFB02E", "#FF6B8B", "#4FD1C5", "#F6E05E", "#A0AEC0"]
DEFAULT_WEIGHTS = ScoreWeights()
R_MOON_KM = 1737.4

LIMITATIONS = ("Geometric line of sight only. Not assessed: landing hazards, slopes, thermal environment, RF link "
               "budget, antenna scheduling. Power/storage values are illustrative estimates, not a flight design. "
               "Surface-start shifts assume arrival moves by exactly the shift (sensitivity analysis, not a "
               "trajectory model). Sites are representative points, not NASA-designated landing sites. 8 of the 9 "
               "Artemis III regions are included: the USGS download for Mons Mouton Plateau failed during the event.")

CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,300,0,0" rel="stylesheet">
<style>
html, body, [class*="css"], .stMarkdown, .stText, button, input, label {{font-family: Inter, 'Segoe UI', Roboto, sans-serif;}}
.stApp {{background: radial-gradient(1200px 500px at 85% -10%, rgba(45,212,191,0.07), transparent 60%), {BG};}}
.block-container {{padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1560px;}}
section[data-testid="stSidebar"] {{background: linear-gradient(180deg, #071A28 0%, #06131F 100%); border-right: 1px solid {BORDER};}}
.material-symbols-outlined {{font-family:'Material Symbols Rounded','Material Symbols Outlined'; font-weight:400; font-style:normal; line-height:1;
   display:inline-block; vertical-align:middle; -webkit-font-feature-settings:'liga'; font-feature-settings:'liga';}}
/* page title banner (real LOLA terrain) */
.lln-banner {{position:relative; border-radius:16px; padding:22px 26px 18px 26px; margin-bottom:16px; overflow:hidden;
   background: linear-gradient(90deg, rgba(6,19,31,0.96) 0%, rgba(6,19,31,0.80) 45%, rgba(6,19,31,0.25) 100%), url("BANNER_URI");
   background-size: cover; background-position: center; border:1px solid {BORDER};}}
.lln-banner .row {{display:flex; align-items:center; gap:16px;}}
.lln-banner .ico {{width:52px; height:52px; border:1.5px solid {TEAL}; border-radius:12px; display:flex; align-items:center;
   justify-content:center; color:{TEAL}; background:rgba(45,212,191,0.06);}}
.lln-banner .ico .material-symbols-outlined {{font-size:30px;}}
.lln-banner h1 {{margin:0; font-size:2.35rem; font-weight:800; color:#F2F8FA; letter-spacing:-0.02em;}}
.lln-banner .sub {{color:#C2D3DC; font-size:1.0rem; margin-top:4px;}}
.lln-banner .bar {{width:74px; height:3px; background:{TEAL}; border-radius:3px; margin-top:12px; box-shadow:0 0 12px {TEAL};}}
.lln-pill {{display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:4px 12px; font-size:0.82rem; font-weight:600;}}
.lln-pill.ok {{background:rgba(61,220,151,0.10); color:#3DDC97; border:1px solid rgba(61,220,151,0.55);}}
.lln-pill.amber {{background:rgba(245,165,36,0.12); color:{AMBER}; border:1px solid rgba(245,165,36,0.65);}}
/* cards = keyed Streamlit containers */
[class*="st-key-card_"], [class*="st-key-amber_"] {{background: linear-gradient(160deg, rgba(14,40,56,0.92) 0%, rgba(9,27,40,0.92) 100%);
   border:1px solid rgba(45,212,191,0.38); border-radius:16px; padding:16px 18px !important;
   box-shadow: 0 0 0 1px rgba(45,212,191,0.05), 0 8px 30px rgba(0,0,0,0.35), inset 0 0 22px rgba(45,212,191,0.04);}}
[class*="st-key-amber_"] {{border-color: rgba(245,165,36,0.75); box-shadow: 0 0 18px rgba(245,165,36,0.12);}}
.lln-ct {{display:flex; align-items:center; gap:10px; font-size:1.18rem; font-weight:700; color:#F2F8FA; margin-bottom:6px;}}
.lln-ct .material-symbols-outlined {{color:{TEAL}; font-size:24px;}}
.lln-ct small {{color:#9FB4C0; font-weight:500; font-size:0.85rem;}}
/* KPI cards */
.lln-k {{display:flex; gap:14px; align-items:flex-start; border-radius:16px; padding:16px 18px; height:100%;
   background: linear-gradient(160deg, rgba(14,40,56,0.95), rgba(9,27,40,0.95)); border:1px solid rgba(45,212,191,0.45);}}
.lln-k.amber {{border-color: rgba(245,165,36,0.8);}}
.lln-k .ib {{min-width:46px; height:46px; border-radius:12px; display:flex; align-items:center; justify-content:center;
   border:1.5px solid currentColor;}}
.lln-k .ib .material-symbols-outlined {{font-size:26px;}}
.lln-k .lb {{font-weight:700; color:#E6F1F5; font-size:0.98rem;}}
.lln-k .vl {{font-weight:800; font-size:1.55rem; line-height:1.25;}}
.lln-k .sb {{color:#B5C7D1; font-size:0.84rem;}}
.lln-k.sm {{padding:10px 12px; gap:10px;}}
.lln-k.sm .ib {{min-width:36px; height:36px; border-radius:10px;}}
.lln-k.sm .ib .material-symbols-outlined {{font-size:21px;}}
.lln-k.sm .lb {{font-size:0.84rem;}}
.lln-k.sm .vl {{font-size:1.2rem; white-space:nowrap;}}
.lln-k.sm .sb {{font-size:0.76rem;}}
.lln-kpi {{flex:1; background:{PANEL}; border:1px solid {BORDER}; border-radius:14px; padding:14px 16px;}}
.lln-kpi .lbl {{color:#9FB4C0; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.06em;}}
.lln-kpi .val {{font-size:1.55rem; font-weight:700; margin-top:2px;}}
.lln-kpi .sub {{color:#9FB4C0; font-size:0.8rem;}}
.lln-chip {{display:inline-block; padding:3px 11px; border-radius:999px; font-size:0.76rem; font-weight:700; letter-spacing:0.02em;}}
/* tables */
.lln-table {{width:100%; border-collapse:separate; border-spacing:0 4px; font-size:0.88rem;}}
.lln-table th {{text-align:left; color:#C9D8E0; font-weight:600; padding:6px 8px; border-bottom:1px solid {BORDER};}}
.lln-table td {{padding:6px 8px; background:rgba(255,255,255,0.015);}}
.lln-table td, .lln-table th {{white-space:nowrap;}}
.lln-table tr.top td {{background:rgba(45,212,191,0.10); border-top:1px solid {TEAL}; border-bottom:1px solid {TEAL};}}
.lln-table tr.top td:first-child {{border-left:1px solid {TEAL}; border-radius:8px 0 0 8px;}}
.lln-table tr.top td:last-child {{border-right:1px solid {TEAL}; border-radius:0 8px 8px 0;}}
.lln-pv {{display:inline-block; min-width:44px; text-align:center; padding:2px 8px; border-radius:999px; font-weight:700;
   font-size:0.8rem; background:rgba(45,212,191,0.12); color:#7FF0DD; border:1px solid rgba(45,212,191,0.35);}}
.lln-bar {{display:inline-block; height:8px; border-radius:6px; background:linear-gradient(90deg,#2F80ED,#4C8DFF); vertical-align:middle;}}
.lln-dot {{display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px;}}
/* station cards */
.lln-st {{background: linear-gradient(160deg, rgba(14,40,56,0.95), rgba(9,27,40,0.95)); border:1px solid rgba(45,212,191,0.45);
   border-radius:16px; padding:14px 16px; margin-bottom:10px;}}
.lln-st .hd {{display:flex; gap:12px; align-items:center; margin-bottom:10px;}}
.lln-st .hd .ib {{width:48px; height:48px; border-radius:12px; border:1.5px solid rgba(45,212,191,0.6); color:{TEAL};
   display:flex; align-items:center; justify-content:center;}}
.lln-st .nm {{font-weight:800; font-size:1.08rem; color:#F2F8FA; margin-bottom:4px;}}
.lln-st .rw {{display:flex; justify-content:space-between; align-items:center; font-size:0.9rem; padding:4px 0; color:#C9D8E0;}}
.lln-st .rw b {{color:#F2F8FA; font-size:0.98rem;}}
.lln-st .rw .material-symbols-outlined {{font-size:19px; margin-right:8px;}}
.lln-st .mut {{color:#7F95A2; font-size:0.76rem; margin-top:6px;}}
/* summary bar */
.lln-sum {{display:flex; border:1px solid rgba(245,165,36,0.75); border-radius:16px; padding:14px 8px;
   background: linear-gradient(160deg, rgba(14,40,56,0.95), rgba(9,27,40,0.95)); box-shadow: 0 0 18px rgba(245,165,36,0.10);}}
.lln-sum > div {{flex:1; display:flex; gap:14px; align-items:center; padding:2px 18px; border-right:1px solid {BORDER};}}
.lln-sum > div:last-child {{border-right:none;}}
.lln-sum .material-symbols-outlined {{font-size:38px; color:{AMBER};}}
.lln-sum .lb {{color:#E6F1F5; font-weight:600; font-size:0.95rem;}}
.lln-sum .vl {{font-weight:800; font-size:1.5rem; color:#F2F8FA;}}
.lln-sum .sb {{color:#B5C7D1; font-size:0.84rem;}}
/* clock + events */
.lln-clock {{font-family:'JetBrains Mono','Cascadia Mono',Consolas,monospace; font-size:clamp(1.3rem, 2.1vw, 2.15rem); font-weight:700; white-space:nowrap;
   color:#F2F8FA; letter-spacing:0.02em; line-height:1.1;}}
.lln-clock-sub {{font-family:'JetBrains Mono','Cascadia Mono',Consolas,monospace; color:#9FB4C0; font-size:0.82rem;}}
.lln-ev {{font-family:'JetBrains Mono','Cascadia Mono',Consolas,monospace; font-size:0.84rem; color:#DCE7EC;
   display:flex; gap:12px; align-items:center; padding:6px 2px; border-bottom:1px solid #15303F;}}
.lln-ev .d {{width:9px; height:9px; border-radius:50%;}}
.lln-ev .tm {{color:#E6F1F5; min-width:88px;}}
.lln-ev .tg {{margin-left:auto; color:#7F95A2;}}
.lln-sec {{display:flex; align-items:center; gap:10px; font-size:1.2rem; font-weight:700; margin:20px 0 10px 0; color:#F2F8FA;}}
.lln-sec .material-symbols-outlined {{color:{TEAL};}}
.lln-sec span.s {{color:#9FB4C0; font-weight:500; font-size:0.85rem;}}
.lln-rec {{background:linear-gradient(135deg, #0F2A22 0%, #10241E 100%); border:1px solid #2F7A5B; border-radius:16px; padding:16px 20px;}}
.lln-rec h4 {{margin:0 0 6px 0; color:#3DDC97;}}
.lln-warn {{background:#2A1F0F; border:1px solid #8A5A1F; border-radius:16px; padding:14px 18px;}}
.lln-demo {{background:#2A0F18; border:1px solid #8A1F3A; border-radius:16px; padding:14px 18px;}}
.lln-badge {{display:inline-flex; align-items:center; gap:6px; background:rgba(61,220,151,0.10); border:1px solid rgba(61,220,151,0.55);
   color:#3DDC97; border-radius:999px; padding:4px 12px; font-size:0.82rem; font-weight:600;}}
.lln-foot {{color:#6F8592; font-size:0.76rem; margin-top:22px;}}
.lln-mode h3 {{margin:0; font-size:1.55rem; font-weight:800; color:#F2F8FA;}}
.lln-mode p {{color:#C9D8E0; font-size:1.0rem;}}
.lln-mode .it {{display:flex; align-items:center; gap:12px; color:#E6F1F5; padding:5px 0; font-size:0.98rem;}}
.lln-mode .it .material-symbols-outlined {{color:{TEAL}; font-size:24px;}}
[class*="st-key-amber_"] .lln-mode .it .material-symbols-outlined {{color:{AMBER};}}
div[data-testid="stPageLink"] a {{border:1px solid rgba(45,212,191,0.6); border-radius:12px; justify-content:center; padding:8px 12px;}}
[class*="st-key-amber_"] div[data-testid="stPageLink"] a {{border-color: rgba(245,165,36,0.85);}}
.stTabs [data-baseweb="tab"] {{border:1px solid {BORDER}; border-radius:10px; padding:6px 16px; margin-right:6px; background:{PANEL};}}
.stTabs [aria-selected="true"] {{border-color:{TEAL} !important; background:rgba(45,212,191,0.12) !important;}}
</style>
"""

def _data_uri(path: Path, mime: str) -> str:
    import base64
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def setup_page(title: str = "", icon: str = ""):
    """Inject theme CSS (page config is set once in app.py)."""
    st.markdown(CSS.replace("BANNER_URI", _data_uri(ROOT / "assets" / "banner.jpg", "image/jpeg")),
                unsafe_allow_html=True)


def mi(name: str, size: int | None = None, color: str | None = None) -> str:
    style = (f"font-size:{size}px;" if size else "") + (f"color:{color};" if color else "")
    return f'<span class="material-symbols-outlined" style="{style}">{name}</span>'


def banner(icon: str, title: str, subtitle: str, pills: str = ""):
    st.markdown(f'<div class="lln-banner">{("<div style=margin-bottom:10px>" + pills + "</div>") if pills else ""}'
                f'<div class="row"><div class="ico">{mi(icon)}</div><div><h1>{title}</h1>'
                f'<div class="sub">{subtitle}</div></div></div><div class="bar"></div></div>', unsafe_allow_html=True)


def card_title(icon: str, text: str, small: str = ""):
    st.markdown(f'<div class="lln-ct">{mi(icon)}<span>{text}</span>{"<small>" + small + "</small>" if small else ""}</div>',
                unsafe_allow_html=True)


def kcard(icon: str, label: str, value: str, sub: str = "", color: str = TEAL, amber: bool = False,
          small: bool = False) -> str:
    return (f'<div class="lln-k{" amber" if amber else ""}{" sm" if small else ""}"><div class="ib" style="color:{color}">{mi(icon)}</div>'
            f'<div><div class="lb">{label}</div><div class="vl" style="color:{color}">{value}</div>'
            f'<div class="sb">{sub}</div></div></div>')


def validated_pill() -> str:
    v = validation_report()
    return (f'<span class="lln-pill ok">{mi("check", 18)} Ephemeris validated vs JPL Horizons · max error '
            f'{v["overall_max_error_deg"]:.5f}°</span>' if v else "")


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


def weights_sidebar(expander: bool = True) -> ScoreWeights:
    import contextlib
    ctx = st.expander("⚖️ Score weights (your preferences)") if expander else contextlib.nullcontext()
    with ctx:
        w = ScoreWeights(st.slider("Weight: power (sunlight)", 0.0, 1.0, DEFAULT_WEIGHTS.w_sun),
                         st.slider("Weight: communication", 0.0, 1.0, DEFAULT_WEIGHTS.w_dte),
                         st.slider("Weight: both at once", 0.0, 1.0, DEFAULT_WEIGHTS.w_both),
                         st.slider("Penalty: longest dark gap", 0.0, 0.5, DEFAULT_WEIGHTS.w_gap_dark),
                         st.slider("Penalty: longest no-comm gap", 0.0, 0.5, DEFAULT_WEIGHTS.w_gap_dte))
        if not w.is_valid():
            st.warning("Power, communication and both cannot all be zero — using the default weights.")
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


STATUS = {  # (label, colour)
    "available": ("STATION AVAILABLE", "#3DDC97"),
    "power": ("POWER ONLY · NO COMM", "#FFB02E"),
    "comm": ("COMM ONLY · ON BATTERY", "#4C8DFF"),
    "none": ("UNAVAILABLE", "#FF6B8B"),
}


def status_of(sunlit: bool, comm: bool) -> str:
    return "available" if sunlit and comm else "power" if sunlit else "comm" if comm else "none"


def doy(t: pd.Timestamp) -> str:
    """NASA-style UTC day-of-year time tag, e.g. 2027-228T18:30:00Z"""
    return f"{t:%Y-%j}T{t:%H:%M:%S}Z"


def tminus(t: pd.Timestamp, now: pd.Timestamp) -> str:
    """Compact countdown like T+07:40 or T+1d 07:40."""
    m = int(round((t - now).total_seconds() / 60))
    d, rem = divmod(abs(m), 1440)
    return f"T{'+' if m >= 0 else '-'}{str(d) + 'd ' if d else ''}{rem // 60:02d}:{rem % 60:02d}"


def met(t: pd.Timestamp, t0: pd.Timestamp) -> str:
    s = int((t - t0).total_seconds())
    sign = "+" if s >= 0 else "-"
    s = abs(s)
    return f"T{sign}{s // 86400}d {s % 86400 // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def south_pole_map(site_ids, scores: dict | None = None, height: int = 520, highlight: str | None = None,
                   status: dict | None = None):
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
        if status is not None and sid in status:
            lab, col = STATUS[status[sid]]
            labels.append(f"{r['name']}")
        else:
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
    fig.update_xaxes(range=[cx - span / 2, cx + span / 2], visible=False, fixedrange=True, constrain="domain")
    fig.update_yaxes(range=[cy - span / 2, cy + span / 2], visible=False, scaleanchor="x", scaleratio=1,
                     fixedrange=True, constrain="domain")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      dragmode=False)
    return fig


FONT = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def style_fig(fig, height=360, title=None):
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#C9D1E3", family=FONT, size=13),
                      title=dict(text=title, font=dict(size=16, color="#E6EAF2", family=FONT)) if title else None,
                      hoverlabel=dict(bgcolor="#0F1628", bordercolor=BORDER, font=dict(family=FONT, size=12)),
                      margin=dict(l=10, r=10, t=40 if title else 10, b=10),
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
