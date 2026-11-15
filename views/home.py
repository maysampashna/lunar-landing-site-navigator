"""Home — choose Explorer mode or Mission Control mode."""
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
            f'<div><h1>Lunar Landing Site Navigator</h1><div class="sub">Compare lunar south-pole landing sites by '
            f'sunlight, Earth visibility, NASA Deep Space Network coverage, terrain horizon, and mission timing.</div>'
            f'<div class="bar"></div></div><div>{ui.validated_pill()}</div></div></div>', unsafe_allow_html=True)

c_map, c_exp, c_mc = st.columns([1.05, 1, 1])
with c_map:
    with st.container(key="card_home_map"):
        st.plotly_chart(ui.south_pole_map([s for s in ["malapert_massif", "de_gerlache_rim_2", "mons_mouton", "nobile_rim_2"] if s in names] or list(names), None, height=420), width="stretch",
                        config={"displayModeBar": False, "scrollZoom": False})
with c_exp:
    with st.container(key="card_explorer"):
        st.markdown(f'<div class="lln-mode"><div class="lln-ct" style="font-size:1.5rem">{ui.mi("map", 34)}'
                    '<span>Explorer Mode</span></div><p>Understand the Moon, compare sites visually, and learn why '
                    'timing matters at the south pole.</p>'
                    f'<div class="it">{ui.mi("explore")}Guided sky view from any site</div>'
                    f'<div class="it">{ui.mi("menu_book")}Plain-language summaries</div>'
                    f'<div class="it">{ui.mi("image")}Visual comparisons on real terrain</div>'
                    f'<div class="it">{ui.mi("public")}Live sky right now</div></div>', unsafe_allow_html=True)
        st.write("")
        st.page_link("views/sky_view.py", label="Start Explorer Mode", icon=":material/arrow_forward:",
                     use_container_width=True)
with c_mc:
    with st.container(key="amber_missioncontrol"):
        st.markdown(f'<div class="lln-mode"><div class="lln-ct" style="font-size:1.5rem">'
                    f'{ui.mi("satellite_alt", 34, ui.AMBER)}<span>Mission Control Mode</span></div><p>Evaluate '
                    'terrain-aware visibility, power, Deep Space Network communication and schedule risk.</p>'
                    f'<div class="it">{ui.mi("description")}Decision report & recommendation</div>'
                    f'<div class="it">{ui.mi("schedule")}Mission clock to the second (UTC DOY, MET)</div>'
                    f'<div class="it">{ui.mi("cell_tower")}Station availability & DSN coverage</div>'
                    f'<div class="it">{ui.mi("calendar_month")}Landing-date finder</div></div>', unsafe_allow_html=True)
        st.write("")
        st.page_link("views/overview.py", label="Start Mission Control Mode", icon=":material/arrow_forward:",
                     use_container_width=True)

st.markdown(f'<div class="lln-sec">{ui.mi("grid_view")}Explore the tool</div>', unsafe_allow_html=True)
cards = [("thumb_map.png", "Mission Overview", "Landing sites, station status, DSN and key events.", "views/overview.py"),
         ("thumb_sky.png", "Sky View", "Sun, Earth and the real horizon through the mission.", "views/sky_view.py"),
         ("thumb_heatmap.png", "Date Finder", "Find the best landing windows by site.", "views/date_finder.py")]
for col, (img, title, desc, page) in zip(st.columns(3), cards):
    with col:
        with st.container(key=f"card_tool_{title.replace(' ', '_')}"):
            a, b = st.columns([1, 1.25])
            a.image(str(ROOT / "assets" / img), width="stretch")
            b.markdown(f"**{title}**  \n<span style='color:#B5C7D1;font-size:0.9rem'>{desc}</span>",
                       unsafe_allow_html=True)
            b.page_link(page, label="Open", icon=":material/arrow_forward:")

ui.footer()
