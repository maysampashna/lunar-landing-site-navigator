"""Topocentric Sun and Earth positions from a point on the lunar surface.

Follows Skyfield's documented lunar-surface workflow:
DE421 ephemeris + moon_080317.tf + pck00008.tpc + moon_pa_de421_1900-2050.bpc,
site defined in the MOON_ME_DE421 frame (the same frame as the LOLA DEMs).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

KERNEL_FILES = {
    "spk": "de421.bsp",
    "fk": "moon_080317.tf",
    "pck_text": "pck00008.tpc",
    "pck_binary": "moon_pa_de421_1900-2050.bpc",
}
FRAME_NAME = "MOON_ME_DE421"


class LunarSky:
    """Loads kernels once; computes Sun/Earth az/el for any lunar site and time grid."""

    def __init__(self, kernel_dir: str | Path):
        from skyfield.api import Loader, PlanetaryConstants

        kernel_dir = Path(kernel_dir)
        missing = [f for f in KERNEL_FILES.values() if not (kernel_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing kernels in {kernel_dir}: {missing}. Run scripts/download_data.py first."
            )
        load = Loader(str(kernel_dir))
        self.ts = load.timescale(builtin=True)
        self.eph = load(KERNEL_FILES["spk"])
        pc = PlanetaryConstants()
        pc.read_text(load(KERNEL_FILES["fk"]))
        pc.read_text(load(KERNEL_FILES["pck_text"]))
        pc.read_binary(load(KERNEL_FILES["pck_binary"]))
        self.pc = pc
        self.frame = pc.build_frame_named(FRAME_NAME)
        self.moon = self.eph["moon"]
        self.sun = self.eph["sun"]
        self.earth = self.eph["earth"]

    def site(self, lat_deg: float, lon_deg: float, height_m: float = 0.0):
        """height_m is above the 1737.4 km reference sphere (same reference as LOLA LDEM heights)."""
        return self.moon + self.pc.build_latlon_degrees(self.frame, lat_deg, lon_deg, elevation_m=height_m)

    def compute(self, lat_deg, lon_deg, height_m, times_utc: pd.DatetimeIndex,
                chunk: int = 24 * 400) -> pd.DataFrame:
        """Return DataFrame indexed by time_utc with sun/earth az, el, distance."""
        place = self.site(lat_deg, lon_deg, height_m)
        times_utc = pd.DatetimeIndex(times_utc)
        if times_utc.tz is None:
            times_utc = times_utc.tz_localize("UTC")
        out = []
        for i in range(0, len(times_utc), chunk):
            tt = times_utc[i:i + chunk]
            t = self.ts.from_datetimes(tt.to_pydatetime())
            obs = place.at(t)
            s_alt, s_az, s_d = obs.observe(self.sun).apparent().altaz()
            e_alt, e_az, e_d = obs.observe(self.earth).apparent().altaz()
            out.append(pd.DataFrame({
                "time_utc": tt,
                "sun_az_deg": s_az.degrees, "sun_el_deg": s_alt.degrees, "sun_dist_au": s_d.au,
                "earth_az_deg": e_az.degrees, "earth_el_deg": e_alt.degrees, "earth_dist_km": e_d.km,
            }))
        return pd.concat(out, ignore_index=True)


def hourly_grid(start: str, end: str, step_h: float = 1.0) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq=pd.Timedelta(hours=step_h), tz="UTC", inclusive="left")
