#!/usr/bin/env python3
"""Frame renderer for the Athlo 30x30 speedrun reel (1080x1920, 30 fps, 900 frames).

python3 speedrun/picture.py                 -> work/speedrun/picture.mp4
python3 speedrun/picture.py --still 1,12.5  -> work/speedrun/stills/*.png
"""
import math, os, subprocess, sys, json
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import font
from timeline import *

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work", "speedrun")

BG = (11, 9, 18)
ORANGE = (255, 170, 0)
PINK = (255, 10, 96)
WHITE = (255, 255, 255)
SHADOW = (58, 6, 40)
PANEL = (22, 17, 34)
DIM = (70, 58, 92)

# ------------------------------------------------------------------ easing
def cl(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def ramp(x, a, b): return cl((x - a) / (b - a))
def eo(x): x = cl(x); return 1 - (1 - x) ** 3
def eob(x, s=1.9):
    x = cl(x); x -= 1
    return x * x * ((s + 1) * x + s) + 1
def mix(c1, c2, k): return tuple(int(round(a + (b - a) * k)) for a, b in zip(c1, c2))
def grad_col(k): return mix(ORANGE, PINK, cl(k))

# ------------------------------------------------------------------ text
TEXT_LOG = []   # (t, string, y0, y1) for the safe-area audit

def _fill_arr(fill, h, w):
    if fill == "G":
        k = np.linspace(0, 1, max(w, 1))[None, :, None]
        return (np.array(ORANGE) * (1 - k) + np.array(PINK) * k).repeat(h, 0)
    if fill == "GV":
        k = np.linspace(0, 1, max(h, 1))[:, None, None]
        return (np.array(ORANGE) * (1 - k) + np.array(PINK) * k).repeat(w, 1)
    c = {"W": WHITE, "O": ORANGE, "P": PINK, "D": DIM}.get(fill, fill)
    return np.broadcast_to(np.array(c), (h, w, 3))

@lru_cache(maxsize=None)
def text_img(s, scale, fill="W", shadow=True):
    m = np.kron(font.cells(s), np.ones((scale, scale), np.uint8)).astype(bool)
    h, w = m.shape
    pad = max(2, scale) if shadow else 0
    out = np.zeros((h + pad, w + pad, 4), np.uint8)
    if shadow:
        out[pad:, pad:, :3][m] = SHADOW
        out[pad:, pad:, 3][m] = 255
    out[:h, :w, :3][m] = _fill_arr(fill, h, w)[m]
    out[:h, :w, 3][m] = 255
    return Image.fromarray(out, "RGBA")

def paste(img, src, x, y, alpha=1.0):
    """Alpha-composite src at (x, y), clipped to the frame, with optional opacity."""
    x, y = int(round(x)), int(round(y))
    if alpha <= 0.003:
        return
    if alpha < 0.997:
        src = src.copy()
        a = np.asarray(src)[..., 3].astype(np.float32) * alpha
        src.putalpha(Image.fromarray(a.astype(np.uint8)))
    W_, H_ = img.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W_, x + src.width), min(H_, y + src.height)
    if x1 <= x0 or y1 <= y0:
        return
    c = src.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    img.paste(c, (x0, y0), c)

def put(img, s, x, y, scale, fill="W", anchor="c", alpha=1.0, zoom=1.0, shadow=True, t=None):
    """Draw pixel text. y is the top of the caps. Returns (x0, y0, x1, y1)."""
    im = text_img(s, scale, fill, shadow)
    if zoom != 1.0:
        im = im.resize((max(1, int(im.width * zoom)), max(1, int(im.height * zoom))), Image.NEAREST)
    w = font.width(s, scale) * zoom
    h = 7 * scale * zoom
    if anchor == "c": x0 = x - w / 2
    elif anchor == "r": x0 = x - w
    else: x0 = x
    y0 = y - (h - 7 * scale) / 2 if zoom != 1.0 else y
    paste(img, im, x0, y0, alpha)
    if alpha > 0.05 and t is not None:
        TEXT_LOG.append((round(t, 3), s, int(y0), int(y0 + h + (scale if shadow else 0))))
    return (x0, y0, x0 + w, y0 + h)

# ------------------------------------------------------------------ sprites (drawn here at low res, upscaled NEAREST)
def sprite(draw_fn, size, scale):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im))
    return im.resize((size[0] * scale, size[1] * scale), Image.NEAREST)

DK = (28, 14, 40, 255)
def _pk(c): return c + (255,)
O4, P4, W4 = _pk(ORANGE), _pk(PINK), _pk(WHITE)
MID4 = _pk(mix(ORANGE, PINK, 0.5))

def ic_padel(d):
    d.ellipse((5, 1, 18, 15), fill=O4); d.ellipse((7, 3, 16, 13), fill=MID4)
    for x in range(8, 16, 3):
        for y in range(4, 13, 3):
            d.point((x, y), fill=DK)
    d.rectangle((10, 15, 13, 16), fill=O4); d.rectangle((10, 17, 13, 22), fill=P4)
    d.line((10, 19, 13, 19), fill=W4); d.ellipse((18, 15, 21, 18), fill=W4)

def ic_run(d):
    d.polygon([(3, 15), (3, 9), (7, 8), (9, 11), (15, 12), (21, 14), (21, 16), (3, 16)], fill=P4)
    d.rectangle((3, 17, 21, 18), fill=W4); d.rectangle((3, 16, 21, 16), fill=O4)
    for x in (8, 10, 12): d.point((x, 11), fill=W4)
    d.line((4, 9, 6, 9), fill=O4)

def ic_ball(d):
    d.ellipse((3, 3, 20, 20), fill=W4)
    d.polygon([(11, 8), (14, 10), (13, 13), (10, 13), (9, 10)], fill=DK)
    d.polygon([(11, 3), (13, 3), (12, 5)], fill=DK); d.polygon([(3, 11), (5, 10), (5, 13)], fill=DK)
    d.polygon([(20, 11), (18, 10), (18, 13)], fill=DK); d.polygon([(7, 18), (9, 17), (9, 20)], fill=DK)
    d.polygon([(16, 18), (14, 17), (14, 20)], fill=DK)
    d.arc((3, 3, 20, 20), 200, 330, fill=O4)

