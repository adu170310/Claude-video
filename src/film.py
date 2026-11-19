#!/usr/bin/env python3
"""Athlo launch film - picture renderer.

Renders 1080x1920 @ 30 fps frames with Pillow + numpy and pipes them to ffmpeg.
Usage: python3 src/film.py [--frames a:b] [--still t1,t2,...] [--workers 4]
"""
import argparse, math, os, random, subprocess, sys
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import *  # noqa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AS = os.path.join(ROOT, "work", "assets")
FD = "/usr/share/fonts/opentype/inter/"

# brand + app palette
ORANGE = (255, 172, 0)
PINK = (255, 10, 108)
WHITE = (255, 255, 255)
BG = (7, 7, 9)
DARK = (28, 42, 50)
CREAM = (243, 241, 236)
YELLOW = (243, 186, 25)
GRAY = (122, 126, 130)
CHIP = (231, 229, 224)
LINEC = (226, 223, 216)

# ------------------------------------------------------------------ easing

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x

def prog(t, t0, d):
    return clamp((t - t0) / d)

def e_out(x):   # quint ease-out: fast start, long confident settle
    return 1 - (1 - x) ** 5

def e_out3(x):
    return 1 - (1 - x) ** 3

def e_in3(x):
    return x ** 3

def e_io(x):    # cubic in-out
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2

def e_sine(x):
    return -(math.cos(math.pi * x) - 1) / 2

def lerp(a, b, x):
    return a + (b - a) * x

# ------------------------------------------------------------------ fonts / text

@lru_cache(None)
def font(name, size):
    return ImageFont.truetype(FD + name + ".otf", int(round(size)))

class Text:
    """A text sprite. Baseline-left of the text sits at (bx, by) inside the image."""
    def __init__(self, s, name, size, color=WHITE, tracking=-0.025, gradient=None):
        f = font(name, size)
        adv = [f.getlength(c) for c in s]
        tr = tracking * size
        self.width = sum(adv) + tr * (len(s) - 1)
        asc, desc = f.getmetrics()
        pad = int(size * 0.35) + 24
        w, h = int(self.width) + 2 * pad, asc + desc + 2 * pad
        m = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(m)
        x = pad
        self.xs = []
        for c, a in zip(s, adv):
            self.xs.append(x - pad)
            d.text((x, pad), c, font=f, fill=255)
            x += a + tr
        self.bx, self.by = pad, pad + asc
        self.cap = 0.727 * size
        self.size = size
        if gradient:
            g = np.linspace(0, 1, w)[None, :, None]
            c0, c1 = np.array(gradient[0])[None, None], np.array(gradient[1])[None, None]
            x0 = pad / w; x1 = (pad + self.width) / w
            gg = np.clip((g - x0) / (x1 - x0), 0, 1)
            rgb = (c0 * (1 - gg) + c1 * gg) * np.ones((h, 1, 1))
            img = Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")
        else:
            img = Image.new("RGBA", (w, h), color + (0,))
        img.putalpha(m)
        self.img = img

    @property
    def center(self):  # optical centre (cap-height middle)
        return (self.bx + self.width / 2, self.by - self.cap / 2)

@lru_cache(None)
def T(s, name="InterDisplay-SemiBold", size=100, color=WHITE, tracking=-0.025, gradient=None):
    return Text(s, name, size, color, tracking, gradient)

# ------------------------------------------------------------------ compositing

class Cam:
    """Camera push: scales everything placed through it about (cx, cy)."""
    def __init__(self, s=1.0, cx=W / 2, cy=H / 2, dx=0.0, dy=0.0):
        self.s, self.cx, self.cy, self.dx, self.dy = s, cx, cy, dx, dy

    def map(self, x, y):
        return self.cx + (x - self.cx) * self.s + self.dx, self.cy + (y - self.cy) * self.s + self.dy

NOCAM = Cam()

def place(canvas, img, x, y, ax, ay, scale=1.0, opacity=1.0, blur=0.0, cam=NOCAM):
    """Composite RGBA img so its point (ax, ay) lands on canvas (x, y), sub-pixel accurate."""
    if opacity <= 0.003 or scale <= 0.01:
        return
    x, y = cam.map(x, y)
    scale *= cam.s
    w, h = img.size
    left, top = x - ax * scale, y - ay * scale
    L, Tt = math.floor(left), math.floor(top)
    fx, fy = left - L, top - Tt
    ow, oh = int(math.ceil(w * scale + fx)) + 1, int(math.ceil(h * scale + fy)) + 1
    if L >= W or Tt >= H or L + ow <= 0 or Tt + oh <= 0:
        return
    if abs(scale - 1) < 1e-4 and fx < 1e-3 and fy < 1e-3:
        im = img
    else:
        if scale < 0.75:  # pre-shrink to avoid aliasing on big downscales
            k = max(scale, 0.05) * 1.3
            img = img.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)
            sx = img.size[0] / w
            im = img.transform((ow, oh), Image.AFFINE,
                               (sx / scale, 0, -fx * sx / scale, 0, sx / scale, -fy * sx / scale),
                               resample=Image.BICUBIC)
        else:
            im = img.transform((ow, oh), Image.AFFINE, (1 / scale, 0, -fx / scale, 0, 1 / scale, -fy / scale),
                               resample=Image.BICUBIC)
    if blur > 0.3:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    if opacity < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * opacity))
        im = im.copy(); im.putalpha(a)
    # crop to canvas
    cl, ct = max(0, -L), max(0, -Tt)
    cr, cb = min(im.size[0], W - L), min(im.size[1], H - Tt)
    if cr <= cl or cb <= ct:
        return
    if (cl, ct, cr, cb) != (0, 0) + im.size:
        im = im.crop((cl, ct, cr, cb))
    canvas.alpha_composite(im, (L + cl, Tt + ct))

def put_text(canvas, t, x, y, align="center", opacity=1.0, blur=0.0, scale=1.0, cam=NOCAM):
    """Place a Text so that its cap-middle sits at y; align=center/left/right by x."""
    ax = {"center": t.bx + t.width / 2, "left": t.bx, "right": t.bx + t.width}[align]
    ay = t.by - t.cap / 2
    place(canvas, t.img, x, y, ax, ay, scale, opacity, blur, cam)

def rrect_img(w, h, r, fill, outline=None, width=1, ss=3):
    """Anti-aliased rounded rectangle (supersampled)."""
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill, outline=outline,
                        width=width * ss if outline else 0)
    return im.resize((w, h), Image.LANCZOS)

def pad_img(im, p):
    out = Image.new("RGBA", (im.width + 2 * p, im.height + 2 * p), (0, 0, 0, 0))
    out.alpha_composite(im, (p, p))
    return out

# ------------------------------------------------------------------ background

LW, LH = 135, 240
_gy, _gx = np.mgrid[0:LH, 0:LW].astype(np.float32)
_gx = (_gx + 0.5) * (W / LW); _gy = (_gy + 0.5) * (H / LH)

def glow_field(blobs):
    """blobs: (x, y, radius, (r,g,b), intensity). Returns float32 HxWx3 0..255 at full size."""
    acc = np.zeros((LH, LW, 3), np.float32)
    for x, y, r, c, a in blobs:
        if a <= 0.002:
            continue
        r = r * 0.82
        g = np.exp(-(((_gx - x) ** 2 + (_gy - y) ** 2) / (2 * r * r)))
        acc += g[..., None] * (np.array(c, np.float32) * a * 0.85)[None, None]
    img = Image.fromarray(np.clip(acc + np.array(BG, np.float32), 0, 255).astype(np.uint8), "RGB")
    return img.resize((W, H), Image.BICUBIC)

