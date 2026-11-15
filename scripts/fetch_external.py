"""ONE command to download every external dataset (standard library only - runs with any Python 3).

    python scripts/fetch_external.py              # kernels + LOLA DEMs + USGS regions
    python scripts/fetch_external.py --horizons   # JPL Horizons validation samples (run AFTER sites are final)

Run this on a machine with normal internet (e.g. Anaconda Prompt on Windows).
"""
from __future__ import annotations

import json
import random
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels"
PGDA = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp"
SB_ITEM = "671a6fa8d34efed5620f89f8"   # USGS Artemis III navigational grids, DOI 10.5066/P1MEQ6UK
UA = {"User-Agent": "Mozilla/5.0 (Bulldogs Beyond Earth - NASA Space Apps 2026)"}

KERNELS = {
    "de421.bsp": f"{NAIF}/spk/planets/a_old_versions/de421.bsp",
    "moon_080317.tf": f"{NAIF}/fk/satellites/moon_080317.tf",
    "pck00008.tpc": f"{NAIF}/pck/a_old_versions/pck00008.tpc",
    "moon_pa_de421_1900-2050.bpc": f"{NAIF}/pck/moon_pa_de421_1900-2050.bpc",
}
DEMS = ["LDEM_80S_80MPP_ADJ.TIF", "LDEM_60S_240MPP_ADJ.TIF", "LDEM_80S_80MPP_ADJ_HILL.TIF"]


def get(url, dest: Path, min_bytes=1000, refresh=False):
    if not refresh and dest.exists() and dest.stat().st_size >= min_bytes:
        print(f"  ok (exists) {dest.name}  {dest.stat().st_size / 1e6:.1f} MB")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done, t0 = 0, time.time()
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    sys.stdout.write(f"\r  downloading {dest.name}: {100 * done / total:5.1f}% of {total / 1e6:.0f} MB"
                                     f"  ({done / 1e6 / max(time.time() - t0, 1e-3):.1f} MB/s)")
                    sys.stdout.flush()
        print()
        if tmp.stat().st_size < min_bytes:
            raise IOError(f"file too small ({tmp.stat().st_size} bytes)")
        tmp.replace(dest)
        print(f"  ok {dest.name}  {dest.stat().st_size / 1e6:.1f} MB")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"\n  !! FAILED {url}\n     {e}")
        tmp.unlink(missing_ok=True)
        return False