def ic_gym(d):
    d.rectangle((5, 11, 18, 12), fill=W4)
    d.rectangle((2, 7, 4, 16), fill=O4); d.rectangle((5, 8, 6, 15), fill=MID4)
    d.rectangle((19, 7, 21, 16), fill=P4); d.rectangle((17, 8, 18, 15), fill=MID4)

def ic_swim(d):
    for row, c in ((14, O4), (18, P4)):
        for x in range(0, 24):
            y = row + int(round(math.sin(x * 0.8) * 1.0))
            d.point((x, y), fill=c); d.point((x, y + 1), fill=c)
    d.ellipse((6, 7, 11, 12), fill=O4); d.rectangle((7, 9, 10, 9), fill=W4)
    d.line((12, 11, 15, 6), fill=W4); d.line((15, 6, 19, 8), fill=W4); d.line((12, 12, 15, 7), fill=W4)

ICONS = [ic_padel, ic_run, ic_ball, ic_gym, ic_swim]

def ic_trophy(d):
    d.rectangle((4, 1, 11, 7), fill=O4); d.rectangle((5, 8, 10, 8), fill=O4)
    d.rectangle((7, 9, 8, 11), fill=MID4); d.rectangle((4, 12, 11, 13), fill=P4)
    d.rectangle((1, 2, 3, 2), fill=O4); d.rectangle((1, 2, 1, 4), fill=O4); d.rectangle((2, 5, 3, 5), fill=O4)
    d.rectangle((12, 2, 14, 2), fill=O4); d.rectangle((14, 2, 14, 4), fill=O4); d.rectangle((12, 5, 13, 5), fill=O4)
    d.point((6, 3), fill=W4); d.point((6, 4), fill=W4)

def ic_star(d):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 7.6 if i % 2 == 0 else 3.4
        pts.append((8 + r * math.cos(a), 8.4 + r * math.sin(a)))
    d.polygon(pts, fill=O4)
    d.polygon([(8, 3), (10, 7), (8, 9), (6, 7)], fill=_pk((255, 214, 120)))
    d.point((7, 5), fill=W4)

def ic_boss(d):
    d.rectangle((2, 5, 21, 23), fill=P4)
    d.rectangle((2, 5, 21, 9), fill=O4)
    d.rectangle((6, 2, 7, 6), fill=W4); d.rectangle((16, 2, 17, 6), fill=W4)
    d.rectangle((5, 12, 9, 15), fill=W4); d.rectangle((14, 12, 18, 15), fill=W4)
    d.rectangle((7, 13, 8, 15), fill=DK); d.rectangle((15, 13, 16, 15), fill=DK)
    d.line((4, 10, 9, 11), fill=DK); d.line((19, 10, 14, 11), fill=DK)
    d.rectangle((6, 17, 17, 21), fill=DK)
    for x in range(6, 18, 3):
        d.polygon([(x, 17), (x + 2, 17), (x + 1, 19)], fill=W4)
    d.rectangle((3, 24, 7, 25), fill=O4); d.rectangle((16, 24, 20, 25), fill=O4)

def ic_heart(d):
    d.polygon([(0, 2), (2, 0), (3, 0), (4, 1), (5, 0), (6, 0), (8, 2), (8, 3), (4, 7), (0, 3)], fill=P4)
    d.point((2, 1), fill=W4)

def ic_arrow(d):  # up arrow
    d.polygon([(4, 0), (8, 4), (6, 4), (6, 9), (2, 9), (2, 4), (0, 4)], fill=O4)

def ic_down(d):
    d.polygon([(0, 0), (8, 0), (4, 5)], fill=W4)

@lru_cache(maxsize=None)
def SPR(name, scale):
    tbl = {"padel": (ic_padel, (24, 24)), "run": (ic_run, (24, 24)), "ball": (ic_ball, (24, 24)),
           "gym": (ic_gym, (24, 24)), "swim": (ic_swim, (24, 24)), "trophy": (ic_trophy, (16, 15)),
           "star": (ic_star, (17, 17)), "boss": (ic_boss, (24, 26)), "heart": (ic_heart, (9, 8)),
           "arrow": (ic_arrow, (9, 10)), "down": (ic_down, (9, 6))}
    fn, size = tbl[name]
    return sprite(fn, size, scale)

ICON_NAMES = ["padel", "run", "ball", "gym", "swim"]

