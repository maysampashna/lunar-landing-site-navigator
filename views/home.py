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
    "peak_near_cabeus_b": "A high peak overlooking Cabeus crater, where NASA's LCROSS impactor detected water in "
                          "2009. Its height lifts it above much of the surrounding shadow while keeping it close "
                          "to some of the most promising ice deposits at the pole.",
    "haworth": "Beside Haworth, a large crater whose floor never sees sunlight. Landing here would put crews within "
               "reach of one of the south pole's permanently shadowed, potentially ice-bearing craters.",
    "malapert_massif": "One of the highest summits near the pole, on the Earth-facing side of the Moon at almost "
                       "exactly 0° longitude, which helps keep Earth above the horizon for communication. "
                       "Intuitive Machines' IM-1 lander touched down near Malapert A crater in February 2024.",
    "mons_mouton": "A flat-topped mountain with a broad summit plateau, named in 2022 after NASA mathematician "
                   "Melba Roy Mouton. It was the planned destination of NASA's VIPER rover, and Intuitive "
                   "Machines' Athena lander touched down on it in March 2025.",
    "nobile_rim_1": "On the rim of Nobile crater, right next to the Mons Mouton plateau. The rim crest stands high "
                    "above the dark crater floor, combining good sunlight and line of sight with easy access to "
                    "shadowed terrain.",
    "nobile_rim_2": "A lower stretch of Nobile's rim on its far, eastern side and the farthest site from the pole. "
                    "Comparing it with Nobile Rim 1 shows how much elevation alone changes sunlight and Earth "
                    "visibility.",
    "de_gerlache_rim_2": "The closest site to the pole, on the rim of de Gerlache crater next to Shackleton. The "
                         "ridges between these two craters are known for some of the longest periods of sunlight "
                         "anywhere at the lunar south pole.",
    "slater_plain": "A comparatively smooth, low plain near Slater crater, on the far-side hemisphere of the Moon. "
                    "Smooth ground favours a safe touchdown, while its far-side position makes Earth contact "
                    "a key question to check.",
}
WHY = "One of NASA's nine Artemis III candidate regions (October 2024), chosen with Lunar Reconnaissance Orbiter data."


def where(sid):
    lat, lon, h = srow.loc[sid, "lat_deg"], srow.loc[sid, "lon_deg"], srow.loc[sid, "height_m"]
    km = (90 - abs(lat)) * 3.14159265 / 180 * 1737.4
    return (f"{abs(lat):.1f}°S · {abs(lon):.1f}°{'E' if lon >= 0 else 'W'} · about {km:,.0f} km from the pole · "
            f"elevation {h:+,.0f} m")


