"""Fine-resolution recomputation for the selected decision window.

Precomputed data is hourly (good for scanning dates). Hourly sampling can miss short shadows or
communication interruptions, so the Decision Report recomputes its windows at a finer step
(default 10 min) when the kernels are available. Otherwise the app labels results 'approximate (hourly)'.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import visibility
from .ephemeris import KERNEL_FILES, LunarSky, hourly_grid
from .horizon import HorizonProfile

KERNEL_DIR = Path(__file__).resolve().parent.parent / "kernels"
_SKY: LunarSky | None = None


def kernels_available(kernel_dir: Path = KERNEL_DIR) -> bool:
    return all((kernel_dir / f).exists() for f in KERNEL_FILES.values())


def sky(kernel_dir: Path = KERNEL_DIR) -> LunarSky:
    global _SKY
    if _SKY is None:
        _SKY = LunarSky(kernel_dir)
    return _SKY


def dsn_series(start, end, step_min: float = 10.0, mask_deg: float = 10.0) -> pd.DataFrame:
    from .dsn import coverage, moon_elevations
    start = pd.Timestamp(start)
    start = start.tz_localize("UTC") if start.tz is None else start
    times = hourly_grid(start.isoformat(), pd.Timestamp(end).isoformat(), step_h=step_min / 60.0)
    return coverage(moon_elevations(sky(), times), mask_deg)


def at_time(site: pd.Series, horizon: HorizonProfile | None, when, params: visibility.VisParams,
            dsn_mask_deg: float = 10.0) -> pd.Series:
    """Exact-instant (to the second) visibility + DSN state for one site."""
    from .dsn import coverage, moon_elevations
    when = pd.Timestamp(when)
    when = when.tz_localize("UTC") if when.tz is None else when
    h = float(site.height_m) if pd.notna(site.get("height_m")) and str(site.get("height_m")) != "" else 0.0
    idx = pd.DatetimeIndex([when])
    eph = sky().compute(site.lat_deg, site.lon_deg, h, idx)
    d = coverage(moon_elevations(sky(), idx), dsn_mask_deg)
    v = visibility.compute(eph, horizon, params, dsn_any=d["dsn_any"].to_numpy())
    return pd.concat([v.iloc[0], d.drop(columns="time_utc").iloc[0]])


def fine_visibility(site: pd.Series, horizon: HorizonProfile | None, start, end, params: visibility.VisParams,
                    step_min: float = 10.0, dsn: pd.DataFrame | None = None) -> pd.DataFrame:
    h = float(site.height_m) if pd.notna(site.get("height_m")) and str(site.get("height_m")) != "" else 0.0
    start = pd.Timestamp(start)
    start = start.tz_localize("UTC") if start.tz is None else start
    times = hourly_grid(start.isoformat(), pd.Timestamp(end).isoformat(), step_h=step_min / 60.0)
    eph = sky().compute(site.lat_deg, site.lon_deg, h, times)
    dsn_any = None
    if dsn is not None:
        dsn_any = dsn.set_index("time_utc")["dsn_any"].reindex(pd.DatetimeIndex(eph["time_utc"]),
                                                                  method="nearest").to_numpy()
    return visibility.compute(eph, horizon, params, dsn_any=dsn_any)
