"""NASA Deep Space Network (DSN) geometric coverage of the Moon.

For direct-to-Earth (DTE) communication a lunar station needs (1) Earth above its local terrain horizon and
(2) at least one DSN complex on Earth that sees the Moon above its elevation mask. This module computes (2):
the Moon's elevation at the three DSN complexes. Geometric only - it does not model antenna scheduling,
link budgets or competing missions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Representative 70 m / 34 m antenna sites of the three complexes (lat, lon east, height m)
DSN_COMPLEXES = {
    "Goldstone": (35.4259, -116.8895, 1001.0),   # DSS-14, California, USA
    "Madrid": (40.4313, -4.2481, 834.0),         # DSS-63, Robledo de Chavela, Spain
    "Canberra": (-35.4022, 148.9813, 689.0),     # DSS-43, Tidbinbilla, Australia
}
DEFAULT_MASK_DEG = 10.0


def moon_elevations(sky, times_utc: pd.DatetimeIndex, chunk: int = 24 * 400) -> pd.DataFrame:
    """Moon topocentric elevation (deg) at each DSN complex. `sky` is an engine.ephemeris.LunarSky."""
    from skyfield.api import wgs84

    times_utc = pd.DatetimeIndex(times_utc)
    if times_utc.tz is None:
        times_utc = times_utc.tz_localize("UTC")
    earth, moon = sky.eph["earth"], sky.eph["moon"]
    out = {name: [] for name in DSN_COMPLEXES}
    for i in range(0, len(times_utc), chunk):
        t = sky.ts.from_datetimes(times_utc[i:i + chunk].to_pydatetime())
        for name, (lat, lon, h) in DSN_COMPLEXES.items():
            alt, _, _ = (earth + wgs84.latlon(lat, lon, elevation_m=h)).at(t).observe(moon).apparent().altaz()
            out[name].append(alt.degrees)
    df = pd.DataFrame({f"dsn_{k.lower()}_el": np.concatenate(v) for k, v in out.items()})
    df.insert(0, "time_utc", times_utc)
    return df


def coverage(dsn_df: pd.DataFrame, mask_deg: float = DEFAULT_MASK_DEG) -> pd.DataFrame:
    """Adds dsn_any (bool) and dsn_best (name of complex with the highest Moon elevation above the mask)."""
    cols = [f"dsn_{k.lower()}_el" for k in DSN_COMPLEXES]
    el = dsn_df[cols].to_numpy()
    best_idx = el.argmax(axis=1)
    names = np.array(list(DSN_COMPLEXES))
    out = dsn_df.copy()
    out["dsn_any"] = el.max(axis=1) >= mask_deg
    out["dsn_best"] = np.where(out["dsn_any"], names[best_idx], "")
    out["dsn_best_el"] = el.max(axis=1)
    return out
