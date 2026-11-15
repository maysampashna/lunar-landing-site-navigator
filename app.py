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
    st.Page("views/overview.py", title="Mission Overview", icon=":material/rocket_launch:"),
    st.Page("views/sky_view.py", title="Sky View", icon=":material/satellite_alt:"),
    st.Page("views/date_finder.py", title="Date Finder", icon=":material/calendar_month:"),
    st.Page("views/validation.py", title="Validation & Sources", icon=":material/fact_check:"),
])
pg.run()