def scene_glows(t):
    """Soft orange-to-pink light that breathes through the film."""
    bl = []
    dr = lambda f, a: math.sin(t * f) * a
    if t < S2:  # opening: a whisper of light under the line
        a = 0.10 * e_sine(prog(t, 0.2, 2.5)) * (1 - prog(t, 4.2, 0.8))
        bl += [(380 + dr(0.4, 40), 1180, 420, ORANGE, a), (720 + dr(0.3, 40), 1260, 420, PINK, a * 0.9)]
    elif t < S3:
        a = 0.10 + 0.05 * prog(t, S2, 3)
        burst = 0.0
        if t > MERGE - 0.15:
            burst = math.exp(-max(0, t - MERGE) * 3.0) * prog(t, MERGE - 0.15, 0.15)
        settle = e_out3(prog(t, MERGE, 1.5))
        a2 = a + 0.22 * settle
        fade = 1 - e_sine(prog(t, S2_OUT, 0.55))
        bl += [(300 + dr(0.35, 60), 760 + dr(0.27, 80), 460, ORANGE, a2 * fade),
               (800 + dr(0.3, 60), 1400 + dr(0.22, 80), 480, PINK, a2 * fade),
               (540, 1100, 260 + 300 * burst, (255, 120, 80), 0.9 * burst)]
    elif t < LANDS[0] - SLIDE:
        k = prog(t, S3, 7.5)
        a = (0.16 + 0.10 * e_sine(prog(t, S3, 1.0))) * (1 - 0.6 * e_sine(prog(t, S3_OUT, 0.9)))
        bl += [(lerp(250, 760, k), 700 + dr(0.4, 60), 480, ORANGE, a),
               (lerp(850, 330, k), 1350 + dr(0.35, 60), 520, PINK, a * 1.1)]
        if t > WORDS[4]:
            b = 0.10 * e_out3(prog(t, WORDS[4], 0.8)) * (1 - prog(t, S3_OUT, 0.6))
            bl.append((380, 1250, 300, PINK, b))
    elif t < LOGO:
        a = 0.26 * e_sine(prog(t, LANDS[0] - SLIDE, 1.0)) * (1 - 0.5 * e_sine(prog(t, S4_OUT, 0.7)))
        bl += [(330 + dr(0.3, 70), 900 + dr(0.25, 90), 430, ORANGE, a),
               (760 + dr(0.28, 70), 1350 + dr(0.2, 90), 460, PINK, a * 1.1)]
    else:
        a = 0.30 * e_sine(prog(t, LOGO - 0.3, 1.4))
        bl += [(370 + dr(0.25, 30), 760, 330, ORANGE, a),
               (700 + dr(0.22, 30), 820, 360, PINK, a),
               (540, 1250 + dr(0.2, 40), 600, (255, 80, 70), a * 0.35)]
    return bl

_vig = None
def vignette():
    global _vig
    if _vig is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
        _vig = (1 - 0.35 * np.clip(d - 0.35, 0, 1) ** 1.5)[..., None].astype(np.float32)
    return _vig

_grain = None
def grain(i):
    global _grain
    if _grain is None:
        rng = np.random.default_rng(7)
        _grain = [rng.normal(0, 1.6, (H, W, 1)).astype(np.float32) for _ in range(6)]
    return _grain[i % 6]

# ------------------------------------------------------------------ assets

@lru_cache(None)
def asset(name):
    return Image.open(os.path.join(AS, name)).convert("RGBA")

@lru_cache(None)
def photo(name, w, h):
    im = Image.open(os.path.join(AS, f"photo_{name}.png")).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s + 1), int(im.height * s + 1)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))

@lru_cache(None)
def round_mask(w, h, r, ss=3):
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=255)
    return m.resize((w, h), Image.LANCZOS)

# ------------------------------------------------------------------ phone + screens
# Screens are laid out in "units" (a 520-wide phone) and drawn at U x resolution, so the
# phone can be large in frame and the UI stays crisp.

U = 1.22
SW, SH = 520, 1130          # screen size in units
BZ = 13                     # bezel
PW, PH = SW + 2 * BZ, SH + 2 * BZ
STATUS = 64
HEADER_H = 74
CONTENT_Y = STATUS + HEADER_H

def px(v):
    return int(round(v * U))

def F(name, size):
    return font(name, size * U)

def FL(name, size, s):
    """Text length in units."""
    return font(name, size * U).getlength(s) / U

def _sc(v):
    if isinstance(v, (int, float)):
        return v * U
    return type(v)(_sc(x) for x in v) if not isinstance(v, list) else [_sc(x) for x in v]

class SD:
    """ImageDraw wrapper that takes coordinates in units."""
    def __init__(self, im):
        self.d = ImageDraw.Draw(im)
    def text(self, xy, s, font=None, fill=None, anchor=None):
        self.d.text(_sc(xy), s, font=font, fill=fill, anchor=anchor)
    def rounded_rectangle(self, box, r, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(_sc(box), r * U, fill=fill, outline=outline, width=max(1, round(width * U)))
    def line(self, pts, fill=None, width=1, joint=None):
        self.d.line(_sc(pts), fill=fill, width=max(1, round(width * U)), joint=joint)
    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(_sc(box), fill=fill, outline=outline, width=max(1, round(width * U)))
    def arc(self, box, a0, a1, fill=None, width=1):
        self.d.arc(_sc(box), a0, a1, fill=fill, width=max(1, round(width * U)))
    def pieslice(self, box, a0, a1, fill=None):
        self.d.pieslice(_sc(box), a0, a1, fill=fill)
    def polygon(self, pts, fill=None):
        self.d.polygon(_sc(pts), fill=fill)
    def rectangle(self, box, fill=None, outline=None):
        self.d.rectangle(_sc(box), fill=fill, outline=outline)

def comp(im, sprite, x, y):
    im.alpha_composite(sprite, (px(x), px(y)))

def ui_text(d, xy, s, name="Inter-Medium", size=15, fill=DARK, anchor="la", tracking=0.0):
    f = F(name, size)
    if tracking == 0:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)
        return FL(name, size, s)
    x, y = xy
    total = sum(FL(name, size, c) for c in s) + tracking * (len(s) - 1)
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for c in s:
        d.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1])
        x += FL(name, size, c) + tracking
    return total

def star(d, cx, cy, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)

def check(d, x, y, s, fill, w=3):
    d.line([(x, y + s * 0.5), (x + s * 0.38, y + s * 0.85), (x + s, y + s * 0.1)], fill=fill, width=w, joint="curve")

def uphoto(name, w, h):
    return photo(name, px(w), px(h))

def umask(w, h, r):
    return round_mask(px(w), px(h), px(r))

