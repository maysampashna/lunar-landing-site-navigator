"""Home — title, an orbital view of the south pole with the candidate sites, and three ways in."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import ui_common as ui

ui.setup_page()
ROOT = Path(__file__).resolve().parent.parent
hero = ui._data_uri(ROOT / "assets" / "home_moon.jpg", "image/jpeg")
stars = ui._data_uri(ROOT / "assets" / "stars.jpg", "image/jpeg")

st.markdown(f"""<style>
[data-testid="stAppViewContainer"] {{background:#02060C url("{stars}") center / cover fixed;}}
.lln-h {{position:relative; width:100%; aspect-ratio: 2400 / 1350; border-radius:18px; overflow:hidden;
   background:url("{hero}") center / cover no-repeat; box-shadow:0 0 0 1px rgba(80,220,255,0.18), 0 20px 60px rgba(0,0,0,0.6);}}
.lln-h .ttl {{position:absolute; top:3.2%; left:50%; transform:translateX(-50%); width:min(70%, 900px);
   padding:14px 34px 12px 34px; border-radius:18px; text-align:center;
   background:linear-gradient(180deg, rgba(8,28,44,0.88), rgba(5,18,30,0.88));
   border:1.5px solid rgba(80,220,255,0.75); box-shadow:0 0 22px rgba(80,220,255,0.35), inset 0 0 18px rgba(80,220,255,0.10);}}
.lln-h .ttl .row {{display:flex; align-items:center; justify-content:center; gap:16px;}}
.lln-h .ttl h1 {{margin:0; padding:0; font-size:clamp(1.5rem, 2.9vw, 2.7rem); font-weight:800; color:#F4FAFC;}}
.lln-h .ttl .sub {{color:#C9DCE5; font-size:clamp(0.8rem, 1.05vw, 1.02rem); margin-top:4px;}}
.lln-h .btns {{position:absolute; left:3%; right:3%; bottom:3%; display:flex; gap:3%;}}
.lln-h .btns a {{flex:1; display:flex; align-items:center; justify-content:space-between; gap:14px; text-decoration:none;
   padding:clamp(8px, 1.0vw, 15px) clamp(14px, 1.8vw, 28px); border-radius:16px; background:rgba(5,16,28,0.82);
   color:#F4FAFC !important; font-weight:700; font-size:clamp(0.95rem, 1.45vw, 1.45rem); backdrop-filter:blur(4px);
   transition:transform .15s ease, box-shadow .15s ease;}}
.lln-h .btns a:hover {{transform:translateY(-3px);}}
.lln-h .btns a .ic {{font-size:clamp(1.6rem, 2.4vw, 2.4rem);}}
.lln-h .btns a .lb {{flex:1; text-align:left;}}
.lln-h .b1 {{border:1.5px solid #4FA3FF; box-shadow:0 0 20px rgba(79,163,255,0.45);}} .lln-h .b1 .ic, .lln-h .b1 .ar {{color:#4FA3FF;}}
.lln-h .b2 {{border:1.5px solid #A97BFF; box-shadow:0 0 20px rgba(169,123,255,0.45);}} .lln-h .b2 .ic, .lln-h .b2 .ar {{color:#B58CFF;}}
.lln-h .b3 {{border:1.5px solid #2DD4BF; box-shadow:0 0 20px rgba(45,212,191,0.45);}} .lln-h .b3 .ic, .lln-h .b3 .ar {{color:#2DD4BF;}}
.lln-credit {{text-align:right; color:#6F8592; font-size:0.76rem; margin:6px 4px 0 0;}}
</style>""", unsafe_allow_html=True)

st.markdown(
    '<div class="lln-h">'
    f'<div class="ttl"><div class="row">{ui.mi("rocket_launch", 44, "#50DCFF")}<h1>Lunar Landing Site Navigator</h1></div>'
    '<div class="sub">Where and when to land at the lunar south pole — sunlight for power, Earth in view for '
    'communication.</div></div>'
    '<div class="btns">'
    f'<a class="b1" href="mission" target="_self"><span class="ic">{ui.mi("bar_chart", 40, "#4FA3FF")}</span>'
    f'<span class="lb">Mission Dashboard</span><span class="ar">{ui.mi("arrow_forward", 28, "#4FA3FF")}</span></a>'
    f'<a class="b2" href="date_finder" target="_self"><span class="ic">{ui.mi("calendar_month", 40, "#B58CFF")}</span>'
    f'<span class="lb">Best Date Finder</span><span class="ar">{ui.mi("arrow_forward", 28, "#B58CFF")}</span></a>'
    f'<a class="b3" href="validation" target="_self"><span class="ic">{ui.mi("settings", 40, "#2DD4BF")}</span>'
    f'<span class="lb">Data Validation</span><span class="ar">{ui.mi("arrow_forward", 28, "#2DD4BF")}</span></a>'
    '</div></div>'
    '<div class="lln-credit">Rendered from NASA LOLA terrain (Lunar Reconnaissance Orbiter) · sites: USGS Artemis III '
    'regions · Sun and Earth placement illustrative</div>', unsafe_allow_html=True)

ui.footer(link=False)
