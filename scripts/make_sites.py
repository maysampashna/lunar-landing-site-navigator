"""Build data/sites.csv from the USGS Artemis III region grids (DOI 10.5066/P1MEQ6UK).

For each region: read its 1 km grid shapefile(s), union the cells into a footprint, take an
INTERIOR representative point (shapely representative_point -> guaranteed inside), and convert
it to lunar lat/lon using the shapefile's OWN lunar CRS (never an Earth/WGS84 transform).
The point is FIXED for all dates (no per-window optimisation).

    python scripts/make_sites.py data/raw/usgs_regions

Provisional rows (published reference points) already in sites.csv are kept unless replaced.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REGIONS = ["Peak_Near_Cabeus_B", "Haworth", "Malapert_Massif", "Mons_Mouton_Plateau", "Mons_Mouton",
           "Nobile_Rim_1", "Nobile_Rim_2", "de_Gerlache_Rim_2", "Slater_Plain"]


def region_files(folder: Path, region: str) -> list[Path]:
    shp = [p for p in folder.rglob("*.shp") if region.lower() in p.name.lower()]
    # prefer the 1 km grids (file names contain '1km' / '1000')
    km = [p for p in shp if re.search(r"1\s*km|1000", p.name, re.I)]
    # avoid matching 'Mons_Mouton' files that are actually 'Mons_Mouton_Plateau'
    if region == "Mons_Mouton":
        km = [p for p in (km or shp) if "plateau" not in p.name.lower()]
    return km or shp


def interior_point(files: list[Path]):
    import geopandas as gpd
    from pyproj import Transformer
    from shapely.ops import unary_union

    gdfs = [gpd.read_file(f) for f in files]
    crs = gdfs[0].crs
    if crs is None:
        raise ValueError(f"{files[0]} has no .prj / CRS")
    if not crs.is_projected:
        raise ValueError(f"{files[0]}: expected a projected lunar CRS, got {crs}")
    body = (crs.ellipsoid.name if crs.ellipsoid else "") + " " + crs.to_wkt()
    if "moon" not in body.lower():
        raise ValueError(f"{files[0]}: CRS does not look lunar ({crs.name}); refusing Earth transforms")
    geoms = []
    for g in gdfs:
        g = g.to_crs(crs) if g.crs != crs else g
        geoms.extend(g.geometry.values)
    footprint = unary_union(geoms)
    pt = footprint.representative_point()
    to_geo = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    lon, lat = to_geo.transform(pt.x, pt.y)
    lon = (lon + 180) % 360 - 180
    return lat, lon, footprint.area / 1e6


def main(folder: str):
    folder = Path(folder)
    sites_path = ROOT / "data" / "sites.csv"
    sites = pd.read_csv(sites_path) if sites_path.exists() else pd.DataFrame()
    rows = []
    for r in REGIONS:
        files = region_files(folder, r)
        if not files:
            print(f"!! no shapefile found for {r}")
            continue
        lat, lon, area = interior_point(files)
        assert -90 <= lat <= -80, f"{r}: latitude {lat} not near south pole - check CRS handling"
        print(f"{r:22s} lat {lat:9.4f}  lon {lon:9.4f}  footprint {area:7.1f} km^2  ({len(files)} file(s))")
        rows.append({"site_id": r.lower(), "name": r.replace("_", " "), "lat_deg": round(lat, 5),
                     "lon_deg": round(lon, 5), "height_m": "", "frame": "ME",
                     "kind": "artemis_region",
                     "source": "USGS DOI 10.5066/P1MEQ6UK (regions from LROC QuickMap)",
                     "point_rule": "interior representative point of union of 1 km grid cells; fixed for all dates",
                     "note": "representative point, not a NASA-designated landing site",
                     "provisional": False})
    new = pd.DataFrame(rows)
    if not sites.empty:
        sites = sites[~sites["site_id"].isin(new["site_id"])]
        new = pd.concat([new, sites], ignore_index=True)
    new.to_csv(sites_path, index=False)
    print(f"wrote {sites_path} ({len(new)} sites). Heights are filled by precompute_horizons.py")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "raw" / "usgs_regions"))
