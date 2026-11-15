"""Combine ephemeris + terrain horizon into per-time visibility.

sun_frac_terrain = fraction of the solar disc above the terrain horizon (finite disc)
eclipse_frac     = fraction of the solar disc hidden behind Earth (lunar eclipse seen from the Moon)
sun_frac         = sun_frac_terrain * (1 - eclipse_frac)   (independence approximation)
earth_frac       = fraction of Earth's disc above the terrain horizon
sunlit           = sun_frac >= sunlit_threshold
dte_visible      = potential direct-to-Earth visibility: Earth centre >= horizon + mask
                   (geometric line of sight only; NOT a link budget or antenna schedule)
*_uncertain      = the DEM did not cover the full ray at that azimuth AND unknown far terrain
                   could plausibly change the result (body sits between the known horizon and the
                   bound on what missing terrain could subtend). Uncertain results are excluded
                   from confident rankings (see metrics/finder).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .geometry import (angular_separation_deg, covered_fraction, disc_fraction_above, earth_radius_deg,
                       max_far_terrain_angle_deg, sun_radius_deg)
from .horizon import HorizonProfile
from .power import PowerParams, solar_power_w


@dataclass
class VisParams:
    sunlit_threshold: float = 0.5      # fraction of solar disc that must be visible
    earth_mask_deg: float = 0.0        # extra elevation margin above terrain for DTE
    require_dsn: bool = False          # DTE also needs a DSN complex seeing the Moon (dsn_any must be supplied)
    power: PowerParams = field(default_factory=PowerParams)


def _uncertain(el, radius, hz, incomplete, coverage_km):
    bound = max_far_terrain_angle_deg(coverage_km)
    # visible per known terrain (some of the disc above hz) but unknown terrain could reach above it
    return incomplete & (el + radius > hz) & (el - radius < bound)


def compute(ephem: pd.DataFrame, horizon: HorizonProfile | None, params: VisParams,
            dsn_any: np.ndarray | None = None) -> pd.DataFrame:
    """ephem columns: time_utc, sun_az_deg, sun_el_deg, sun_dist_au, earth_az_deg, earth_el_deg, earth_dist_km.
    horizon=None -> flat (0 deg) horizon (for comparison / fallback)."""
    s_az = ephem["sun_az_deg"].to_numpy(float)
    s_el = ephem["sun_el_deg"].to_numpy(float)
    e_az = ephem["earth_az_deg"].to_numpy(float)
    e_el = ephem["earth_el_deg"].to_numpy(float)
    r_sun = sun_radius_deg(ephem["sun_dist_au"].to_numpy(float))
    r_earth = earth_radius_deg(ephem["earth_dist_km"].to_numpy(float))
    n = len(ephem)

    if horizon is None:
        # No terrain at all: plot against a flat 0-deg horizon, but EVERY step is uncertain,
        # so no confident result can ever come from missing terrain.
        hz_sun = hz_earth = np.zeros(n)
        unc_sun = unc_earth = np.ones(n, bool)
    else:
        hz_sun, hz_earth = horizon.at(s_az), horizon.at(e_az)
        unc_sun = _uncertain(s_el, r_sun, hz_sun, horizon.incomplete_at(s_az), horizon.coverage_at(s_az))
        unc_earth = _uncertain(e_el, r_earth, hz_earth, horizon.incomplete_at(e_az), horizon.coverage_at(e_az))
        # Directions with NO terrain samples (NaN horizon) are always uncertain; plot them as flat.
        nan_s, nan_e = ~np.isfinite(hz_sun), ~np.isfinite(hz_earth)
        unc_sun = unc_sun | nan_s
        unc_earth = unc_earth | nan_e
        hz_sun = np.where(nan_s, 0.0, hz_sun)
        hz_earth = np.where(nan_e, 0.0, hz_earth)

    sun_frac_terrain = disc_fraction_above(s_el, hz_sun, r_sun)
    eclipse_frac = covered_fraction(r_sun, r_earth, angular_separation_deg(s_az, s_el, e_az, e_el))
    sun_frac = sun_frac_terrain * (1.0 - eclipse_frac)
    earth_frac = disc_fraction_above(e_el, hz_earth, r_earth)
    sunlit = sun_frac >= params.sunlit_threshold
    earth_in_view = (e_el - hz_earth) >= params.earth_mask_deg
    dsn = np.ones(n, bool) if dsn_any is None else np.asarray(dsn_any, bool)
    dte = earth_in_view & dsn if params.require_dsn else earth_in_view

    return pd.DataFrame({
        "time_utc": ephem["time_utc"].to_numpy(),
        "sun_az_deg": s_az, "sun_el_deg": s_el, "earth_az_deg": e_az, "earth_el_deg": e_el,
        "horizon_at_sun_deg": hz_sun, "horizon_at_earth_deg": hz_earth,
        "sun_radius_deg": r_sun, "earth_radius_deg": r_earth,
        "sun_frac_terrain": sun_frac_terrain, "eclipse_frac": eclipse_frac,
        "sun_frac": sun_frac, "earth_frac": earth_frac,
        "sunlit": sunlit, "earth_in_view": earth_in_view, "dsn_any": dsn, "dte_visible": dte, "both": sunlit & dte,
        "sun_uncertain": unc_sun, "earth_uncertain": unc_earth, "uncertain": unc_sun | unc_earth,
        "p_solar_w": solar_power_w(sun_frac, ephem["sun_dist_au"].to_numpy(float), params.power),
    })