def sb_json(url):
    req = urllib.request.Request(url, headers=dict(UA, Accept="application/json"))
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_usgs():
    out = ROOT / "data" / "raw" / "usgs_regions"
    out.mkdir(parents=True, exist_ok=True)
    items = []
    try:
        items.append(sb_json(f"https://www.sciencebase.gov/catalog/item/{SB_ITEM}?format=json"))
        kids = sb_json(f"https://www.sciencebase.gov/catalog/items?parentId={SB_ITEM}&format=json&max=100&fields=title,files")
        items += kids.get("items", [])
    except Exception as e:  # noqa: BLE001
        print(f"  !! ScienceBase API failed: {e}")
    files = []
    for it in items:
        for f in it.get("files", []) or []:
            name, url = f.get("name", ""), f.get("downloadUri") or f.get("url")
            if url and name.lower().endswith((".zip", ".shp", ".shx", ".dbf", ".prj", ".cpg")):
                files.append((name, url, f.get("size", 0)))
    if not files:
        print("  !! Could not list USGS files automatically. Manual step:\n"
              f"     open https://www.sciencebase.gov/catalog/item/{SB_ITEM}\n"
              f"     download the region zip(s) into {out}\n     then re-run this script.")
        return False
    print(f"  {len(files)} USGS file(s) listed")
    ok = True
    for name, url, _ in files:
        ok &= get(url, out / name, min_bytes=100_000)
    # extract ONLY the small 1 km grids (the 10 m grids unpack to ~1 GB per region and are not needed)
    one_km = out.parent / "usgs_1km"
    for z in sorted(out.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                if z.name.startswith("A3_"):
                    zf.extractall(out.parent / "a3_regions")
                else:
                    zf.extractall(one_km, members=[n for n in zf.namelist() if "_1km_" in n])
            print(f"  extracted {z.name}")
        except zipfile.BadZipFile:
            print(f"  !! {z.name} is not a zip (server returned an error page) - deleting so it is retried")
            z.unlink(missing_ok=True)
            ok = False
    return ok


def fetch_horizons(n=50, seed=42):
    import csv
    sites = list(csv.DictReader(open(ROOT / "data" / "sites.csv", newline="", encoding="utf-8")))
    out = ROOT / "data" / "raw" / "horizons"
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for s in sites:
        times = sorted(t0 + timedelta(minutes=rng.randrange(0, 5 * 365 * 24 * 60)) for _ in range(n))
        h_km = float(s["height_m"]) / 1000.0 if s.get("height_m") not in (None, "", "nan") else 0.0
        lon = float(s["lon_deg"]) % 360.0
        for body, code in (("sun", "10"), ("earth", "399")):
            params = {
                "format": "json", "COMMAND": f"'{code}'", "OBJ_DATA": "NO", "MAKE_EPHEM": "YES",
                "EPHEM_TYPE": "OBSERVER", "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
                "SITE_COORD": f"'{lon:.6f},{float(s['lat_deg']):.6f},{h_km:.4f}'",
                "TLIST": "\n".join(t.strftime("'%Y-%m-%d %H:%M'") for t in times), "TLIST_TYPE": "CAL",
                "TIME_TYPE": "UT", "QUANTITIES": "'4'", "ANG_FORMAT": "DEG", "CSV_FORMAT": "YES",
                "EXTRA_PREC": "YES", "APPARENT": "AIRLESS",
            }
            url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(params)
            res = sb_json(url)
            (out / f"{s['site_id']}_{body}.json").write_text(json.dumps({
                "site_id": s["site_id"], "lat_deg": float(s["lat_deg"]), "lon_deg": float(s["lon_deg"]),
                "height_m": h_km * 1000, "body": body, "times_utc": [t.strftime("%Y-%m-%d %H:%M") for t in times],
                "horizons_result": res.get("result", "")}, indent=1))
            ok = "$$SOE" in res.get("result", "")
            print(f"  {'ok' if ok else '!! ERROR'} Horizons {s['site_id']} {body}")
            time.sleep(1.0)


def main():
    if "--horizons" in sys.argv:
        print("Official NAIF kernels (refresh)")
        for name in ("de421.bsp", "pck00008.tpc"):
            get(KERNELS[name], ROOT / "kernels" / name, refresh=True)
        print("USGS regions (retry any missing)")
        fetch_usgs()
        print("JPL Horizons validation samples -> data/raw/horizons/")
        fetch_horizons()
        print("\nDone. Next: python scripts/validate_horizons.py --offline")
        return
    results = {}
    print("1/3 NAIF SPICE kernels -> kernels/ (official copies replace the bundled mirrors)")
    for name, url in KERNELS.items():
        # download to .part and replace only on success, so a failed download never removes a working kernel
        results[name] = get(url, ROOT / "kernels" / name, refresh=True)
    print("2/3 LOLA DEMs -> data/raw/  (~420 MB, a few minutes)")
    for name in DEMS:
        results[name] = get(f"{PGDA}/{name}", ROOT / "data" / "raw" / name, min_bytes=1_000_000)
    print("3/3 USGS Artemis III region grids -> data/raw/usgs_regions/")
    results["USGS regions"] = fetch_usgs()
    print("\nSUMMARY")
    for k, v in results.items():
        print(f"  {'OK    ' if v else 'FAILED'} {k}")
    print("\nDone. Next: make_sites.py, precompute_horizons.py, precompute_ephem.py (see README).")


if __name__ == "__main__":
    main()
