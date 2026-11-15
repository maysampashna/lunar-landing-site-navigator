"""Terrain horizon profiles from LOLA DEMs.

CRITICAL azimuth convention: rays are cast along LOCAL GEOGRAPHIC bearings on the lunar
sphere (great-circle destination points in lat/lon), and only then projected into the DEM's
south-polar-stereographic grid. The DEM grid's "up" is NOT geographic north (it differs by an
angle that depends on longitude), so rays must never be cast along grid rows/columns.

Elevation angle of a terrain sample at arc distance d:
    angle = atan( (h_terrain - h_observer) / d  -  d / (2 R) )
(the d/(2R) term is the Moon-curvature drop).
Samples where no DEM covers the point are NaN and flagged; they are never treated as flat.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .geometry import R_MOON_M, destination

# Fallback CRS used by LOLA polar products if the GeoTIFF carries no CRS.
LOLA_SPS_PROJ = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"


class RasterDEM:
    """Bilinear sampler for a (windowed) GeoTIFF DEM, queried with lunar lat/lon."""

    def __init__(self, path: str | Path, center_latlon: tuple[float, float] | None = None,
                 half_width_m: float | None = None, name: str | None = None):
        import rasterio
        from rasterio.windows import from_bounds
        from pyproj import CRS, Transformer

        self.name = name or Path(path).name
        with rasterio.open(path) as src:
            crs = CRS.from_user_input(src.crs.to_wkt()) if src.crs else CRS.from_proj4(LOLA_SPS_PROJ)
            geo = crs.geodetic_crs
            self._to_xy = Transformer.from_crs(geo, crs, always_xy=True)
            if center_latlon is not None and half_width_m is not None:
                cx, cy = self._to_xy.transform(center_latlon[1], center_latlon[0])
                win = from_bounds(cx - half_width_m, cy - half_width_m, cx + half_width_m, cy + half_width_m,
                                  transform=src.transform)
                win = win.round_offsets().round_lengths()
                data = src.read(1, window=win, boundless=True, fill_value=np.nan).astype("float32")
                transform = src.window_transform(win)
            else:
                data = src.read(1).astype("float32")
                transform = src.transform
            nodata = src.nodata
        if nodata is not None and not np.isnan(nodata):
            data[data == nodata] = np.nan
        self.data = data
        self.inv = ~transform
        self.pixel_m = abs(transform.a)

    def sample(self, lat_deg, lon_deg):
        lat_deg = np.asarray(lat_deg, float)
        lon_deg = np.asarray(lon_deg, float)
        x, y = self._to_xy.transform(lon_deg, lat_deg)
        a = self.inv
        x = np.asarray(x); y = np.asarray(y)
        col = a.a * x + a.b * y + a.c
        row = a.d * x + a.e * y + a.f
        col = np.asarray(col) - 0.5   # pixel centres
        row = np.asarray(row) - 0.5
        c0 = np.floor(col).astype(int)
        r0 = np.floor(row).astype(int)
        fc = col - c0
        fr = row - r0
        H, W = self.data.shape
        ok = (c0 >= 0) & (r0 >= 0) & (c0 + 1 < W) & (r0 + 1 < H)
        out = np.full(col.shape, np.nan, dtype=float)
        c0o, r0o, fco, fro = c0[ok], r0[ok], fc[ok], fr[ok]
        d = self.data
        v = (d[r0o, c0o] * (1 - fco) * (1 - fro) + d[r0o, c0o + 1] * fco * (1 - fro)
             + d[r0o + 1, c0o] * (1 - fco) * fro + d[r0o + 1, c0o + 1] * fco * fro)
        out[ok] = v
        return out


class MultiDEM:
    """Use the first DEM (highest resolution) that has data; fall back to the next."""

    def __init__(self, dems: list):
        self.dems = dems
        self.pixel_m = dems[0].pixel_m

    def sample(self, lat_deg, lon_deg):
        out = None
        for dem in self.dems:
            v = dem.sample(lat_deg, lon_deg)
            out = v if out is None else np.where(np.isnan(out), v, out)
        return out


@dataclass
class HorizonProfile:
    az_deg: np.ndarray            # (N,) bearings, clockwise from local geographic north
    horizon_el_deg: np.ndarray    # (N,) max terrain elevation angle (deg); NaN if no data at all
    coverage_km: np.ndarray       # (N,) distance up to which the ray had continuous DEM data
    incomplete: np.ndarray        # (N,) bool: ray ran out of DEM data before max distance
    site_height_m: float          # DEM surface height at the site (m, above 1737.4 km sphere)
    observer_height_m: float      # observer height above the surface (m)
    max_dist_km: float

    def save(self, path):
        np.savez_compressed(path, az_deg=self.az_deg, horizon_el_deg=self.horizon_el_deg,
                            coverage_km=self.coverage_km, incomplete=self.incomplete,
                            site_height_m=self.site_height_m, observer_height_m=self.observer_height_m,
                            max_dist_km=self.max_dist_km)

    @classmethod
    def load(cls, path):
        z = np.load(path)
        return cls(z["az_deg"], z["horizon_el_deg"], z["coverage_km"], z["incomplete"].astype(bool),
                   float(z["site_height_m"]), float(z["observer_height_m"]), float(z["max_dist_km"]))

    def at(self, az_deg):
        """Horizon elevation at arbitrary azimuth(s) (periodic linear interpolation).
        Returns NaN where either neighbouring ray has no terrain samples at all."""
        az = np.asarray(az_deg, float) % 360.0
        val = np.interp(az, self.az_deg, self.horizon_el_deg, period=360.0)
        bad = ~np.isfinite(self.horizon_el_deg)
        if bad.any():
            step = self.az_deg[1] - self.az_deg[0]
            i0 = np.floor(az / step).astype(int) % len(self.az_deg)
            i1 = (i0 + 1) % len(self.az_deg)
            val = np.where(bad[i0] | bad[i1], np.nan, val)
        return val

    def _idx(self, az_deg):
        step = self.az_deg[1] - self.az_deg[0]
        return np.rint((np.asarray(az_deg) % 360.0) / step).astype(int) % len(self.az_deg)

    def incomplete_at(self, az_deg):
        return self.incomplete[self._idx(az_deg)]

    def coverage_at(self, az_deg):
        return self.coverage_km[self._idx(az_deg)]


def sample_distances(pixel_m: float, max_dist_m: float, far_factor: float = 0.004) -> np.ndarray:
    """Ray sample distances: ~1 pixel spacing near the site, growing slowly with distance
    (spacing = max(pixel, far_factor * d)) so far-field sampling stays cheap."""
    d = [pixel_m]
    while d[-1] < max_dist_m:
        d.append(d[-1] + max(pixel_m, far_factor * d[-1]))
    return np.array(d[:-1] + [max_dist_m])


def compute_horizon(lat_deg: float, lon_deg: float, dem, az_step_deg: float = 0.5,
                    max_dist_km: float = 150.0, observer_height_m: float = 2.0,
                    site_height_m: float | None = None, far_factor: float = 0.004) -> HorizonProfile:
    """Compute the terrain horizon around a site.

    dem: object with .sample(lat, lon) -> heights (m, NaN outside coverage) and .pixel_m.
    """
    az = np.arange(0.0, 360.0, az_step_deg)
    dists = sample_distances(dem.pixel_m, max_dist_km * 1000.0, far_factor)
    if site_height_m is None:
        site_height_m = float(dem.sample(np.array([lat_deg]), np.array([lon_deg]))[0])
        if np.isnan(site_height_m):
            raise ValueError(f"No DEM data at site ({lat_deg}, {lon_deg})")
    h_obs = site_height_m + observer_height_m

    AZ, D = np.meshgrid(az, dists, indexing="ij")          # (Naz, Nd)
    lat2, lon2 = destination(lat_deg, lon_deg, AZ, D)
    h = dem.sample(lat2.ravel(), lon2.ravel()).reshape(AZ.shape)
    angle = np.degrees(np.arctan((h - h_obs) / D - D / (2.0 * R_MOON_M)))

    valid = ~np.isnan(h)
    horizon = np.where(valid.any(axis=1), np.nanmax(np.where(valid, angle, -np.inf), axis=1), np.nan)
    # continuous coverage: distance of the last valid sample before the first gap
    first_gap = np.where(valid.all(axis=1), D.shape[1], np.argmin(valid, axis=1))
    coverage = np.where(first_gap > 0, dists[np.maximum(first_gap - 1, 0)], 0.0) / 1000.0
    incomplete = ~valid.all(axis=1)
    return HorizonProfile(az, horizon, coverage, incomplete, site_height_m, observer_height_m, max_dist_km)
