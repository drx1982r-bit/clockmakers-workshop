"""
cw_textures.py - generates image textures procedurally with numpy
(a clockmaker's blueprint drawing).  Saved to materials/textures/.
"""
import math
import os
import numpy as np


def _aa_line_mask(d, w):
    return np.clip(1.0 - np.abs(d) / w, 0.0, 1.0)


def blueprint(path, W=2048, H=1408, seed=7):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ink = np.zeros((H, W), np.float32)

    def circle(cx, cy, r, w=1.4):
        nonlocal ink
        d = np.hypot(xx - cx, yy - cy) - r
        ink = np.maximum(ink, _aa_line_mask(d, w))

    def gear(cx, cy, teeth, rp, m, w=1.6):
        nonlocal ink
        ang = np.arctan2(yy - cy, xx - cx)
        rho = np.hypot(xx - cx, yy - cy)
        sq = np.clip(np.sin(ang * teeth) * 3.0, -1, 1)
        r = rp + sq * m
        ink = np.maximum(ink, _aa_line_mask(rho - r, w) * (rho < rp + m * 1.5))
        circle(cx, cy, rp - m * 2.5, 1.0)
        circle(cx, cy, rp * 0.18, 1.2)
        circle(cx, cy, rp * 0.06, 1.0)
        for k in range(5):
            a = k * math.tau / 5
            dx, dy = math.cos(a), math.sin(a)
            # spoke edges
            for off in (-rp * 0.05, rp * 0.05):
                d = (xx - cx) * (-dy) + (yy - cy) * dx - off
                along = (xx - cx) * dx + (yy - cy) * dy
                ink = np.maximum(ink, _aa_line_mask(d, 1.0) *
                                 ((along > rp * 0.18) & (along < rp - m * 2.5)))

    def line(x0, y0, x1, y1, w=1.0, dash=0):
        nonlocal ink
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        t = (xx - x0) * ux + (yy - y0) * uy
        d = (xx - x0) * (-uy) + (yy - y0) * ux
        m = _aa_line_mask(d, w) * ((t > 0) & (t < L))
        if dash:
            m = m * ((t % (dash * 2)) < dash)
        ink = np.maximum(ink, m)

    gears = [(620, 640, 96, 330, 10), (1090, 470, 20, 70, 10), (1300, 760, 64, 200, 9),
             (1560, 470, 14, 50, 9), (1660, 1050, 40, 120, 7)]
    for g in gears:
        gear(*g)
        cx, cy = g[0], g[1]
        line(cx - g[3] - 60, cy, cx + g[3] + 60, cy, 0.8, dash=14)   # centre lines
        line(cx, cy - g[3] - 60, cx, cy + g[3] + 60, 0.8, dash=14)
    # dimension lines + border + title block
    line(290, 1060, 950, 1060, 0.9)
    for x in (290, 950):
        line(x, 1040, x, 1080, 0.9)
    for (x0, y0, x1, y1) in [(60, 60, W - 60, 60), (W - 60, 60, W - 60, H - 60),
                             (W - 60, H - 60, 60, H - 60), (60, H - 60, 60, 60)]:
        line(x0, y0, x1, y1, 2.2)
    line(W - 640, H - 220, W - 60, H - 220, 1.4)
    line(W - 640, H - 220, W - 640, H - 60, 1.4)
    for i in range(1, 4):
        line(W - 640, H - 220 + i * 40, W - 60, H - 220 + i * 40, 0.8)
    # pseudo hand-lettering strokes in the title block
    for row in range(4):
        x = W - 620
        while x < W - 90:
            wlen = rng.integers(18, 70)
            line(x, H - 200 + row * 40 + 10, x + wlen, H - 200 + row * 40 + 10, 1.6)
            x += wlen + rng.integers(10, 22)
    # paper: blue with fibres and fading
    base = np.array([0.09, 0.22, 0.48], np.float32)
    noise = rng.normal(0, 1, (H // 8 + 1, W // 8 + 1)).astype(np.float32)
    noise = np.kron(noise, np.ones((8, 8), np.float32))[:H, :W]
    fine = rng.normal(0, 1, (H, W)).astype(np.float32) * 0.015
    vign = 1.0 - 0.35 * (((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 2.5)
    paper = base[None, None, :] * (vign[..., None] * (1 + noise[..., None] * 0.04 + fine[..., None]))
    ink_col = np.array([0.86, 0.90, 0.95], np.float32)
    img = paper * (1 - ink[..., None] * 0.9) + ink_col * ink[..., None] * 0.9
    img = np.clip(img, 0, 1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return img  # float RGB, top row first


def save_with_bpy(img, path, name):
    """Create a Blender image from a numpy array, save it as PNG and pack it into the .blend."""
    import bpy
    H, W, _ = img.shape
    im = bpy.data.images.get(name) or bpy.data.images.new(name, W, H, alpha=False)
    rgba = np.ones((H, W, 4), np.float32)
    rgba[..., :3] = img[::-1]  # Blender stores bottom row first
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    im.pack()
    return im
