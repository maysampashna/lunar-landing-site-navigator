"""Home — what the tool does, and two ways in: Explorer Mode or Mission Control Mode."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import ui_common as ui

ui.setup_page()
names = ui.names()
ROOT = Path(__file__).resolve().parent.parent

st.markdown(f'<div class="lln-banner"><div class="row" style="justify-content:space-between;flex-wrap:wrap">'
            f'<div><h1>Lunar Landing Site Navigator</h1><div class="sub">Compare lunar south-pole landing sites and '
            f'dates by when the Sun (power) and Earth (communication) are above the real terrain horizon.</div></div>'
            f'<div>{ui.validated_pill()}</div></div></div>', unsafe_allow_html=True)

c_map, c_modes = st.columns([1.45, 1.55])
with c_map:
    with st.container(key="card_home_map"):
        shown = [s for s in ui.DEFAULT_SITE_IDS if s in names] or list(names)[:4]
        st.plotly_chart(ui.south_pole_map(shown, None, height=470), width="stretch",
                        config={"displayModeBar": False, "scrollZoom": False})
        st.caption(f"{len(shown)} of {len(names)} candidate sites shown, on NASA LOLA terrain around the lunar "
                   "south pole. Sites are representative points in NASA's Artemis III candidate regions.")
with c_modes:
    e, m = st.columns(2)
    with e:
        with st.container(key="card_explorer"):
            st.markdown(f'<div class="lln-mode"><div class="lln-ct" style="font-size:1.35rem">{ui.mi("explore", 30)}'
                        '<span>Explorer Mode</span></div><p>New to the Moon? Three questions, answered with '
                        'pictures.</p></div>', unsafe_allow_html=True)
            st.page_link("views/overview.py", label="1 · Where are the candidate sites?", icon=":material/map:")
            st.page_link("views/sky_view.py", label="2 · When are the Sun and Earth visible?",
                         icon=":material/wb_sunny:")
            st.page_link("views/date_finder.py", label="3 · Why does the landing date matter?",
                         icon=":material/calendar_month:")
    with m:
        with st.container(key="amber_missioncontrol"):
            st.markdown(f'<div class="lln-mode"><div class="lln-ct" style="font-size:1.35rem">'
                        f'{ui.mi("satellite_alt", 30, ui.AMBER)}<span>Mission Control Mode</span></div><p>Full '
                        'analysis: mission clock, DSN geometry, schedule risk, storage and every control.</p></div>',
                        unsafe_allow_html=True)
            st.page_link("views/overview.py", label="Open Mission Overview", icon=":material/arrow_forward:")
            st.page_link("views/date_finder.py", label="Search landing dates", icon=":material/arrow_forward:")
            st.page_link("views/validation.py", label="Check the evidence", icon=":material/arrow_forward:")

    st.markdown(f'<div class="lln-sec" style="margin-top:12px">{ui.mi("grid_view")}Explore the tool</div>',
                unsafe_allow_html=True)
    cards = [("thumb_map.png", "Mission Overview", "Decision summary, clock and site status", "views/overview.py"),
             ("thumb_sky.png", "Sky View", "Sun and Earth over the real skyline", "views/sky_view.py"),
             ("thumb_heatmap.png", "Date Finder", "Best landing windows by date", "views/date_finder.py")]
    for col, (img, title, desc, page) in zip(st.columns(3), cards):
        with col:
            with st.container(key=f"card_tool_{title.replace(' ', '_')}"):
                st.image(str(ROOT / "assets" / img), width="stretch")
                st.page_link(page, label=title, icon=":material/arrow_forward:")
                st.markdown(f"<span style='color:#B5C7D1;font-size:0.86rem'>{desc}</span>", unsafe_allow_html=True)

ui.footer()
