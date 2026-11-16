"""Render the Home page hero image: an orbital view toward the lunar south pole over real NASA LOLA terrain,
with the candidate sites labelled against a star field.

Terrain: LOLA LDEM_60S_240MPP (polar cap, 7.7 km cells) and LDEM_80S_80MPP (site region, 0.96 km cells) via
data/terrain3d.npz. Shading: Lambert from a low polar Sun (illustrative lighting, not a computed sky state).

    python scripts/make_home_moon.py      → assets/home_moon.jpg, assets/stars.jpg
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
R = 1737.4                         # km
W, H = 2400, 1250
EXAG = 2.5                         # relief exaggeration used for shading normals
AIM = 0.07                         # tilts the view up so the horizon and stars show at the top


def font(size, bold=False):
    names = (["/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"] if bold else
             ["/usr/share/fonts/opentype/inter/Inter-Regular.otf"])
    names += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf"]
    for f in names:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def latlon_xyz(lat, lon, r=1.0):
    la, lo = np.radians(lat), np.radians(lon)
    return np.stack([r * np.cos(la) * np.cos(lo), r * np.cos(la) * np.sin(lo), r * np.sin(la)], -1)


def polar_xyz(xkm, ykm, h_m):
    rho = np.hypot(xkm, ykm)
    lat = -90.0 + 2.0 * np.degrees(np.arctan(rho / (2 * R)))
    lon = np.degrees(np.arctan2(xkm, ykm))
    return latlon_xyz(lat, lon, R + h_m / 1000.0 * EXAG)


def shade_grid(z, ulx, uly, cell, sun):
    """Lambert shading of a polar-stereographic height grid, from true 3D normals."""
    n0, n1 = z.shape
    X = ulx + (np.arange(n1) + 0.5) * cell
    Y = uly - (np.arange(n0) + 0.5) * cell
    P = polar_xyz(*np.meshgrid(X, Y), z)
    du, dv = np.gradient(P, axis=1), np.gradient(P, axis=0)
    nrm = np.cross(du, dv)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    out = P / np.linalg.norm(P, axis=-1, keepdims=True)
    nrm *= np.sign((nrm * out).sum(-1, keepdims=True))                # outward
    return np.clip((nrm * sun).sum(-1), 0, 1)


def star_field(rng, w, h, n):
    img = np.zeros((h, w, 3), float) + np.array([2, 4, 9]) / 255.0
    x, y = rng.integers(0, w, n), rng.integers(0, h, n)
    b = (rng.random(n) ** 7) * 0.95 + 0.04
    tint = np.array([[1, 1, 1], [0.78, 0.86, 1.0], [1.0, 0.9, 0.76], [0.9, 0.95, 1.0]])[rng.integers(0, 4, n)]
    np.add.at(img, (y, x), b[:, None] * tint)
    bright = b > 0.55
    for xi, yi, ti in zip(x[bright], y[bright], tint[bright]):
        img[max(yi - 1, 0):yi + 2, xi] += 0.22 * ti
        img[yi, max(xi - 1, 0):xi + 2] += 0.22 * ti
    yy, xx = np.mgrid[0:h, 0:w]
    band = np.exp(-(((yy - 0.25 * h) - 0.18 * (xx - 0.5 * w)) / (0.16 * h)) ** 2)
    img += band[..., None] * np.array([0.035, 0.04, 0.055]) * (0.6 + 0.4 * rng.random((h, w, 1)))
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.35))


def main():
    t = np.load(ROOT / "data" / "terrain3d.npz")
    sites = list(csv.DictReader(open(ROOT / "data" / "sites.csv")))

    sun = latlon_xyz(-2.0, 120.0)                                        # low polar Sun, from the frame's right
    cap_l = shade_grid(t["cap"].astype(float), *(t["cap_ul"] / 1000.0), sun)
    rx0, ry0, rc = t["region_ul"] / 1000.0
    reg_l = shade_grid(t["region"].astype(float), rx0, ry0, rc, sun)

    # camera in orbit ~330 km up over 76°S on the 180° side, looking toward the site cluster near the pole
    target = latlon_xyz(-88.6, -20.0, R)
    cam = latlon_xyz(-80.5, 170.0, R + 230.0)
    fwd = target - cam; fwd /= np.linalg.norm(fwd)
    upr = cam / np.linalg.norm(cam)                                     # local vertical → level horizon
    right = np.cross(fwd, upr); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    tanf = np.tan(np.radians(56.0) / 2)
    yy, xx = np.mgrid[0:H, 0:W]
    sx = (xx + 0.5 - W / 2) / (W / 2) * tanf
    sy = (H / 2 - yy - 0.5) / (W / 2) * tanf + AIM
    d = fwd + sx[..., None] * right + sy[..., None] * up
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    b = (d * cam).sum(-1); c = (cam * cam).sum() - R * R
    disc = b * b - c
    hit = (disc > 0) & (b < 0)
    tt = -b - np.sqrt(np.clip(disc, 0, None))
    P = cam + tt[..., None] * d
    lat = np.degrees(np.arcsin(np.clip(P[..., 2] / R, -1, 1)))
    lon = np.degrees(np.arctan2(P[..., 1], P[..., 0]))
    rho = 2 * R * np.tan(np.radians((90 + lat) / 2))
    px_, py_ = rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))

    def sample(grid, ulx, uly, cell):
        n0, n1 = grid.shape
        fx = (px_ - ulx) / cell - 0.5; fy = (uly - py_) / cell - 0.5
        x0 = np.clip(np.floor(fx).astype(int), 0, n1 - 2); y0 = np.clip(np.floor(fy).astype(int), 0, n0 - 2)
        ax = np.clip(fx - x0, 0, 1); ay = np.clip(fy - y0, 0, 1)
        v = (grid[y0, x0] * (1 - ax) * (1 - ay) + grid[y0, x0 + 1] * ax * (1 - ay)
             + grid[y0 + 1, x0] * (1 - ax) * ay + grid[y0 + 1, x0 + 1] * ax * ay)
        ok = (fx >= 0) & (fy >= 0) & (fx <= n1 - 1) & (fy <= n0 - 1)
        return v, ok

    lam_cap, ok_cap = sample(cap_l, *(t["cap_ul"] / 1000.0))
    lam_reg, ok_reg = sample(reg_l, rx0, ry0, rc)
    n_reg = t["region"].shape[0]
    ex = np.minimum.reduce([(px_ - rx0), (rx0 + n_reg * rc - px_), (ry0 - py_), (py_ - (ry0 - n_reg * rc))])
    wreg = np.clip(ex / 25.0, 0, 1) * ok_reg
    lam = np.where(ok_cap, lam_cap, np.clip((P / R * sun).sum(-1), 0, 1))
    lam = lam * (1 - wreg) + lam_reg * wreg
    grey = 0.05 + 0.80 * np.clip(lam * np.where(wreg > 0.5, 1.7, 1.3), 0, 1) ** 0.9
    rgb = grey[..., None] * np.array([1.0, 0.985, 0.955])
    dist = np.linalg.norm(P - cam, axis=-1)
    rgb *= (1.0 - 0.25 * np.clip((dist - 330) / 1400, 0, 1))[..., None]

    sky = np.asarray(star_field(np.random.default_rng(5), W, H, 9000), float) / 255.0
    img = np.where(hit[..., None], rgb, sky)
    edge = np.asarray(Image.fromarray((hit * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), float) / 255
    img += (np.abs(edge - hit) * 0.10)[..., None] * np.array([0.6, 0.8, 1.0])
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))

    draw = ImageDraw.Draw(out)
    pts = []
    for s in sites:
        q = latlon_xyz(float(s["lat_deg"]), float(s["lon_deg"]), R + float(s["height_m"]) / 1000.0) - cam
        zf = q @ fwd
        u = (q @ right) / zf / tanf * (W / 2) + W / 2
        v = H / 2 - ((q @ up) / zf - AIM) / tanf * (W / 2)
        pts.append((u, v, s["name"]))
    pts.sort(key=lambda p: p[0])
    f = font(30, bold=True)
    teal, amber = (45, 212, 191), (245, 165, 36)
    widths = [draw.textlength(nm, font=f) + 24 for _, _, nm in pts]
    rows = {0: [], 1: []}
    for k, p_ in enumerate(pts):
        rows[k % 2].append(k)
    lx = {k: pts[k][0] for k in range(len(pts))}
    for ks in rows.values():                                          # push apart left-to-right, then centre
        for _ in range(50):
            for a_, b_ in zip(ks, ks[1:]):
                gap = lx[b_] - lx[a_] - (widths[a_] + widths[b_]) / 2 - 16
                if gap < 0:
                    lx[a_] += gap / 2; lx[b_] -= gap / 2
        for k in ks:
            lx[k] = float(np.clip(lx[k], widths[k] / 2 + 20, W - widths[k] / 2 - 20))
    for k, (u, v, name) in enumerate(pts):
        ly = 70 + (k % 2) * 62
        tw = widths[k] - 24
        draw.line([(lx[k], ly + 22), (u, v - 9)], fill=teal, width=3)
        draw.rounded_rectangle([lx[k] - tw / 2 - 12, ly - 18, lx[k] + tw / 2 + 12, ly + 22], radius=8,
                               fill=(6, 19, 31), outline=teal, width=2)
        draw.text((lx[k], ly + 2), name, font=f, fill=(235, 244, 247), anchor="mm")
        draw.ellipse([u - 8, v - 8, u + 8, v + 8], fill=amber, outline=(255, 255, 255), width=3)
    out.save(ROOT / "assets" / "home_moon.jpg", quality=90, optimize=True, progressive=True)
    star_field(np.random.default_rng(11), 1920, 1080, 6500).save(ROOT / "assets" / "stars.jpg", quality=85,
                                                                optimize=True)
    print("saved assets/home_moon.jpg, assets/stars.jpg")


if __name__ == "__main__":
    main()