def grad_disc(r):
    """The 'You' avatar: brand orange/pink disc."""
    n = max(2, px(2 * r))
    g = Image.new("RGBA", (n * 3, n * 3), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    gd.ellipse((0, 0, n * 3 - 1, n * 3 - 1), fill=PINK)
    gd.pieslice((0, 0, n * 3 - 1, n * 3 - 1), 90, 270, fill=ORANGE)
    return g.resize((n, n), Image.LANCZOS)

@lru_cache(None)
def status_bar():
    im = Image.new("RGBA", (px(SW), px(STATUS)), CREAM + (255,))
    d = SD(im)
    k = (10, 10, 12)
    d.text((58, 36), "9:41", font=F("Inter-SemiBold", 17), fill=k, anchor="mm")
    x = SW - 118
    for i in range(4):
        h = 5 + i * 2.6
        d.rounded_rectangle((x + i * 6, 41 - h, x + i * 6 + 3.6, 41), 1, fill=k)
    cx, cy = SW - 76, 42
    for r in (12, 7.5):
        d.arc((cx - r, cy - r, cx + r, cy + r), 225, 315, fill=k, width=2.6)
    d.ellipse((cx - 2, cy - 4, cx + 2, cy), fill=k)
    d.rounded_rectangle((SW - 58, 30, SW - 30, 43), 4, outline=k, width=1)
    d.rounded_rectangle((SW - 56, 32, SW - 36, 41), 2, fill=k)
    d.rounded_rectangle((SW - 28, 34, SW - 26, 39), 1, fill=k)
    return im

@lru_cache(None)
def app_header():
    """The real Athlo app header (logo + menu) lifted from the screen recording."""
    hd = Image.open(os.path.join(AS, "app_header.png")).convert("RGB")
    hd = hd.crop((0, 15, hd.width, hd.height))
    return hd.resize((px(SW), int(hd.height * px(SW) / hd.width)), Image.LANCZOS)

@lru_cache(None)
def app_page():
    p = Image.open(os.path.join(AS, "app_page.png")).convert("RGB")
    return p.resize((px(SW), int(p.height * px(SW) / p.width)), Image.LANCZOS)

def screen_base():
    return Image.new("RGBA", (px(SW), px(SH)), CREAM + (255,))

def finish_screen(im):
    im.paste(app_header(), (0, px(STATUS + 2)))
    im.alpha_composite(status_bar(), (0, 0))
    SD(im).rounded_rectangle((SW / 2 - 66, SH - 15, SW / 2 + 66, SH - 10), 3, fill=(20, 20, 22))
    return im

def real_app_screen(scroll):
    """Scroll through the real app home page (stitched from the screen recording)."""
    im = screen_base()
    page = app_page()
    y0 = 330 * px(SW) / 1206
    winh = px(SH - CONTENT_Y - 24)
    crop = page.transform((px(SW), winh), Image.AFFINE, (1, 0, 0, 0, 1, y0 + scroll * U), resample=Image.BICUBIC)
    im.paste(crop, (0, px(CONTENT_Y)))
    return finish_screen(im)

def card_shadow(im, box, r):
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    SD(sh).rounded_rectangle((box[0], box[1] + 4, box[2], box[3] + 4), r, fill=(40, 30, 10, 26))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6 * U)))

def with_opacity(layer, op):
    if op < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * op)))
    return layer

def facility_card(size, y, ph, name, area, rating, tag, price, op=1.0, h=272):
    x0, x1 = 16, SW - 16
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    card_shadow(layer, (x0, y, x1, y + h), 22)
    d = SD(layer)
    d.rounded_rectangle((x0, y, x1, y + h), 22, fill=WHITE)
    pw, phh = x1 - x0, 168
    p = uphoto(ph, pw, phh).convert("RGBA")
    m = umask(pw, phh + 40, 22).crop((0, 0, p.width, p.height))
    p.putalpha(m)
    comp(layer, p, x0, y)
    d.text((x0 + 18, y + phh + 16), name, font=F("Inter-SemiBold", 18), fill=DARK)
    d.text((x0 + 18, y + phh + 42), area, font=F("Inter-Regular", 13), fill=GRAY)
    d.rounded_rectangle((x1 - 76, y + phh + 14, x1 - 16, y + phh + 40), 13, fill=(253, 241, 205))
    star(d, x1 - 60, y + phh + 27, 6.5, YELLOW)
    d.text((x1 - 50, y + phh + 27), rating, font=F("Inter-SemiBold", 13), fill=DARK, anchor="lm")
    tw = FL("Inter-Medium", 11, tag) + 20
    d.rounded_rectangle((x0 + 18, y + h - 34, x0 + 18 + tw, y + h - 12), 11, fill=CHIP)
    d.text((x0 + 28, y + h - 23), tag, font=F("Inter-Medium", 11), fill=DARK, anchor="lm")
    ui_text(d, (x1 - 18, y + h - 23), price, "Inter-SemiBold", 13, DARK, "rm")
    ui_text(d, (x1 - 20 - FL("Inter-SemiBold", 13, price), y + h - 23), "from ", "Inter-Regular", 12, GRAY, "rm")
    d.rounded_rectangle((x0 + 12, y + 12, x0 + 92, y + 34), 11, fill=YELLOW)
    ui_text(d, (x0 + 52, y + 23), "FEATURED", "Inter-Bold", 9, DARK, "mm", tracking=1.2)
    return with_opacity(layer, op)

def kicker_title(d, kicker, title, accent=None, y=CONTENT_Y + 22):
    ui_text(d, (20, y), kicker, "Inter-Medium", 11, (110, 114, 118), "lt", tracking=2.4)
    d.text((20, y + 22), title, font=F("InterDisplay-SemiBold", 29), fill=DARK)
    if accent:
        x = 20 + FL("InterDisplay-SemiBold", 29, title + " ")
        d.text((x, y + 22), accent, font=F("InterDisplay-SemiBold", 29), fill=YELLOW)

def chips(d, y, labels, active):
    x = 16
    for i, c in enumerate(labels):
        w = FL("Inter-Medium", 13, c) + 30
        d.rounded_rectangle((x, y, x + w, y + 34), 17, fill=YELLOW if i == active else CHIP)
        d.text((x + w / 2, y + 17), c, font=F("Inter-Medium", 13), fill=DARK, anchor="mm")
        x += w + 8

def screen_find(lt):
    """1. Find a court: search types, results rise in."""
    im = screen_base()
    d = SD(im)
    kicker_title(d, "FIND A COURT", "Places to", "play")
    y = CONTENT_Y + 88
    d.rounded_rectangle((16, y, SW - 16, y + 46), 23, fill=WHITE, outline=LINEC, width=1)
    d.ellipse((34, y + 15, 46, y + 27), outline=GRAY, width=2)
    d.line([(44, y + 26), (49, y + 31)], fill=GRAY, width=2)
    query = "Padel, Dubai Marina"
    n = int(len(query) * clamp((lt + 0.25) / 0.7))
    if n == 0:
        d.text((60, y + 23), "Search by name or area", font=F("Inter-Regular", 14), fill=(150, 152, 155), anchor="lm")
        cx = 60
    else:
        cx = 60 + ui_text(d, (60, y + 23), query[:n], "Inter-Medium", 14, DARK, "lm")
    if (lt * 2.2) % 1 < 0.6 and lt < 0.9:
        d.line([(cx + 2, y + 13), (cx + 2, y + 33)], fill=YELLOW, width=2)
    y2 = y + 62
    act = lt > 0.45
    chips(d, y2, ["All sports", "Padel", "Tennis", "Football", "Basketball"], 1 if act else 0)
    d.text((20, y2 + 56), "3 places near you" if act else "13 places", font=F("Inter-SemiBold", 15), fill=DARK)
    d.text((SW - 20, y2 + 58), "Sorted by distance", font=F("Inter-Regular", 11), fill=GRAY, anchor="ra")
    cards = [("padel", "Padel Point Marina", "Dubai Marina, Dubai", "4.5", "Padel", "AED 130"),
             ("tennis", "Safa Racket Club", "Al Safa, Dubai", "5.0", "Padel  ·  Tennis", "AED 70"),
             ("night", "The Cage JLT", "Jumeirah Lake Towers", "4.5", "Football", "AED 240")]
    for i, c in enumerate(cards):
        k = e_out(prog(lt, 0.5 + i * 0.14, 0.75))
        if k <= 0:
            continue
        cy = y2 + 92 + i * 290 + (1 - k) * 46
        im.alpha_composite(facility_card(im.size, cy, *c, op=k))
    return finish_screen(im)

