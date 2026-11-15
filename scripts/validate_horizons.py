"""EPHEMERIS validation: compare our Skyfield Sun/Earth az/el with JPL Horizons topocentric output.

    python scripts/validate_horizons.py [--n 50] [site_id ...]      # online (calls the Horizons API)
    python scripts/validate_horizons.py --offline                    # uses data/raw/horizons/*.json saved by
                                                                     # scripts/fetch_external.py --horizons

Writes data/validation.json. This validates CELESTIAL POSITIONS ONLY (not terrain, visibility
or power). Horizons API docs: https://ssd-api.jpl.nasa.gov/doc/horizons.html
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.ephemeris import LunarSky  # noqa: E402

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
TARGETS = {"sun": "10", "earth": "399"}


def horizons_azel(target: str, lat, lon, height_km, times: pd.DatetimeIndex):
    tlist = "\n".join(t.strftime("'%Y-%m-%d %H:%M'") for t in times)
    params = {
        "format": "json", "COMMAND": f"'{target}'", "OBJ_DATA": "NO", "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER", "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{lon % 360:.6f},{lat:.6f},{height_km:.4f}'",
        "TLIST": tlist, "TLIST_TYPE": "CAL", "TIME_TYPE": "UT", "QUANTITIES": "'4'",
        "ANG_FORMAT": "DEG", "CSV_FORMAT": "YES", "EXTRA_PREC": "YES", "APPARENT": "AIRLESS",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        res = json.load(r)["result"]
    if "$$SOE" not in res:
        raise RuntimeError(res[:2000])
    body = res.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    az, el = [], []
    for line in body:
        nums = []
        for f in line.split(","):
            try:
                nums.append(float(f))
            except ValueError:
                pass
        az.append(nums[-2])
        el.append(nums[-1])
    return np.array(az), np.array(el)


def parse_result(res: str):
    if "$$SOE" not in res:
        raise RuntimeError(res[:2000])
    body = res.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    az, el = [], []
    for line in body:
        nums = []
        for f in line.split(","):
            try:
                nums.append(float(f))
            except ValueError:
                pass
        az.append(nums[-2])
        el.append(nums[-1])
    return np.array(az), np.array(el)


def offline_samples():
    """Yield (site_id, lat, lon, height_m, body, times, haz, hel) from saved Horizons responses."""
    for f in sorted((ROOT / "data" / "raw" / "horizons").glob("*.json")):
        d = json.loads(f.read_text())
        haz, hel = parse_result(d["horizons_result"])
        times = pd.DatetimeIndex(pd.to_datetime(d["times_utc"], utc=True))
        yield d["site_id"], d["lat_deg"], d["lon_deg"], d["height_m"], d["body"], times, haz, hel


def angdiff(a, b):
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", nargs="*")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    sky = LunarSky(ROOT / "kernels")
    if a.offline:
        report = {"what": "Ephemeris validation vs JPL Horizons (positions only)", "sites": {}}
        for sid, lat, lon, h_m, body, times, haz, hel in offline_samples():
            ours = sky.compute(lat, lon, h_m, times)
            daz_sky = angdiff(ours[f"{body}_az_deg"], haz) * np.cos(np.radians(hel))
            delv = ours[f"{body}_el_deg"].to_numpy() - hel
            r = {"n": int(len(times)), "max_abs_del_deg": float(np.abs(delv).max()),
                 "median_abs_del_deg": float(np.median(np.abs(delv))),
                 "max_abs_daz_sky_deg": float(np.abs(daz_sky).max()),
                 "median_abs_daz_sky_deg": float(np.median(np.abs(daz_sky)))}
            report["sites"].setdefault(sid, {})[body] = r
            print(f"{sid:22s} {body:5s} max|dEl| {r['max_abs_del_deg']:.5f} deg  max|dAz*cos(el)| {r['max_abs_daz_sky_deg']:.5f} deg")
        _finish(report)
        return
    sites = pd.read_csv(ROOT / "data" / "sites.csv")
    sites = sites[sites.site_id.isin(a.sites)] if a.sites else sites.head(3)
    rng = np.random.default_rng(42)
    span = pd.date_range("2026-01-01", "2031-01-01", freq="1min", tz="UTC")
    report = {"what": "Ephemeris validation vs JPL Horizons (positions only)", "sites": {}}
    for _, s in sites.iterrows():
        times = pd.DatetimeIndex(sorted(rng.choice(span, a.n, replace=False))).floor("min")
        h_m = float(s.height_m) if pd.notna(s.get("height_m")) and str(s.get("height_m")) != "" else 0.0
        ours = sky.compute(s.lat_deg, s.lon_deg, h_m, times)
        site_rep = {}
        for body, code in TARGETS.items():
            haz, hel = horizons_azel(code, s.lat_deg, s.lon_deg, h_m / 1000.0, times)
            daz = angdiff(ours[f"{body}_az_deg"], haz)
            # azimuth error matters less near zenith; scale by cos(el) for an on-sky separation
            daz_sky = daz * np.cos(np.radians(hel))
            delv = ours[f"{body}_el_deg"].to_numpy() - hel
            site_rep[body] = {"n": int(len(times)),
                              "max_abs_del_deg": float(np.abs(delv).max()),
                              "median_abs_del_deg": float(np.median(np.abs(delv))),
                              "max_abs_daz_sky_deg": float(np.abs(daz_sky).max()),
                              "median_abs_daz_sky_deg": float(np.median(np.abs(daz_sky)))}
            print(f"{s.site_id:22s} {body:5s} max|dEl| {site_rep[body]['max_abs_del_deg']:.5f} deg"
                  f"  max|dAz*cos(el)| {site_rep[body]['max_abs_daz_sky_deg']:.5f} deg")
            time.sleep(1.0)   # be polite to the API
        report["sites"][s.site_id] = site_rep
    _finish(report)


def _finish(report):
    if not report["sites"]:
        raise SystemExit("No Horizons samples found.")
    allmax = max(v["max_abs_del_deg"] for r in report["sites"].values() for v in r.values())
    allmaz = max(v["max_abs_daz_sky_deg"] for r in report["sites"].values() for v in r.values())
    report["overall_max_error_deg"] = float(max(allmax, allmaz))
    report["generated_utc"] = pd.Timestamp.now('UTC').isoformat()
    (ROOT / "data" / "validation.json").write_text(json.dumps(report, indent=2))
    print(f"\nOverall max error: {report['overall_max_error_deg']:.5f} deg  -> data/validation.json")
    if report["overall_max_error_deg"] > 0.05:
        print("!! > 0.05 deg: check frame (MOON_ME_DE421), longitude sign (east +), and site height")


if __name__ == "__main__":
    main()