def tip(sid):
    h = srow.loc[sid, "height_m"] / 1000.0
    return (f'<div class="tip"><div class="tn">{names[sid]}</div>'
            f'<div class="tf">{where(sid)}</div><div class="tx">{ABOUT.get(sid, "")}</div>'
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

mode = "3D Moon"
if mode == "Picture":
    st.markdown('<div class="lln-h">' + hotspots + TITLE + BUTTONS + '</div>', unsafe_allow_html=True)
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

    CAM = dict(lat=-52.0, dist=0.70, depth=0.43, lift=0.045)     # picture-like start: across the pole, horizon on top
    HOME_EXAG = 3.0
    LABEL = dict(ring=430.0, stem=40.0, lift=60.0, tilt=230.0)               # km: label ring radius, stem height, ring height

    @st.cache_resource
    def home_mesh(exag: float):
        """One seamless south-polar surface (LOLA 60°S cap + finer 80°S site region, tapered to the sphere at
        the rim) plus a plain sphere for the rest of the Moon — no overlapping pieces, so no gaps."""
        t = ui.terrain3d()
        R = ui.R_MOON_KM
        rim = 2 * R * np.tan(np.radians(15.0))                       # 60°S in polar-stereographic km

        def bilinear(grid, ulx, uly, cell, X, Y):
            n0, n1 = grid.shape
            fx = (X - ulx) / cell - 0.5; fy = (uly - Y) / cell - 0.5
            x0 = np.clip(np.floor(fx).astype(int), 0, n1 - 2); y0 = np.clip(np.floor(fy).astype(int), 0, n0 - 2)
            ax_ = np.clip(fx - x0, 0, 1); ay_ = np.clip(fy - y0, 0, 1)
            return (grid[y0, x0] * (1 - ax_) * (1 - ay_) + grid[y0, x0 + 1] * ax_ * (1 - ay_)
                    + grid[y0 + 1, x0] * (1 - ax_) * ay_ + grid[y0 + 1, x0 + 1] * ax_ * ay_)

        rr = np.linspace(0.0, rim, 190) ** 1.0
        th = np.radians(np.linspace(0.0, 360.0, 421))
        RR, TH = np.meshgrid(rr, th, indexing="ij")                     # round grid: the edge is a clean circle
        X, Y = RR * np.sin(TH), RR * np.cos(TH)
        cap = t["cap"].astype(float)
        h = bilinear(cap, *(t["cap_ul"] / 1000.0), X, Y)
        rx0, ry0, rc = t["region_ul"] / 1000.0
        reg = t["region"].astype(float)
        span = reg.shape[0] * rc
        edge = np.minimum.reduce([X - rx0, rx0 + span - X, ry0 - Y, Y - (ry0 - span)])
        wr = np.clip(edge / 25.0, 0, 1)                                 # blend the finer region in over 25 km
        h = np.where(wr > 0, (1 - wr) * h + wr * bilinear(reg, rx0, ry0, rc, X, Y), h)
        rho = np.hypot(X, Y)
        taper = np.clip((rim - rho) / 160.0, 0, 1)
        taper = taper * taper * (3 - 2 * taper)                         # smoothstep to zero height at 60°S
        h = h * taper
        cap_xyz = ui._polar_xyz(X, Y, h, exag)
        la, lo = np.meshgrid(np.linspace(-60.6, 90, 77), np.linspace(0, 360, 145), indexing="ij")
        sphere = ui._latlon_xyz(la, lo, R - 0.4)                       # tucks just under the cap's rim
        r2 = lambda a: tuple(np.round(v, 1) for v in a)                # noqa: E731
        return r2(sphere), r2(cap_xyz)

    def home_globe(rev):
        sphere, capxyz = home_mesh(HOME_EXAG)
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
        for (x, y, z) in (sphere, capxyz):
            fig.add_trace(go.Surface(x=x, y=y, z=z, surfacecolor=np.clip(mottle(np.shape(z)), 0, 1), cmin=0, cmax=1,
                                     colorscale=moon, showscale=False, hoverinfo="skip", lighting=lit,
                                     lightposition=light))
        ids = list(names)
        pts = np.array(ui._latlon_xyz(srow.loc[ids, "lat_deg"].values, srow.loc[ids, "lon_deg"].values,
                                      ui.R_MOON_KM + srow.loc[ids, "height_m"].astype(float).values / 1000
                                      * HOME_EXAG + 6)).T
        fig.add_trace(go.Scatter3d(x=pts[:, 0], y=pts[:, 1], z=pts[:, 2], mode="markers", hoverinfo="skip",
                                   marker=dict(size=7, color="#F4FBFF",
                                               line=dict(color=[ui.site_color(i) for i in ids], width=5))))
        # Labels live in 3D on a ring around the site cluster, in the same angular order as the sites, so the
        # leaders never cross however the Moon is turned. Each leader: a short vertical stem, then an arm out.
        Rm = ui.R_MOON_KM
        nrm = pts.mean(axis=0); nrm /= np.linalg.norm(nrm)             # local vertical at the cluster
        e1 = np.cross(nrm, [1.0, 0.0, 0.0]); e1 /= np.linalg.norm(e1)
        e2 = np.cross(nrm, e1)
        rel = pts - np.outer(pts @ nrm, nrm)
        ang = np.arctan2(rel @ e2, rel @ e1)
        order = np.argsort(ang)
        n_ = len(order)
        step = 2 * np.pi / n_
        base = np.angle(np.mean(np.exp(1j * (ang[order] - step * np.arange(n_)))))
        RING, STEM, LIFT = LABEL["ring"], LABEL["stem"], LABEL["lift"]
        cam_h = eye - (eye @ nrm) * nrm; cam_h /= np.linalg.norm(cam_h)     # toward the starting camera
        anns, label_colors = [], []
        hov_x, hov_c, hov_t = [], [], []
        for rank, k in enumerate(order):
            sid = ids[k]
            col = ui.site_color(sid)
            label_colors.append(col)
            t_ = base + step * rank
            up_k = pts[k] / np.linalg.norm(pts[k])
            top = pts[k] + up_k * STEM                                  # top of the vertical stem
            hdir = np.cos(t_) * e1 + np.sin(t_) * e2
            lift_k = LIFT + LABEL["tilt"] * (1 - hdir @ cam_h) / 2          # near side low, far side high
            anchor = nrm * Rm + RING * hdir
            anchor = anchor / np.linalg.norm(anchor) * (Rm + lift_k)
            line = np.array([pts[k], top, anchor])
            fig.add_trace(go.Scatter3d(x=line[:, 0], y=line[:, 1], z=line[:, 2], mode="lines", hoverinfo="skip",
                                       line=dict(color=col, width=4)))
            anns.append(dict(
                x=float(anchor[0]), y=float(anchor[1]), z=float(anchor[2]),
                text=f"<span style='color:{col}'>●</span>  <b>{names[sid]}</b>", showarrow=False,
                xanchor="center", yanchor="middle",
                bgcolor="rgba(6,20,36,0.82)", bordercolor=col, borderwidth=1.5, borderpad=8,
                font=dict(color="#F2FAFD", size=13.5, family=ui.FONT),
))
            hov_x.append(anchor); hov_c.append(col)
            hov_t.append(f"<b>{names[sid]}</b><br><span style='color:{col}'>{wrap(where(sid), 52)}</span>"
                         f"<br><br>{wrap(ABOUT.get(sid, ''), 52)}<br><br><i>{wrap(WHY, 52)}</i>")
        hx = np.array(hov_x)
        fig.add_trace(go.Scatter3d(x=hx[:, 0], y=hx[:, 1], z=hx[:, 2], mode="markers", hovertext=hov_t,
                                   hoverinfo="text", marker=dict(size=26, color="#06182A", opacity=0.01),
                                   hoverlabel=dict(bgcolor="rgba(4,14,26,0.96)", bordercolor=hov_c, align="left",
                                                   font=dict(color="#E2EEF3", size=13, family=ui.FONT))))
        L = 1.22 * ui.R_MOON_KM                                     # room for the label ring above the pole
        ks = 1.08 / 1.22                                            # keep the same framing as before
        ax = dict(visible=False, range=[-L, L], showspikes=False)
        fig.update_layout(height=800, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                          showlegend=False, uirevision=f"home-globe-{rev}", hoverlabel=dict(align="left"),
                          scene=dict(bgcolor="rgba(0,0,0,0)", aspectmode="cube", xaxis=ax, yaxis=ax, zaxis=ax,
                                     dragmode="orbit", annotations=anns,
                                     camera=dict(center=dict(zip("xyz", map(float, (center + up * CAM["lift"]) * ks))),
                                                 eye=dict(zip("xyz", map(float, (eye + up * CAM["lift"]) * ks))),
                                                 up=dict(zip("xyz", map(float, up))))))
        fig.update_traces(contours_x_highlight=False, contours_y_highlight=False, contours_z_highlight=False,
                          selector=dict(type="surface"))
        return fig, label_colors

    rev = st.session_state.get("home_globe_rev", 0)
    with st.container(key="home_stage"):
        st.markdown('<div class="lln-ov top">' + TITLE + '</div>', unsafe_allow_html=True)
        if st.button("Reset view", icon=":material/restart_alt:", key="home_reset"):
            st.session_state["home_globe_rev"] = rev + 1
            st.rerun()
        fig_g, label_colors = home_globe(rev)
        css = "".join(
            f'.st-key-home_stage .annotation-scene[data-index="{i_}"] rect.bg {{rx:11px; ry:11px; '
            f'filter:drop-shadow(0 0 5px {c_}) drop-shadow(0 0 14px {c_}66); transition:filter .15s;}}'
            f'.st-key-home_stage .annotation-scene[data-index="{i_}"]:hover rect.bg {{fill-opacity:0.98 !important; '
            f'filter:drop-shadow(0 0 8px {c_}) drop-shadow(0 0 22px {c_});}}'
            f'.st-key-home_stage .annotation-scene[data-index="{i_}"] .annotation-arrow-g path '
            f'{{filter:drop-shadow(0 0 3px {c_});}}'
            for i_, c_ in enumerate(label_colors))
        st.markdown(f"<style>{css}.st-key-home_stage .annotation-text {{letter-spacing:0.02em;}}</style>",
                    unsafe_allow_html=True)
        st.plotly_chart(fig_g, width="stretch", key=f"home_globe_{rev}",
                        config={"displayModeBar": False, "scrollZoom": True})
        st.markdown('<div class="lln-ov bot">' + BUTTONS + '</div>', unsafe_allow_html=True)


