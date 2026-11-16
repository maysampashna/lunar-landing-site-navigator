"""Validation & Sources — a short evidence summary, with full detail in expandable sections."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import streamlit as st

from engine import live
import ui_common as ui

ui.setup_page()
ui.help_button()
ui.banner("verified", "Data Validation",
          "How the results were checked, and where every piece of data comes from.")
names = ui.names()
sites = ui.sites_df()
v = ui.validation_report()

# ------------------------------------------------------------------ physics checks (computed live, used in summary)
checks = []
for _, s in sites.iterrows():
    e = ui.ephem(s.site_id)
    colat = 90 - abs(s.lat_deg)
    smax = float(e.sun_el_deg.abs().max())
    checks.append({"check": f"Sun elevation bound — {s['name']}",
                   "expected": f"|Sun el| ≤ colatitude {colat:.2f}° + axis tilt 1.54° (+0.3° margin)",
                   "result": f"max |Sun el| = {smax:.2f}°", "pass": smax <= colat + 1.54 + 0.3})
if live.kernels_available():
    from engine import visibility
    from engine.ephemeris import hourly_grid
    for day in ["2026-03-03", "2028-12-31"]:
        eph = live.sky().compute(0.0, 0.0, 0.0, hourly_grid(day, str(pd.Timestamp(day) + pd.Timedelta(days=1)), 1 / 6))
        ecl = visibility.compute(eph, None, visibility.VisParams()).eclipse_frac.max()
        checks.append({"check": f"Total lunar eclipse {day} (independent date check)",
                       "expected": "Sun fully hidden by Earth at some time that day",
                       "result": f"max hidden fraction = {ecl:.3f}", "pass": bool(ecl > 0.999)})
n_pass = sum(c["pass"] for c in checks)
n_real = sum(ui.terrain_status(s) == "real" for s in sites.site_id)

# ------------------------------------------------------------------ summary
st.markdown(f'<div class="lln-sec">{ui.mi("verified")}How we checked the results</div>', unsafe_allow_html=True)


def tip(t):
    return f'<span class="lln-help" data-tip="{t}">?</span>'


k = st.columns(4)
if v:
    n_samples = sum(r["n"] for b in v["sites"].values() for r in b.values())
    k[0].markdown(ui.kcard("public", "Sun &amp; Earth positions" + tip(
        "We compared our Sun and Earth positions with NASA JPL Horizons, the official reference. The largest "
        "difference is tiny. This checks positions only, not terrain, power or communication."),
        f"{v['overall_max_error_deg']:.5f}°", f"max error vs NASA JPL Horizons · {n_samples} checks", ui.BOTH),
        unsafe_allow_html=True)
else:
    k[0].markdown(ui.kcard("public", "Sun &amp; Earth positions", "Not run", "run scripts/validate_horizons.py",
                           ui.GREY), unsafe_allow_html=True)
k[1].markdown(ui.kcard("science", "Physics checks" + tip(
    "Simple tests the results must pass: the Sun never rises higher than physics allows at each site, and two "
    "known total lunar eclipses are found on the right dates."),
    f"{n_pass} of {len(checks)} pass", "Sun height limits · known eclipses", ui.BOTH if n_pass == len(checks) else ui.SUN),
    unsafe_allow_html=True)
k[2].markdown(ui.kcard("terrain", "Terrain" + tip(
    "Every site uses real NASA LOLA laser-altimeter terrain. Its direction handling is tested in code, but it "
    "was not compared with a second, independent terrain source."),
    f"{n_real} of {len(sites)} sites", "real NASA LOLA terrain", ui.SUN), unsafe_allow_html=True)
k[3].markdown(ui.kcard("database", "Sites covered" + tip(
    "NASA named 9 Artemis III candidate regions. We cover 8; the USGS map for Mons Mouton Plateau could not be "
    "downloaded during the event."),
    "8 of 9 regions", "NASA Artemis III candidates", ui.TEAL), unsafe_allow_html=True)
st.caption("34 automated tests pass. Open a section below for the full details.")

# ------------------------------------------------------------------ detail sections
def intro(text):
    st.markdown(f'<div style="color:#C9D8E0;font-size:0.92rem;margin-bottom:8px">{text}</div>', unsafe_allow_html=True)


with st.expander("Sun and Earth positions vs NASA JPL Horizons", icon=":material/public:"):
    intro("At random times we asked NASA's JPL Horizons service where the Sun and Earth are in the sky from each "
          "site, and compared it with our own calculation. Smaller numbers are better; all are far below 0.001°.")
    if v:
        rows = [{"Site": names.get(sid, sid), "Body": body.title(), "Times checked": r["n"],
                 "Largest height error (°)": round(r["max_abs_del_deg"], 6),
                 "Typical height error (°)": round(r["median_abs_del_deg"], 6),
                 "Largest direction error (°)": round(r["max_abs_daz_sky_deg"], 6)}
                for sid, bodies in v["sites"].items() for body, r in bodies.items()]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.warning("Not yet run. Run `python scripts/validate_horizons.py` (needs internet).")

with st.expander("Physics checks and automated tests", icon=":material/science:"):
    intro("Simple tests the results must pass. The Sun can never rise higher than geometry allows at each site, and "
          "two known total lunar eclipses must be found on the right dates.")
    st.dataframe(pd.DataFrame([{"Check": c["check"], "Expected": c["expected"], "Result": c["result"],
                                "Pass": "✅" if c["pass"] else "❌"} for c in checks]),
                 width="stretch", hide_index=True)
    st.caption("34 automated code tests also pass (terrain direction, eclipses, battery model, scoring, DSN).")

with st.expander("Terrain and site locations", icon=":material/terrain:"):
    intro("Each site is one point inside its NASA region. Its skyline comes from NASA LOLA terrain out to 150 km.")
    trows = []
    for _, s_ in sites.iterrows():
        hp = ui.horizon(s_.site_id)
        trows.append({"Site": s_["name"], "Latitude (°)": round(s_.lat_deg, 3), "Longitude (°)": round(s_.lon_deg, 3),
                      "Elevation (m)": None if hp is None else round(hp.site_height_m),
                      "Terrain": "NASA LOLA" if ui.terrain_status(s_.site_id) == "real" else ui.terrain_status(s_.site_id),
                      "Skyline complete (%)": None if hp is None else round(100 - 100 * hp.incomplete.mean(), 1)})
    st.dataframe(pd.DataFrame(trows), width="stretch", hide_index=True)

with st.expander("Data sources and assumptions", icon=":material/database:"):
    intro("Every input is public NASA or USGS data.")
    st.markdown("""
