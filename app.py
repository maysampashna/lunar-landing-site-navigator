"""Lunar Landing Site Navigator — entry point (NASA Space Apps 2026, Bulldogs Beyond Earth).

Run:  streamlit run app.py
"""
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Lunar Landing Site Navigator", page_icon=str(ROOT / "assets" / "logo_moon.png"),
                   layout="wide")
st.logo(str(ROOT / "assets" / "logo_full.png"), size="large", icon_image=str(ROOT / "assets" / "logo_moon.png"))

pg = st.navigation([
    st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/mission.py", title="Mission Dashboard", icon=":material/space_dashboard:"),
    st.Page("views/date_finder.py", title="Best Date Finder", icon=":material/event_available:"),
    st.Page("views/validation.py", title="Data Validation", icon=":material/verified:"),
])
pg.run()
