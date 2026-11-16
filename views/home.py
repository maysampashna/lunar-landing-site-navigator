"""Home — title, an orbital view of the south pole with the candidate sites, and three ways in."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

import pandas as pd
import streamlit as st

from engine import finder
from engine.metrics import ScoreWeights
from engine.power import PowerParams
import ui_common as ui

ui.setup_page()
ROOT = Path(__file__).resolve().parent.parent
hero = ui._data_uri(ROOT / "assets" / "home_moon.jpg", "image/jpeg")
stars = ui._data_uri(ROOT / "assets" / "stars.jpg", "image/jpeg")
names = ui.names()
srow = ui.sites_df().set_index("site_id")

# what each site is (from its NASA region name and our LOLA terrain data)
ABOUT = {
    "peak_near_cabeus_b": "A high peak near Cabeus B crater, close to Cabeus, where NASA's LCROSS impact in 2009 "
                          "found water.",
    "haworth": "Next to Haworth crater, one of the large permanently shadowed craters near the pole.",
    "malapert_massif": "A large mountain massif, among the highest ground near the south pole.",
    "mons_mouton": "A broad, flat-topped mountain named after NASA mathematician Melba Mouton.",
    "nobile_rim_1": "On the rim of Nobile crater, a large crater in the polar region.",
    "nobile_rim_2": "On the rim of Nobile crater, a large crater in the polar region.",
    "de_gerlache_rim_2": "On the rim of de Gerlache crater, beside Shackleton crater near the pole.",
    "slater_plain": "A smoother plain near Slater crater.",
}
WHY = ("Why chosen: one of NASA's nine Artemis III candidate regions (Oct 2024), picked from Lunar Reconnaissance "
       "Orbiter data for diverse geology, access to cold shadowed areas that may hold water ice, and flexible "
       "mission timing.")


@st.cache_data(show_spinner="Scoring the sites…")
def quick_scores(start, dur):
    ids = list(names)
    vis = {s_: ui.site_vis_hourly(s_) for s_ in ids}
    table, _ = finder.shift_compare(vis, start, duration_h=dur * 24, shifts_h=(0, 24, 48), weights=ScoreWeights(),
                                    power=PowerParams(), terrain_real={s_: ui.terrain_status(s_) == "real" for s_ in ids})
    return table[table.shift_h == 0].set_index("site_id")


start = ui.mission_start()
dur = float(st.session_state["m_dur"])
try:
    sc = quick_scores(start, dur)
except Exception:                                    # keep Home usable even if scoring is unavailable
    sc = None


def tip(sid):
    h = srow.loc[sid, "height_m"] / 1000.0
    ours = ""
    if sc is not None and sid in sc.index:
        r = sc.loc[sid]
        ours = (f'<div class="tl">Our analysis · {dur:g}-day stay from {start:%Y-%m-%d}</div>'
                f'<div class="tm">Sunlight <b>{r.pct_sunlit:.0f}%</b> · Earth contact <b>{r.pct_dte:.0f}%</b> · '
                f'worst-case score <b>{r.worst_case_score:.0f}</b>/100</div>')
    return (f'<div class="tip"><div class="tn">{names[sid]}</div>'
            f'<div class="tx">{ABOUT.get(sid, "")} Elevation {h:+.1f} km (LOLA).</div>'
            f'<div class="tx why">{WHY}</div>{ours}'
            '<div class="tf">Point = representative location inside the USGS region grid, not an official '
            'landing spot.</div></div>')


hot = json.loads((ROOT / "assets" / "home_moon_labels.json").read_text())
hotspots = "".join(
    f'<div class="hs" style="left:{h_["x"] * 100:.2f}%;top:{h_["y"] * 100:.2f}%;width:{h_["w"] * 100:.2f}%;'
    f'height:{h_["h"] * 100:.2f}%">{tip(h_["site_id"])}</div>' for h_ in hot if h_["site_id"] in names)

st.markdown(f"""<style>
[data-testid="stAppViewContainer"] {{background:#02060C url("{stars}") center / cover fixed;}}
.lln-h {{position:relative; width:100%; aspect-ratio: 2400 / 1350; border-radius:18px;
   background:url("{hero}") center / cover no-repeat; box-shadow:0 0 0 1px rgba(80,220,255,0.18), 0 20px 60px rgba(0,0,0,0.6);}}
.lln-h .ttl {{position:absolute; top:2.2%; left:50%; transform:translateX(-50%); width:min(80%, 1080px);
   filter: drop-shadow(0 0 16px rgba(80,220,255,0.55)) drop-shadow(0 0 40px rgba(120,110,255,0.25));}}
.lln-h .ttl .edge {{padding:2px; clip-path:polygon(3.2% 0, 96.8% 0, 100% 50%, 96.8% 100%, 3.2% 100%, 0 50%);
   background:linear-gradient(90deg, #50DCFF 0%, #9AF0FF 30%, #A97BFF 70%, #50DCFF 100%);}}
.lln-h .ttl .core {{clip-path:polygon(3.2% 0, 96.8% 0, 100% 50%, 96.8% 100%, 3.2% 100%, 0 50%);
   background:radial-gradient(ellipse at 50% 0%, rgba(80,220,255,0.22), transparent 65%),
              linear-gradient(180deg, rgba(10,30,48,0.94), rgba(4,14,26,0.94));
   padding:clamp(5px, 0.7vw, 10px) 6%; display:flex; align-items:center; justify-content:center; gap:18px;}}
.lln-h .ttl .bar {{flex:0 0 clamp(30px, 6vw, 90px); height:2px; border-radius:2px;
   background:linear-gradient(90deg, transparent, #50DCFF);}}
.lln-h .ttl .bar.r {{background:linear-gradient(90deg, #A97BFF, transparent);}}
.lln-h .ttl h1 {{margin:0; padding:0; font-size:clamp(1.4rem, 2.7vw, 2.6rem); font-weight:800; letter-spacing:0.02em;
   background:linear-gradient(90deg, #FFFFFF 0%, #BFF4FF 55%, #D4C4FF 100%); -webkit-background-clip:text;
   background-clip:text; color:transparent; white-space:nowrap;}}
.lln-h .ttl .ic {{filter:drop-shadow(0 0 8px rgba(80,220,255,0.9));}}
.lln-h .btns {{position:absolute; left:3%; right:3%; bottom:3%; display:flex; gap:3%;}}
.lln-h .btns a {{flex:1; display:flex; align-items:center; justify-content:space-between; gap:14px; text-decoration:none;
   padding:clamp(4px, 0.55vw, 9px) clamp(14px, 1.8vw, 28px); border-radius:14px; background:rgba(5,16,28,0.82);
   color:#F4FAFC !important; font-weight:700; font-size:clamp(0.9rem, 1.25vw, 1.25rem); backdrop-filter:blur(4px);
   transition:transform .15s ease, box-shadow .15s ease;}}
.lln-h .btns a:hover {{transform:translateY(-3px);}}
.lln-h .btns a .ic {{font-size:clamp(1.3rem, 1.9vw, 1.9rem);}}
.lln-h .btns a .lb {{flex:1; text-align:left;}}
.lln-h .b1 {{border:1.5px solid #4FA3FF; box-shadow:0 0 20px rgba(79,163,255,0.45);}} .lln-h .b1 .ic, .lln-h .b1 .ar {{color:#4FA3FF;}}
.lln-h .b2 {{border:1.5px solid #A97BFF; box-shadow:0 0 20px rgba(169,123,255,0.45);}} .lln-h .b2 .ic, .lln-h .b2 .ar {{color:#B58CFF;}}
.lln-h .b3 {{border:1.5px solid #2DD4BF; box-shadow:0 0 20px rgba(45,212,191,0.45);}} .lln-h .b3 .ic, .lln-h .b3 .ar {{color:#2DD4BF;}}
.lln-h .hs {{position:absolute; cursor:help; border-radius:8px; z-index:5;}}
.lln-h .hs:hover {{box-shadow:0 0 0 2px #7FE6FF, 0 0 18px rgba(80,220,255,0.7);}}
.lln-h .hs .tip {{display:none; position:absolute; top:calc(100% + 10px); left:50%; transform:translateX(-50%);
   width:340px; padding:14px 16px; border-radius:12px; background:rgba(5,16,28,0.97); z-index:20;
   border:1.5px solid rgba(80,220,255,0.8); box-shadow:0 10px 30px rgba(0,0,0,0.6), 0 0 18px rgba(80,220,255,0.3);
   color:#DCE9EF; font-size:0.86rem; line-height:1.4; text-align:left; pointer-events:none;}}
.lln-h .hs:hover .tip {{display:block;}}
.lln-h .hs .tn {{font-weight:800; font-size:1.05rem; color:#7FE6FF; margin-bottom:4px;}}
.lln-h .hs .tx {{margin-bottom:6px;}} .lln-h .hs .why {{color:#B9CCD6;}}
.lln-h .hs .tl {{color:#F5A524; font-weight:700; font-size:0.8rem; margin-top:4px;}}
.lln-h .hs .tm {{margin-bottom:6px;}} .lln-h .hs .tm b {{color:#F4FAFC;}}
.lln-h .hs .tf {{color:#7F95A2; font-size:0.74rem;}}
.lln-credit {{text-align:right; color:#6F8592; font-size:0.76rem; margin:6px 4px 0 0;}}
</style>""", unsafe_allow_html=True)

st.markdown(
    '<div class="lln-h">' + hotspots +
    f'<div class="ttl"><div class="edge"><div class="core"><span class="bar"></span>'
    f'<span class="ic">{ui.mi("rocket_launch", 38, "#7FE6FF")}</span><h1>Lunar Landing Site Navigator</h1>'
    '<span class="bar r"></span></div></div></div>'
    '<div class="btns">'
    f'<a class="b1" href="mission" target="_self"><span class="ic">{ui.mi("bar_chart", 32, "#4FA3FF")}</span>'
    f'<span class="lb">Mission Dashboard</span><span class="ar">{ui.mi("arrow_forward", 24, "#4FA3FF")}</span></a>'
    f'<a class="b2" href="date_finder" target="_self"><span class="ic">{ui.mi("calendar_month", 32, "#B58CFF")}</span>'
    f'<span class="lb">Best Date Finder</span><span class="ar">{ui.mi("arrow_forward", 24, "#B58CFF")}</span></a>'
    f'<a class="b3" href="validation" target="_self"><span class="ic">{ui.mi("settings", 32, "#2DD4BF")}</span>'
    f'<span class="lb">Data Validation</span><span class="ar">{ui.mi("arrow_forward", 24, "#2DD4BF")}</span></a>'
    '</div></div>'
    '<div class="lln-credit">Rendered from NASA LOLA terrain (Lunar Reconnaissance Orbiter) · sites: USGS Artemis III '
    'regions · Sun placement illustrative</div>', unsafe_allow_html=True)

ui.footer(link=False)
