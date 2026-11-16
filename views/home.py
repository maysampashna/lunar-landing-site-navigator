"""Home — title, the Moon with the candidate sites, and three ways in."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import ui_common as ui

ui.setup_page()
ROOT = Path(__file__).resolve().parent.parent

st.markdown(f"""<style>
[data-testid="stAppViewContainer"] {{
  background: #03070E url("{ui._data_uri(ROOT / "assets" / "stars.jpg", "image/jpeg")}") center / cover fixed;
}}
.lln-home-head {{display:flex; align-items:center; justify-content:center; gap:18px; margin:6px 0 4px 0;}}
.lln-home-head h1 {{font-size:3rem; font-weight:800; color:#F2F8FA; margin:0; padding:0; letter-spacing:0.01em;}}
.lln-home-tag {{text-align:center; color:#AFC3CE; font-size:1.08rem; margin-bottom:6px;}}
.lln-hero-img img {{width:100%; display:block;
   -webkit-mask-image: radial-gradient(ellipse 72% 70% at 50% 48%, #000 62%, transparent 100%);
   mask-image: radial-gradient(ellipse 72% 70% at 50% 48%, #000 62%, transparent 100%);}}
[class*="st-key-home_go_"] {{padding:20px 18px !important; text-align:center; border-radius:14px;
   border:1px solid rgba(45,212,191,0.45); background:rgba(9,27,40,0.82); backdrop-filter: blur(3px);}}
[class*="st-key-home_go_"]:hover {{border-color:#2DD4BF; background:rgba(14,40,56,0.9);}}
[class*="st-key-home_go_"] div[data-testid="stPageLink"] a {{justify-content:center; border:none; background:none; width:100%; display:flex;}}
[class*="st-key-home_go_"] div[data-testid="stPageLink"] p {{font-size:1.35rem; font-weight:700; color:#F2F8FA;}}
[class*="st-key-home_go_"] div[data-testid="stPageLink"] span[data-testid="stIconMaterial"] {{font-size:1.9rem;}}
</style>""", unsafe_allow_html=True)

st.markdown(f'<div class="lln-home-head">{ui.mi("rocket_launch", 46, ui.TEAL)}<h1>Lunar Landing Site Navigator</h1></div>'
            '<div class="lln-home-tag">Where and when to land at the lunar south pole — sunlight for power, '
            'Earth in view for communication.</div>', unsafe_allow_html=True)
st.markdown(f'<div class="lln-hero-img"><img alt="The Moon with the Artemis III candidate landing sites" '
            f'src="{ui._data_uri(ROOT / "assets" / "home_moon.jpg", "image/jpeg")}"></div>', unsafe_allow_html=True)
st.write("")
for col, (key, page, label, icon) in zip(st.columns(3, gap="medium"), [
        ("home_go_dashboard", "views/mission.py", "Mission Dashboard", ":material/space_dashboard:"),
        ("home_go_dates", "views/date_finder.py", "Best Date Finder", ":material/event_available:"),
        ("home_go_validation", "views/validation.py", "Data Validation", ":material/verified:")]):
    with col:
        with st.container(key=f"{key}"):
            st.page_link(page, label=label, icon=icon)

ui.footer(link=False)