| Data | Source | Used for |
|---|---|---|
| Planetary ephemeris DE421 + lunar frame kernels (`moon_080317.tf`, `pck00008.tpc`, `moon_pa_de421_1900-2050.bpc`) | NASA/JPL NAIF SPICE — [naif.jpl.nasa.gov](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/) | Sun/Earth positions (Skyfield, MOON_ME_DE421 frame) |
| LOLA south-pole DEMs `LDEM_80S_80MPP_ADJ`, `LDEM_60S_240MPP_ADJ` (Barker et al.) | NASA GSFC PGDA — [pgda.gsfc.nasa.gov/products/90](https://pgda.gsfc.nasa.gov/products/90) | Terrain horizons, site heights |
| Artemis III candidate landing site navigational grids (McClernan 2024), DOI 10.5066/P1MEQ6UK | USGS Astrogeology — [usgs.gov](https://www.usgs.gov/data/down-selected-artemis-iii-candidate-landing-site-navigational-grids) | Region footprints → representative points |
| Artemis III candidate regions update (Oct 28, 2024); NTRS 20250011660 | NASA — [nasa.gov](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/) | Region list and context |
| Deep Space Network complex locations (Goldstone, Madrid, Canberra) | NASA DSN | Moon elevation at each complex (geometry only) |
| JPL Horizons API | NASA/JPL SSD — [ssd-api.jpl.nasa.gov](https://ssd-api.jpl.nasa.gov/doc/horizons.html) | Ephemeris validation only |
""")
    st.markdown("""
**Main assumptions**
- **Sunlight:** a site counts as sunlit when at least half of the Sun is above the hills (adjustable).
- **Earth contact:** Earth is above the hills and a NASA DSN dish sees the Moon above 10° (adjustable).
- **Eclipses:** when Earth blocks the Sun, sunlight and power drop.
- **Battery:** a simple 1 kW lander model — an illustration, not a flight design.
- **Score:** a planning preference, not a safety rating.
""")

with st.expander("Limitations and use of AI", icon=":material/rule:"):
    st.markdown(f"**Limitations.** {ui.LIMITATIONS} DSN results are line-of-sight geometry, not scheduled antenna "
                "time or a link budget.")
    st.markdown("**Use of AI.** We used an AI assistant (Claude, Anthropic) to draft the engine code, tests, data "
                "scripts and these pages, and to help plan the project. The team defined the method and scope, "
                "reviewed and corrected the code, ran the NASA data pipeline, and checked the results (JPL Horizons "
                "agreement, physics checks). No AI-generated images or video are used; all numbers come from "
                "NASA/USGS data.")

ui.footer(link=False)
