#!/usr/bin/env python3
"""Athlo launch film (30 s cut) - picture renderer.

Renders 1080x1920 @ 30 fps frames with Pillow + numpy and pipes them to ffmpeg.
Usage: python3 src/film.py [--frames a:b] [--still t1,t2,...] [--workers 4]
"""
import argparse, math, os, random, subprocess, sys
from functools import lru_cache
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

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
        _grain = [rng.normal(0, 1.0, (H, W, 1)).astype(np.float32) for _ in range(6)]
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
    data = [["Player", "Paid", "Slot", "Court"], ["Omar", "yes", "8pm?", "#2"], ["Sara", "-", "9pm", "??"],
            ["Karim", "yes", "8pm", "#2"], ["Lina", "-", "?", ""], ["Arjun", "yes?", "7pm", "#1"],
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
    """Fragments of how sport is organised today. Each flies in and lands on a growing pile.
    (sprite, x, y, depth, land_time, phase, speed, from_x, from_y, start_angle)"""
    rnd = random.Random(4)
    items = [
        (chat_header("Padel crew", "Omar, Sara, Karim, +11"), 560, 700, 1.0),
        (bubble(["Anyone free for padel", "tonight?"], "Omar", (255, 170, 80)), 720, 880, 1.05),
        (call_card("Missed call (3)", "Sports club"), 360, 1420, 0.95),
        (bubble(["Which court again??"], "Sara", (120, 200, 255)), 260, 1000, 0.9),
        (sheet(), 700, 1290, 0.9),
        (bubble(["Need 2 more for", "5-a-side!"], "Karim", (180, 140, 255)), 780, 1090, 0.85),
        (notif("Sunday Football", "Is it 7 or 8? Someone confirm"), 330, 1180, 0.75),
        (bubble(["Who's paying for the pitch?"], mine=True), 420, 1300, 1.0),
        (call_card("Calling...", "Booking line", red=False), 800, 700, 0.7),
        (bubble(["Court's full. Again."], "Arjun", (255, 120, 150)), 230, 820, 0.7),
        (notif("Voicemail", "Hi, about your 8pm slot..."), 640, 1460, 0.6),
        (bubble(["Running 10 min late"], "Lina", (120, 230, 160)), 860, 1420, 0.65),
        (sheet(), 200, 1250, 0.55),
        (bubble(["8 or 8:30??"], "Omar", (255, 170, 80)), 520, 960, 0.8),
        (bubble(["Can someone call the club?"]), 540, 1150, 1.0),
    ]
    out = []
    n = len(items)
    for i, (im, x, y, z) in enumerate(items):
        ang = rnd.uniform(-6, 6)
        sp = pad_img(im, 30).rotate(ang, Image.BICUBIC, expand=True)
        land = -0.35 + i * (3.1 / (n - 1)) + rnd.uniform(-0.08, 0.08)  # some are already landing on frame one
        side = rnd.choice(["l", "r", "b"])
        fx = -500 if side == "l" else W + 500 if side == "r" else x + rnd.uniform(-200, 200)
        fy = y + rnd.uniform(-250, 250) if side != "b" else H + 400
        out.append((sp, x, y, z, land, rnd.uniform(0, 6.28), rnd.uniform(0.3, 0.55), fx, fy, rnd.uniform(-14, 14)))
    return sorted(out, key=lambda o: o[3])

# ------------------------------------------------------------------ real app details (zoom shots)

@lru_cache(None)
def ui(name):
    return Image.open(os.path.join(AS, f"ui_{name}.png")).convert("RGB")

def card_from(im, width, radius=40):
    """Scale a real UI crop to display width and give it rounded corners."""
    s = width / im.width
    im = im.resize((int(round(width)), int(round(im.height * s))), Image.LANCZOS).convert("RGBA")
    im.putalpha(round_mask(im.width, im.height, radius))
    return im

@lru_cache(None)
def card_shadow_img(w, h, r=40):
    p = 80
    im = Image.new("RGBA", (w + 2 * p, h + 2 * p), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((p, p + 18, p + w, p + h + 18), r, fill=(0, 0, 0, 190))
    return im.filter(ImageFilter.GaussianBlur(30))

def put_card(cv, card, x, y, scale=1.0, opacity=1.0, cam=NOCAM):
    sh = card_shadow_img(card.width, card.height)
    place(cv, sh, x, y, sh.width / 2, sh.height / 2, scale, opacity * 0.85, 0, cam)
    place(cv, card, x, y, card.width / 2, card.height / 2, scale, opacity, 0, cam)

CW = 960  # display width of a detail card

# Places to play: count "13 places" up from zero, then hand back to the real pixels.
DIGITS = (15, 838, 96, 916)     # patch box in crop coords (bg covers the real "13")

def detail_discover(lt):
    im = ui("places").copy()
    k = clamp((lt - 0.35) / 0.9)
    fade = 1 - clamp((lt - 1.3) / 0.25)
    if lt < 1.55:
        patch = Image.new("RGB", (DIGITS[2] - DIGITS[0], DIGITS[3] - DIGITS[1]), (244, 242, 237))
        d = ImageDraw.Draw(patch)
        n = int(round(13 * e_out3(k)))
        f = font("InterDisplay-SemiBold", 86)
        sq = 68 / f.getlength("13")   # squeeze Inter's wider digits to the app's "13" width
        g = Image.new("L", (200, 120), 0)
        ImageDraw.Draw(g).text((0, 100), str(n), font=f, fill=255, anchor="ls")
        g = g.resize((int(200 * sq), 120), Image.LANCZOS)
        ink = Image.new("RGB", g.size, (24, 28, 32))
        patch.paste(ink, (19 - DIGITS[0], 908 - DIGITS[1] - 100), g)
        im.paste(Image.blend(im.crop(DIGITS), patch, fade), DIGITS[:2])
    return card_from(im, CW)

BTN = (72, 1018, 614, 1159)     # "Find a facility" button in the hero crop
HERO_BG = (28, 42, 50)

def detail_book(lt):
    im = ui("hero").copy().convert("RGBA")
    p = math.sin(math.pi * clamp((lt - 0.95) / 0.32))
    if p > 0:
        btn = im.crop(BTN)
        bw, bh = btn.size
        s = 1 - 0.07 * p
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((BTN[0] - 3, BTN[1] - 3, BTN[2] + 3, BTN[3] + 3), (bh + 6) // 2, fill=HERO_BG)
        b2 = btn.resize((int(bw * s), int(bh * s)), Image.LANCZOS)
        m = round_mask(b2.width, b2.height, b2.height // 2)
        im.paste(b2, (int(BTN[0] + (bw - b2.width) / 2), int(BTN[1] + (bh - b2.height) / 2)), m)
    r = clamp((lt - 1.02) / 0.6)
    if 0 < r < 1:  # tap ripple
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        cx, cy = (BTN[0] + BTN[2]) / 2, (BTN[1] + BTN[3]) / 2
        rad = 60 + 330 * e_out3(r)
        ImageDraw.Draw(lay).ellipse((cx - rad, cy - rad * 0.55, cx + rad, cy + rad * 0.55),
                                    outline=(255, 255, 255, int(140 * (1 - r))), width=6)
        im.alpha_composite(lay)
    return card_from(im.convert("RGB"), 900)

@lru_cache(None)
def chip_box():
    import json
    return tuple(json.load(open(os.path.join(AS, "ui_boxes.json")))["football_chip"])

def detail_play(lt):
    im = ui("chips").copy()
    x0, y0, x1, y1 = chip_box()
    on = clamp((lt - 0.95) / 0.18)
    p = math.sin(math.pi * clamp((lt - 0.85) / 0.3))
    if on > 0 or p > 0:
        chip = im.crop((x0, y0, x1, y1))
        a = np.asarray(chip, np.float32)
        ratio = np.array(YELLOW, np.float32) / np.array((232, 230, 225), np.float32)
        lit = np.clip(a * (1 + (ratio - 1) * on), 0, 255).astype(np.uint8)
        chip = Image.fromarray(lit, "RGB")
        s = 1 - 0.08 * p
        cw, ch = chip.size
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((x0 - 2, y0 - 2, x1 + 2, y1 + 2), (ch + 4) // 2, fill=(244, 242, 237))
        c2 = chip.resize((int(cw * s), int(ch * s)), Image.LANCZOS)
        im.paste(c2, (int(x0 + (cw - c2.width) / 2), int(y0 + (ch - c2.height) / 2)),
                 round_mask(c2.width, c2.height, c2.height // 2))
    return card_from(im, CW)

ROW_H = 171

def menu_card(crop, sel_from, sel_to, lt, dim_others=True):
    """Real menu rows; the app's own 'active row' tint slides onto the selected row."""
    im = crop.copy()
    k = e_io(clamp((lt - 0.5) / 0.55))
    sel = lerp(sel_from, sel_to, k)
    y = 8 + sel * ROW_H
    hl = Image.new("RGB", im.size, (255, 255, 255))
    ImageDraw.Draw(hl).rounded_rectangle((14, y, im.width - 18, y + ROW_H - 16), 30, fill=(229, 227, 221))
    on = clamp((lt - 0.35) / 0.3)
    im = Image.blend(im, ImageChops.darker(im, hl), on)
    if dim_others:
        veil = Image.new("RGB", im.size, (244, 242, 237))
        m = Image.new("L", im.size, int(150 * clamp((lt - 0.8) / 0.4)))
        ImageDraw.Draw(m).rectangle((0, y - 4, im.width, y + ROW_H - 10), fill=0)
        im = Image.composite(veil, im, m)
    return im

def detail_train(lt):
    return card_from(menu_card(ui("menu_train"), 0, 1, lt), CW)

def detail_compete(lt):
    return card_from(menu_card(ui("menu_compete"), 1, 2, lt), CW)

DETAILS = [("Discover.", detail_discover), ("Book.", detail_book), ("Play.", detail_play),
           ("Train.", detail_train), ("Compete.", detail_compete)]

# ------------------------------------------------------------------ scenes

WORD_Y = 340          # cap-centre of the big word in each detail moment
CARD_TOP = 500        # cards start below the word and end above the bottom fifth

def scene_hook(cv, t):
    cam = Cam(1.0 + 0.035 * e_sine(prog(t, 0, COLLAPSE)), cy=1000)
    cx, cy = W / 2, 1000
    for sp, x, y, z, land, ph, spd, fx0, fy0, a0 in clutter():
        k = e_out(prog(t, land - 0.55, 0.55))
        if k <= 0:
            continue
        drift = max(0.0, t - land)
        px_ = lerp(fx0, x, k) + math.sin(t * spd + ph) * 14 * z
        py_ = lerp(fy0, y, k) + math.cos(t * spd * 0.8 + ph) * 10 * z - drift * 5 * z
        scale = 0.9 * z * lerp(1.12, 1.0, k)
        op = (0.5 + 0.5 * z) * clamp(k * 3)
        blur = max(0.0, (1.0 - z) * 8)
        c = e_in3(clamp((t - COLLAPSE - (1 - z) * 0.15) / 0.55))
        if c > 0:
            px_, py_ = lerp(px_, cx, c), lerp(py_, cy, c)
            scale *= 1 - 0.88 * c
            op *= 1 - c ** 1.5
        place(cv, sp, px_, py_, sp.width / 2, sp.height / 2, scale, op, blur, cam)
    # headline over a soft scrim so it reads against the pile
    k = e_out(prog(t, HOOK_IN, 0.5))
    out = e_io(prog(t, HOOK_OUT, 0.25))
    op = k * (1 - out)
    if op <= 0:
        return
    sc = scrim()
    place(cv, sc, W / 2, 380, sc.width / 2, sc.height / 2, 1, op * 0.92)
    l1 = T("Sport in Dubai", "InterDisplay-SemiBold", 112, tracking=-0.03)
    put_text(cv, l1, W / 2, 330 + (1 - k) * 26 - out * 16, opacity=op, blur=(1 - k) * 6)
    l2 = T("is scattered.", "InterDisplay-SemiBold", 112, tracking=-0.03)
    x0 = W / 2 - l2.width / 2
    # three letters slip out of line, then settle back clearly
    nud = {4: (-3, -11, -5), 7: (2, 10, 4), 10: (4, -8, 6)}
    n = e_out(prog(t, NUDGE, 0.2)) * (1 - e_io(prog(t, NUDGE + 0.3, 0.5)))
    for i, c in enumerate("is scattered."):
        if c == " ":
            continue
        ch = T(c, "InterDisplay-SemiBold", 112, tracking=0)
        dx, dy, rot = nud.get(i, (0, 0, 0))
        img = ch.img
        if rot and n > 0.01:
            img = img.rotate(rot * n, Image.BICUBIC, center=(ch.bx + ch.width / 2, ch.by - ch.cap / 2))
        place(cv, img, x0 + l2.xs[i] + dx * n, 456 + (1 - k) * 26 - out * 16 + dy * n, ch.bx, ch.by - ch.cap / 2,
              1.0, op, (1 - k) * 6)

@lru_cache(None)
def scrim():
    im = Image.new("RGBA", (W + 200, 560), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((40, 60, W + 160, 500), fill=(6, 6, 8, 215))
    return im.filter(ImageFilter.GaussianBlur(60))

def logo_sprite():
    return asset("logo_full.png")

def put_logo(cv, x, y, width, op=1.0, blur=0.0, reveal=1.0, cam=NOCAM):
    """Real Athlo logo; 'reveal' wipes the wordmark in after the rings."""
    rings, word = asset("logo_rings.png"), asset("logo_word.png")
    s = width / (rings.width + word.width)
    lx = x - width / 2
    place(cv, rings, lx + rings.width * s / 2, y, rings.width / 2, rings.height / 2, s, op, blur, cam)
    if reveal > 0:
        place(cv, word, lx + rings.width * s + word.width * s / 2 - (1 - reveal) * 30, y, word.width / 2,
              word.height / 2, s, op * reveal, blur + (1 - reveal) * 8, cam)

def scene_app(cv, t):
    """Chaos collapses into the real Athlo logo, then the real app in one phone."""
    k = e_out(prog(t, MERGE - 0.05, 0.9))
    up = e_io(prog(t, LOGO_UP, 0.6))
    out = e_io(prog(t, APP_OUT, 0.26))
    y = lerp(900, 300, up)
    wdt = lerp(800, 470, up) * lerp(0.86, 1.0, k)
    lo = e_io(prog(t, APP_OUT, 0.2))
    put_logo(cv, W / 2, y - lo * 14, wdt, op=k * (1 - lo), blur=(1 - k) * 10,
             reveal=e_out(prog(t, MERGE + 0.3, 0.8)))
    pk = e_out(prog(t, LOGO_UP + 0.42, 0.85))
    if pk > 0:
        scroll = 600 * e_io(prog(t, LOGO_UP + 1.05, 1.0))
        ph = phone(real_app_screen(scroll))
        sc = 0.735
        cy = 1003   # phone spans ~489..1517: inside the safe area, nothing hidden at the bottom
        po = e_io(prog(t, APP_OUT - 0.07, 0.5))   # carousel: the Discover card pushes the phone out
        put_phone(cv, ph, W / 2 - po * 1000, cy + (1 - pk) * 520, scale=sc, opacity=min(1, pk * 1.4))

def scene_words(cv, t):
    cam = Cam(1.0 + 0.02 * e_sine(prog(t, WORDS[0], 12.5)), cy=900)
    for i, (word, fn) in enumerate(DETAILS):
        w0 = WORDS[i]
        w1 = WORDS[i + 1] if i < 4 else RECAP[0]
        lt = t - w0
        if t < (APP_OUT - 0.08 if i == 0 else w0 - 0.15) or t > w1:
            continue
        # word: lands on the beat; leaves completely before the next word appears
        k = e_out(prog(t, w0 - 0.08, 0.55))
        o = e_io(prog(t, w1 - 0.34, 0.24))
        grad = (ORANGE, PINK) if i == 4 else None
        tx = T(word, "InterDisplay-Bold", 168, tracking=-0.035, gradient=grad)
        put_text(cv, tx, W / 2, WORD_Y + (1 - k) * 46 - o * 26, opacity=k * (1 - o), blur=(1 - k) * 8,
                 scale=lerp(1.05, 1.0, k), cam=cam)
        # card: slides in from the right, out to the left
        ci = e_io(prog(t, APP_OUT - 0.07, 0.5)) if i == 0 else e_out(prog(t, w0 - 0.15, 0.75))
        co = e_in3(prog(t, w1 - 0.38, 0.36))
        card = fn(lt)
        cy = CARD_TOP + card.height / 2 + max(0, (900 - card.height) / 2 - 40)
        x = W / 2 + (1 - ci) * (1000 if i == 0 else 900) - co * 1000
        put_card(cv, card, x, cy, scale=1.0 if i == 0 else lerp(0.96, 1.0, ci),
                 opacity=1.0 if i == 0 else min(1, ci * 1.6) * (1 - co * 0.6), cam=cam)

def scene_recap(cv, t):
    words = ["Discover.", "Book.", "Play.", "Train.", "Compete."]
    lh = 150
    top = 960 - 2 * lh
    o = e_io(prog(t, RECAP_OUT, 0.18))
    for i, w in enumerate(words):
        k = e_out(prog(t, RECAP[i] - 0.04, 0.45))
        if k <= 0:
            continue  # upcoming words are never shown
        tx = T(w, "InterDisplay-Bold", 138, tracking=-0.035, gradient=(ORANGE, PINK) if i == 4 else None)
        put_text(cv, tx, W / 2, top + i * lh + (1 - k) * 36 - o * 20, opacity=k * (1 - o), blur=(1 - k) * 6)

def scene_end(cv, t):
    cam = Cam(1.0 + 0.025 * e_sine(prog(t, LOGO, 7.5)), cy=900)
    k = e_out(prog(t, RECAP_OUT + 0.12, 0.5))   # starts as the recap finishes clearing
    up = e_io(prog(t, LINE_OUT + 0.05, 0.6))
    put_logo(cv, W / 2, lerp(650, 360, up), lerp(780, 540, up) * lerp(0.9, 1, k), op=k, blur=(1 - k) * 10,
             reveal=e_out(prog(t, LOGO + 0.25, 0.8)), cam=cam)
    o = e_io(prog(t, LINE_OUT, 0.25))
    for j, ln in enumerate(["Your sports life,", "in one place."]):
        kk = e_out(prog(t, LINE + j * 0.12, 0.7))
        tx = T(ln, "InterDisplay-SemiBold", 86, tracking=-0.03)
        put_text(cv, tx, W / 2, 960 + j * 104 + (1 - kk) * 28 - o * 16, opacity=kk * (1 - o), blur=(1 - kk) * 6, cam=cam)
    # the call to action: the largest line in the film's ending
    for j, ln in enumerate(["Join the Dubai", "Fitness 30x30"]):
        kk = e_out(prog(t, CTA + j * 0.1, 0.75))
        tx = T(ln, "InterDisplay-Bold", 116, tracking=-0.035)
        put_text(cv, tx, W / 2, 660 + j * 134 + (1 - kk) * 30, opacity=kk, blur=(1 - kk) * 6, cam=cam)
    kw = e_out(prog(t, WHOOP, 0.7))
    tx = T("Win a Whoop for playing any sport.", "InterDisplay-Medium", 48, color=(222, 222, 228), tracking=-0.015)
    put_text(cv, tx, W / 2, 945 + (1 - kw) * 22, opacity=kw, blur=(1 - kw) * 5, cam=cam)
    kb = e_out(prog(t, BUTTON, 0.8))
    if kb > 0:
        b = link_button()
        pulse = 1 - 0.045 * math.sin(math.pi * prog(t, PULSE, 0.3))
        place(cv, b, W / 2, 1185 + (1 - kb) * 30, b.width / 2, b.height / 2, lerp(0.92, 1, kb) * pulse, kb, 0, cam)

@lru_cache(None)
def link_button():
    tx = T("Link in bio", "InterDisplay-SemiBold", 72, color=WHITE, tracking=-0.015)
    w, h = 760, 164
    ss = 3
    g = np.linspace(0, 1, w * ss)[None, :, None]
    rgb = (np.array(ORANGE)[None, None] * (1 - g) + np.array(PINK)[None, None] * g) * np.ones((h * ss, 1, 1))
    im = Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), h * ss // 2, fill=255)
    im.putalpha(m)
    im = pad_img(im.resize((w, h), Image.LANCZOS), 60)
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((60, 80, 60 + w, 60 + h + 10), h // 2, fill=(255, 60, 90, 120))
    out = glow.filter(ImageFilter.GaussianBlur(26))
    out.alpha_composite(im)
    ax = tx.bx + tx.width / 2; ay = tx.by - tx.cap / 2
    out.alpha_composite(tx.img, (int(round(out.width / 2 - ax)), int(round(out.height / 2 - ay))))
    return out

# ------------------------------------------------------------------ background

def scene_glows(t):
    """Soft orange-to-pink light, always on: there are no dark gaps."""
    dr = lambda f, a: math.sin(t * f) * a
    base = 0.17 + 0.05 * e_sine(prog(t, 0, 4))
    bl = [(300 + dr(0.35, 70), 820 + dr(0.27, 90), 460, ORANGE, base),
          (790 + dr(0.3, 70), 1320 + dr(0.22, 90), 480, PINK, base * 1.05)]
    burst = 0.0
    if t > MERGE - 0.2:
        burst = math.exp(-max(0, t - MERGE) * 2.6) * prog(t, MERGE - 0.2, 0.2)
    bl.append((540, 950, 240 + 320 * burst, (255, 120, 80), 0.85 * burst))
    if t >= LOGO - 0.4:
        lb = math.exp(-max(0, t - LOGO + 0.3) * 2.2) * prog(t, RECAP_OUT, 0.2)
        bl.append((540, 650, 260 + 220 * lb, (255, 120, 80), 0.6 * lb))
        e = 0.12 * e_sine(prog(t, LOGO - 0.4, 1.2))
        bl += [(380, 700, 330, ORANGE, e), (720, 760, 340, PINK, e), (540, 1190, 380, (255, 70, 90), e * 0.8)]
    return bl

# ------------------------------------------------------------------ frame

def render(i):
    t = i / FPS
    bg = glow_field(scene_glows(t))
    cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if t < MERGE + 0.2:
        scene_hook(cv, t)
    if MERGE - 0.1 <= t < WORDS[0]:
        scene_app(cv, t)
    if APP_OUT - 0.1 <= t < RECAP[0] + 0.05:
        scene_words(cv, t)
    if RECAP[0] - 0.1 <= t < LOGO:
        scene_recap(cv, t)
    if t >= RECAP_OUT + 0.1:
        scene_end(cv, t)
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