@lru_cache(maxsize=None)
def glow(r, col, strength=1.0):
    s = 2 * r
    yy, xx = np.mgrid[0:s, 0:s]
    d = np.sqrt((xx - r + .5) ** 2 + (yy - r + .5) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** 2.2 * 255 * strength
    out = np.zeros((s, s, 4), np.uint8)
    out[..., :3] = col; out[..., 3] = a.astype(np.uint8)
    return Image.fromarray(out, "RGBA")

def paste_c(img, im, cx, cy, alpha=1.0, zoom=1.0):
    if zoom != 1.0:
        im = im.resize((max(1, int(im.width * zoom)), max(1, int(im.height * zoom))), Image.NEAREST)
    paste(img, im, cx - im.width / 2, cy - im.height / 2, alpha)

def sparkle(d, x, y, r, col):
    """4-point pixel sparkle of radius r (in 6 px blocks)."""
    p = 6
    if r <= 0: return
    d.rectangle((x - p // 2, y - r * p, x + p // 2, y + r * p), fill=col)
    d.rectangle((x - r * p, y - p // 2, x + r * p, y + p // 2), fill=col)
    if r >= 2:
        d.rectangle((x - p, y - p, x + p, y + p), fill=WHITE + (255,))

def pixel_box(d, x0, y0, x1, y1, fill, border=None, bw=6, cut=12):
    """Box with chamfered (pixel) corners."""
    pts = [(x0 + cut, y0), (x1 - cut, y0), (x1, y0 + cut), (x1, y1 - cut), (x1 - cut, y1), (x0 + cut, y1), (x0, y1 - cut), (x0, y0 + cut)]
    if border is not None:
        d.polygon(pts, fill=border)
        c2 = cut - bw // 2
        pts = [(x0 + bw + c2, y0 + bw), (x1 - bw - c2, y0 + bw), (x1 - bw, y0 + bw + c2), (x1 - bw, y1 - bw - c2),
               (x1 - bw - c2, y1 - bw), (x0 + bw + c2, y1 - bw), (x0 + bw, y1 - bw - c2), (x0 + bw, y0 + bw + c2)]
    d.polygon(pts, fill=fill)

@lru_cache(maxsize=None)
def grad_rect(w, h, vertical=False):
    k = (np.linspace(0, 1, h)[:, None] if vertical else np.linspace(0, 1, w)[None, :])
    k = np.broadcast_to(k, (h, w))[..., None]
    rgb = np.array(ORANGE) * (1 - k) + np.array(PINK) * k
    out = np.dstack([rgb, np.full((h, w), 255)]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

def grad_box(img, x0, y0, x1, y1, cut=12, border=None, bw=6, alpha=1.0):
    w, h = int(x1 - x0), int(y1 - y0)
    if w <= 2 or h <= 2: return
    g = grad_rect(w, h).copy()
    m = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(m)
    pixel_box(md, 0, 0, w - 1, h - 1, 255, None, cut=cut)
    if alpha < 1: m = m.point(lambda v: int(v * alpha))
    g.putalpha(m)
    if border is not None:
        d = ImageDraw.Draw(img, "RGBA")
        pixel_box(d, x0 - bw, y0 - bw, x1 - 1 + bw, y1 - 1 + bw, border, None, cut=cut + bw // 2)
    img.paste(g, (int(x0), int(y0)), g)

# ------------------------------------------------------------------ background
HY = 1400  # horizon

def build_base():
    a = np.zeros((H, W, 3), np.float32)
    y = np.arange(H)[:, None]
    a[:] = BG
    # purple haze rising toward the horizon
    k = np.clip((y - 700) / (HY - 700), 0, 1) ** 2
    a += k[..., None] * np.array([52, 10, 46])
    # horizon glow: orange core fading to pink then dark
    dy = (y - HY).astype(np.float32)
    g = np.exp(-(dy / 70.0) ** 2)[..., None]
    a += g * np.array([255, 70, 60]) * 0.55
    a = np.broadcast_to(a, (H, W, 3)).copy()
    # floor
    a[HY:] = np.array(BG) * 0.9 + np.array([30, 6, 28]) * np.linspace(1, 0.3, H - HY)[:, None, None]
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    # pixel Dubai skyline silhouette on the horizon (drawn here; generic shapes)
    sky = (34, 16, 50, 255)
    rng = np.random.default_rng(7)
    x = 0
    while x < W:
        bw = int(rng.integers(3, 8)) * 12
        bh = int(rng.integers(3, 14)) * 12
        if 420 < x < 660: bh = int(rng.integers(2, 6)) * 12
        d.rectangle((x, HY - bh, x + bw - 6, HY), fill=sky)
        x += bw
    # the tall tower, stepped
    cx = 540
    for i, (hw, top) in enumerate([(54, 120), (42, 220), (30, 320), (20, 410), (12, 480), (6, 560), (3, 640)]):
        d.rectangle((cx - hw, HY - top, cx + hw, HY), fill=sky)
    for xx in (240, 840):
        d.rectangle((xx, HY - 260, xx + 36, HY), fill=sky); d.rectangle((xx + 12, HY - 300, xx + 24, HY - 260), fill=sky)
    d.line((0, HY, W, HY), fill=(255, 120, 60, 255), width=3)
    return img.convert("RGB")

def build_post():
    y = np.arange(H, dtype=np.float32)[:, None]
    x = np.arange(W, dtype=np.float32)[None, :]
    v = 1 - 0.38 * (((x - W / 2) / (W * 0.75)) ** 2 + ((y - H / 2) / (H * 0.62)) ** 2)
    v = np.clip(v, 0.55, 1)
    v[3::4, :] *= 0.86   # scanlines
    return v[..., None].astype(np.float32)

STARS = np.random.default_rng(3).random((140, 4))

def speed(bt):
    """Star/grid speed multiplier through the run."""
    s = 1.0
    s += 5.0 * math.exp(-((bt - 6) / 0.8) ** 2)                     # GO warp
    if 28 <= bt < 38: s += 1.0 + (bt - 28) * 0.25                     # combo ramps up
    if 38 <= bt < 44: s = 0.6
    s += 4.0 * math.exp(-((bt - 48) / 1.0) ** 2)                      # victory
    if bt >= 53: s = 0.8
    return s

_CUM = None
def travel(fi):
    global _CUM
    if _CUM is None:
        sp = [speed(i / FPS / B) for i in range(N + 2)]
        _CUM = np.concatenate([[0], np.cumsum(sp)]) / FPS
    return float(_CUM[min(fi, N + 1)])

def draw_bg(img, fi, bt):
    d = ImageDraw.Draw(img, "RGBA")
    tr = travel(fi)
    sp = speed(bt)
    for i, (sx, sy, ss, sph) in enumerate(STARS):
        y = (sy * HY + tr * (40 + 120 * ss)) % (HY - 120)
        x = sx * W
        size = 6 if ss > 0.8 else 3
        tw = 0.5 + 0.5 * math.sin(bt * 3 + sph * 20)
        col = mix(BG, (WHITE, ORANGE, PINK)[i % 3], 0.35 + 0.6 * tw * (0.5 + ss / 2))
        streak = max(0, int(min(140, (sp - 1) * 18 * (0.5 + ss))))
        d.rectangle((x, y - streak, x + size - 1, y + size - 1), fill=col)
    # perspective floor grid
    ph = (tr * 1.6) % 1.0
    for n in range(1, 34):
        z = n - ph
        if z <= 0.15: continue
        y = HY + 560 / z
        if y > H: continue
        k = cl(1 - (z / 34))
        d.line((0, y, W, y), fill=mix(BG, grad_col(1 - k), 0.25 + 0.7 * k), width=3 if z < 4 else 2)
    for i in range(-14, 15):
        xb = 540 + i * 170
        d.line((540 + i * 6, HY, xb, H), fill=mix(BG, PINK, 0.55), width=3)

# ------------------------------------------------------------------ HUD state
def eased_steps(bt, steps, dur=0.5):
    v = 0.0
    for b, dv in steps:
        if bt >= b: v += dv * eob((bt - b) / dur, 2.4)
    return v

XP_STEPS = [(a, 0.11) for a in ACH] + [(b, 0.07) for b, _ in COMBOS] + [(WIN, 0.20)]
def xp(bt): return cl(0.04 + eased_steps(bt, XP_STEPS), 0, 1.0)
def xp_flash(bt):
    return max([math.exp(-max(0, bt - b) * 5) if bt >= b else 0 for b, _ in XP_STEPS] + [0])

HP_STEPS = [(s, -0.15) for s in STOMPS] + [(COLLECT, 0.45)]
def hp(bt): return cl(0.9 + 0.1 * ramp(bt, 0, 1) + eased_steps(bt, HP_STEPS, 0.6), 0, 1)

def day(bt):
    if bt < SESS0: return 1
    if bt >= BOSS0: return 21
    return 1 + int(20 * (bt - SESS0) / (BOSS0 - SESS0))

def rank_value(bt):
    """Displayed (illustrative) rank, with a fast slot-machine roll between values."""
    if bt < RANK0: return None
    v = None
    for b, a, z in RANKS + [RANK_WIN]:
        if bt >= b:
            k = eo((bt - b) / 0.9)
            v = a + (z - a) * k
    return v

def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20: suf = "TH"
    else: suf = {1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH")
    return f"{n}{suf}"

def draw_hud(img, bt, t, show_corners=True):
    d = ImageDraw.Draw(img, "RGBA")
    # main panel
    pixel_box(d, 36, 200, 1044, 392, PANEL + (235,), None, cut=18)
    g = grad_rect(1008, 5)
    paste(img, g, 36, 200); paste(img, g, 36, 387)
    # HP
    paste(img, SPR("heart", 5), 56, 229)
    put(img, "HP", 108, 232, 4, "W", "l", t=t)
    x0, x1, y0, y1 = 170, 600, 226, 266
    d.rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), fill=(48, 36, 66, 255))
    segs = 10; sw = (x1 - x0 - (segs - 1) * 6) / segs
    hv = hp(bt) * segs
    hit = max([math.exp(-max(0, bt - s) * 6) if bt >= s else 0 for s in STOMPS] + [0])
    for i in range(segs):
        a = x0 + i * (sw + 6)
        f = cl(hv - i)
        if f > 0:
            col = mix(PINK, WHITE, hit * 0.7)
            d.rectangle((a, y0, a + sw * f, y1), fill=col + (255,))
            d.rectangle((a, y0, a + sw * f, y0 + 6), fill=mix(col, WHITE, 0.45) + (255,))
    # XP
    put(img, "XP", 108, 314, 4, "W", "l", t=t)
    paste(img, SPR("star", 2), 54, 309)
    x0, x1, y0, y1 = 170, 600, 308, 348
    d.rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), fill=(48, 36, 66, 255))
    fw = int((x1 - x0) * xp(bt))
    if fw > 2:
        paste(img, grad_rect(fw, y1 - y0), x0, y0)
        fl = xp_flash(bt)
        d.rectangle((x0, y0, x0 + fw, y0 + 6), fill=(255, 240, 220, int(120 + 135 * fl)))
        if fl > 0.05:
            paste(img, glow(60, ORANGE, 0.9), x0 + fw - 60, y0 + 20 - 60, fl)
    for k in range(1, 10):   # tick marks only, no values
        xx = x0 + (x1 - x0) * k / 10
        d.rectangle((xx - 1, y1 - 8, xx + 1, y1), fill=(20, 14, 30, 200))
    # Day counter
    put(img, f"DAY {day(bt):02d} OF 30", 1020, 230, 5, "W", "r", t=t)
    dd = day(bt)
    for i in range(30):
        r, c = divmod(i, 15)
        xx = 650 + c * 25; yy = 296 + r * 26
        col = grad_col(c / 14) if i < dd else (48, 36, 66)
        if i == dd - 1 and int(bt * 4) % 2 == 0: col = WHITE
        d.rectangle((xx, yy, xx + 19, yy + 18), fill=col + (255,))
    if not show_corners:
        return
    # run timer (top-left corner)
    pixel_box(d, 36, 410, 366, 530, PANEL + (220,), None, cut=12)
    put(img, "RUN TIME", 56, 424, 3, (170, 150, 200), "l", t=t)
    rt = min(t, tb(WIN))
    done = t >= tb(WIN)
    put(img, f"{int(rt // 60):02d}:{rt % 60:05.2f}", 56, 460, 6, "G" if done else "W", "l", t=t)
    # rank tracker (top-right corner) -- illustrative ranks
    pixel_box(d, 774, 410, 1044, 530, PANEL + (220,), None, cut=12)
    put(img, "EXAMPLE RANK", 1024, 424, 3, "O", "r", t=t)
    rv = rank_value(bt)
    s = "--" if rv is None else ordinal(round(rv))
    rolling = rv is not None and any(b <= bt < b + 0.9 for b, _, _ in RANKS + [RANK_WIN])
    put(img, s, 1024, 458, 8, "G" if (rv is not None and round(rv) == 1) else "W", "r", t=t,
        zoom=1.0 + (0.08 if rolling else 0.0))
    if rolling:
        paste(img, SPR("arrow", 4), 790, 470 - 20 * ((bt * 4) % 1))

# ------------------------------------------------------------------ scenes
def sc_intro(img, bt, t):
    d = ImageDraw.Draw(img, "RGBA")
    pulse = 1 + 0.035 * math.exp(-((bt % 1) * 6))
    put(img, "ATHLO 30x30.", 540, 690, 14, "G", zoom=pulse, t=t)
    put(img, "SPEEDRUN ATTEMPT.", 540, 840, 7, "W", t=t)
    # loading bar fills fast
    f = cl(0.06 + 0.94 * eo(bt / 4.0))
    x0, x1, y0, y1 = 150, 930, 1010, 1070
    pixel_box(d, x0 - 12, y0 - 12, x1 + 12, y1 + 12, PANEL + (255,), WHITE + (255,), bw=6, cut=12)
    segs = 20; sw = (x1 - x0 - (segs - 1) * 6) / segs
    for i in range(segs):
        a = cl(f * segs - i)
        if a > 0:
            xx = x0 + i * (sw + 6)
            d.rectangle((xx, y0, xx + sw * a, y1), fill=grad_col(i / (segs - 1)) + (255,))
    if bt < 4:
        dots = "." * (1 + int(bt * 3) % 3)
        put(img, "LOADING" + dots, x0, 1110, 5, "W", "l", t=t)
    elif bt < GO:
        if int(bt * 4) % 2 == 0:
            put(img, "READY?", 540, 1110, 6, "O", t=t)
    if bt >= GO:
        k = (bt - GO)
        put(img, "GO!", 540, 1150, 22, "G", zoom=0.4 + 0.6 * eob(k / 0.35), t=t)
    # a few loading sparkles riding the bar head
    hx = x0 + (x1 - x0) * f
    for j in range(3):
        ph = (bt * 3 + j / 3) % 1
        sparkle(d, int(hx + 10 - ph * 60), int(1040 + (j - 1) * 30 * ph), 2 if ph < 0.5 else 1, WHITE + (255,))

def sc_session(img, bt, t, i):
    lt = bt - SESS[i]
    sport, ach = SPORTS[i]
    d = ImageDraw.Draw(img, "RGBA")
    cy = 760
    pop = eob(lt / 0.3)
    paste_c(img, glow(230, mix(ORANGE, PINK, i / 4), 0.55), 540, cy, 0.6 + 0.4 * math.sin(lt * 6) ** 2)
    paste_c(img, SPR(ICON_NAMES[i], 11), 540, cy + 6 * math.sin(lt * 4), 1.0, zoom=max(0.05, pop))
    put(img, "SESSION LOGGED", 540, 925, 5, "O", alpha=cl(lt / 0.15), t=t)
    put(img, sport, 540, 980, 12, "W", zoom=max(0.05, eob((lt - 0.05) / 0.3)), t=t)
    # session pips 1..5
    for j in range(5):
        xx = 540 + (j - 2) * 46
        col = grad_col(j / 4) if j <= i else (48, 36, 66)
        d.rectangle((xx - 14, 1100, xx + 14, 1112), fill=col + (255,))
    if lt >= 1:
        k = lt - 1
        off = (1 - eob(k / 0.3, 1.4)) * 1100
        x0, x1, y0, y1 = 70 + off, 1010 + off, 1170, 1370
        grad_box(img, x0, y0, x1, y1, cut=18, border=WHITE + (255,), bw=6)
        pixel_box(d, x0 + 10, y0 + 10, x1 - 10, y1 - 10, PANEL + (240,), None, cut=12)
        paste(img, SPR("trophy", 6), x0 + 34, y0 + 56)
        put(img, "ACHIEVEMENT UNLOCKED", x0 + 560, y0 + 40, 5, "O", t=t)
        put(img, ach, x0 + 560, y0 + 100, 9, "G", t=t)
        # sparkles bursting around the banner and icon
        rng = np.random.default_rng(100 + i)
        pts = rng.random((16, 3))
        for px, py, ph in pts:
            age = k * 2.2 - ph * 0.6
            if 0 < age < 1:
                r = int(round(4 * math.sin(math.pi * age)))
                xx = int(80 + px * 920); yy = int(1140 + py * 260) if ph > 0.45 else int(600 + py * 300)
                sparkle(d, xx, yy - int(age * 40), r, (WHITE, ORANGE, PINK)[int(ph * 3) % 3] + (255,))
        # floating "+XP" under the HUD
        if k < 1.2:
            put(img, "+XP", 470, 420 - 40 * eo(k / 1.2), 6, "G", alpha=1 - ramp(k, 0.8, 1.2), t=t)

def sc_rank(img, bt, t):
    d = ImageDraw.Draw(img, "RGBA")
    put(img, "EXAMPLE LEADERBOARD", 540, 600, 4, "O", t=t)
    rv = rank_value(bt)
    rolling = any(b <= bt < b + 0.9 for b, _, _ in RANKS)
    put(img, "YOUR RANK", 540, 660, 6, "W", t=t)
    jit = 6 * math.sin(bt * 40) if rolling else 0
    put(img, ordinal(round(rv)), 540 + jit, 730, 24, "G", zoom=1.0 + 0.06 * rolling, t=t)
    # ladder of placeholder rows that scrolls as the rank climbs (no names, no values)
    fr = rv - math.floor(rv)
    base = math.floor(rv)
    for j in range(-2, 3):
        r = base + j
        yy = 1230 + j * 64 + fr * 64
        if r < 1 or yy < 1080 or yy > 1420: continue
        you = abs((r - rv)) < 0.5
        a = 1 - abs(yy - 1230) / 220
        if you:
            grad_box(img, 150, yy - 26, 930, yy + 26, cut=8)
            put(img, f"#{r}", 180, yy - 14, 4, "W", "l", t=t)
            put(img, "YOU", 900, yy - 14, 4, "W", "r", t=t)
        else:
            d.rectangle((150, yy - 22, 930, yy + 22), fill=(36, 28, 52, int(255 * a)))
            put(img, f"#{r}", 180, yy - 14, 4, "D", "l", alpha=a, shadow=False, t=t)
            d.rectangle((290, yy - 6, 290 + 180 + (r * 37) % 220, yy + 6), fill=(70, 58, 92, int(255 * a)))
    put(img, "ILLUSTRATIVE, NOT THE LIVE BOARD", 540, 1440, 4, "O", t=t)
    for b, _, _ in RANKS:
        k = bt - b
        if 0 <= k < 0.9:
            for j in range(4):
                yy = 1000 - ((k * 3 + j / 4) % 1) * 360
                paste(img, SPR("arrow", 6), 120 + (j % 2) * 30, yy)
                paste(img, SPR("arrow", 6), 900 - (j % 2) * 30, yy)

def sc_combo(img, bt, t):
    stage = max(i for i, (b, _) in enumerate(COMBOS) if bt >= b)
    b0, n = COMBOS[stage]
    lt = bt - b0
    d = ImageDraw.Draw(img, "RGBA")
    put(img, "COMBO", 540, 610, 8, "W", t=t)
    shake = (stage + 1) * 3
    jx = shake * math.sin(bt * 31); jy = shake * math.cos(bt * 27)
    paste_c(img, glow(260, PINK, 0.6), 540, 830, 0.5 + 0.5 * math.exp(-lt * 3))
    put(img, f"x{n}", 540 + jx, 720 + jy, 30, "G", zoom=0.6 + 0.4 * eob(lt / 0.3, 2.6), t=t)
    put(img, f"{n}-DAY STREAK", 540, 990, 9, "W", zoom=0.5 + 0.5 * eob(lt / 0.25), t=t)
    # streak pips: 7 flames-as-blocks
    for j in range(7):
        xx = 540 + (j - 3) * 104
        on = j < n
        flick = 1 + 0.15 * math.sin(bt * 20 + j)
        if on:
            hh = int(70 * flick)
            paste(img, grad_rect(64, hh, True), xx - 32, 1180 - hh)
            d.rectangle((xx - 16, 1180 - hh // 2, xx + 16, 1180), fill=(255, 230, 160, 255))
        else:
            d.rectangle((xx - 32, 1130, xx + 32, 1180), outline=(70, 58, 92, 255), width=4)
    # combo timer bar that drains between hits
    nxt = COMBOS[stage + 1][0] if stage + 1 < len(COMBOS) else BOSS0
    f = 1 - (bt - b0) / (nxt - b0)
    d.rectangle((200, 1240, 880, 1270), fill=(48, 36, 66, 255))
    d.rectangle((200, 1240, 200 + 680 * f, 1270), fill=mix(ORANGE, WHITE, 0.2 * (1 - f)) + (255,))
    put(img, "KEEP IT GOING", 540, 1310, 4, "W", t=t)
    # speed lines from the edges
    for j in range(10 + stage * 6):
        yy = (j * 137 + bt * 900 * (stage + 1)) % 980 + 560
        ln = 60 + (j * 53) % 140
        side = j % 2
        x = 0 if side == 0 else W - ln
        d.rectangle((x, yy, x + ln, yy + 4), fill=grad_col(j / 16) + (200,))

def combo_flash(bt):
    times = []
    for i, (b, _) in enumerate(COMBOS):
        nxt = COMBOS[i + 1][0] if i + 1 < len(COMBOS) else BOSS0
        step = [2, 1, 0.5][i]
        x = b
        while x < nxt - 1e-6:
            times.append(x); x += step
    a = 0.0
    for x in times:
        if bt >= x: a = max(a, 0.45 * math.exp(-(bt - x) * B * 14))
    return a, times

def sc_boss(img, bt, t):
    lt = bt - BOSS0
    d = ImageDraw.Draw(img, "RGBA")
    # warning stripes band
    if lt < 6:
        y0, y1 = 568, 648
        off = int(bt * 60) % 80
        for x in range(-80, W + 80, 80):
            d.polygon([(x + off, y1), (x + off + 40, y0), (x + off + 80, y0), (x + off + 40, y1)], fill=ORANGE + (255,))
        d.rectangle((0, y0 - 4, W, y0), fill=PINK + (255,)); d.rectangle((0, y1, W, y1 + 4), fill=PINK + (255,))
        if int(bt * 4) % 2 == 0:
            pixel_box(d, 300, y0 + 6, 780, y1 - 6, BG + (255,), None, cut=8)
            put(img, "WARNING!", 540, y0 + 19, 6, "W", t=t)
    # boss sprite: bobbing calendar monster
    bob = 10 * math.sin(bt * math.pi)
    stomp = max([math.exp(-(bt - s) * 6) if bt >= s else 0 for s in STOMPS] + [0])
    paste_c(img, glow(300, PINK, 0.7), 540, 900, 0.6 + 0.4 * stomp)
    paste_c(img, SPR("boss", 12), 540, 900 + bob - 30 * stomp, 1.0, zoom=1.0 + 0.08 * stomp)
    put(img, "FINAL BOSS:", 540, 1110, 8, "W", t=t)
    put(img, "9 DAYS LEFT", 540, 1190, 12, "G", zoom=1 + 0.05 * stomp, t=t)
    # boss bar: nine segments, one per remaining day
    for j in range(9):
        xx = 150 + j * 88
        d.rectangle((xx, 1330, xx + 76, 1370), fill=PINK + (255,))
        d.rectangle((xx, 1330, xx + 76, 1338), fill=mix(PINK, WHITE, 0.4) + (255,))
    put(img, "BOSS", 150, 1390, 4, "W", "l", t=t)
    put(img, "9 DAYS", 930, 1390, 4, "W", "r", t=t)

def shake_amt(bt):
    s = 0.0
    for b in STOMPS:
        if bt >= b: s = max(s, 26 * math.exp(-(bt - b) * B * 7))
    if BOSS0 <= bt < POWER0: s = max(s, 3)
    if bt >= WIN: s = max(s, 18 * math.exp(-(bt - WIN) * B * 8))
    return s

def sc_power(img, bt, t):
    d = ImageDraw.Draw(img, "RGBA")
    if bt < WIN:
        lt = bt - POWER0
        appear = eob(lt / 0.4)
        got = bt >= COLLECT
        cy = 820 + 12 * math.sin(bt * 3)
        gl = 0.7 + 0.3 * math.sin(bt * 8)
        paste_c(img, glow(300, ORANGE, 1.0), 540, cy, gl * appear)
        # expanding pixel rings
        for j in range(3):
            ph = (bt * 0.9 + j / 3) % 1
            r = 120 + 260 * ph
            d.ellipse((540 - r, cy - r, 540 + r, cy + r), outline=grad_col(ph) + (int(255 * (1 - ph)),), width=6)
        # orbiting sparkles
        for j in range(6):
            a = bt * 2.4 + j * math.pi / 3
            sparkle(d, int(540 + 190 * math.cos(a)), int(cy + 110 * math.sin(a)), 2 + (j % 2), (WHITE + (255,)))
        zoom = (0.2 + 0.8 * appear) * (1 + 0.08 * math.sin(bt * 6)) * (1 + 0.35 * math.exp(-(bt - COLLECT) * 5) if got else 1)
        paste_c(img, SPR("star", 16), 540, cy, 1.0, zoom=zoom)
        if got:
            k = bt - COLLECT
            put(img, "POWER-UP ACQUIRED:", 540, 1070, 6, "O", zoom=0.5 + 0.5 * eob(k / 0.3), t=t)
            put(img, "ONE SESSION", 540, 1150, 11, "W", alpha=cl((k - 0.2) / 0.2), t=t)
            put(img, "A DAY", 540, 1250, 11, "G", alpha=cl((k - 0.4) / 0.2), t=t)
        else:
            put(img, "PICK IT UP!", 540, 1150, 6, "W", alpha=0.5 + 0.5 * (int(bt * 4) % 2), t=t)
    else:
        k = bt - WIN
        put(img, "VICTORY!", 540, 610, 12, "G", zoom=0.4 + 0.6 * eob(k / 0.35), t=t)
        paste_c(img, glow(320, ORANGE, 0.9), 540, 940, 0.8)
        put(img, "RANK", 540, 750, 7, "W", t=t)
        put(img, "1ST", 540, 830, 30, "W", zoom=0.3 + 0.7 * eob((k - 0.1) / 0.35, 2.6), t=t)
        put(img, "EXAMPLE RANK", 540, 1080, 5, "O", t=t)
        put(img, "RUN COMPLETE", 540, 1150, 7, "W", alpha=cl((k - 0.5) / 0.2), t=t)
        # pixel confetti
        rng = np.random.default_rng(11)
        P = rng.random((90, 4))
        for px, py, ps, pc in P:
            yy = 560 + ((py * 700 + (k * B) * (380 + 520 * ps)) % 980)
            xx = px * W + 30 * math.sin(k * 3 + pc * 9)
            sz = 8 if ps > 0.5 else 12
            d.rectangle((xx, yy, xx + sz, yy + sz), fill=(WHITE, ORANGE, PINK, mix(ORANGE, PINK, .5))[int(pc * 4)] + (255,))

LOGO = None
def sc_end(img, bt, t):
    global LOGO
    d = ImageDraw.Draw(img, "RGBA")
    if bt < CARD:
        lt = bt - END0
        if (lt % 1.0) < 0.62:
            put(img, "PRESS START", 540, 900, 11, "W", t=t)
        paste(img, SPR("arrow", 5).rotate(-90, expand=True), 120 + 10 * math.sin(bt * 6), 905)
        put(img, "1 PLAYER", 540, 1040, 5, "O", t=t)
        return
    lt = bt - CARD
    if LOGO is None:
        LOGO = Image.open(os.path.join(WK, "logo.png"))
        w = 760; LOGO = LOGO.resize((w, int(LOGO.height * w / LOGO.width)), Image.LANCZOS)
    z = eob(lt / 0.5, 1.6)
    paste_c(img, glow(380, PINK, 0.35), 540, 650, 1.0)
    paste_c(img, LOGO, 540, 650, cl(lt / 0.2), zoom=0.6 + 0.4 * z)
    lines = [("JOIN THE", "W"), ("ATHLO 30x30", "G"), ("CHALLENGE", "W")]
    for j, (s, f) in enumerate(lines):
        k = lt - 0.25 - j * 0.18
        if k > 0:
            put(img, s, 540, 830 + j * 118, 14, f, zoom=0.5 + 0.5 * eob(k / 0.3), t=t)
    k = lt - 1.0
    if k > 0:
        pulse = 1 + 0.035 * math.exp(-((bt % 1) * 5))
        sc = eob(k / 0.3) * pulse
        bw, bh = 760 * sc, 170 * sc
        cx, cy = 540, 1300
        grad_box(img, cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, cut=int(24 * sc), border=WHITE + (255,), bw=8)
        # shine sweep across the button
        sx = ((bt * 0.5) % 1.6 - 0.3) * bw
        if 0 < sx < bw - 40:
            d.polygon([(cx - bw / 2 + sx, cy - bh / 2 + 8), (cx - bw / 2 + sx + 40, cy - bh / 2 + 8),
                       (cx - bw / 2 + sx + 10, cy + bh / 2 - 8), (cx - bw / 2 + sx - 30, cy + bh / 2 - 8)], fill=(255, 255, 255, 70))
        put(img, "LINK IN BIO", cx, cy - 32 * sc, 9, "W", zoom=sc, t=t)
        for j in range(3):
            paste_c(img, SPR("down", 6), 540, 1440 + j * 34 + 10 * math.sin(bt * 5 - j), 1 - j * 0.3)

# ------------------------------------------------------------------ transitions & post
def wipe(img, bt):
    """Gradient pixel-block wipe across scene cuts (never black)."""
    for c in SCENE_CUTS:
        k = (bt - c) / 0.5 + 0.5   # 0..1 over one beat centred on the cut
        if 0 <= k <= 1:
            d = ImageDraw.Draw(img, "RGBA")
            bs = 120
            for gy in range(0, H, bs):
                for gx in range(0, W, bs):
                    diag = (gx / W + gy / H) / 2
                    v = 1 - abs((k * 1.6 - 0.3) - diag) * 4
                    if v > 0:
                        s = int(bs * min(1, v) / 2)
                        cxx, cyy = gx + bs // 2, gy + bs // 2
                        d.rectangle((cxx - s, cyy - s, cxx + s, cyy + s), fill=grad_col(diag) + (255,))

def flash_amt(bt):
    a = 0.0
    if bt >= GO: a = max(a, 0.55 * math.exp(-(bt - GO) * B * 10))
    for s in SESS:
        if bt >= s + 1: a = max(a, 0.25 * math.exp(-(bt - s - 1) * B * 14))
    fa, _ = combo_flash(bt)
    a = max(a, fa)
    for s in STOMPS:
        if bt >= s: a = max(a, 0.35 * math.exp(-(bt - s) * B * 12))
    if bt >= COLLECT: a = max(a, 0.5 * math.exp(-(bt - COLLECT) * B * 9))
    if bt >= WIN: a = max(a, 0.55 * math.exp(-(bt - WIN) * B * 8))
    if bt >= CARD: a = max(a, 0.5 * math.exp(-(bt - CARD) * B * 9))
    return a

def flash_col(bt):
    _, times = combo_flash(bt)
    if COMBO0 <= bt < BOSS0:
        n = sum(1 for x in times if x <= bt)
        return (WHITE, ORANGE, PINK)[n % 3]
    if BOSS0 <= bt < POWER0: return PINK
    return WHITE

BASE = POST = None
def frame(fi):
    global BASE, POST
    if BASE is None:
        BASE = build_base(); POST = build_post()
    t = fi / FPS
    bt = t / B
    img = BASE.copy()
    draw_bg(img, fi, bt)
    # scene layer
    if bt < SESS0: sc_intro(img, bt, t)
    elif bt < RANK0: sc_session(img, bt, t, min(4, int((bt - SESS0) // SESS_LEN)))
    elif bt < COMBO0: sc_rank(img, bt, t)
    elif bt < BOSS0: sc_combo(img, bt, t)
    elif bt < POWER0: sc_boss(img, bt, t)
    elif bt < END0: sc_power(img, bt, t)
    else: sc_end(img, bt, t)
    a = np.asarray(img.convert("RGB"))
    # screen shake on the play-field (HUD stays put, like a real game)
    s = shake_amt(bt)
    if s > 0.5:
        dx = int(round(s * math.sin(t * 91.0))); dy = int(round(s * math.cos(t * 77.0)))
        p = int(math.ceil(s)) + 1
        a = np.pad(a, ((p, p), (p, p), (0, 0)), mode="edge")[p - dy:p - dy + H, p - dx:p - dx + W]
    img = Image.fromarray(np.ascontiguousarray(a))
    draw_hud(img, bt, t, show_corners=bt < CARD)
    wipe(img, bt)
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    fa = flash_amt(bt)
    if fa > 0.01:
        a = a * (1 - fa) + np.array(flash_col(bt), np.float32) * fa
    # chromatic split on big hits
    ca = int(round(shake_amt(bt) / 4 + 10 * fa * (bt >= COMBO0)))
    if ca > 0:
        a[:, ca:, 0] = a[:, :-ca, 0]; a[:, :-ca, 2] = a[:, ca:, 2]
    a = a * POST
    return np.clip(a, 0, 255).astype(np.uint8)

def frame_bytes(fi):
    return frame(fi).tobytes()

def main():
    os.makedirs(WK, exist_ok=True)
    if len(sys.argv) > 2 and sys.argv[1] == "--still":
        sd = os.path.join(WK, "stills"); os.makedirs(sd, exist_ok=True)
        for s in sys.argv[2].split(","):
            fi = int(round(float(s) * FPS))
            Image.fromarray(frame(fi)).save(os.path.join(sd, f"t{float(s):05.2f}.png"))
        return
    from multiprocessing import Pool
    out = os.path.join(WK, "picture.mp4")
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow",
                           "-profile:v", "high", "-level", "4.2", "-crf", "18", "-maxrate", "6M", "-bufsize", "12M",
                           "-g", "30", "-bf", "2", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
                           "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv", out], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, b in enumerate(pool.imap(frame_bytes, range(N), chunksize=4)):
            ff.stdin.write(b)
            if i % 150 == 0: print("frame", i, flush=True)
    ff.stdin.close(); ff.wait()
    # safe-area audit (text positions recorded in a separate single-process pass)
    TEXT_LOG.clear()
    for fi in range(0, N, 3):
        t = fi / FPS; bt = t / B
        img = Image.new("RGB", (W, H))
        if bt < SESS0: sc_intro(img, bt, t)
        elif bt < RANK0: sc_session(img, bt, t, min(4, int((bt - SESS0) // SESS_LEN)))
        elif bt < COMBO0: sc_rank(img, bt, t)
        elif bt < BOSS0: sc_combo(img, bt, t)
        elif bt < POWER0: sc_boss(img, bt, t)
        elif bt < END0: sc_power(img, bt, t)
        else: sc_end(img, bt, t)
        draw_hud(img, bt, t, show_corners=bt < CARD)
    bad = [e for e in TEXT_LOG if e[2] < SAFE_TOP or e[3] > SAFE_BOT]
    print(f"text draws audited: {len(TEXT_LOG)}, outside safe area: {len(bad)}")
    for e in bad[:20]: print("  ", e)
    print("wrote", out)

if __name__ == "__main__":
    main()
