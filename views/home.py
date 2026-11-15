"""Home — what the tool does, and two ways in: Explorer Mode or Mission Control Mode."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import ui_common as ui

ui.setup_page()

st.markdown(f'<div class="lln-banner lln-hero"><div class="row">{ui.mi("rocket_launch", 46, "#F2F8FA")}'
            '<div><h1>Lunar Landing Site Navigator</h1><div class="sub">Compare lunar south-pole landing sites by '
            'sunlight, Earth visibility, communication and mission timing — computed from NASA data.</div>'
            f'<div style="margin-top:12px">{ui.validated_pill()}</div></div></div></div>', unsafe_allow_html=True)

e, m = st.columns(2, gap="medium")
with e:
    with st.container(key="card_explorer"):
        st.markdown(f'<div class="lln-mode">{ui.mi("groups", 40, ui.TEAL)}<h3>Explorer Mode</h3>'
                    '<p>Learn and explore the Moon with a guided, visual experience.</p></div>',
                    unsafe_allow_html=True)
        st.page_link("views/sky_view.py", label="Start exploring", icon=":material/arrow_forward:")
with m:
    with st.container(key="amber_missioncontrol"):
        st.markdown(f'<div class="lln-mode">{ui.mi("tune", 40, ui.AMBER)}<h3>Mission Control Mode</h3>'
                    '<p>Plan a mission, compare sites, and make a landing decision.</p></div>',
                    unsafe_allow_html=True)
        st.page_link("views/overview.py", label="Open Mission Control", icon=":material/arrow_forward:")

st.markdown('<div class="lln-sec" style="color:#7FF0DD;font-size:1.05rem">Explore the tool</div>',
            unsafe_allow_html=True)
for col, (page, label, icon) in zip(st.columns(4, gap="medium"), [
        ("views/overview.py", "Mission Overview", ":material/bar_chart:"),
        ("views/sky_view.py", "Sky View", ":material/landscape:"),
        ("views/date_finder.py", "Date Finder", ":material/calendar_month:"),
        ("views/validation.py", "Validation & Sources", ":material/fact_check:")]):
    with col:
        with st.container(key=f"card_nav_{label.split()[0]}"):
            st.page_link(page, label=label, icon=icon)

ui.footer(link=False)
