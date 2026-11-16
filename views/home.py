"""Home — what the tool does, a 3D view of the real lunar south pole, and three ways in."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from engine import live, visibility
import ui_common as ui

ui.setup_page()
names = ui.names()

# subtle star field behind the home page only
st.markdown("""<style>
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1px 1px at 12% 18%, rgba(255,255,255,0.55), transparent 60%),
    radial-gradient(1px 1px at 33% 72%, rgba(255,255,255,0.45), transparent 60%),
    radial-gradient(1.5px 1.5px at 58% 26%, rgba(255,255,255,0.60), transparent 60%),
    radial-gradient(1px 1px at 76% 64%, rgba(255,255,255,0.40), transparent 60%),
    radial-gradient(1px 1px at 88% 12%, rgba(255,255,255,0.50), transparent 60%),
    radial-gradient(1px 1px at 47% 90%, rgba(255,255,255,0.35), transparent 60%),
    radial-gradient(1.2px 1.2px at 6% 82%, rgba(255,255,255,0.45), transparent 60%),
    radial-gradient(1px 1px at 68% 44%, rgba(255,255,255,0.30), transparent 60%),
    radial-gradient(ellipse at 70% 0%, rgba(45,212,191,0.10), transparent 55%),
    radial-gradient(ellipse at 0% 100%, rgba(76,141,255,0.10), transparent 50%),
    #040B14;
  background-size: 380px 380px, 520px 520px, 610px 610px, 450px 450px, 700px 700px, 330px 330px, 560px 560px,
                   420px 420px, 100% 100%, 100% 100%, 100% 100%;
}
.lln-home-title {font-size:2.9rem; font-weight:800; line-height:1.1; color:#F2F8FA; margin:28px 0 10px 0;}
.lln-home-sub {font-size:1.12rem; color:#C2D3DC; max-width:560px; margin-bottom:16px;}
.lln-home-card {font-size:0.95rem; color:#B5C7D1; margin:6px 0 10px 0; min-height:44px;}
.lln-home-card h3 {color:#F2F8FA; font-size:1.3rem; margin:8px 0 6px 0;}
</style>""", unsafe_allow_html=True)

left, right = st.columns([1, 1.25], gap="large", vertical_alignment="center")
with left:
    st.markdown(f'{ui.mi("rocket_launch", 44, ui.TEAL)}<div class="lln-home-title">Lunar Landing<br>Site Navigator</div>'
                '<div class="lln-home-sub">Compare lunar south-pole landing sites and dates by when the Sun '
                '(power) and Earth (communication) are above the real terrain horizon — computed from NASA data.'
                f'</div>{ui.validated_pill()}', unsafe_allow_html=True)
with right:
    view = st.segmented_control("Globe view", ["All sites", "Whole Moon"], default="All sites",
                                label_visibility="collapsed") or "All sites"
    sun = None
    if live.kernels_available():                     # light the Moon by the real Sun at the selected landing time
        site = st.session_state["m_site"]
        r = ui.sites_df().set_index("site_id").loc[site]
        row = live.at_time(r, ui.horizon(site), ui.mission_start(), visibility.VisParams())
        sun = ui.sun_vector(r.lat_deg, r.lon_deg, row.sun_az_deg, row.sun_el_deg)
    fig = ui.moon_globe(list(names), sun_vec=sun, view=view, height=480)
    if fig is not None:
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True,
                                                      "modeBarButtonsToRemove": ["toImage"]})
        st.caption("The Moon lit by the Sun on the selected landing date. The south polar cap shows NASA LOLA laser-"
                   "altimetry terrain (heights ×5); the rest is a smooth sphere. Drag to rotate, scroll to zoom.")

st.write("")
cards = [
    ("card_go_dashboard", "space_dashboard", ui.TEAL, "Mission Dashboard",
     "Pick sites and a landing time: 3D view, map, mission clock and the recommended site.",
     "views/mission.py", "Open dashboard"),
    ("amber_go_dates", "event_available", ui.AMBER, "Best Date Finder",
     "Rank landing dates from 2026 to 2031 and open any of them in the dashboard.",
     "views/date_finder.py", "Find the best dates"),
    ("card_go_validation", "verified", ui.BOTH, "Data Validation",
     "How the results were checked against JPL Horizons, and every NASA data source used.",
     "views/validation.py", "See the evidence"),
]
for col, (key, icon, color, title, desc, page, cta) in zip(st.columns(3, gap="medium"), cards):
    with col:
        with st.container(key=key):
            st.markdown(f'<div class="lln-home-card">{ui.mi(icon, 34, color)}<h3>{title}</h3>{desc}</div>',
                        unsafe_allow_html=True)
            st.page_link(page, label=cta, icon=":material/arrow_forward:")

ui.footer(link=False)
