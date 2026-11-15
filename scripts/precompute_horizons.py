"""Precompute terrain horizon profiles for all (or selected) sites.

    python scripts/precompute_horizons.py                     # all sites in data/sites.csv
    python scripts/precompute_horizons.py malapert_massif ...  # selected sites

Near field: LDEM_80S_80MPP_ADJ.TIF (or the 20 m DEM if present and --hires).
Far field:  LDEM_60S_240MPP_ADJ.TIF. Missing terrain is flagged (incomplete), never flat.
Also writes the DEM surface height back into sites.csv (height_m).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.horizon import MultiDEM, RasterDEM, compute_horizon  # noqa: E402

RAW = ROOT / "data" / "raw"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", nargs="*")
    ap.add_argument("--max-km", type=float, default=150.0)
    ap.add_argument("--az-step", type=float, default=0.5)
    ap.add_argument("--observer-m", type=float, default=2.0)
    ap.add_argument("--hires", action="store_true", help="use the 20 m DEM for the near field")
    a = ap.parse_args()

    sites = pd.read_csv(ROOT / "data" / "sites.csv")
    todo = sites if not a.sites else sites[sites["site_id"].isin(a.sites)]
    near_name = "LDEM_80S_20MPP_ADJ.TIF" if a.hires else "LDEM_80S_80MPP_ADJ.TIF"
    out_dir = ROOT / "data" / "horizon"
    out_dir.mkdir(parents=True, exist_ok=True)
    half = a.max_km * 1000 + 5000
    for _, s in todo.iterrows():
        t0 = time.time()
        near = RasterDEM(RAW / near_name, (s.lat_deg, s.lon_deg), half, name=near_name)
        far = RasterDEM(RAW / "LDEM_60S_240MPP_ADJ.TIF", (s.lat_deg, s.lon_deg), half, name="LDEM_60S_240MPP")
        dem = MultiDEM([near, far])
        hp = compute_horizon(s.lat_deg, s.lon_deg, dem, az_step_deg=a.az_step, max_dist_km=a.max_km,
                             observer_height_m=a.observer_m)
        hp.save(out_dir / f"{s.site_id}.npz")
        (out_dir / f"{s.site_id}.SYNTHETIC").unlink(missing_ok=True)
        sites.loc[sites.site_id == s.site_id, "height_m"] = round(hp.site_height_m, 1)
        print(f"{s.site_id:24s} h={hp.site_height_m:8.1f} m  horizon {np.nanmin(hp.horizon_el_deg):5.2f}..{np.nanmax(hp.horizon_el_deg):5.2f} deg"
              f"  incomplete rays {hp.incomplete.mean()*100:4.1f}%  ({time.time()-t0:.1f}s)")
    sites.to_csv(ROOT / "data" / "sites.csv", index=False)


if __name__ == "__main__":
    main()
