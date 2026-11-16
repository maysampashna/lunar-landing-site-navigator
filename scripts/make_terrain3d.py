"""Cut small LOLA terrain tiles for the 3D views (needs data/raw/LDEM_80S_80MPP_ADJ.TIF and tifffile).

Run from the project folder that contains data/raw. Writes data/terrain3d.npz (~1.2 MB)."""
import csv, numpy as np, tifffile
R = 1737400.0
dem = tifffile.imread("data/raw/LDEM_80S_80MPP_ADJ.TIF")          # (7600, 7600) metres, 80 m pixels
X0, Y0, PX = -304000.0, 304000.0, 80.0
def rc(x, y):  # pixel centre containing (x, y)
    return int((Y0 - y) // PX), int((x - X0) // PX)
def block(a, f):
    n0, n1 = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    return np.nanmean(a[:n0, :n1].reshape(n0 // f, f, n1 // f, f), axis=(1, 3))
sites = list(csv.DictReader(open("_github_upload/data/sites.csv")))
out, xs, ys = {}, [], []
HALF, F = 40000.0, 4                                                  # +/-40 km, 320 m cells
for s in sites:
    lat, lon = float(s["lat_deg"]), float(s["lon_deg"])
    rho = 2 * R * np.tan(np.radians((90 + lat) / 2))
    x, y = rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))
    xs.append(x); ys.append(y)
    r0, c0 = rc(x, y)
    n = int(HALF / PX)
    patch = dem[r0 - n:r0 + n, c0 - n:c0 + n]
    out[f"site_{s['site_id']}"] = np.round(block(patch, F)).astype(np.int16)
    out[f"xy_{s['site_id']}"] = np.array([x, y, X0 + (c0 - n) * PX, Y0 - (r0 - n) * PX])  # site xy, patch upper-left corner
    print(s["site_id"], "csv h", s["height_m"], "dem h", round(float(dem[r0, c0]), 1), out[f"site_{s['site_id']}"].shape)
# regional tile around all sites (+/-60 km margin), ~960 m cells
pad = 60000.0
x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
side = max(x1 - x0, y1 - y0); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
ra, ca = rc(cx - side / 2, cy + side / 2); rb, cb = rc(cx + side / 2, cy - side / 2)
reg = block(dem[ra:rb, ca:cb], 12)
out["region"] = np.round(reg).astype(np.int16)
out["region_ul"] = np.array([X0 + ca * PX, Y0 - ra * PX, 12 * PX])
out["meta"] = np.array([HALF, F * PX])
np.savez_compressed("_github_upload/data/terrain3d.npz", **out)
print("region", reg.shape, "ul", out["region_ul"])

# wide tiles for the 3D observer view: +/-96 km at 640 m cells (keys wide_<site>, wxy_<site>, wmeta)
out = dict(np.load("_github_upload/data/terrain3d.npz"))
HALF, F = 96000.0, 8
for s in sites:
    lat, lon = float(s["lat_deg"]), float(s["lon_deg"])
    rho = 2 * R * np.tan(np.radians((90 + lat) / 2))
    x, y = rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))
    r0, c0 = rc(x, y); n = int(HALF / PX); a, b = max(r0 - n, 0), max(c0 - n, 0)
    out[f"wide_{s['site_id']}"] = np.round(block(dem[a:r0 + n, b:c0 + n], F)).astype(np.int16)
    out[f"wxy_{s['site_id']}"] = np.array([x, y, X0 + b * PX, Y0 - a * PX])
out["wmeta"] = np.array([HALF, F * PX])
np.savez_compressed("_github_upload/data/terrain3d.npz", **out)
