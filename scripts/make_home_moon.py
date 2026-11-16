"""Render the Home page hero image: an orbital view toward the lunar south pole over real NASA LOLA terrain,
with the candidate sites labelled against a star field.

Terrain: LOLA LDEM_60S_240MPP (polar cap, 7.7 km cells) and LDEM_80S_80MPP (site region, 0.96 km cells) via
data/terrain3d.npz. Shading: Lambert from a low polar Sun (illustrative lighting, not a computed sky state).

    python scripts/make_home_moon.py      → assets/home_moon.jpg, assets/stars.jpg
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
R = 1737.4                         # km
W, H = 2400, 1350
EXAG = 2.5                         # relief exaggeration used for shading normals
AIM = 0.06                         # tilts the view up so the horizon and stars show at the top


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


    # camera in orbit ~330 km up over 76°S on the 180° side, looking toward the site cluster near the pole
    target = latlon_xyz(-88.6, -20.0, R)
    cam = latlon_xyz(-79.0, 170.0, R + 380.0)
    fwd = target - cam; fwd /= np.linalg.norm(fwd)
    upr = cam / np.linalg.norm(cam)                                     # local vertical → level horizon
    right = np.cross(fwd, upr); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    # Sun low over the horizon, upper-left of the frame; terrain is lit from that direction (illustrative)
    sun = 0.20 * fwd - 0.95 * right + 0.22 * up
    sun /= np.linalg.norm(sun)
    tanf = np.tan(np.radians(60.0) / 2)
    cap_l = shade_grid(t["cap"].astype(float), *(t["cap_ul"] / 1000.0), sun)
    rx0, ry0, rc = t["region_ul"] / 1000.0
    reg_l = shade_grid(t["region"].astype(float), rx0, ry0, rc, sun)
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
    wreg = np.clip(ex / 80.0, 0, 1) * ok_reg
    lam = np.where(ok_cap, lam_cap, np.clip((P / R * sun).sum(-1), 0, 1))
    lam = lam * (1 - wreg) + lam_reg * wreg
    grey = 0.07 + 0.88 * np.clip(lam * np.where(wreg > 0.5, 1.6, 1.3), 0, 1) ** 0.8
    rgb = grey[..., None] * np.array([1.0, 0.985, 0.955])
    dist = np.linalg.norm(P - cam, axis=-1)
    rgb *= (1.0 - 0.25 * np.clip((dist - 330) / 1400, 0, 1))[..., None]

    sky = np.asarray(star_field(np.random.default_rng(5), W, H, 9000), float) / 255.0
    img = np.where(hit[..., None], rgb, sky)
    edge = np.asarray(Image.fromarray((hit * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), float) / 255
    img += (np.abs(edge - hit) * 0.10)[..., None] * np.array([0.6, 0.8, 1.0])
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))

    def proj(vec):
        zf = vec @ fwd
        return (vec @ right) / zf / tanf * (W / 2) + W / 2, H / 2 - ((vec @ up) / zf - AIM) / tanf * (W / 2), zf > 0

    # Sun glow (upper left) and a small Earth near the horizon (upper right) — illustrative
    glow = Image.new("RGB", (W, H), (0, 0, 0)); gd = ImageDraw.Draw(glow)
    sx_, sy_, _ = proj(sun * 1e6)
    sx_, sy_ = float(np.clip(sx_, 60, W * 0.3)), float(np.clip(sy_, 80, H * 0.3))
    for r_, c_ in ((260, (40, 28, 10)), (140, (110, 80, 30)), (60, (255, 220, 150)), (26, (255, 250, 235))):
        gd.ellipse([sx_ - r_, sy_ - r_, sx_ + r_, sy_ + r_], fill=c_)
    glow = glow.filter(ImageFilter.GaussianBlur(38))
    out = Image.fromarray(np.clip(np.asarray(out, float) + np.asarray(glow, float), 0, 255).astype(np.uint8))
    ImageDraw.Draw(out).ellipse([sx_ - 22, sy_ - 22, sx_ + 22, sy_ + 22], fill=(255, 251, 240))
    ex_, ey_, er = W * 0.905, H * 0.30, 74
    yy2, xx2 = np.mgrid[0:H, 0:W]
    dd = np.hypot(xx2 - ex_, yy2 - ey_) / er
    disc_ = dd <= 1
    zz = np.sqrt(np.clip(1 - dd ** 2, 0, 1))
    lit = np.clip(((xx2 - ex_) / er) * -0.75 + zz * 0.55 + ((ey_ - yy2) / er) * 0.2, 0, 1)
    earth = np.stack([0.20 + 0.55 * lit, 0.38 + 0.50 * lit, 0.75 + 0.25 * lit], -1) * (0.25 + 0.75 * lit[..., None])
    arr = np.asarray(out, float) / 255
    halo = np.clip(1.25 - dd, 0, 0.25)[..., None] * np.array([0.25, 0.45, 0.9]) * (~disc_)[..., None]
    arr = np.where(disc_[..., None], earth, arr + halo)
    out = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))

    # site markers and labels with a soft cyan glow
    pts = []
    for s_ in sites:
        u, v, okv = proj(latlon_xyz(float(s_["lat_deg"]), float(s_["lon_deg"]), R + float(s_["height_m"]) / 1000.0) - cam)
        if okv:
            pts.append((u, v, s_["name"], s_["site_id"]))
    pts.sort(key=lambda p_: p_[0])
    f = font(30, bold=True)
    cyan = (80, 220, 255)
    draw = ImageDraw.Draw(out)

    def wrap(name):
        w_ = name.split()
        return name if len(name) <= 14 or len(w_) == 1 else " ".join(w_[:len(w_) // 2 + (len(w_) == 3)]) + "\n" + \
            " ".join(w_[len(w_) // 2 + (len(w_) == 3):])

    boxes = []
    for k, (u, v, name, sid) in enumerate(pts):
        txt = wrap(name)
        bb = draw.multiline_textbbox((0, 0), txt, font=f, align="center", spacing=4)
        bw, bh = bb[2] - bb[0] + 34, bb[3] - bb[1] + 26
        ly = max(H * 0.27, v - 120 - (k % 3) * 66)
        boxes.append([u, ly, bw, bh, txt, u, v, sid])
    for _ in range(60):                                                   # spread boxes horizontally
        for a_, b_ in zip(boxes, boxes[1:]):
            gap = (b_[0] - a_[0]) - (a_[2] + b_[2]) / 2 - 18
            if gap < 0 and abs(a_[1] - b_[1]) < (a_[3] + b_[3]) / 2 + 10:
                a_[0] += gap / 2; b_[0] -= gap / 2
    layer = Image.new("RGB", (W, H), (0, 0, 0)); ld = ImageDraw.Draw(layer)
    for lx, ly, bw, bh, txt, u, v, sid in boxes:
        lx = float(np.clip(lx, bw / 2 + 20, W - bw / 2 - 20))
        ld.line([(lx, ly + bh / 2), (u, v)], fill=cyan, width=6)
        ld.ellipse([u - 16, v - 16, u + 16, v + 16], fill=cyan)
        ld.rounded_rectangle([lx - bw / 2, ly - bh / 2, lx + bw / 2, ly + bh / 2], radius=12, outline=cyan, width=6)
    layer = layer.filter(ImageFilter.GaussianBlur(9))
    out = Image.fromarray(np.clip(np.asarray(out, float) + 0.8 * np.asarray(layer, float), 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(out)
    hot = []
    for lx, ly, bw, bh, txt, u, v, sid in boxes:
        lx = float(np.clip(lx, bw / 2 + 20, W - bw / 2 - 20))
        hot.append({"site_id": sid, "x": (lx - bw / 2) / W, "y": (ly - bh / 2) / H, "w": bw / W, "h": bh / H})
        draw.line([(lx, ly + bh / 2), (u, v)], fill=(150, 235, 255), width=2)
        draw.rounded_rectangle([lx - bw / 2, ly - bh / 2, lx + bw / 2, ly + bh / 2], radius=12,
                               fill=(6, 22, 36), outline=(110, 225, 255), width=2)
        draw.multiline_text((lx, ly), txt, font=f, fill=(240, 248, 252), anchor="mm", align="center", spacing=4)
        draw.ellipse([u - 7, v - 7, u + 7, v + 7], fill=(230, 252, 255))
    # darken the bottom for the buttons
    fade = np.clip((np.arange(H) - 0.70 * H) / (0.30 * H), 0, 1) ** 1.5 * 0.65
    out = Image.fromarray((np.asarray(out, float) * (1 - fade)[:, None, None]).astype(np.uint8))
    (ROOT / "assets" / "home_moon_labels.json").write_text(json.dumps(hot, indent=1))
    out.save(ROOT / "assets" / "home_moon.jpg", quality=90, optimize=True, progressive=True)
    star_field(np.random.default_rng(11), 1920, 1080, 6500).save(ROOT / "assets" / "stars.jpg", quality=85,
                                                                optimize=True)
    print("saved assets/home_moon.jpg, assets/stars.jpg")


if __name__ == "__main__":
    main()
