"""Download all external data (run on a laptop with internet; ~420 MB total).

    python scripts/download_data.py            # kernels + 80 m + 240 m DEMs + hillshade
    python scripts/download_data.py --hires    # also the 20 m DEM (~1.7 GB, optional)

USGS Artemis III region grids must be downloaded by hand (ScienceBase has no stable direct
file URLs):  https://www.sciencebase.gov/catalog/item/671a6fa8d34efed5620f89f8
Download the zip(s), extract into data/raw/usgs_regions/, then run scripts/make_sites.py.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels"
PGDA = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp"

KERNELS = {
    "de421.bsp": f"{NAIF}/spk/planets/de421.bsp",
    "moon_080317.tf": f"{NAIF}/fk/satellites/moon_080317.tf",
    "pck00008.tpc": f"{NAIF}/pck/pck00008.tpc",
    "moon_pa_de421_1900-2050.bpc": f"{NAIF}/pck/moon_pa_de421_1900-2050.bpc",
}
DEMS = {
    "LDEM_80S_80MPP_ADJ.TIF": f"{PGDA}/LDEM_80S_80MPP_ADJ.TIF",
    "LDEM_60S_240MPP_ADJ.TIF": f"{PGDA}/LDEM_60S_240MPP_ADJ.TIF",
    "LDEM_80S_80MPP_ADJ_HILL.TIF": f"{PGDA}/LDEM_80S_80MPP_ADJ_HILL.TIF",
}
HIRES = {"LDEM_80S_20MPP_ADJ.TIF": f"{PGDA}/LDEM_80S_20MPP_ADJ.TIF"}


def fetch(url: str, dest: Path, force: bool = False):
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"  exists  {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  get     {url}")

    def hook(blocks, bs, total):
        if total > 0:
            pct = min(100, blocks * bs * 100 // total)
            sys.stdout.write(f"\r          {pct:3d}% of {total/1e6:.0f} MB")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, tmp, hook)
    print()
    tmp.rename(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hires", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    print("NAIF kernels ->", ROOT / "kernels")
    for name, url in KERNELS.items():
        fetch(url, ROOT / "kernels" / name, a.force)
    print("LOLA DEMs ->", ROOT / "data" / "raw")
    dems = dict(DEMS, **(HIRES if a.hires else {}))
    for name, url in dems.items():
        fetch(url, ROOT / "data" / "raw" / name, a.force)
    print("\nDone. Next: download USGS region grids by hand (see this file's docstring),"
          " then run scripts/make_sites.py")


if __name__ == "__main__":
    main()
