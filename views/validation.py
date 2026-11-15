"""Validation & Sources — evidence for every number in the app."""
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
ui.banner("fact_check", "Validation & Sources", "Evidence behind every number: JPL Horizons comparison, physics checks, terrain status, data citations and AI use.", ui.validated_pill())
names = ui.names()
sites = ui.sites_df()

# ------------------------------------------------------------------ 1. ephemeris vs Horizons
st.markdown(f'<div class="lln-sec">{ui.mi("verified")}1 · Ephemeris validation vs JPL Horizons (positions only)</div>', unsafe_allow_html=True)
v = ui.validation_report()
if v:
    rows = [{"site": names.get(sid, sid), "body": body, "n": r["n"],
             "max |ΔEl| (°)": r["max_abs_del_deg"], "median |ΔEl| (°)": r["median_abs_del_deg"],
             "max |ΔAz·cos El| (°)": r["max_abs_daz_sky_deg"]}
            for sid, bodies in v["sites"].items() for body, r in bodies.items()]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.success(f"Overall max error {v['overall_max_error_deg']:.5f}° (generated {v.get('generated_utc', '?')})")
else:
    st.warning("Not yet run. Run `python scripts/validate_horizons.py` (needs internet) to compare our Skyfield "
               "positions with JPL Horizons topocentric az/el at random times.")
st.caption("This checks Sun/Earth positions only — not terrain, visibility or power.")

# ------------------------------------------------------------------ 2. built-in physics checks
st.markdown(f'<div class="lln-sec">{ui.mi("science")}2 · Built-in physics checks (computed live)</div>', unsafe_allow_html=True)
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
st.dataframe(pd.DataFrame(checks), width="stretch", hide_index=True)
st.caption("Terrain orientation is unit-tested with synthetic mountains at known bearings from several "
           "longitudes (tests/test_engine.py), guarding against rotated horizons from the polar-stereographic grid.")

# ------------------------------------------------------------------ 3. terrain status
st.markdown(f'<div class="lln-sec">{ui.mi("terrain")}3 · Terrain horizons and site points</div>', unsafe_allow_html=True)
trows = []
for _, s in sites.iterrows():
    hp = ui.horizon(s.site_id)
    trows.append({"site": s["name"], "lat": s.lat_deg, "lon": s.lon_deg,
                  "terrain": ui.terrain_status(s.site_id),
                  "rays incomplete (%)": None if hp is None else round(100 * hp.incomplete.mean(), 1),
                  "min coverage (km)": None if hp is None else round(float(np.nanmin(hp.coverage_km)), 1),
                  "site height (m)": None if hp is None else round(hp.site_height_m, 1),
                  "provisional point": s.provisional, "point source": s.source})
st.dataframe(pd.DataFrame(trows), width="stretch", hide_index=True)
st.caption("Horizons: LOLA 80 m DEM near field + 240 m far field to 150 km, observer 2 m above the surface, rays "
           "along local geographic bearings. Missing terrain is flagged; results that missing terrain could change "
           "are 'uncertain' and excluded from confident rankings.")

# ------------------------------------------------------------------ 4. sources
st.markdown(f'<div class="lln-sec">{ui.mi("database")}4 · Data sources</div>', unsafe_allow_html=True)
st.markdown("""
| Data | Source | Used for |
|---|---|---|
| Planetary ephemeris DE421 + lunar frame kernels (`moon_080317.tf`, `pck00008.tpc`, `moon_pa_de421_1900-2050.bpc`) | NASA/JPL NAIF SPICE — [naif.jpl.nasa.gov](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/) | Sun/Earth positions (Skyfield, MOON_ME_DE421 frame) |
| LOLA south-pole DEMs `LDEM_80S_80MPP_ADJ`, `LDEM_60S_240MPP_ADJ` (Barker et al.) | NASA GSFC PGDA — [pgda.gsfc.nasa.gov/products/90](https://pgda.gsfc.nasa.gov/products/90) | Terrain horizons, site heights |
| Artemis III candidate landing site navigational grids (McClernan 2024), DOI 10.5066/P1MEQ6UK | USGS Astrogeology — [usgs.gov](https://www.usgs.gov/data/down-selected-artemis-iii-candidate-landing-site-navigational-grids) | Region footprints → representative points |
| Artemis III candidate regions update (Oct 28, 2024); NTRS 20250011660 | NASA — [nasa.gov](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/) | Region list and context |
| JPL Horizons API | NASA/JPL SSD — [ssd-api.jpl.nasa.gov](https://ssd-api.jpl.nasa.gov/doc/horizons.html) | Ephemeris validation only |
| Illumination literature (Mazarico et al. 2011; Gläser et al. 2014) | Icarus | Plausibility comparison |
""")

st.markdown(f'<div class="lln-sec">{ui.mi("rule")}5 · Assumptions & limitations</div>', unsafe_allow_html=True)
st.markdown(f"""
- Sunlit when ≥ 50 % of the solar disc is above the terrain (adjustable); potential direct-to-Earth visibility when Earth's centre is above terrain + mask.
- Eclipses: the Sun disc hidden by Earth reduces sunlight and power (circle-overlap model).
- Power: vertical Sun-tracking array, constant load, charge/discharge efficiency 95 %, depth of discharge 80 % — **illustrative**.
- Score = user-weighted preference calculation (positive weights normalised), not a safety rating.
- Hourly data for date scanning; Decision Report windows recomputed at 10 minutes.
- {ui.LIMITATIONS}
""")
st.markdown(f'<div class="lln-sec">{ui.mi("smart_toy")}6 · Use of AI</div>', unsafe_allow_html=True)
st.markdown("We used an AI assistant (Claude, Anthropic) to draft the engine code, tests, data scripts and these "
            "pages, and to help plan the project. The team defined the method and scope, reviewed and corrected the "
            "code, ran the NASA data pipeline, and verified every result (JPL Horizons agreement, physics checks). "
            "No AI-generated images or video are used; all numbers come from NASA/USGS data.")
