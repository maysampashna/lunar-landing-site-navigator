"""Development data so the UI can be built before the DEMs arrive.

Ephemeris is REAL (computed with the kernels). Horizon profiles are SYNTHETIC
(smooth random ridgelines) and each site gets a marker file horizon/<site>.SYNTHETIC that the
app must display as a warning. Run precompute_horizons.py to replace them with real terrain.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.horizon import HorizonProfile  # noqa: E402


def synthetic_horizon(seed: int) -> HorizonProfile:
    rng = np.random.default_rng(seed)
    az = np.arange(0, 360, 0.5)
    h = np.zeros_like(az)
    for k in range(1, 9):
        h += rng.normal(0, 0.8 / k) * np.cos(np.radians(k * az) + rng.uniform(0, 2 * np.pi))
    h = np.clip(h + 0.5, -1.0, 4.0)
    return HorizonProfile(az, h, np.full_like(az, 150.0), np.zeros_like(az, bool), 0.0, 2.0, 150.0)


def main():
    sites = pd.read_csv(ROOT / "data" / "sites.csv")
    (ROOT / "data" / "horizon").mkdir(parents=True, exist_ok=True)
    for i, s in sites.iterrows():
        p = ROOT / "data" / "horizon" / f"{s.site_id}.npz"
        if p.exists() and not (ROOT / "data" / "horizon" / f"{s.site_id}.SYNTHETIC").exists():
            continue   # never overwrite real terrain
        synthetic_horizon(1000 + i).save(p)
        (ROOT / "data" / "horizon" / f"{s.site_id}.SYNTHETIC").write_text("synthetic horizon - not real terrain\n")
        print("synthetic horizon:", s.site_id)
    missing = [s.site_id for _, s in sites.iterrows() if not (ROOT / "data" / "ephem" / f"{s.site_id}.parquet").exists()]
    if missing:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "precompute_ephem.py"), *missing], check=True)


if __name__ == "__main__":
    main()
