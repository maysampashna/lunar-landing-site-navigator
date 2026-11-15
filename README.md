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

## Quick start (team)

```bash
pip install -r requirements-dev.txt
python scripts/download_data.py          # NAIF kernels + LOLA 80 m / 240 m DEMs (~420 MB)
# USGS region grids: download by hand -> data/raw/usgs_regions/  (see download_data.py docstring)
python scripts/make_sites.py             # sites.csv from USGS polygons (interior points, lunar CRS)
python scripts/precompute_horizons.py    # terrain horizons (+ site heights)
python scripts/precompute_ephem.py       # hourly Sun/Earth az/el 2026-01-01 -> 2031-03-01
python scripts/validate_horizons.py      # ephemeris check vs JPL Horizons -> data/validation.json
pytest -q                                # unit tests (incl. terrain-azimuth orientation tests)
streamlit run app.py
```

Pages: **Decision Report** (main) · **Date Finder** (best start dates + calendar heatmap) ·
**Validation & Sources** (Horizons results, built-in physics checks, terrain status, citations).

**Confidence rule:** a recommendation is shown only for sites with REAL LOLA terrain and ≤5 % uncertain
time. Synthetic or missing terrain → "Demonstration ranking only (not a recommendation)".

Before the DEMs arrive, `python scripts/make_fake_data.py` gives REAL ephemeris + SYNTHETIC
horizons (the app shows a red warning for synthetic terrain).

Deployment (Streamlit Community Cloud) needs `app.py`, `engine/`, `kernels/` (~19 MB, for 10-min
recomputation), `data/sites.csv`, `data/ephem/`, `data/horizon/`, `data/validation.json` and
`requirements.txt`. Raw DEMs stay offline.

**Kernel provenance:** the kernels bundled in the starter zip came from mirrors (de421 from the
`skyfield-data` package; lunar frame kernels from public GitHub copies). Replace them with the NAIF
originals: `python scripts/download_data.py --force`, then re-run the tests and `validate_horizons.py`.

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
| Resolution | Hourly precompute for date scanning; the Decision Report recomputes its windows at 10-min resolution with the kernels (else labelled approximate) |
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
