#!/usr/bin/env python3
"""Reel 2 (new) "every type of person at Dubai Run": 14.5 s, 1080x1920, 30 fps.

Deadpan list format: hard cuts on a 100 BPM grid (beats at 0.3 + 0.6k s), one small numbered label
per shot in the upper third (white, no stroke, soft shadow), warm grade, "athlo." in the last second.
Footage is read from work/ (git-ignored). Writes work/r2t/picture.mp4; audio via reel2_types_audio.py.

Usage: reel2_types.py [--still t1,t2,...]
"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT = os.path.join(ROOT, "work", "footage")
WK = os.path.join(ROOT, "work", "r2t"); os.makedirs(WK, exist_ok=True)
CLIP2690 = os.path.join(ROOT, "work", "r2", "f2690")           # frames of IMG_2690.MOV (stand-in)
W, H, FPS, DUR = 1080, 1920, 30, 14.5
N = int(round(DUR * FPS))
ORANGE = (0xEB, 0x57, 0x17)
F_LABEL = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

def load(name):
    return ImageOps.exif_transpose(Image.open(os.path.join(FT, name))).convert("RGB")

# ---------------------------------------------------------------- grade
def warm_lut():
    x = np.arange(256) / 255.0
    s = x + 0.06 * np.sin(2 * np.pi * x) * -1           # gentle S-curve (more contrast)
    s = np.clip(s, 0, 1)
    r = np.clip(s * 1.05 + 0.012, 0, 1)                 # warmer highlights
    g = np.clip(s * 1.00 + 0.004, 0, 1)
    b = np.clip(s * 0.92 + 0.010, 0, 1)                 # pull blue, keep a touch of lift in blacks
    return [int(round(v * 255)) for v in np.concatenate([r, g, b])]
LUT = warm_lut()

def grade(im):
    im = im.point(LUT)
    # mild saturation boost
    a = np.asarray(im).astype(np.float32)
    l = a.mean(axis=2, keepdims=True)
    a = np.clip(l + (a - l) * 1.06, 0, 255)
    return Image.fromarray(a.astype(np.uint8))

# ---------------------------------------------------------------- framing
def cover(src, cx, cy, s):
    """Full-bleed view centred on (cx, cy) at scale s (output px per source px)."""
    hw, hh = W / (2 * s), H / (2 * s)
    cx = min(max(cx, hw), src.width - hw); cy = min(max(cy, hh), src.height - hh)
    return src.resize((W, H), Image.LANCZOS, box=(cx - hw, cy - hh, cx + hw, cy + hh))

def blur_bg(src):
    s = max(W / src.width, H / src.height)
    im = src.resize((math.ceil(src.width * s), math.ceil(src.height * s)), Image.BILINEAR)
    x0, y0 = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x0, y0, x0 + W, y0 + H)).filter(ImageFilter.GaussianBlur(45))
    return Image.blend(Image.new("RGB", (W, H)), im, 0.55)

def inset(src):
    """Source is narrower than 1080: show it at native size (no upscaling) on its own blurred fill."""
    out = blur_bg(src)
    sh = Image.new("L", (W, H), 0)
    x0, y0 = (W - src.width) // 2, (H - src.height) // 2
    ImageDraw.Draw(sh).rectangle((x0, y0 + 10, x0 + src.width, y0 + src.height + 10), fill=150)
    out.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(22)))
    out.paste(src, (x0, y0))
    return out

# ---------------------------------------------------------------- labels
def shadowed(lines, size, font=F_LABEL, lead=1.18, extra=None):
    f = ImageFont.truetype(font, size)
    asc, desc = f.getmetrics(); lh = int(size * lead)
    w = max(math.ceil(f.getlength(l)) for l in lines) + 60
    h = lh * len(lines) + desc + 60
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
    for i, l in enumerate(lines):
        d.text((30, 30 + i * lh), l, font=f, fill="white")
    if extra: extra(d, f)
    a = txt.getchannel("A")
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(6)).point(lambda v: min(255, int(v * 0.75))))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 3)); out.alpha_composite(txt)
    return out

def wrap(text, size, maxw=900, font=F_LABEL):
    if "\n" in text:
        return text.split("\n")
    f = ImageFont.truetype(font, size); words = text.split(); lines = [""]
    for wd in words:
        t = (lines[-1] + " " + wd).strip()
        if f.getlength(t) <= maxw: lines[-1] = t
        else: lines.append(wd)
    return lines

LX, LY = 60, 300
_g = np.clip(1 - np.arange(H) / 760.0, 0, 1) ** 1.6 * 0.42 * 255     # soft top scrim for legibility
SCRIM = Image.new("RGBA", (W, H), (0, 0, 0, 0))
SCRIM.putalpha(Image.fromarray(np.repeat(_g[:, None], W, axis=1).astype(np.uint8)))          # top-left of label block (upper third, clear of IG's top bar)

def label(text, size=56):
    return shadowed(wrap(text, size), size)

def wordmark():
    f = ImageFont.truetype(F_BOLD, 46)
    def dot(d, f):
        d.text((30 + f.getlength("athlo"), 30), ".", font=f, fill=ORANGE)
    return shadowed(["athlo"], 46, font=F_BOLD, extra=dot)

# ---------------------------------------------------------------- shots
S_SMOKE = load("5ad9f8c7-ee3f-4e22-8d4a-e0813f4b1bef.jpg")   # stand-in for IMG_2682.MOV
S_COST = load("IMG_6396.JPG")
S_JELLY = load("2b7b453a-c09c-48d3-887a-4082d7fd27ea.jpg")
S_KNEEL = load("1170fedb-6d7e-405d-923b-689d7a3e3bb6.jpg")
S_CURL = load("29e42714-a3c1-40f6-bc19-751afc337979.jpg")
S_FAM = load("fa750c1f-380b-4a21-8027-be2eb67daa92.jpg")
REV = sorted(os.listdir(CLIP2690))

def still(src, cx, cy, s, drift=0.025):
    """Full-bleed still with a barely-there drift so it doesn't feel frozen (no zoom gimmick)."""
    return lambda u: cover(src, cx, cy, s * (1 + drift * u))

