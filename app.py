"""Lunar Landing Site Navigator — entry point (NASA Space Apps 2026, Bulldogs Beyond Earth).

Run:  streamlit run app.py
"""
import streamlit as st

pg = st.navigation([
    st.Page("views/overview.py", title="Mission Overview", icon="🚀", default=True),
    st.Page("views/sky_view.py", title="Sky View", icon="🔭"),
    st.Page("views/date_finder.py", title="Date Finder", icon="📅"),
    st.Page("views/validation.py", title="Validation & Sources", icon="✅"),
])
pg.run()
