# Lunar Landing Site Navigator — Bulldogs Beyond Earth (NASA Space Apps Challenge 2026)

Compare lunar south-pole candidate sites and dates by **terrain-aware Sun and Earth visibility**, an
**illustrative power/storage estimate**, and **sensitivity to surface-start timing** (+24 / +48 h),
answering one question: *which location is best modeled for a 6-day stay, and does a slip change that?*

> 8 of the 9 Artemis III candidate regions are included (the USGS download for Mons Mouton Plateau
> failed during the event). Validation: Sun/Earth positions match JPL Horizons to 0.00001° at all 8 sites.
>
> Artemis III candidate regions (the crewed landing is now planned for Artemis IV). Points are
> representative points, not NASA-designated landing sites. Not assessed: landing hazards, slopes,
> thermal environment, RF link budget, antenna scheduling.

## What the app does

| Page | What you get |
|---|---|
| 🏠 **Home** | A rotatable 3D Moon with real NASA LOLA terrain on the south polar cap, the eight sites labelled (hover for what each site is and why its region was chosen), and buttons to the three pages |
| 🚀 **Mission Dashboard** | One horizontal control panel (sites, site shown in 3D, landing date and hour, stay, selected time, advanced settings) drives everything: the **station ranking** (tie-aware, worst case over landing delays), a 3D observer view of the real terrain with the Sun and Earth, the 360° panorama and sky chart, a NASA-style mission clock with upcoming AOS/LOS and DSN events, and tabs for landing-delay risk, battery, **Deep Space Network** geometry and the visibility timeline |
| 📅 **Best Date Finder** | Best landing dates per site (2026–2031) with tie-aware ranks, one-click **Open in Mission Dashboard**, and a calendar heatmap |
| ✅ **Data Validation** | Validation summary (scope of each check), JPL Horizons comparison, physics checks and tests, terrain status, data sources, limitations and AI-use statement |

The 3D views use small LOLA tiles in `data/terrain3d.npz` (made by `scripts/make_terrain3d.py`); the Home page shows a rotatable 3D Moon. Header banners, logo and thumbnails are generated from the real LOLA south-pole hillshade (`assets/`); no AI-generated imagery is used.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

All data the app needs is in the repo (`data/`, `kernels/`).

## Reproduce the data from NASA/USGS sources

```bash
pip install -r requirements-dev.txt
python scripts/fetch_external.py               # NAIF kernels, LOLA 80 m / 240 m DEMs + hillshade, USGS region grids
python scripts/make_sites.py data/raw/usgs_1km # interior representative point per region (lunar CRS)
python scripts/precompute_horizons.py          # terrain horizons to 150 km + site heights
python scripts/precompute_ephem.py             # hourly Sun/Earth az/el 2026-01-01 -> 2031-03-01
python scripts/fetch_external.py --horizons    # JPL Horizons samples for every site
python scripts/validate_horizons.py --offline  # -> data/validation.json
pytest -q                                      # 34 unit tests
```

**Confidence rule:** a recommendation is shown only for sites with real LOLA terrain and at most 5 % uncertain
time; otherwise the app labels results as a demonstration ranking.

## Method

| Step | Method |
|---|---|
| Positions | Skyfield + JPL DE421 + `moon_080317.tf` + `pck00008.tpc` + `moon_pa_de421_1900-2050.bpc`, site in **MOON_ME_DE421** (same frame as LOLA) |
| Terrain horizon | Rays along **local geographic bearings** (great-circle points on R = 1737.4 km sphere) projected into the DEM; `angle = atan((h − h_obs)/d − d/2R)`; LOLA 80 m near field + 240 m far field to 150 km; observer 2 m; missing terrain flagged, never flat |
| Visibility | Finite disc: fraction of Sun (Earth) disc above terrain; sunlit if ≥ 50 % of the solar disc; potential DTE if Earth centre ≥ terrain + mask |
| Power (illustrative) | `P = A·η·1361·(1 AU/r)²·sun_frac`; stored-energy changes with charge/discharge efficiencies; required usable energy = max drawdown; capacity simulated with a full-charge clamp; end-of-window charge checked separately |
| Score | `100·clip(w_sun·f_sun + w_dte·f_dte + w_both·f_both − w_gd·g_dark − w_ge·g_dte, 0, 1)`; positive weights renormalised to sum 1; gaps normalised by window length |
| Eclipses | Sun disc hidden behind Earth (circle overlap from the site) reduces sunlight and power; total lunar eclipses 2026-03-03 and 2028-12-31 are detected in tests |
| Terrain uncertainty | Where a ray ran out of DEM data and unknown far terrain (≤12 km relief) could reach above the Sun/Earth, the time step is 'uncertain'; sites uncertain >5 % of the time are excluded from the confident ranking |
| Resolution | Hourly precompute for date scanning; the Mission Dashboard recomputes its windows at 10-min resolution with the kernels (else labelled approximate) |
| Communication (DSN) | Direct-to-Earth contact = Earth above the site's terrain horizon (+ mask) **and** the Moon ≥ 10° (adjustable) above the horizon at Goldstone, Madrid or Canberra (geometric; no antenna scheduling or link budget) |
| Timing sensitivity | Assumes surface arrival shifts exactly +24/+48 h; decision = highest worst-case score |

## Validation (reported separately)
1. **Ephemeris** vs JPL Horizons topocentric az/el (`scripts/validate_horizons.py`).
2. **Terrain horizon**: orientation tests with synthetic mountains at known bearings (`tests/`),
   80 m vs 240 m consistency, panorama vs LOLA hillshade.
3. **Literature**: % illumination at published points (Mazarico et al. 2011; Gläser et al. 2014).

## Data sources
- NASA/JPL NAIF SPICE generic kernels (DE421, lunar frame kernels)
- NASA GSFC PGDA LOLA south-pole DEMs (Barker et al.): https://pgda.gsfc.nasa.gov/products/90
- USGS Artemis III candidate landing site navigational grids, DOI 10.5066/P1MEQ6UK
- NASA Artemis III candidate regions update (Oct 28, 2024); NTRS 20250011660
- JPL Horizons API (validation only)

## Use of AI
We used an AI assistant (Claude, by Anthropic) throughout the project:
- **Code:** first drafts of the engine, tests, data scripts and Streamlit pages were AI-generated.
- **Planning:** the AI helped draft the development plan, which we then reviewed in several rounds
  with a second AI tool and revised (frame convention, terrain azimuths, battery model, eclipse
  handling, confidence rules).

The team defined the challenge question and the method, decided scope and priorities, reviewed and
corrected the code, ran the full NASA data pipeline (NAIF kernels, LOLA DEMs, USGS regions) on our
own machine, and verified the results: Sun/Earth positions agree with JPL Horizons to 0.00001°, and
built-in physics checks (Sun elevation limits, known lunar eclipses) pass. No AI-generated images or
video are used. All figures in the app are computed from NASA/USGS data.

## License
Apache-2.0 (to be confirmed by the team).
