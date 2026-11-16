"""Render the Home page hero image: the Moon (north mostly visible, south pole near the lower limb) with labelled
arrows to the candidate sites, over a star field.

Surface: NASA SVS CGI Moon Kit LRO colour map (data/raw/lroc_color_poles_4k.tif, credit NASA's Scientific
Visualization Studio) if present; otherwise our LOLA 60°S polar terrain on a plain sphere.
Lighting is chosen for legibility (a decorative illustration, not a computed sky state).

    python scripts/make_home_moon.py      → assets/home_moon.jpg
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
R_KM = 1737.4
W, H = 2400, 1300                # output (rendered at 1×; text drawn at full size)
CX, CY, RAD = W // 2, 600, 540   # moon disc centre/radius in pixels
LAT0, LON0 = -18.0, 0.0          # sub-observer point: near side, slightly south so the pole is in view


def font(size, bold=False):
    for f in (["/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf"]
              if bold else ["/usr/share/fonts/opentype/inter/Inter-Regular.otf"]) + \
             ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf"]:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def basis():
    la, lo = np.radians(LAT0), np.radians(LON0)
    d = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])      # toward the viewer
    e = np.array([-np.sin(lo), np.cos(lo), 0.0])                                       # east = screen right
    n = np.cross(d, e)                                                                 # screen up (north-ish)
    return d, e, n


def stars(rng):
    img = np.zeros((H, W, 3), float)
    img[:] = np.array([3, 7, 14]) / 255.0
    yy, xx = np.mgrid[0:H, 0:W]
    img += (np.exp(-(((xx - 0.85 * W) / (0.6 * W)) ** 2 + ((yy - 0.05 * H) / (0.5 * H)) ** 2))[..., None]
            * np.array([0.02, 0.05, 0.07]))
    n = 2600
    x, y = rng.integers(0, W, n), rng.integers(0, H, n)
    b = rng.power(6, n)[::-1] ** 3 * 0.9 + 0.05
    tint = rng.choice([[1, 1, 1], [0.8, 0.88, 1.0], [1.0, 0.92, 0.8]], n)
    for xi, yi, bi, ti in zip(x, y, b, tint):
        img[yi, xi] = np.clip(img[yi, xi] + bi * np.array(ti), 0, 1)
    big = rng.random(n) < 0.02
    for xi, yi, ti in zip(x[big], y[big], tint[big]):
        img[max(yi - 1, 0):yi + 2, max(xi - 1, 0):xi + 2] += 0.25 * np.array(ti)
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.4))


def moon_rgb():
    d, e, n = basis()
    yy, xx = np.mgrid[0:H, 0:W]
    u, v = (xx - CX) / RAD, (CY - yy) / RAD
    inside = u ** 2 + v ** 2 <= 1.0
    z = np.sqrt(np.clip(1 - u ** 2 - v ** 2, 0, 1))
    P = u[..., None] * e + v[..., None] * n + z[..., None] * d
    lat = np.degrees(np.arcsin(np.clip(P[..., 2], -1, 1)))
    lon = np.degrees(np.arctan2(P[..., 1], P[..., 0]))
    tex_path = ROOT / "data" / "raw" / "lroc_color_poles_4k.tif"
    if tex_path.exists():
        Image.MAX_IMAGE_PIXELS = None
        tex = np.asarray(Image.open(tex_path).convert("RGB"), float) / 255.0
        th, tw = tex.shape[:2]
        tx = np.clip(((lon + 180) / 360 * tw).astype(int), 0, tw - 1)
        ty = np.clip(((90 - lat) / 180 * th).astype(int), 0, th - 1)
        albedo = tex[ty, tx]
        source = "LRO colour map (NASA SVS CGI Moon Kit)"
    else:
        albedo = np.full(P.shape, 0.62)
        t = np.load(ROOT / "data" / "terrain3d.npz")
        cap = t["cap"].astype(float)
        ulx, uly, cell = t["cap_ul"] / 1000.0
        gy, gx = np.gradient(cap / 1000.0, cell)
        shade = np.clip(0.75 + 2.5 * (-gx * 0.6 + gy * 0.8), 0.3, 1.25)
        rho = 2 * R_KM * np.tan(np.radians((90 + lat) / 2))
        px_ = rho * np.sin(np.radians(lon)); py_ = rho * np.cos(np.radians(lon))
        cx = ((px_ - ulx) / cell).astype(int); cy = ((uly - py_) / cell).astype(int)
        ok = inside & (lat < -60) & (cx >= 0) & (cy >= 0) & (cx < cap.shape[1]) & (cy < cap.shape[0])
        albedo[ok] *= shade[cy[ok], cx[ok], None]
        source = "LOLA polar terrain on a smooth sphere"
    sun = 0.55 * d - 0.62 * e + 0.42 * n
    sun /= np.linalg.norm(sun)
    lam = np.clip((P * sun).sum(-1), 0, 1)
    light = 0.06 + 0.94 * lam ** 0.85
    rgb = np.clip(albedo * light[..., None] * 1.12, 0, 1)
    alpha = np.clip((1 - np.sqrt(u ** 2 + v ** 2)) * RAD + 0.5, 0, 1)                   # 1-px antialiased limb
    return rgb, alpha, source


def project(lat, lon):
    d, e, n = basis()
    la, lo = np.radians(lat), np.radians(lon)
    p = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    return CX + RAD * float(p @ e), CY - RAD * float(p @ n), float(p @ d) > 0


def main():
    rng = np.random.default_rng(7)
    bg = stars(rng)
    rgb, alpha, source = moon_rgb()
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([CX - RAD - 18, CY - RAD - 18, CX + RAD + 18, CY + RAD + 18], fill=60)
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    base = Image.composite(Image.new("RGB", (W, H), (120, 150, 170)), bg, glow)
    moon = Image.fromarray((rgb * 255).astype(np.uint8))
    out = Image.composite(moon, base, Image.fromarray((alpha * 255).astype(np.uint8)))

    sites = list(csv.DictReader(open(ROOT / "data" / "sites.csv")))
    pts = []
    for s in sites:
        x, y, vis = project(float(s["lat_deg"]), float(s["lon_deg"]))
        if vis:
            pts.append((x, y, s["name"]))
    pts.sort(key=lambda p: p[0])
    draw = ImageDraw.Draw(out)
    f = font(30, bold=True)
    left, right = pts[: len(pts) // 2], pts[len(pts) // 2:]
    teal, amber = (45, 212, 191), (245, 165, 36)
    for group, side in ((left, -1), (right, 1)):
        n_ = len(group)
        for k, (x, y, name) in enumerate(sorted(group, key=lambda p: p[1])):
            lx = CX + side * (RAD + 120)
            ly = CY + RAD * 0.25 + k * 62 - (n_ - 1) * 31 + 140
            tw = draw.textlength(name, font=f)
            tx = lx if side > 0 else lx - tw
            elbow = (lx - side * 40, ly)
            draw.line([(x, y), elbow, (lx - side * 8, ly)], fill=teal, width=3)
            draw.ellipse([x - 6, y - 6, x + 6, y + 6], fill=amber, outline=(255, 255, 255), width=2)
            draw.text((tx, ly - 19), name, font=f, fill=(235, 244, 247))
    draw.text((W - 24, H - 20), f"Moon: {source} · sites: USGS Artemis III regions", font=font(20),
              fill=(120, 140, 150), anchor="rd")
    out.convert("RGB").save(ROOT / "assets" / "home_moon.jpg", quality=88, optimize=True, progressive=True)
    stars(np.random.default_rng(11)).save(ROOT / "assets" / "stars.jpg", quality=85, optimize=True)
    print("saved assets/home_moon.jpg using", source)


if __name__ == "__main__":
    main()
