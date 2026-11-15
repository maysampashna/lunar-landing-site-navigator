"""Basic lunar geometry helpers (sphere model, R = 1737.4 km).

Conventions used everywhere in this project:
- Latitude/longitude are lunar planetocentric degrees in the MOON_ME (DE421) frame,
  east-positive longitude in [-180, 180).
- Azimuth/bearing is measured clockwise from LOCAL GEOGRAPHIC NORTH (0 = north, 90 = east),
  the same convention Skyfield's altaz() uses.
- Elevations are degrees above the local horizontal plane (sphere normal).
"""
from __future__ import annotations

import numpy as np

R_MOON_M = 1_737_400.0          # LOLA / IAU reference sphere radius (m)
R_EARTH_KM = 6_371.0            # mean Earth radius, for Earth's apparent disc size
SUN_RADIUS_DEG_1AU = 0.26656    # apparent solar radius at 1 AU (deg)


def destination(lat_deg, lon_deg, bearing_deg, dist_m, radius_m: float = R_MOON_M):
    """Great-circle destination point on a sphere.

    Broadcasts over all inputs. bearing is clockwise from local geographic north.
    Returns (lat_deg, lon_deg) with lon wrapped to [-180, 180).
    """
    phi1 = np.radians(lat_deg)
    lam1 = np.radians(lon_deg)
    theta = np.radians(bearing_deg)
    delta = np.asarray(dist_m, dtype=float) / radius_m

    sin_phi2 = np.sin(phi1) * np.cos(delta) + np.cos(phi1) * np.sin(delta) * np.cos(theta)
    sin_phi2 = np.clip(sin_phi2, -1.0, 1.0)
    phi2 = np.arcsin(sin_phi2)
    y = np.sin(theta) * np.sin(delta) * np.cos(phi1)
    x = np.cos(delta) - np.sin(phi1) * sin_phi2
    lam2 = lam1 + np.arctan2(y, x)
    lon2 = (np.degrees(lam2) + 180.0) % 360.0 - 180.0
    return np.degrees(phi2), lon2


def initial_bearing(lat1, lon1, lat2, lon2):
    """Initial great-circle bearing (deg, clockwise from north) from point 1 to point 2."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dlam = np.radians(np.asarray(lon2) - np.asarray(lon1))
    y = np.sin(dlam) * np.cos(phi2)
    x = np.cos(phi1) * np.sin(phi2) - np.sin(phi1) * np.cos(phi2) * np.cos(dlam)
    return np.degrees(np.arctan2(y, x)) % 360.0


def disc_fraction_above(center_el_deg, horizon_el_deg, radius_deg):
    """Fraction (0..1) of a circular disc's AREA lying above a locally straight horizon line.

    center_el_deg: elevation of the disc centre; horizon_el_deg: terrain horizon elevation
    at the disc's azimuth; radius_deg: apparent angular radius of the disc.
    Uses the circular-segment area formula. Broadcasts.
    """
    r = np.asarray(radius_deg, dtype=float)
    x = np.clip((np.asarray(center_el_deg, float) - np.asarray(horizon_el_deg, float)) / r, -1.0, 1.0)
    return 1.0 - (np.arccos(x) - x * np.sqrt(1.0 - x * x)) / np.pi


def angular_separation_deg(az1, el1, az2, el2):
    """Great-circle separation between two sky directions given as (az, el) in degrees."""
    a1, e1, a2, e2 = map(np.radians, (az1, el1, az2, el2))
    c = np.sin(e1) * np.sin(e2) + np.cos(e1) * np.cos(e2) * np.cos(a1 - a2)
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def covered_fraction(r_small, r_big, sep):
    """Fraction (0..1) of the small disc's area covered by the big disc (planar circle overlap;
    exact enough for discs < 2 deg). Used for the Sun hidden behind Earth (eclipse seen from the Moon)."""
    r = np.asarray(r_small, float)
    R = np.asarray(r_big, float)
    d = np.asarray(sep, float)
    r, R, d = np.broadcast_arrays(r, R, d)
    out = np.zeros(d.shape)
    full = d <= np.abs(R - r)
    out[full] = np.where(R[full] >= r[full], 1.0, (R[full] / r[full]) ** 2)
    part = (~full) & (d < r + R)
    if part.any():
        rp, Rp, dp = r[part], R[part], d[part]
        a1 = rp ** 2 * np.arccos(np.clip((dp ** 2 + rp ** 2 - Rp ** 2) / (2 * dp * rp), -1, 1))
        a2 = Rp ** 2 * np.arccos(np.clip((dp ** 2 + Rp ** 2 - rp ** 2) / (2 * dp * Rp), -1, 1))
        a3 = 0.5 * np.sqrt(np.clip((-dp + rp + Rp) * (dp + rp - Rp) * (dp - rp + Rp) * (dp + rp + Rp), 0, None))
        out[part] = (a1 + a2 - a3) / (np.pi * rp ** 2)
    return out


def max_far_terrain_angle_deg(distance_km, max_relief_m: float = 12_000.0):
    """Upper bound on the elevation angle that UNKNOWN terrain beyond `distance_km` could subtend,
    assuming at most `max_relief_m` height difference to the observer (south-polar relief is < ~10 km),
    including Moon curvature. Used to decide whether missing DEM data could change visibility."""
    d = np.maximum(np.asarray(distance_km, float) * 1000.0, 1.0)
    return np.degrees(np.arctan(max_relief_m / d - d / (2.0 * R_MOON_M)))


def sun_radius_deg(sun_dist_au):
    return SUN_RADIUS_DEG_1AU / np.asarray(sun_dist_au, dtype=float)


def earth_radius_deg(earth_dist_km):
    return np.degrees(np.arcsin(R_EARTH_KM / np.asarray(earth_dist_km, dtype=float)))