SHOTS = [  # (t0, t1, render(u in 0..1), label)
    (0.0, 1.5, still(S_SMOKE, 600, 800, 1.2), "every type of person\nat Dubai Run"),
    (1.5, 3.3, still(S_COST, 2700, 1650, 0.635 * 1.12), "1. came in full costume.\ndidn't run."),
    (3.3, 5.1, (lambda im: (lambda u: im))(inset(S_JELLY)), "2. the jellyfish committee"),
    (5.1, 6.9, still(S_SMOKE, 840, 1020, 1.55), "3. watched the whole thing\nthrough their phone"),
    (6.9, 8.7, still(S_KNEEL, 640, 820, 1.2), "4. stopped for a photo\nevery 200m"),
    (8.7, 10.5, (lambda im: (lambda u: im))(inset(S_CURL)), "5. here for the aesthetic"),
    (10.5, 12.3, (lambda im: (lambda u: im))(inset(S_FAM)), "6. made it a family day out"),
    (12.3, 14.5, None, "7. actually ran it."),
]
LABELS = {s[3]: label(s[3], 64 if i == 0 else 56) for i, s in enumerate(SHOTS)}
US = shadowed(["(us.)"], 56)
WM = wordmark()

REV_X = [(0.0, 810), (0.5, 705), (1.0, 615), (1.5, 600), (2.0, 675), (2.3, 690)]
def clip_frame(u, dur):
    tt = u * 2.3
    idx = min(len(REV) - 1, int(u * len(REV)))
    im = Image.open(os.path.join(CLIP2690, REV[idx])).convert("RGB")
    x = float(np.interp(tt, [p[0] for p in REV_X], [p[1] for p in REV_X]))
    x = min(max(x, 540), im.width - 540)
    return im.crop((round(x - 540), 0, round(x - 540) + W, H))

def frame_at(i):
    t = i / FPS
    for k, (t0, t1, fn, text) in enumerate(SHOTS):
        if t0 <= t < t1 or k == len(SHOTS) - 1:
            u = (t - t0) / (t1 - t0)
            im = clip_frame(u, t1 - t0) if fn is None else fn(u)
            fr = grade(im).convert("RGBA")
            fr.alpha_composite(SCRIM)
            a = 1.0 if t0 == 0 else min(1.0, (t - t0) / 0.1)   # 3-frame settle; frame 1 (thumbnail) fully lit
            lab = LABELS[text]
            if a < 1:
                lab = lab.copy(); lab.putalpha(lab.getchannel("A").point(lambda v: int(v * a)))
            fr.alpha_composite(lab, (LX - 30, LY - 30))
            if k == len(SHOTS) - 1 and t >= 12.9:         # "(us.)" after a 0.5 s hold, on the beat
                b = min(1.0, (t - 12.9) / 0.1)
                us = US.copy(); us.putalpha(us.getchannel("A").point(lambda v: int(v * b)))
                fr.alpha_composite(us, (LX - 30, LY - 30 + lab.height - 46))
            if t >= DUR - 1.0:                              # small wordmark, last second
                b = min(1.0, (t - (DUR - 1.0)) / 0.2)
                wm = WM.copy(); wm.putalpha(wm.getchannel("A").point(lambda v: int(v * b)))
                fr.alpha_composite(wm, (W - wm.width - 34, H - 170 - wm.height))
            return fr.convert("RGB")

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--still":
        os.makedirs(os.path.join(WK, "stills"), exist_ok=True)
        for ts in sys.argv[2].split(","):
            frame_at(round(float(ts) * FPS)).save(os.path.join(WK, "stills", f"t{float(ts):05.2f}.jpg"), quality=88)
        sys.exit()
    out = os.path.join(WK, "picture.mp4")
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-profile:v", "high",
                          "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                          "-colorspace", "bt709", "-g", "15", out], stdin=subprocess.PIPE)
    for i in range(N):
        p.stdin.write(frame_at(i).tobytes())
    p.stdin.close(); p.wait()
    print("wrote", out, N, "frames")