def press(lt, t0, amt=0.06):
    return 1 - amt * math.sin(math.pi * prog(lt, t0, 0.22))

def screen_book(lt):
    """2. Book it: pick a day, pick a slot, confirm."""
    im = screen_base()
    comp(im, uphoto("padel", SW, 250).convert("RGBA"), 0, CONTENT_Y - 6)
    d = SD(im)
    y = CONTENT_Y + 262
    d.text((20, y), "Padel Point Marina", font=F("InterDisplay-SemiBold", 26), fill=DARK)
    d.text((20, y + 36), "Dubai Marina  ·  Padel  ·  Court 2", font=F("Inter-Regular", 13), fill=GRAY)
    d.rounded_rectangle((SW - 82, y + 4, SW - 20, y + 30), 13, fill=(253, 241, 205))
    star(d, SW - 66, y + 17, 6.5, YELLOW)
    d.text((SW - 56, y + 17), "4.5", font=F("Inter-SemiBold", 13), fill=DARK, anchor="lm")
    y += 76
    ui_text(d, (20, y), "PICK A DAY", "Inter-Medium", 11, (110, 114, 118), "lt", tracking=2.2)
    days = [("FRI", "20"), ("SAT", "21"), ("SUN", "22"), ("MON", "23"), ("TUE", "24")]
    bw = (SW - 32 - 4 * 8) / 5
    sel = 1 if lt > 0.3 else 0
    for i, (a, b) in enumerate(days):
        x = 16 + i * (bw + 8)
        on = i == sel
        sc = press(lt, 0.2) if i == 1 else 1.0
        ww, hh = bw * sc, 74 * sc
        bx0, by0 = x + (bw - ww) / 2, y + 22 + (74 - hh) / 2
        d.rounded_rectangle((bx0, by0, bx0 + ww, by0 + hh), 18, fill=DARK if on else WHITE,
                            outline=None if on else LINEC, width=1)
        d.text((x + bw / 2, y + 44), a, font=F("Inter-Medium", 11), fill=(170, 180, 185) if on else GRAY, anchor="mm")
        d.text((x + bw / 2, y + 72), b, font=F("Inter-SemiBold", 21), fill=WHITE if on else DARK, anchor="mm")
    y += 120
    ui_text(d, (20, y), "PICK A TIME", "Inter-Medium", 11, (110, 114, 118), "lt", tracking=2.2)
    slots = ["5:00 PM", "6:00 PM", "7:00 PM", "8:00 PM", "9:00 PM", "10:00 PM"]
    full = {1, 4}
    sw_ = (SW - 32 - 2 * 10) / 3
    pick = lt > 0.85
    for i, s in enumerate(slots):
        cx = 16 + (i % 3) * (sw_ + 10)
        cy = y + 22 + (i // 3) * 58
        sc = press(lt, 0.75) if i == 3 else 1.0
        ww, hh = sw_ * sc, 48 * sc
        bx0, by0 = cx + (sw_ - ww) / 2, cy + (48 - hh) / 2
        if i in full:
            d.rounded_rectangle((bx0, by0, bx0 + ww, by0 + hh), 14, fill=(236, 234, 229))
            d.text((cx + sw_ / 2, cy + 24), s, font=F("Inter-Medium", 14), fill=(185, 185, 185), anchor="mm")
            d.line([(cx + sw_ / 2 - 30, cy + 24), (cx + sw_ / 2 + 30, cy + 24)], fill=(185, 185, 185), width=1)
        else:
            on = i == 3 and pick
            d.rounded_rectangle((bx0, by0, bx0 + ww, by0 + hh), 14, fill=YELLOW if on else WHITE,
                                outline=None if on else LINEC, width=1)
            d.text((cx + sw_ / 2, cy + 24), s, font=F("Inter-SemiBold" if on else "Inter-Medium", 14), fill=DARK, anchor="mm")
    y += 150
    d.line([(20, y), (SW - 20, y)], fill=LINEC, width=1)
    d.text((20, y + 18), "Sat 21 Nov  ·  8:00 PM  ·  60 min", font=F("Inter-Medium", 14), fill=DARK if pick else GRAY)
    d.text((SW - 20, y + 18), "AED 130", font=F("Inter-SemiBold", 14), fill=DARK, anchor="ra")
    by = SH - 112
    done = lt > 1.55
    bp = press(lt, 1.42, 0.04)
    bw2, bh = (SW - 32) * bp, 58 * bp
    bx = (SW - bw2) / 2
    d.rounded_rectangle((bx, by + (58 - bh) / 2, bx + bw2, by + (58 + bh) / 2), 29, fill=YELLOW if done else DARK)
    if done:
        tw = FL("Inter-SemiBold", 17, "Court booked")
        check(d, SW / 2 - tw / 2 - 16, by + 21, 15, DARK, 3)
        d.text((SW / 2 + 10, by + 29), "Court booked", font=F("Inter-SemiBold", 17), fill=DARK, anchor="mm")
    else:
        d.text((SW / 2, by + 29), "Book now  ·  AED 130", font=F("Inter-SemiBold", 17), fill=WHITE, anchor="mm")
    return finish_screen(im)

AV_COLS = [(66, 135, 120), (230, 120, 70), (110, 100, 190), (60, 120, 190), (200, 80, 120),
           (150, 160, 60), (90, 90, 100), (220, 160, 40), (40, 150, 160), (170, 90, 60)]

def avatar(d, cx, cy, r, ini, col, ring=CREAM):
    d.ellipse((cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2), fill=ring)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    d.text((cx, cy + 0.5), ini, font=F("Inter-SemiBold", r * 0.8), fill=WHITE, anchor="mm")

def game_card(im, y, thumb, title, where, have, need, level, jk=None):
    x0, x1, h = 16, SW - 16, 226
    card_shadow(im, (x0, y, x1, y + h), 22)
    d = SD(im)
    d.rounded_rectangle((x0, y, x1, y + h), 22, fill=WHITE)
    th = uphoto(thumb, 56, 56).convert("RGBA")
    th.putalpha(umask(56, 56, 16))
    comp(im, th, x0 + 16, y + 16)
    d.text((x0 + 86, y + 20), title, font=F("Inter-SemiBold", 17), fill=DARK)
    d.text((x0 + 86, y + 46), where, font=F("Inter-Regular", 13), fill=GRAY)
    lw = FL("Inter-Medium", 11, level) + 20
    d.rounded_rectangle((x1 - 16 - lw, y + 18, x1 - 16, y + 40), 11, fill=CHIP)
    d.text((x1 - 16 - lw / 2, y + 29), level, font=F("Inter-Medium", 11), fill=DARK, anchor="mm")
    k = jk or 0.0
    joined = k > 0.25
    cnt = have + (1 if joined else 0)
    ay = y + 106
    shown = min(have, 6)
    for i in range(shown):
        avatar(d, x0 + 32 + i * 26, ay, 16, "ABCDEFGHJKLMNOPRS"[(i * 5 + have) % 17], AV_COLS[(i + have) % 10], WHITE)
    if k > 0:
        r = 16 * e_out(clamp((k - 0.2) * 1.6))
        if r > 0.5:
            cx = x0 + 32 + shown * 26
            d.ellipse((cx - r - 2, ay - r - 2, cx + r + 2, ay + r + 2), fill=WHITE)
            g = grad_disc(r)
            im.alpha_composite(g, (px(cx) - g.width // 2, px(ay) - g.height // 2))
            if r > 9:
                d.text((cx, ay), "You", font=F("Inter-Bold", r * 0.62), fill=WHITE, anchor="mm")
    d.text((x1 - 16, ay), f"{cnt} / {need} players", font=F("Inter-SemiBold", 14), fill=DARK, anchor="rm")
    py = y + 142
    d.rounded_rectangle((x0 + 16, py, x1 - 16, py + 6), 3, fill=CHIP)
    fr = (have + e_out(clamp((k - 0.2) * 1.4))) / need
    d.rounded_rectangle((x0 + 16, py, x0 + 16 + (x1 - x0 - 32) * fr, py + 6), 3, fill=YELLOW)
    by = y + 166
    pr = 1 - 0.05 * math.sin(math.pi * clamp(k / 0.25)) if jk is not None else 1.0
    bw, bh = (x1 - x0 - 32) * pr, 44 * pr
    bx = x0 + 16 + (x1 - x0 - 32 - bw) / 2
    d.rounded_rectangle((bx, by + (44 - bh) / 2, bx + bw, by + (44 + bh) / 2), 22, fill=YELLOW if joined else DARK)
    if joined:
        tw = FL("Inter-SemiBold", 15, "You're in")
        check(d, SW / 2 - tw / 2 - 14, by + 15, 13, DARK, 3)
        d.text((SW / 2 + 9, by + 22), "You're in", font=F("Inter-SemiBold", 15), fill=DARK, anchor="mm")
    else:
        d.text((SW / 2, by + 22), "Join game", font=F("Inter-SemiBold", 15), fill=WHITE, anchor="mm")

def screen_join(lt):
    """3. Join a game: tap Join, you're in."""
    im = screen_base()
    d = SD(im)
    kicker_title(d, "FIND PLAYERS", "Open games", "near you")
    y = CONTENT_Y + 92
    chips(d, y, ["Tonight", "This week", "Football", "Padel", "Basketball"], 0)
    jk = clamp((lt - 0.75) / 0.6)
    game_card(im, y + 54, "night", "5-a-side football", "The Cage JLT  ·  Tonight, 8:00 PM", 8, 10, "All levels",
              jk=jk if lt > 0.75 else None)
    game_card(im, y + 298, "padel", "Doubles padel", "Padel Point Marina  ·  9:30 PM", 3, 4, "Intermediate")
    game_card(im, y + 542, "hoop", "Pickup basketball", "Hoop House, Al Quoz  ·  10:00 PM", 6, 10, "All levels")
    return finish_screen(im)

BOARD = [("Sara K.", "Padel", 3120), ("Omar H.", "Football", 2890), ("Lina M.", "Running", 2610),
         ("Arjun P.", "Tennis", 2350), ("Maya R.", "Padel", 2280), ("Yusuf A.", "Basketball", 2140)]

def screen_board(lt):
    """4. Climb the leaderboard: your row rises from #7 to #3."""
    im = screen_base()
    d = SD(im)
    kicker_title(d, "DUBAI FITNESS 30X30", "Leaderboard")
    y = CONTENT_Y + 92
    d.rounded_rectangle((16, y, SW - 16, y + 40), 20, fill=CHIP)
    half = (SW - 32) / 2
    d.rounded_rectangle((19, y + 3, 16 + half - 3, y + 37), 17, fill=WHITE)
    d.text((16 + half / 2, y + 20), "This week", font=F("Inter-SemiBold", 13), fill=DARK, anchor="mm")
    d.text((16 + half * 1.5, y + 20), "All time", font=F("Inter-Medium", 13), fill=GRAY, anchor="mm")
    k = e_io(prog(lt, 0.35, 1.3))
    pts = int(lerp(1980, 2640, k))
    you_pos = lerp(6, 2, k)
    rank = int(round(you_pos)) + 1
    y += 56
    d.rounded_rectangle((16, y, SW - 16, y + 120), 22, fill=DARK)
    for x, lab in [(34, "YOUR RANK"), (200, "POINTS"), (360, "STREAK")]:
        ui_text(d, (x, y + 22), lab, "Inter-Medium", 10, (150, 165, 170), "lt", tracking=2.0)
    d.text((32, y + 40), f"#{rank}", font=F("InterDisplay-Bold", 50), fill=YELLOW)
    d.text((198, y + 44), f"{pts:,}", font=F("InterDisplay-SemiBold", 30), fill=WHITE)
    d.text((358, y + 44), "12 days", font=F("InterDisplay-SemiBold", 30), fill=WHITE)
    if 7 - rank > 0:
        d.text((104, y + 72), f"↑ {7 - rank}", font=F("Inter-SemiBold", 15), fill=(110, 215, 155))
    y0 = y + 140
    rh = 66
    rows = []
    for i, (n, s, p) in enumerate(BOARD):
        shift = clamp((i + 1) - you_pos) if i >= 2 else 0.0
        rows.append((i + shift, n, s, p, False))
    rows.append((you_pos, "You", "Padel  ·  Football", pts, True))
    for pos, n, s, p, me in sorted(rows, key=lambda r: r[4]):
        ry = y0 + pos * rh
        if me:
            card_shadow(im, (12, ry, SW - 12, ry + rh - 6), 18)
            d = SD(im)
            d.rounded_rectangle((12, ry, SW - 12, ry + rh - 6), 18, fill=WHITE, outline=PINK, width=2)
        r_disp = int(round(pos)) + 1
        d.text((40, ry + 30), str(r_disp), font=F("InterDisplay-SemiBold", 18),
               fill=YELLOW if r_disp <= 3 else GRAY, anchor="mm")
        if me:
            g = grad_disc(20)
            im.alpha_composite(g, (px(86) - g.width // 2, px(ry + 30) - g.height // 2))
            d.text((86, ry + 30), "You", font=F("Inter-Bold", 12), fill=WHITE, anchor="mm")
        else:
            avatar(d, 86, ry + 30, 20, n[0] + n.split()[1][0], AV_COLS[len(n) % 10], CREAM)
        d.text((118, ry + 14), n, font=F("Inter-SemiBold", 16), fill=DARK)
        d.text((118, ry + 36), s, font=F("Inter-Regular", 12), fill=GRAY)
        d.text((SW - 30, ry + 30), f"{p:,}", font=F("Inter-SemiBold", 16), fill=DARK, anchor="rm")
        if not me:
            d.line([(30, ry + rh - 3), (SW - 30, ry + rh - 3)], fill=LINEC, width=1)
    return finish_screen(im)

@lru_cache(None)
def phone_frame():
    k = 3
    w, h = px(PW), px(PH)
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), px(84) * k, fill=(58, 58, 63))
    d.rounded_rectangle((5, 5, w * k - 6, h * k - 6), px(83) * k, fill=(14, 14, 16))
    return im.resize((w, h), Image.LANCZOS)

@lru_cache(None)
def phone_shadow():
    p = 100
    w, h = px(PW), px(PH)
    im = Image.new("RGBA", (w + 2 * p, h + 2 * p), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((p, p + 24, p + w, p + h + 24), px(84), fill=(0, 0, 0, 210))
    return im.filter(ImageFilter.GaussianBlur(38))

def phone(screen):
    """Wrap a screen in a minimal device frame with the dynamic island."""
    im = phone_frame().copy()
    s = screen.copy()
    s.putalpha(umask(SW, SH, 70))
    comp(im, s, BZ, BZ)
    SD(im).rounded_rectangle((PW / 2 - 60, BZ + 12, PW / 2 + 60, BZ + 46), 17, fill=(4, 4, 5))
    return im

def put_phone(canvas, ph, x, y, scale=1.0, opacity=1.0, blur=0.0, cam=NOCAM, shadow=True):
    if shadow:
        sh = phone_shadow()
        place(canvas, sh, x, y, sh.width / 2, sh.height / 2, scale, opacity * 0.9, 0, cam)
    if blur > 0.3:
        ph = pad_img(ph, 24)
    place(canvas, ph, x, y, ph.width / 2, ph.height / 2, scale, opacity, blur, cam)

# ------------------------------------------------------------------ clutter sprites (scene 2)

def bubble(lines, who=None, who_col=(255, 160, 90), mine=False, w=None):
    f = F("Inter-Medium", 30)
    fw = F("Inter-SemiBold", 22)
    tw = max(f.getlength(l) for l in lines)
    if who:
        tw = max(tw, fw.getlength(who))
    w = int(w or tw + 56)
    h = int(36 + (36 if who else 0) + 42 * len(lines))
    im = rrect_img(w, h, 30, (40, 112, 220, 255) if mine else (38, 38, 42, 255))
    d = ImageDraw.Draw(im)
    y = 20
    if who:
        d.text((28, y), who, font=fw, fill=who_col); y += 36
    for l in lines:
        d.text((28, y), l, font=f, fill=WHITE); y += 42
    return im

def chat_header(name, sub):
    im = rrect_img(560, 110, 30, (28, 28, 31, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((24, 22, 90, 88), fill=(70, 70, 76))
    d.text((57, 55), name[0], font=F("Inter-SemiBold", 30), fill=WHITE, anchor="mm")
    d.text((110, 26), name, font=F("Inter-SemiBold", 28), fill=WHITE)
    d.text((110, 64), sub, font=F("Inter-Regular", 22), fill=(150, 150, 158))
    d.ellipse((470, 34, 532, 76), fill=(255, 59, 48))
    d.text((501, 55), "47", font=F("Inter-Bold", 24), fill=WHITE, anchor="mm")
    return im

def sheet():
    cols, rows = [170, 130, 130, 120], 7
    w, rh = sum(cols) + 2, 50
    h = 64 + rh * rows
    im = rrect_img(w + 20, h + 20, 16, (245, 245, 243, 255))
    d = ImageDraw.Draw(im)
    d.text((22, 20), "court_bookings_FINAL_v3.xlsx", font=F("Inter-Medium", 22), fill=(90, 90, 96))
    data = [["Player", "Paid", "Slot", "Court"], ["Omar", "AED 40", "8pm?", "#2"], ["Sara", "-", "9pm", "??"],
            ["Karim", "AED 40", "8pm", "#2"], ["Lina", "-", "?", ""], ["Arjun", "AED 60", "7pm", "#1"],
            ["Maya", "", "", ""]]
    y = 64
    for r, row in enumerate(data):
        x = 10
        for c, cw in enumerate(cols):
            fill = (225, 230, 225) if r == 0 else ((255, 236, 160) if row[c] in ("??", "?", "8pm?") else (255, 255, 255))
            d.rectangle((x, y, x + cw, y + rh), fill=fill, outline=(205, 205, 205))
            d.text((x + 12, y + rh / 2), row[c], font=F("Inter-SemiBold" if r == 0 else "Inter-Regular", 22),
                   fill=(40, 40, 44), anchor="lm")
            x += cw
        y += rh
    return im

def call_card(title, who, red=True):
    im = rrect_img(600, 132, 34, (30, 30, 34, 255))
    d = ImageDraw.Draw(im)
    col = (255, 69, 58) if red else (52, 199, 89)
    d.ellipse((26, 26, 106, 106), fill=col)
    # handset glyph
    hs = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hs)
    hd.arc((20, 20, 100, 100), 200, 340, fill=WHITE, width=16)
    hd.ellipse((14, 52, 40, 72), fill=WHITE); hd.ellipse((80, 52, 106, 72), fill=WHITE)
    hs = hs.rotate(135 if red else 0, Image.BICUBIC).resize((52, 52), Image.LANCZOS)
    im.alpha_composite(hs, (40, 40))
    d.text((128, 32), title, font=F("Inter-Regular", 24), fill=(160, 160, 168))
    d.text((128, 66), who, font=F("Inter-SemiBold", 30), fill=WHITE)
    return im

def notif(app, msg):
    f = F("Inter-Regular", 26)
    w = int(max(f.getlength(msg), 300) + 150)
    im = rrect_img(w, 124, 30, (44, 44, 50, 255))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24, 30, 88, 94), 16, fill=(90, 90, 100))
    d.rounded_rectangle((38, 46, 74, 72), 8, fill=WHITE)
    d.polygon([(44, 70), (44, 82), (56, 70)], fill=WHITE)
    d.text((108, 28), app, font=F("Inter-SemiBold", 24), fill=WHITE)
    d.text((w - 26, 30), "now", font=F("Inter-Regular", 20), fill=(150, 150, 158), anchor="ra")
    d.text((108, 64), msg, font=f, fill=(225, 225, 230))
    return im

@lru_cache(None)
def clutter():
    """(sprite, x, y, depth) - scattered fragments of how sport is organised today."""
    rnd = random.Random(4)
    items = [
        (chat_header("Padel crew", "Omar, Sara, Karim, +11"), 560, 700, 1.0),
        (bubble(["Anyone free for padel", "tonight?"], "Omar", (255, 170, 80)), 720, 900, 1.05),
        (bubble(["Which court again??"], "Sara", (120, 200, 255)), 250, 1020, 0.9),
        (bubble(["Need 2 more for", "5-a-side!"], "Karim", (180, 140, 255)), 770, 1190, 0.85),
        (bubble(["Who's paying for the pitch?"], mine=True), 400, 1360, 1.0),
        (sheet(), 690, 1570, 0.9),
        (call_card("Missed call (3)", "Al Barsha Courts"), 360, 1730, 0.95),
        (call_card("Calling...", "Booking line", red=False), 860, 560, 0.6),
        (notif("Sunday Football", "Is it 7 or 8? Someone confirm"), 330, 1200, 0.7),
        (bubble(["Running 10 min late"], "Lina", (120, 230, 160)), 880, 1430, 0.65),
        (bubble(["Court's full. Again."], "Arjun", (255, 120, 150)), 190, 1560, 0.7),
        (notif("Voicemail", "Hi, about your 8pm slot..."), 640, 1010, 0.55),
        (bubble(["Can someone call the club?"]), 860, 1780, 0.55),
        (sheet(), 170, 840, 0.5),
        (bubble(["8 or 8:30??"], "Omar", (255, 170, 80)), 300, 620, 0.5),
    ]
    out = []
    for i, (im, x, y, z) in enumerate(items):
        ang = rnd.uniform(-5, 5)
        sp = pad_img(im, 30).rotate(ang, Image.BICUBIC, expand=True)
        delay = rnd.uniform(0, 1.9)
        out.append((sp, x, y, z, delay, rnd.uniform(0, 6.28), rnd.uniform(0.25, 0.5)))
    # back to front
    return sorted(out, key=lambda o: o[3])

# ------------------------------------------------------------------ scenes

def scene_open(cv, t):
    cam = Cam(1.0 + 0.05 * e_sine(prog(t, 0, 5.0)))
    k = e_out(prog(t, OPEN_IN, 1.4))
    l1 = T("Sport in Dubai", "InterDisplay-SemiBold", 112, tracking=-0.03)
    l2 = T("is scattered.", "InterDisplay-SemiBold", 112, tracking=-0.03)
    y1, y2 = 900, 1030
    out1 = e_sine(prog(t, 4.0, 0.85))
    put_text(cv, l1, W / 2, y1 + (1 - k) * 40, opacity=k * (1 - out1), blur=(1 - k) * 14 + out1 * 8, cam=cam)
    k2 = e_out(prog(t, OPEN_IN + 0.18, 1.4))
    # line 2 letter by letter so "scattered." can drift apart
    rnd = random.Random(11)
    x0 = W / 2 - l2.width / 2
    s = "is scattered."
    sc = prog(t, SCATTER, 1.6)
    for i, c in enumerate(s):
        if c == " ":
            continue
        ch = T(c, "InterDisplay-SemiBold", 112, tracking=0)
        dx, dy = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
        stag = rnd.uniform(0, 0.35)
        m = e_io(clamp((sc - stag) / 0.65)) if i >= 3 else 0.0
        fade = (1 - m) if i >= 3 else (1 - out1)
        x = x0 + l2.xs[i] + dx * 120 * m
        y = y2 + (1 - k2) * 40 + dy * 110 * m
        put_text(cv, ch, x, y, align="left", opacity=k2 * fade, blur=(1 - k2) * 14 + m * 10, cam=cam)

def scene_clutter(cv, t):
    lt = t - S2
    cam = Cam(1.0 + 0.04 * e_sine(prog(t, S2, 5.0)), cy=1100)
    cx, cy = W / 2, 1110
    for sp, x, y, z, delay, ph, sp_ in clutter():
        k = e_out(prog(lt, 0.15 + delay, 1.2))
        if k <= 0:
            continue
        # float + parallax drift
        fx = x + math.sin(lt * sp_ + ph) * 18 * z + (x - cx) * 0.03 * lt * z
        fy = y + math.cos(lt * sp_ * 0.8 + ph) * 14 * z - lt * 6 * z
        scale = 0.92 * z
        blur = max(0.0, (1.0 - z) * 9)
        op = k * (0.45 + 0.55 * z)
        # anticipation then collapse into the phone
        ant = e_sine(prog(t, COLLAPSE - 0.6, 0.6)) * (1 - prog(t, COLLAPSE, 0.3))
        fx += (fx - cx) * 0.05 * ant; fy += (fy - cy) * 0.05 * ant
        c = e_in3(clamp((t - COLLAPSE - delay * 0.18) / 0.75))
        if c > 0:
            fx, fy = lerp(fx, cx, c), lerp(fy, cy, c)
            scale *= (1 - 0.85 * c)
            op *= (1 - c ** 1.6)
            blur += 8 * c
        place(cv, sp, fx, fy, sp.width / 2, sp.height / 2, scale, op, blur, cam)
    # captions
    names = ["Group chats.", "Spreadsheets.", "Phone calls."]
    out = e_sine(prog(t, COLLAPSE - 0.7, 0.6))
    for i, n in enumerate(names):
        k = e_out(prog(t, CAPS[i], 1.1))
        tx = T(n, "InterDisplay-SemiBold", 84, tracking=-0.03)
        put_text(cv, tx, 96, 300 + i * 100 + (1 - k) * 30, align="left", opacity=k * (1 - out),
                 blur=(1 - k) * 10 + out * 6)
    # phone with the real app
    if t >= MERGE - 0.1:
        pk = e_out(prog(t, MERGE - 0.1, 1.1))
        scroll = 640 * e_io(prog(t, MERGE + 0.9, 3.0))
        ph = phone(real_app_screen(scroll))
        outk = e_sine(prog(t, S2_OUT, 0.55))
        pcam = Cam(1.0 + 0.035 * e_sine(prog(t, MERGE, 4.1)), cy=1130)
        put_phone(cv, ph, W / 2, 1175 + (1 - pk) * 30 - outk * 20, scale=0.9 * lerp(0.82, 1.0, pk) * (1 - 0.04 * outk),
                  opacity=pk * (1 - outk), blur=(1 - pk) * 12 + outk * 10, cam=pcam)
        k = e_out(prog(t, ONE_APP, 1.2))
        tx = T("One clean app.", "InterDisplay-SemiBold", 92, tracking=-0.03)
        put_text(cv, tx, W / 2, 370 + (1 - k) * 30, opacity=k * (1 - outk), blur=(1 - k) * 12 + outk * 6, cam=pcam)

def scene_tagline(cv, t):
    words = ["Discover.", "Book.", "Play.", "Train.", "Compete."]
    cam = Cam(1.0 + 0.06 * e_sine(prog(t, S3, 8.0)), cx=300, cy=960)
    lh = 186
    # the stack re-centres itself as each word lands, so the newest line sits near the middle
    n = sum(e_io(prog(t, w - 0.06, 0.9)) for w in WORDS)
    top = 975 - max(0.0, n - 1) * lh / 2
    full = e_io(prog(t, FULL, 0.8))
    for i, w in enumerate(words):
        t0 = WORDS[i] - 0.06
        k = e_out(prog(t, t0, 1.0))
        if k <= 0:
            continue
        nxt = WORDS[i + 1] - 0.06 if i < 4 else 1e9
        dim = e_out3(prog(t, nxt, 0.5)) * (1 - full)
        op = k * (1 - 0.7 * dim)
        out = e_io(prog(t, S3_OUT + i * 0.07, 0.65))
        grad = (ORANGE, PINK) if i == 4 else None
        tx = T(w, "InterDisplay-Bold", 172, tracking=-0.035, gradient=grad)
        y = top + i * lh + (1 - k) * 70 - out * 80
        put_text(cv, tx, 92, y, align="left", opacity=op * (1 - out), blur=(1 - k) * 16 + out * 10,
                 scale=lerp(1.04, 1.0, k), cam=cam)

SCREENS = [("Find a court.", None, screen_find), ("Book it.", None, screen_book),
           ("Join a game.", None, screen_join), ("Climb the", "leaderboard.", screen_board)]
KICK = ["DISCOVER", "BOOK", "PLAY", "COMPETE"]

def scene_screens(cv, t):
    cam = Cam(1.0 + 0.05 * e_sine(prog(t, LANDS[0] - SLIDE, 12.0)), cy=1150)
    phone_y = 1228
    for i, (h1, h2, fn) in enumerate(SCREENS):
        land = LANDS[i]
        start = land - SLIDE
        nxt = LANDS[i + 1] - SLIDE if i < 3 else None
        if t < start - 0.01:
            continue
        if nxt is not None and t > nxt + SLIDE + 0.01:
            continue
        lt = t - land
        k_in = e_io(prog(t, start, SLIDE))
        k_out = e_io(prog(t, nxt, SLIDE)) if nxt is not None else 0.0
        fin = e_sine(prog(t, S4_OUT, 0.7)) if i == 3 else 0.0
        x = W / 2 + (1 - k_in) * 820 - k_out * 820
        sc = 0.96 * (1.0 - 0.10 * (1 - k_in) - 0.10 * k_out - 0.12 * fin)
        op = (0.35 + 0.65 * k_in) * (1 - 0.65 * k_out) * (1 - fin)
        ph = phone(fn(lt))
        put_phone(cv, ph, x, phone_y + fin * 40, scale=sc, opacity=op, blur=fin * 10, cam=cam)
        # caption: kicker + headline, cross-fading with the slide
        ck = e_out(prog(t, land - 0.35, 1.0))
        co = e_sine(prog(t, nxt - 0.05, 0.4)) if nxt is not None else fin
        if ck > 0 and co < 1:
            kt = T(KICK[i], "Inter-SemiBold", 36, tracking=0.2, gradient=(ORANGE, PINK))
            put_text(cv, kt, W / 2, 258 + (1 - ck) * 20, opacity=ck * (1 - co), blur=(1 - ck) * 6)
            sz = 84
            if h2:
                for j, ln in enumerate([h1, h2]):
                    tx = T(ln, "InterDisplay-SemiBold", sz, tracking=-0.03)
                    put_text(cv, tx, W / 2, 350 + j * 92 + (1 - ck) * 34, opacity=ck * (1 - co),
                             blur=(1 - ck) * 12 + co * 6)
            else:
                tx = T(h1, "InterDisplay-SemiBold", sz, tracking=-0.03)
                put_text(cv, tx, W / 2, 380 + (1 - ck) * 34, opacity=ck * (1 - co), blur=(1 - ck) * 12 + co * 6)

def scene_close(cv, t):
    cam = Cam(1.0 + 0.045 * e_sine(prog(t, LOGO, 8.75)), cy=1000)
    rings = asset("logo_rings.png"); word = asset("logo_word.png")
    full_w = rings.width + word.width
    s = 820 / full_w
    lx = W / 2 - 820 / 2
    ly = 760
    k = e_out(prog(t, LOGO, 1.5))
    rs = s * lerp(0.86, 1.0, k)
    # rings anchor: their own centre
    rcx = lx + rings.width * s / 2
    place(cv, rings, rcx, ly, rings.width / 2, rings.height / 2, rs, k, (1 - k) * 18, cam)
    kw = e_out(prog(t, WORDMARK, 1.3))
    wcx = lx + rings.width * s + word.width * s / 2
    place(cv, word, wcx - (1 - kw) * 40, ly, word.width / 2, word.height / 2, s, kw, (1 - kw) * 14, cam)
    for j, ln in enumerate(["Your sports life,", "in one place."]):
        kk = e_out(prog(t, LINE + j * 0.16, 1.3))
        tx = T(ln, "InterDisplay-SemiBold", 80, tracking=-0.03)
        put_text(cv, tx, W / 2, 1040 + j * 96 + (1 - kk) * 34, opacity=kk, blur=(1 - kk) * 12, cam=cam)
    kc = e_out(prog(t, CTA, 1.2))
    tx = T("Join the Dubai Fitness 30x30.", "InterDisplay-Medium", 46, color=(214, 214, 220), tracking=-0.015)
    put_text(cv, tx, W / 2, 1300 + (1 - kc) * 24, opacity=kc, blur=(1 - kc) * 8, cam=cam)
    kp = e_out(prog(t, PILL, 1.2))
    if kp > 0:
        pill = link_pill()
        place(cv, pill, W / 2, 1418 + (1 - kp) * 24, pill.width / 2, pill.height / 2, lerp(0.94, 1, kp), kp,
              (1 - kp) * 8, cam)

@lru_cache(None)
def link_pill():
    tx = T("Link in bio", "InterDisplay-SemiBold", 40, color=WHITE, tracking=-0.01)
    w, h = int(tx.width + 96), 92
    ss = 3
    g = np.linspace(0, 1, w * ss)[None, :, None]
    rgb = (np.array(ORANGE)[None, None] * (1 - g) + np.array(PINK)[None, None] * g) * np.ones((h * ss, 1, 1))
    im = Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), h * ss // 2, fill=255)
    im.putalpha(m)
    im = im.resize((w, h), Image.LANCZOS)
    im = pad_img(im, 20)
    d = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d.alpha_composite(im)
    ax = tx.bx + tx.width / 2; ay = tx.by - tx.cap / 2
    tl = (int(round(d.width / 2 - ax)), int(round(d.height / 2 - ay)))
    d.alpha_composite(tx.img, tl)
    return d

# ------------------------------------------------------------------ frame

def render(i):
    t = i / FPS
    bg = glow_field(scene_glows(t))
    cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if t < S2:
        scene_open(cv, t)
    elif t < S3:
        scene_clutter(cv, t)
    elif t < LANDS[0] - SLIDE:
        scene_tagline(cv, t)
    elif t < LOGO - 0.0:
        scene_screens(cv, t)
    if t >= LOGO - 0.0:
        scene_close(cv, t)
    if LOGO - 0.6 < t < LOGO:
        scene_screens(cv, t)
    bg = bg.convert("RGBA")
    bg.alpha_composite(cv)
    a = np.asarray(bg.convert("RGB"), dtype=np.float32)
    a = a * vignette() + grain(i)
    return np.clip(a, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ main

def encode(frames, out):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-tune", "grain",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in frames:
        p.stdin.write(render(i).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        sys.exit("ffmpeg failed")

def worker(args):
    a, b, out = args
    encode(range(a, b), out)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", help="comma-separated times to save as PNG")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(ROOT, "work", "picture.mp4"))
    ap.add_argument("--range", help="start:end seconds")
    a = ap.parse_args()
    if a.still:
        os.makedirs(os.path.join(ROOT, "work", "stills"), exist_ok=True)
        for s in a.still.split(","):
            fr = int(round(float(s) * FPS))
            p = os.path.join(ROOT, "work", "stills", f"t{float(s):06.2f}.png")
            Image.fromarray(render(fr)).save(p); print(p)
        return
    n = int(DUR * FPS)
    s0, s1 = 0, n
    if a.range:
        x, y = a.range.split(":"); s0, s1 = int(float(x) * FPS), int(float(y) * FPS)
    from multiprocessing import Pool
    k = a.workers * 3
    bounds = [s0 + (s1 - s0) * j // k for j in range(k + 1)]
    tmp = os.path.join(ROOT, "work", "chunks"); os.makedirs(tmp, exist_ok=True)
    jobs = [(bounds[j], bounds[j + 1], os.path.join(tmp, f"c{j:03d}.mp4")) for j in range(k)]
    with Pool(a.workers) as pool:
        for o in pool.imap(worker, jobs):
            print("done", o, flush=True)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{j[2]}'\n" for j in jobs)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", a.out], check=True)
    print("wrote", a.out)

if __name__ == "__main__":
    main()
