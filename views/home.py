"""Home — title, an orbital view of the south pole with the candidate sites, and three ways in."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

import streamlit as st

import ui_common as ui

ui.setup_page()
ROOT = Path(__file__).resolve().parent.parent
hero = ui._data_uri(ROOT / "assets" / "home_moon.jpg", "image/jpeg")
stars = ui._data_uri(ROOT / "assets" / "stars.jpg", "image/jpeg")
names = ui.names()
srow = ui.sites_df().set_index("site_id")

# what each site is, and why its region is a candidate (NASA gave one shared rationale for all nine regions)
ABOUT = {
    "peak_near_cabeus_b": "A high peak beside Cabeus B crater, close to Cabeus crater, where NASA's LCROSS impact "
                          "in 2009 detected water.",
    "haworth": "A site on the edge of Haworth crater, one of the large, permanently shadowed craters near the "
               "south pole.",
    "malapert_massif": "A broad mountain massif that rises among the highest ground near the south pole.",
    "mons_mouton": "A wide, flat-topped mountain named in honour of NASA mathematician Melba Mouton.",
    "nobile_rim_1": "A site on the rim of Nobile, a large crater in the south polar region.",
    "nobile_rim_2": "A second site on the rim of Nobile crater, on a different stretch of the rim.",
    "de_gerlache_rim_2": "A site on the rim of de Gerlache crater, right next to Shackleton crater and the pole.",
    "slater_plain": "A comparatively smooth plain near Slater crater.",
}
WHY = ("NASA selected this region as one of nine Artemis III candidates in October 2024, using data from the Lunar "
       "Reconnaissance Orbiter. The regions offer diverse geology, some of the Moon's oldest terrain, nearby cold "
       "shadowed areas that may hold water ice, and flexible timing for the mission.")


def tip(sid):
    h = srow.loc[sid, "height_m"] / 1000.0
    return (f'<div class="tip"><div class="tn">{names[sid]}</div>'
            f'<div class="tx">{ABOUT.get(sid, "")} Elevation {h:+.1f} km.</div>'
            f'<div class="tx why">{WHY}</div></div>')


hot = json.loads((ROOT / "assets" / "home_moon_labels.json").read_text())
hotspots = "".join(
    f'<div class="hs" style="left:{h_["x"] * 100:.2f}%;top:{h_["y"] * 100:.2f}%;width:{h_["w"] * 100:.2f}%;'
    f'height:{h_["h"] * 100:.2f}%">{tip(h_["site_id"])}</div>' for h_ in hot if h_["site_id"] in names)

st.markdown(f"""<style>
[data-testid="stAppViewContainer"] {{background:#02060C url("{stars}") center / cover fixed;}}
.lln-h {{position:relative; width:100%; aspect-ratio: 2400 / 1350; border-radius:18px;
   background:url("{hero}") center / cover no-repeat; box-shadow:0 0 0 1px rgba(80,220,255,0.18), 0 20px 60px rgba(0,0,0,0.6);}}
:is(.lln-h, .lln-ov) .ttl {{position:absolute; top:2.2%; left:50%; transform:translateX(-50%); width:min(80%, 1080px);
   filter: drop-shadow(0 0 16px rgba(80,220,255,0.55)) drop-shadow(0 0 40px rgba(120,110,255,0.25));}}
:is(.lln-h, .lln-ov) .ttl .edge {{padding:2px; clip-path:polygon(3.2% 0, 96.8% 0, 100% 50%, 96.8% 100%, 3.2% 100%, 0 50%);
   background:linear-gradient(90deg, #50DCFF 0%, #9AF0FF 30%, #A97BFF 70%, #50DCFF 100%);}}
:is(.lln-h, .lln-ov) .ttl .core {{clip-path:polygon(3.2% 0, 96.8% 0, 100% 50%, 96.8% 100%, 3.2% 100%, 0 50%);
   background:radial-gradient(ellipse at 50% 0%, rgba(80,220,255,0.22), transparent 65%),
              linear-gradient(180deg, rgba(10,30,48,0.94), rgba(4,14,26,0.94));
   padding:clamp(5px, 0.7vw, 10px) 6%; display:flex; align-items:center; justify-content:center; gap:18px;}}
:is(.lln-h, .lln-ov) .ttl .bar {{flex:0 0 clamp(30px, 6vw, 90px); height:2px; border-radius:2px;
   background:linear-gradient(90deg, transparent, #50DCFF);}}
:is(.lln-h, .lln-ov) .ttl .bar.r {{background:linear-gradient(90deg, #A97BFF, transparent);}}
:is(.lln-h, .lln-ov) .ttl h1 {{margin:0; padding:0; font-size:clamp(1.4rem, 2.7vw, 2.6rem); font-weight:800; letter-spacing:0.02em;
   background:linear-gradient(90deg, #FFFFFF 0%, #BFF4FF 55%, #D4C4FF 100%); -webkit-background-clip:text;
   background-clip:text; color:transparent; white-space:nowrap;}}
:is(.lln-h, .lln-ov) .ttl .ic {{filter:drop-shadow(0 0 8px rgba(80,220,255,0.9));}}
:is(.lln-h, .lln-ov) .btns {{position:absolute; left:3%; right:3%; bottom:3%; display:flex; gap:3%;}}
:is(.lln-h, .lln-ov) .btns a {{flex:1; display:flex; align-items:center; justify-content:space-between; gap:14px; text-decoration:none;
   padding:clamp(4px, 0.55vw, 9px) clamp(14px, 1.8vw, 28px); border-radius:14px; background:rgba(5,16,28,0.82);
   color:#F4FAFC !important; font-weight:700; font-size:clamp(0.9rem, 1.25vw, 1.25rem); backdrop-filter:blur(4px);
   transition:transform .15s ease, box-shadow .15s ease;}}
:is(.lln-h, .lln-ov) .btns a:hover {{transform:translateY(-3px);}}
:is(.lln-h, .lln-ov) .btns a .ic {{font-size:clamp(1.3rem, 1.9vw, 1.9rem);}}
:is(.lln-h, .lln-ov) .btns a .lb {{flex:1; text-align:left;}}
:is(.lln-h, .lln-ov) .b1 {{border:1.5px solid #4FA3FF; box-shadow:0 0 20px rgba(79,163,255,0.45);}} :is(.lln-h, .lln-ov) .b1 .ic, :is(.lln-h, .lln-ov) .b1 .ar {{color:#4FA3FF;}}
:is(.lln-h, .lln-ov) .b2 {{border:1.5px solid #A97BFF; box-shadow:0 0 20px rgba(169,123,255,0.45);}} :is(.lln-h, .lln-ov) .b2 .ic, :is(.lln-h, .lln-ov) .b2 .ar {{color:#B58CFF;}}
:is(.lln-h, .lln-ov) .b3 {{border:1.5px solid #2DD4BF; box-shadow:0 0 20px rgba(45,212,191,0.45);}} :is(.lln-h, .lln-ov) .b3 .ic, :is(.lln-h, .lln-ov) .b3 .ar {{color:#2DD4BF;}}
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
.st-key-home_stage {{position:relative; border-radius:18px; overflow:hidden; gap:0 !important;
   background: radial-gradient(circle at 6% 9%, rgba(255,240,200,0.95) 0 1.1%, rgba(255,190,90,0.35) 2.5%,
               rgba(120,80,20,0.12) 9%, transparent 17%), transparent;
   box-shadow:0 0 0 1px rgba(80,220,255,0.18), 0 20px 60px rgba(0,0,0,0.6);}}
.st-key-home_stage [data-testid="stElementContainer"]:has(.lln-ov) {{position:absolute; left:0; right:0; z-index:10;
   pointer-events:none;}}
.st-key-home_stage [data-testid="stElementContainer"]:has(.lln-ov.top) {{top:2%;}}
.st-key-home_stage [data-testid="stElementContainer"]:has(.lln-ov.bot) {{bottom:3%;}}
.st-key-home_stage .lln-ov {{position:relative; height:clamp(48px, 5vw, 70px);}}
.st-key-home_stage .lln-ov .ttl, .st-key-home_stage .lln-ov .btns {{pointer-events:auto;}}
.st-key-home_stage .lln-ov .btns {{bottom:0;}}
.st-key-home_stage .lln-ov .ttl {{top:0;}}
.st-key-home_stage .lln-ov .ttl, .st-key-home_stage .lln-ov .btns {{position:absolute;}}
.st-key-home_reset {{position:absolute !important; top:13%; right:2.5%; z-index:11; width:auto !important;}}
.st-key-home_reset button {{background:rgba(5,16,28,0.85); border:1px solid rgba(80,220,255,0.6); color:#CFF6FF;}}
.lln-credit {{text-align:right; color:#6F8592; font-size:0.76rem; margin:6px 4px 0 0;}}
</style>""", unsafe_allow_html=True)

TITLE = (f'<div class="ttl"><div class="edge"><div class="core"><span class="bar"></span>'
         f'<span class="ic">{ui.mi("rocket_launch", 38, "#7FE6FF")}</span><h1>Lunar Landing Site Navigator</h1>'
         '<span class="bar r"></span></div></div></div>')
BUTTONS = (
    '<div class="btns">'
    f'<a class="b1" href="mission" target="_self"><span class="ic">{ui.mi("bar_chart", 32, "#4FA3FF")}</span>'
    f'<span class="lb">Mission Dashboard</span><span class="ar">{ui.mi("arrow_forward", 24, "#4FA3FF")}</span></a>'
    f'<a class="b2" href="date_finder" target="_self"><span class="ic">{ui.mi("calendar_month", 32, "#B58CFF")}</span>'
    f'<span class="lb">Best Date Finder</span><span class="ar">{ui.mi("arrow_forward", 24, "#B58CFF")}</span></a>'
    f'<a class="b3" href="validation" target="_self"><span class="ic">{ui.mi("settings", 32, "#2DD4BF")}</span>'
    f'<span class="lb">Data Validation</span><span class="ar">{ui.mi("arrow_forward", 24, "#2DD4BF")}</span></a>'
    '</div>')

mode = st.session_state.get("home_mode", "3D Moon")
if mode == "Picture":
    st.markdown('<div class="lln-h">' + hotspots + TITLE + BUTTONS + '</div>', unsafe_allow_html=True)
    credit = "Rendered from NASA LOLA terrain (Lunar Reconnaissance Orbiter)"
else:
    import numpy as np
    import plotly.graph_objects as go

    def wrap(text, n=46):
        out, line = [], ""
        for w in text.split():
            if len(line) + len(w) + 1 > n:
                out.append(line); line = w
            else:
                line = f"{line} {w}".strip()
        return "<br>".join(out + [line])

    CAM = dict(lat=-60.0, dist=0.78, depth=0.42)     # picture-like start: across the pole, horizon on top
    HOME_EXAG = 3.0

    def home_globe(rev):
        sphere, capxyz, regxyz = ui._globe_mesh(HOME_EXAG)
        pole_u = np.array([0.0, 0.0, -1.0])
        center = pole_u * CAM["depth"]                                  # pivot inside the Moon, under the pole
        eye = np.array(ui._latlon_xyz(CAM["lat"], 165.0, 1.0)) * CAM["dist"]
        f_ = center - eye; f_ /= np.linalg.norm(f_)                     # view direction
        up = pole_u - (pole_u @ f_) * f_; up /= np.linalg.norm(up)       # pole toward the top of the screen
        right = np.cross(f_, up)
        sun = -0.35 * f_ - 0.90 * right + 0.30 * up                    # from the upper left (illustrative)
        sun /= np.linalg.norm(sun)
        light = dict(x=float(sun[0] * 1e5), y=float(sun[1] * 1e5), z=float(sun[2] * 1e5))
        lit = dict(ambient=0.06, diffuse=1.0, specular=0.02, roughness=0.95, fresnel=0.0)
        moon = [[0, "#4E4C49"], [0.35, "#7A7772"], [0.7, "#A19D96"], [1, "#C9C5BD"]]
        rng = np.random.default_rng(3)

        def mottle(shape, scales=((3, 0.5), (8, 0.3), (20, 0.2))):
            from PIL import Image as _I, ImageFilter as _F
            out = np.zeros(shape)
            for blur, wgt in scales:
                r = (rng.random(shape) * 255).astype(np.uint8)
                g = np.asarray(_I.fromarray(r).filter(_F.GaussianBlur(blur)), float)
                out += wgt * (g - g.mean()) / (g.std() + 1e-6)
            return 0.55 + 0.17 * out

        fig = go.Figure()
        for (x, y, z) in (sphere, capxyz, regxyz):
            fig.add_trace(go.Surface(x=x, y=y, z=z, surfacecolor=np.clip(mottle(np.shape(z)), 0, 1), cmin=0, cmax=1,
                                     colorscale=moon, showscale=False, hoverinfo="skip", lighting=lit,
                                     lightposition=light))
        ids = list(names)
        pts = np.array(ui._latlon_xyz(srow.loc[ids, "lat_deg"].values, srow.loc[ids, "lon_deg"].values,
                                      ui.R_MOON_KM + srow.loc[ids, "height_m"].astype(float).values / 1000
                                      * HOME_EXAG + 6)).T
        fig.add_trace(go.Scatter3d(x=pts[:, 0], y=pts[:, 1], z=pts[:, 2], mode="markers", hoverinfo="skip",
                                   marker=dict(size=7, color="#E6FCFF", line=dict(color="#50DCFF", width=4))))
        sx_, sy_ = pts @ right, pts @ up                              # screen-plane coordinates (km)
        cx_, cy_ = sx_.mean(), sy_.mean()
        order = np.argsort(np.arctan2(sy_ - cy_, sx_ - cx_))
        anns = []
        for rank, k in enumerate(order):
            sid = ids[k]
            ang = np.arctan2(sy_[k] - cy_, sx_[k] - cx_)
            if np.hypot(sx_[k] - cx_, sy_[k] - cy_) < 8:              # a site at the centre: label straight down
                ang = -np.pi / 2
            rr_ = 1.0 + 0.7 * (rank % 2)
            ox, oy = 125 * rr_ * np.cos(ang), 95 * rr_ * np.sin(ang)
            anns.append(dict(
                x=float(pts[k, 0]), y=float(pts[k, 1]), z=float(pts[k, 2]), text=f"<b>{names[sid]}</b>",
                showarrow=True, arrowcolor="#50DCFF", arrowwidth=2, arrowhead=0, ax=int(ox), ay=int(-oy),
                bgcolor="rgba(6,22,36,0.92)", bordercolor="#6EE1FF", borderwidth=1.5, borderpad=5,
                font=dict(color="#F0F8FC", size=13, family=ui.FONT),
                hovertext=(f"<b>{names[sid]}</b><br>{wrap(ABOUT.get(sid, ''))} Elevation "
                           f"{srow.loc[sid, 'height_m'] / 1000:+.1f} km.<br><br>{wrap(WHY)}"),
                hoverlabel=dict(bgcolor="rgba(5,16,28,0.97)", bordercolor="#50DCFF",
                                font=dict(color="#DCE9EF", size=12, family=ui.FONT))))
        L = 1.08 * ui.R_MOON_KM
        ax = dict(visible=False, range=[-L, L])
        fig.update_layout(height=800, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                          showlegend=False, uirevision=f"home-globe-{rev}", hoverlabel=dict(align="left"),
                          scene=dict(bgcolor="rgba(0,0,0,0)", aspectmode="cube", xaxis=ax, yaxis=ax, zaxis=ax,
                                     dragmode="orbit", annotations=anns,
                                     camera=dict(center=dict(zip("xyz", map(float, center))),
                                                 eye=dict(zip("xyz", map(float, eye))),
                                                 up=dict(zip("xyz", map(float, up))))))
        return fig

    rev = st.session_state.get("home_globe_rev", 0)
    with st.container(key="home_stage"):
        st.markdown('<div class="lln-ov top">' + TITLE + '</div>', unsafe_allow_html=True)
        if st.button("Reset view", icon=":material/restart_alt:", key="home_reset"):
            st.session_state["home_globe_rev"] = rev + 1
            st.rerun()
        st.plotly_chart(home_globe(rev), width="stretch", key=f"home_globe_{rev}",
                        config={"displayModeBar": False, "scrollZoom": True})
        st.markdown('<div class="lln-ov bot">' + BUTTONS + '</div>', unsafe_allow_html=True)
    credit = ("NASA LOLA terrain on the south polar cap (heights ×3), smooth sphere elsewhere · drag to rotate, "
              "scroll to zoom")

c1, c2 = st.columns([1, 4], vertical_alignment="center")
c1.segmented_control("Home view", ["3D Moon", "Picture"], key="home_mode", default="3D Moon",
                     label_visibility="collapsed")
c2.markdown(f'<div class="lln-credit">{credit} · sites: USGS Artemis III regions · Sun placement illustrative</div>',
            unsafe_allow_html=True)

ui.footer(link=False)
