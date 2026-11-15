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
SUN, EARTH, BOTH, GREY = "#FFB02E", "#38BDF8", "#3DDC97", "#8A93A6"   # amber = Sun/power, cyan = Earth/comms
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
.block-container {{padding-top: 4.4rem !important; padding-bottom: 1.5rem !important; max-width: 1480px; margin: 0 auto;}}
[data-testid="stWidgetLabel"] p {{font-size: 0.92rem; color:#C9D8E0;}}
[data-testid="stExpander"] summary p {{font-size: 0.95rem; font-weight:600;}}
[data-testid="stCaptionContainer"] {{font-size: 0.86rem; color:#9FB4C0;}}
section[data-testid="stSidebar"] {{background: linear-gradient(180deg, #071A28 0%, #06131F 100%); border-right: 1px solid {BORDER};}}
.material-symbols-outlined {{font-family:'Material Symbols Rounded','Material Symbols Outlined'; font-weight:400; font-style:normal; line-height:1;
   display:inline-block; vertical-align:middle; -webkit-font-feature-settings:'liga'; font-feature-settings:'liga';}}
/* page title banner (real LOLA terrain) */
.lln-banner {{position:relative; border-radius:14px; padding:14px 22px 12px 22px; margin-bottom:12px; overflow:hidden;
   background: linear-gradient(90deg, rgba(6,19,31,0.97) 0%, rgba(6,19,31,0.88) 50%, rgba(6,19,31,0.55) 100%), url("BANNER_URI");
   background-size: cover; background-position: center; border:1px solid {BORDER};}}
.lln-banner .row {{display:flex; align-items:center; gap:16px;}}
.lln-banner .ico {{width:44px; height:44px; border:1.5px solid {TEAL}; border-radius:12px; display:flex; align-items:center;
   justify-content:center; color:{TEAL}; background:rgba(45,212,191,0.06);}}
.lln-banner .ico .material-symbols-outlined {{font-size:26px;}}
.lln-banner h1 {{margin:0; padding:0; font-size:1.9rem; font-weight:800; color:#F2F8FA; letter-spacing:-0.02em;}}
.lln-banner .sub {{color:#C2D3DC; font-size:0.98rem; margin-top:2px;}}
.lln-banner .bar {{display:none;}}
.lln-pill {{display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:4px 12px; font-size:0.82rem; font-weight:600;}}
.lln-pill.ok {{background:rgba(61,220,151,0.10); color:#3DDC97; border:1px solid rgba(61,220,151,0.55);}}
.lln-pill.amber {{background:rgba(245,165,36,0.12); color:{AMBER}; border:1px solid rgba(245,165,36,0.65);}}
/* cards = keyed Streamlit containers */
[class*="st-key-card_"], [class*="st-key-amber_"] {{background: linear-gradient(160deg, rgba(14,40,56,0.92) 0%, rgba(9,27,40,0.92) 100%);
   border:1px solid rgba(45,212,191,0.28); border-radius:14px; padding:14px 16px !important;
   box-shadow: 0 6px 20px rgba(0,0,0,0.30);}}
[class*="st-key-amber_"] {{border-color: rgba(245,165,36,0.65);}}
.lln-ct {{display:flex; align-items:center; gap:10px; font-size:1.08rem; font-weight:700; color:#F2F8FA; margin-bottom:6px;}}
.lln-ct .material-symbols-outlined {{color:{TEAL}; font-size:22px;}}
.lln-ct small {{color:#9FB4C0; font-weight:500; font-size:0.85rem;}}
/* KPI cards */
.lln-k {{display:flex; gap:12px; align-items:flex-start; border-radius:14px; padding:12px 14px; height:100%;
   background: linear-gradient(160deg, rgba(14,40,56,0.95), rgba(9,27,40,0.95)); border:1px solid rgba(45,212,191,0.30);}}
.lln-k.amber {{border-color: rgba(245,165,36,0.65);}}
.lln-k .ib {{min-width:40px; height:40px; border-radius:12px; display:flex; align-items:center; justify-content:center;
   border:1.5px solid currentColor;}}
.lln-k .ib .material-symbols-outlined {{font-size:23px;}}
.lln-k .lb {{font-weight:700; color:#E6F1F5; font-size:0.98rem;}}
.lln-k .vl {{font-weight:800; font-size:1.4rem; line-height:1.25;}}
.lln-k .sb {{color:#B5C7D1; font-size:0.86rem;}}
.lln-k.sm {{padding:10px 12px; gap:10px; flex:1 1 0; min-width:0;}}
.lln-k.sm .vl, .lln-k.sm .sb {{overflow:hidden; text-overflow:ellipsis;}}
.lln-k.sm .ib {{min-width:36px; height:36px; border-radius:10px;}}
.lln-k.sm .ib .material-symbols-outlined {{font-size:21px;}}
.lln-k.sm .lb {{font-size:0.84rem;}}
.lln-k.sm .vl {{font-size:1.2rem; white-space:nowrap;}}
.lln-k.sm .sb {{font-size:0.8rem;}}
.lln-kpi {{flex:1; background:{PANEL}; border:1px solid {BORDER}; border-radius:14px; padding:14px 16px;}}
.lln-kpi .lbl {{color:#9FB4C0; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.06em;}}
.lln-kpi .val {{font-size:1.55rem; font-weight:700; margin-top:2px;}}
.lln-kpi .sub {{color:#9FB4C0; font-size:0.8rem;}}
.lln-chip {{display:inline-block; padding:3px 11px; border-radius:999px; font-size:0.76rem; font-weight:700; letter-spacing:0.02em;}}
/* tables */
.lln-table {{width:100%; border-collapse:separate; border-spacing:0 3px; font-size:0.93rem; font-variant-numeric: tabular-nums;}}
.lln-table th {{text-align:left; color:#9FB4C0; font-weight:600; font-size:0.8rem; padding:6px 8px; border-bottom:1px solid {BORDER};}}
.lln-table th[title] {{cursor:help; text-decoration: underline dotted #4A6474;}}
.lln-table td.n, .lln-table th.n {{text-align:right;}}
.lln-table tr.tie td {{background:rgba(45,212,191,0.05);}}
.lln-table td {{padding:6px 8px; background:rgba(255,255,255,0.015); color:#E6F1F5;}}
.lln-table td, .lln-table th {{white-space:nowrap;}}
.lln-table tr.top td {{background:rgba(45,212,191,0.10); border-top:1px solid {TEAL}; border-bottom:1px solid {TEAL};}}
.lln-table tr.top td:first-child {{border-left:1px solid {TEAL}; border-radius:8px 0 0 8px;}}
.lln-table tr.top td:last-child {{border-right:1px solid {TEAL}; border-radius:0 8px 8px 0;}}
.lln-pv {{display:inline-block; min-width:44px; text-align:center; padding:2px 8px; border-radius:999px; font-weight:700;
   font-size:0.8rem; background:rgba(45,212,191,0.12); color:#7FF0DD; border:1px solid rgba(45,212,191,0.35);}}
.lln-bar {{display:inline-block; height:8px; border-radius:6px; background:linear-gradient(90deg,#2F80ED,#4C8DFF); vertical-align:middle;}}
.lln-dot {{display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px;}}
/* station cards */
.lln-st {{background: linear-gradient(160deg, rgba(14,40,56,0.95), rgba(9,27,40,0.95)); border:1px solid rgba(45,212,191,0.30);
   border-radius:14px; padding:12px 14px; margin-bottom:8px;}}
.lln-st .hd {{display:flex; gap:10px; align-items:center; margin-bottom:6px;}}
.lln-st .hd .ib {{width:38px; height:38px; border-radius:12px; border:1.5px solid rgba(45,212,191,0.6); color:{TEAL};
   display:flex; align-items:center; justify-content:center;}}
.lln-st .nm {{font-weight:800; font-size:1.02rem; color:#F2F8FA; margin-bottom:4px;}}
.lln-st .rw {{display:flex; justify-content:space-between; align-items:center; font-size:0.9rem; padding:3px 0; color:#C9D8E0;}}
.lln-st .rw b {{color:#F2F8FA; font-size:0.98rem;}}
.lln-st .rw .material-symbols-outlined {{font-size:19px; margin-right:8px;}}
.lln-st .mut {{color:#8FA4B0; font-size:0.8rem; margin-top:4px;}}
.lln-st.focus {{border-color:rgba(245,165,36,0.8);}}
/* summary bar */
.lln-sum {{display:flex; border:1px solid {BORDER}; border-radius:14px; padding:12px 8px;
   background: linear-gradient(160deg, rgba(14,40,56,0.95), rgba(9,27,40,0.95));}}
.lln-sum > div {{flex:1; display:flex; gap:14px; align-items:center; padding:2px 18px; border-right:1px solid {BORDER};}}
.lln-sum > div:last-child {{border-right:none;}}
.lln-sum .material-symbols-outlined {{font-size:30px; color:{TEAL};}}
.lln-sum .lb {{color:#E6F1F5; font-weight:600; font-size:0.95rem;}}
.lln-sum .vl {{font-weight:800; font-size:1.3rem; color:#F2F8FA;}}
.lln-sum .sb {{color:#B5C7D1; font-size:0.84rem;}}
/* clock + events */
.lln-clock {{font-family:'JetBrains Mono','Cascadia Mono',Consolas,monospace; font-size:clamp(1.05rem, 1.42vw, 1.7rem); font-weight:700; white-space:nowrap;
   color:#F2F8FA; letter-spacing:0.02em; line-height:1.1;}}
.lln-clock-sub {{font-family:'JetBrains Mono','Cascadia Mono',Consolas,monospace; color:#9FB4C0; font-size:0.82rem;}}
.lln-ev {{font-family:'JetBrains Mono','Cascadia Mono',Consolas,monospace; font-size:0.84rem; color:#DCE7EC;
   display:flex; gap:12px; align-items:center; padding:6px 2px; border-bottom:1px solid #15303F;}}
.lln-ev .d {{width:9px; height:9px; border-radius:50%;}}
.lln-ev .tm {{color:#E6F1F5; min-width:88px;}}
.lln-ev .tg {{margin-left:auto; color:#7F95A2;}}
.lln-sec {{display:flex; align-items:baseline; gap:10px; font-size:1.12rem; font-weight:700; margin:16px 0 8px 0; color:#F2F8FA;}}
.lln-sec .material-symbols-outlined {{color:{TEAL};}}
.lln-sec span.s {{color:#9FB4C0; font-weight:500; font-size:0.85rem;}}
.lln-rec {{background:linear-gradient(135deg, #0F2A22 0%, #10241E 100%); border:1px solid #2F7A5B; border-radius:16px; padding:16px 20px;}}
.lln-rec h4 {{margin:0 0 6px 0; color:#3DDC97;}}
.lln-warn {{background:#2A1F0F; border:1px solid #8A5A1F; border-radius:16px; padding:14px 18px;}}
.lln-demo {{background:#2A0F18; border:1px solid #8A1F3A; border-radius:16px; padding:14px 18px;}}
.lln-badge {{display:inline-flex; align-items:center; gap:6px; background:rgba(61,220,151,0.10); border:1px solid rgba(61,220,151,0.55);
   color:#3DDC97; border-radius:999px; padding:4px 12px; font-size:0.82rem; font-weight:600;}}
.lln-foot {{color:#8FA4B0; font-size:0.84rem; margin-top:18px; border-top:1px solid {BORDER}; padding-top:10px;}}
.lln-hero {{padding:44px 40px 36px 40px; min-height:200px; display:flex; align-items:center;
   background: linear-gradient(90deg, rgba(6,19,31,0.95) 0%, rgba(6,19,31,0.70) 55%, rgba(6,19,31,0.20) 100%), url("BANNER_URI");
   background-size:cover; background-position:center;}}
.lln-hero h1 {{font-size:2.5rem !important;}}
.lln-hero .row {{gap:22px;}}
.lln-mode {{padding:6px 4px 2px 4px;}}
.lln-mode p {{margin:4px 0 8px 0;}}
[class*="st-key-card_nav_"] {{padding:6px 10px !important;}}
[class*="st-key-card_nav_"] div[data-testid="stPageLink"] a {{border:none; justify-content:flex-start;}}
[class*="st-key-card_nav_"] div[data-testid="stPageLink"] p {{font-size:1rem; font-weight:600;}}
.lln-mode h3 {{margin:0; font-size:1.4rem; font-weight:800; color:#F2F8FA;}}
.lln-mode p {{color:#C9D8E0; font-size:1.0rem;}}
.lln-mode .it {{display:flex; align-items:center; gap:12px; color:#E6F1F5; padding:5px 0; font-size:0.98rem;}}
.lln-mode .it .material-symbols-outlined {{color:{TEAL}; font-size:24px;}}
[class*="st-key-amber_"] .lln-mode .it .material-symbols-outlined {{color:{AMBER};}}
div[data-testid="stPageLink"] a {{border:1px solid rgba(45,212,191,0.6); border-radius:12px; justify-content:center; padding:8px 12px;}}
[class*="st-key-amber_"] div[data-testid="stPageLink"] a {{border-color: rgba(245,165,36,0.85);}}
.stTabs [data-baseweb="tab"] {{border:1px solid {BORDER}; border-radius:10px; padding:6px 16px; margin-right:6px; background:{PANEL};}}
.stTabs [data-baseweb="tab"] p {{font-size:0.95rem; font-weight:600;}}
/* Mission Decision Summary */
.lln-dec {{display:grid; grid-template-columns: 1.15fr 0.55fr 1.5fr 1.6fr; gap:14px; align-items:stretch;
   border:1px solid rgba(245,165,36,0.65); border-radius:14px; padding:14px 16px; margin:12px 0 4px 0;
   background: linear-gradient(160deg, rgba(20,38,48,0.96), rgba(9,27,40,0.96));}}
.lln-dec .site {{border:1px solid rgba(245,165,36,0.6); border-radius:12px; padding:10px 14px; background:rgba(245,165,36,0.06);}}
.lln-dec .site .lb, .lln-dec .score .lb {{color:#C9D8E0; font-size:0.82rem; font-weight:600;}}
.lln-dec .site .nm {{color:{AMBER}; font-weight:800; font-size:1.3rem; line-height:1.25;}}
.lln-dec .score {{border:1px solid {BORDER}; border-radius:12px; padding:10px 12px; text-align:center;}}
.lln-dec .score .vl {{font-weight:800; font-size:1.7rem; color:#F2F8FA;}}
.lln-dec .mt {{display:grid; grid-template-columns:auto 1fr; column-gap:12px; row-gap:3px; font-size:0.9rem; align-content:center;}}
.lln-dec .mt span {{color:#B5C7D1;}} .lln-dec .mt b {{color:#F2F8FA; font-variant-numeric: tabular-nums;}}
.lln-dec .why {{font-size:0.9rem; color:#DCE7EC; align-self:center;}}
.lln-dec .why .nt {{color:#8FA4B0; font-size:0.8rem; margin-top:6px;}}
.lln-tag {{display:inline-block; font-size:0.72rem; font-weight:700; letter-spacing:0.05em; color:#9FB4C0; border:1px solid {BORDER};
   border-radius:6px; padding:1px 7px; margin-left:8px; vertical-align:middle; text-transform:uppercase;}}
@media (max-width: 1100px) {{ .lln-dec {{grid-template-columns: 1fr 1fr;}} .lln-sum {{flex-wrap:wrap;}} }}
.stTabs [aria-selected="true"] {{border-color:{TEAL} !important; background:rgba(45,212,191,0.12) !important;}}
</style>
"""

def _data_uri(path: Path, mime: str) -> str:
    import base64
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


DEFAULT_SITE_IDS = ["malapert_massif", "de_gerlache_rim_2", "mons_mouton", "nobile_rim_2"]


def shared_defaults() -> dict:
    """One set of mission selections shared by every page (Overview, Sky View, Date Finder)."""
    ids = list(names())
    four = [s for s in DEFAULT_SITE_IDS if s in ids] or ids[:4]
    return {"m_sites": four, "m_date": pd.Timestamp("2027-08-16").date(), "m_hour": 12, "m_dur": 6.0,
            "m_site": "de_gerlache_rim_2" if "de_gerlache_rim_2" in ids else ids[0]}


def setup_page(title: str = "", icon: str = ""):
    """Inject theme CSS (page config is set once in app.py) and keep shared selections alive across pages.

    Streamlit drops a widget's value when its page is not shown; re-assigning the key on every page keeps
    the site, date, hour and stay the user picked when they move between pages."""
    st.markdown(CSS.replace("BANNER_URI", _data_uri(ROOT / "assets" / "banner.jpg", "image/jpeg")),
                unsafe_allow_html=True)
    for k, v in shared_defaults().items():
        st.session_state[k] = st.session_state.get(k, v)


def mission_start() -> pd.Timestamp:
    return pd.Timestamp(st.session_state["m_date"]).tz_localize("UTC") + pd.Timedelta(hours=int(st.session_state["m_hour"]))


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
# 2D map: drag to move, +/- buttons to zoom, house button to reset; the mouse wheel scrolls the page
MAP_CONFIG = {"displaylogo": False, "scrollZoom": False,
              "modeBarButtonsToRemove": ["toImage", "select2d", "lasso2d", "autoScale2d", "zoom2d"]}


def polar_xy_km(lat_deg, lon_deg):
    """South-polar stereographic (true scale at the pole, R = 1737.4 km) — same projection as the LOLA DEMs."""
    rho = 2 * R_MOON_KM * np.tan(np.radians((90 + np.asarray(lat_deg, float)) / 2))
    lon = np.radians(np.asarray(lon_deg, float))
    return rho * np.sin(lon), rho * np.cos(lon)


@st.cache_data
def _basemap():
    meta = json.loads((ROOT / "data" / "basemap_hill.json").read_text())
    return Image.open(ROOT / "data" / "basemap_hill.png"), meta


STATUS = {  # (label, colour) — modeled geometry at the selected time
    "available": ("SUN + EARTH", "#3DDC97"),
    "power": ("SUN ONLY", "#FFB02E"),
    "comm": ("EARTH ONLY", "#38BDF8"),
    "none": ("NEITHER", "#FF6B8B"),
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
    fig.add_trace(go.Scatter(x=x, y=y, mode="markers", hovertext=hover, hoverinfo="text", customdata=ids,
                             marker=dict(size=sizes, color=colors, line=dict(color="white", width=2),
                                         symbol="diamond"), unselected=dict(marker=dict(opacity=1)),
                             selected=dict(marker=dict(opacity=1)), showlegend=False))
    for xi, yi, lab_, col_, sid in zip(x, y, labels, colors, ids):
        fig.add_annotation(x=xi, y=yi, text=f"<b>{lab_}</b>", showarrow=False, yshift=20,
                           font=dict(color=AMBER if sid == highlight else "white", size=14 if sid == highlight else 13),
                           bgcolor="rgba(10,15,30,0.82)", bordercolor=AMBER if sid == highlight else col_,
                           borderwidth=2 if sid == highlight else 1.2, borderpad=3)
    pad = 45
    xr = [min(x.min(), 0) - pad, max(x.max(), 0) + pad]
    yr = [min(y.min(), 0) - pad, max(y.max(), 0) + pad]
    span = max(xr[1] - xr[0], yr[1] - yr[0])
    cx, cy = np.mean(xr), np.mean(yr)
    # scale bar 50 km
    bx, by = cx - span / 2 + 18, cy - span / 2 + 14
    fig.add_shape(type="line", x0=bx, x1=bx + 50, y0=by, y1=by, line=dict(color="white", width=3))
    fig.add_annotation(x=bx + 25, y=by, text="50 km", showarrow=False, yshift=10, font=dict(color="white", size=11))
    fig.update_xaxes(range=[cx - span / 2, cx + span / 2], visible=False, constrain="domain")
    fig.update_yaxes(range=[cy - span / 2, cy + span / 2], visible=False, scaleanchor="x", scaleratio=1,
                     constrain="domain")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      dragmode="pan", uirevision="southpole")
    return fig


FONT = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def style_fig(fig, height=360, title=None):
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#C9D1E3", family=FONT, size=14),
                      title=dict(text=title, font=dict(size=16, color="#E6EAF2", family=FONT)) if title else None,
                      hoverlabel=dict(bgcolor="#0F1628", bordercolor=BORDER, font=dict(family=FONT, size=12)),
                      margin=dict(l=10, r=10, t=40 if title else 10, b=10),
                      legend=dict(orientation="h", yanchor="top", y=-0.12, x=0))
    if title:
        fig.update_layout(margin=dict(l=10, r=10, t=44, b=60))
    fig.update_xaxes(gridcolor="#1E2742", zerolinecolor="#2A3556")
    fig.update_yaxes(gridcolor="#1E2742", zerolinecolor="#2A3556")
    return fig


def footer(link: bool = True):
    a, b = st.columns([5, 1.1], vertical_alignment="center")
    a.markdown('<div class="lln-foot">Modeled line-of-sight comparison for planning, not a landing-safety assessment. '
               'Data: NASA/JPL SPICE · NASA LOLA terrain · USGS Artemis III regions. Team Bulldogs Beyond Earth · '
               'NASA Space Apps 2026.</div>', unsafe_allow_html=True)
    if link:
        b.page_link("views/validation.py", label="Validation & Sources", icon=":material/fact_check:")


# ------------------------------------------------------------------ 3D terrain (real LOLA tiles, data/terrain3d.npz)
@st.cache_resource
def terrain3d():
    p = ROOT / "data" / "terrain3d.npz"
    return dict(np.load(p)) if p.exists() else None


MOON_GREYS = [[0, "#1B1E24"], [0.35, "#4A4F58"], [0.7, "#8C9099"], [1, "#D6D8DC"]]


def observer_3d(site_id: str, row, horizon_prof, exag: float = 3.0, height: int = 600):
    """3D view from the site: LOLA terrain within 40 km (east/north/up, lunar curvature included), the full
    150 km skyline drawn as a ring, and the Sun and Earth placed along their true azimuth/elevation."""
    t = terrain3d()
    if t is None or f"site_{site_id}" not in t:
        return None
    z = t[f"site_{site_id}"].astype(float)
    xs, ys, ulx, uly = t[f"xy_{site_id}"] / 1000.0
    cell = float(t["meta"][1]) / 1000.0
    n = z.shape[0]
    XX, YY = np.meshgrid(ulx + (np.arange(n) + 0.5) * cell, uly - (np.arange(n) + 0.5) * cell)
    dx, dy = XX - xs, YY - ys
    lon = np.radians(float(sites_df().set_index("site_id").loc[site_id, "lon_deg"]))
    E = dx * np.cos(lon) - dy * np.sin(lon)            # local east (km)   — orientation checked against
    N = dx * np.sin(lon) + dy * np.cos(lon)            # local north (km)    the stored horizon profiles
    h0 = horizon_prof.site_height_m
    rr = np.hypot(E, N)
    Z = ((z - h0) / 1000.0 - rr ** 2 / (2 * R_MOON_KM)) * exag
    Z[rr > 38.0] = np.nan                                 # round 38 km disc, matching the skyline ring
    fig = go.Figure()
    sun_dir = np.array([np.sin(np.radians(row.sun_az_deg)), np.cos(np.radians(row.sun_az_deg)),
                        np.tan(np.radians(max(row.sun_el_deg, 0.5))) * exag])
    # shading from the real Sun direction at the selected time, using true (unexaggerated) slopes
    zt = (z - h0) / 1000.0 - rr ** 2 / (2 * R_MOON_KM)
    nE, nN = np.gradient(zt, axis=1), np.gradient(zt, axis=0)
    dEc, dNc = np.gradient(E, axis=1), np.gradient(N, axis=1)
    dEr, dNr = np.gradient(E, axis=0), np.gradient(N, axis=0)
    det = dEc * dNr - dEr * dNc
    zE = (nE * dNr - nN * dNc) / det                       # dz/dEast  (chain rule on the rotated grid)
    zN = (nN * dEc - nE * dEr) / det                       # dz/dNorth
    sa, se = np.radians(row.sun_az_deg), np.radians(row.sun_el_deg)
    sv = np.array([np.sin(sa) * np.cos(se), np.cos(sa) * np.cos(se), np.sin(se)])
    lam = (-zE * sv[0] - zN * sv[1] + sv[2]) / np.sqrt(1 + zE ** 2 + zN ** 2)
    shade = 0.22 + 0.78 * np.clip(lam * 3.0, 0, 1) ** 0.6 if row.sun_el_deg > -1 else np.full_like(zt, 0.12)
    shade = np.where(np.isnan(Z), np.nan, shade)
    fig.add_trace(go.Surface(x=E, y=N, z=Z, surfacecolor=shade, cmin=0, cmax=1, showscale=False,
                             colorscale=[[0, "#0B0C0F"], [0.3, "#3A3B3F"], [0.65, "#8E8C87"], [1, "#DEDBD3"]],
                             hoverinfo="skip", name="LOLA terrain",
                             lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0, fresnel=0.0)))
    for lab, a in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        fig.add_trace(go.Scatter3d(x=[41 * np.sin(np.radians(a))], y=[41 * np.cos(np.radians(a))], z=[0], mode="text",
                                   text=[f"<b>{lab}</b>"], textfont=dict(color="#E6F1F5", size=15), showlegend=False,
                                   hoverinfo="skip"))
    site_name = sites_df().set_index("site_id").loc[site_id, "name"]
    pole = 2.2 * exag / 3.0
    fig.add_trace(go.Scatter3d(x=[0, 0], y=[0, 0], z=[0, pole], mode="lines", line=dict(color=AMBER, width=8),
                               showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter3d(x=[0], y=[0], z=[pole], mode="markers+text", text=[f"<b>Station · {site_name}</b>"],
                               textposition="top center", textfont=dict(color=AMBER, size=15),
                               marker=dict(size=10, color=AMBER, symbol="diamond", line=dict(color="white", width=2)),
                               name="Station (site)", hoverinfo="skip"))
    th = np.linspace(0, 2 * np.pi, 60)
    fig.add_trace(go.Scatter3d(x=1.2 * np.cos(th), y=1.2 * np.sin(th), z=np.full(60, 0.05), mode="lines",
                               line=dict(color=AMBER, width=5), showlegend=False, hoverinfo="skip"))
    D = 47.0                                               # just beyond the skyline ring
    for key, nm, col, tpos in (("sun", "Sun", "#FFD36E", "top center"), ("earth", "Earth", EARTH, "bottom center")):
        a_, e_ = np.radians(row[f"{key}_az_deg"]), row[f"{key}_el_deg"]
        clear = e_ - row[f"horizon_at_{key}_deg"]
        vis = (row.sun_frac > 0) if key == "sun" else bool(row.earth_in_view)
        p = [D * np.sin(a_), D * np.cos(a_), D * np.tan(np.radians(e_)) * exag]
        c = col if vis else "#8A93A6"
        fig.add_trace(go.Scatter3d(x=[0, p[0]], y=[0, p[1]], z=[0.05, p[2]], mode="lines",
                                   line=dict(color=c, width=4, dash="solid" if vis else "dash"), showlegend=False,
                                   hoverinfo="skip"))
        fig.add_trace(go.Scatter3d(
            x=[p[0]], y=[p[1]], z=[p[2]], mode="markers+text", name=nm,
            text=[f"<b>{nm}</b> · El {e_:+.2f}° · Az {row[f'{key}_az_deg']:.0f}°" + ("" if vis else " (behind terrain)")],
            textposition=tpos, textfont=dict(color=c, size=14),
            marker=dict(size=13 if key == "sun" else 11, color=c if vis else "rgba(0,0,0,0)",
                        line=dict(color=c, width=3)), hoverinfo="skip"))
    cam_az = np.radians(row.sun_az_deg - 115.0)          # side-on to the Sun: lit slopes and the Sun both in view
    back = np.array([np.sin(cam_az), np.cos(cam_az)])
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", uirevision=site_id,
        font=dict(family=FONT, color="#C9D1E3"), showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=0.0, x=0.01, bgcolor="rgba(6,19,31,0.6)"),
        scene=dict(bgcolor="#000000", aspectmode="data",
                   xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                   camera=dict(eye=dict(x=float(back[0]) * 1.75, y=float(back[1]) * 1.75, z=1.0),
                               center=dict(x=0, y=0, z=-0.1))))
    return fig


def region_3d(site_ids, status: dict | None = None, scores: dict | None = None, highlight: str | None = None,
              exag: float = 4.0, height: int = 470):
    """Rotatable 3D relief of the south-pole region from the LOLA DEM (~1 km cells), with the sites marked."""
    t = terrain3d()
    if t is None:
        return None
    z = t["region"].astype(float)[::2, ::2]
    ulx, uly, cell = t["region_ul"] / 1000.0
    cell *= 2
    n0, n1 = z.shape
    X = ulx + (np.arange(n1) + 0.5) * cell
    Y = uly - (np.arange(n0) + 0.5) * cell
    fig = go.Figure(go.Surface(x=X, y=Y, z=z / 1000.0 * exag, surfacecolor=z, colorscale=MOON_GREYS,
                               showscale=False, hoverinfo="skip",
                               lighting=dict(ambient=0.45, diffuse=0.85, specular=0.05, roughness=0.9),
                               lightposition=dict(x=-1e5, y=1e5, z=5e4)))
    s = sites_df().set_index("site_id")
    ids = [i for i in site_ids if i in s.index]
    x, y = polar_xy_km(s.loc[ids, "lat_deg"].values, s.loc[ids, "lon_deg"].values)
    zz = s.loc[ids, "height_m"].astype(float).values / 1000.0 * exag + 1.5
    cols, labs = [], []
    for sid in ids:
        if status is not None and sid in status:
            cols.append(STATUS[status[sid]][1])
        elif scores is not None and sid in scores:
            cols.append(rating(scores[sid])[1])
        else:
            cols.append(site_color(sid))
        labs.append(f"<b>{s.loc[sid, 'name']}</b>")
    fig.add_trace(go.Scatter3d(x=x, y=y, z=zz, mode="markers+text", text=labs, textposition="top center",
                               textfont=dict(color=[AMBER if i == highlight else "white" for i in ids], size=13),
                               marker=dict(size=[9 if i == highlight else 6 for i in ids], color=cols,
                                           line=dict(color="white", width=2), symbol="diamond"), hoverinfo="skip"))
    fig.add_trace(go.Scatter3d(x=[0], y=[0], z=[float(np.nanmax(z)) / 1000 * exag * 0.2], mode="text",
                               text=["South Pole"], textfont=dict(color="#E6F1F5", size=12), hoverinfo="skip"))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      showlegend=False, uirevision="region3d",
                      scene=dict(bgcolor="#03050C", aspectmode="data",
                                 xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                                 camera=dict(eye=dict(x=0.0, y=-1.55, z=1.65), center=dict(x=0, y=0, z=-0.25))))
    return fig
