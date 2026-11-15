"""Precompute hourly Sun/Earth topocentric az/el for every site (2026-01-01 -> 2031-03-01 UTC).

    python scripts/precompute_ephem.py [site_id ...]

Uses height_m from sites.csv (filled by precompute_horizons.py); 0 if missing.
(Height changes az/el negligibly; the local vertical on a sphere does not depend on height.)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.ephemeris import LunarSky, hourly_grid  # noqa: E402

START, END = "2026-01-01", "2031-03-01"


def main(selected):
    sky = LunarSky(ROOT / "kernels")
    sites = pd.read_csv(ROOT / "data" / "sites.csv")
    if selected:
        sites = sites[sites.site_id.isin(selected)]
    times = hourly_grid(START, END)
    out = ROOT / "data" / "ephem"
    out.mkdir(parents=True, exist_ok=True)
    for _, s in sites.iterrows():
        t0 = time.time()
        h = float(s.height_m) if pd.notna(s.get("height_m")) and str(s.get("height_m")) != "" else 0.0
        df = sky.compute(s.lat_deg, s.lon_deg, h, times)
        df.astype({c: "float32" for c in df.columns if c != "time_utc"}).to_parquet(out / f"{s.site_id}.parquet", index=False)
        print(f"{s.site_id:24s} {len(df)} rows  sun el {df.sun_el_deg.min():6.2f}..{df.sun_el_deg.max():5.2f}"
              f"  earth el {df.earth_el_deg.min():6.2f}..{df.earth_el_deg.max():5.2f}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1:])
