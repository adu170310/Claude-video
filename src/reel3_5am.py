#!/usr/bin/env python3
"""Reel 3 "was 5am worth it?": 14 s, 1080x1920, 30 fps, loops.

Viral format: a question hook on a half-asleep teammate, real capture-time stamps (from each file's
metadata) escalating through the morning, and the answer landing on the drop at golden hour.
Hard cuts on a 120 BPM grid. Footage is read from git-ignored work/. Writes work/r3/picture.mp4.

Usage: reel3_5am.py [--still t1,t2,...]
"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import pillow_heif; pillow_heif.register_heif_opener()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work"); FT = os.path.join(WK, "footage"); R3 = os.path.join(WK, "r3")
W, H, FPS, DUR = 1080, 1920, 30, 14.0
N = int(DUR * FPS)
ORANGE, PINK = (0xEB, 0x57, 0x17), (0xF0, 0x2E, 0x7A)
FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

def load(name, max_side=2400):
    im = ImageOps.exif_transpose(Image.open(os.path.join(FT, name))).convert("RGB")
    if max(im.size) > max_side:                       # plenty for a 1080 frame with a 6 % push
        r = max_side / max(im.size); im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    return im

# ---------------------------------------------------------------- grade (Reel 1 match: natural, a touch warm)
def _lut():
    x = np.arange(256) / 255.0
    s = np.clip(x - 0.035 * np.sin(2 * np.pi * x), 0, 1)
    r, g, b = np.clip(s * 1.03 + 0.006, 0, 1), np.clip(s + 0.002, 0, 1), np.clip(s * 0.96 + 0.006, 0, 1)
    return [int(round(v * 255)) for v in np.concatenate([r, g, b])]
LUT = _lut()
def grade(im):
    a = np.asarray(im.point(LUT)).astype(np.float32); l = a.mean(axis=2, keepdims=True)
    return Image.fromarray(np.clip(l + (a - l) * 1.08, 0, 255).astype(np.uint8))

# ---------------------------------------------------------------- framing
def cover(src, cx, cy, s):
    hw, hh = W / (2 * s), H / (2 * s)
    cx = min(max(cx, hw), src.width - hw); cy = min(max(cy, hh), src.height - hh)
    return src.resize((W, H), Image.LANCZOS, box=(cx - hw, cy - hh, cx + hw, cy + hh))

def push(name, fx=0.5, fy=0.5, zoom=1.0, max_side=2400):
    """Full-bleed photo, focus at (fx, fy) of the frame, gentle 100 -> 106 % push."""
    src = load(name, max_side); s0 = max(W / src.width, H / src.height) * zoom
    return lambda u: cover(src, src.width * fx, src.height * fy, s0 * (1 + 0.06 * u))

def inset(name):
    src = load(name)
    s = max(W / src.width, H / src.height)
    bg = src.resize((math.ceil(src.width * s), math.ceil(src.height * s)), Image.BILINEAR)
    x0, y0 = (bg.width - W) // 2, (bg.height - H) // 2
    bg = Image.blend(Image.new("RGB", (W, H)), bg.crop((x0, y0, x0 + W, y0 + H)).filter(ImageFilter.GaussianBlur(45)), 0.55)
    def f(u):
        k = 0.94 + 0.06 * u                                    # never above native size
        im = src.resize((round(src.width * k), round(src.height * k)), Image.LANCZOS)
        out = bg.copy(); out.paste(im, ((W - im.width) // 2, (H - im.height) // 2)); return out
    return f

def clip(tag):
    d = os.path.join(R3, "clips", tag); fs = sorted(os.listdir(d))
    return lambda u: Image.open(os.path.join(d, fs[min(len(fs) - 1, int(u * len(fs)))])).convert("RGB")

# ---------------------------------------------------------------- text
_emo = ImageFont.truetype(EMOJI, 109)
def emoji_img(ch, h):
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=_emo, embedded_color=True)
    im = im.crop(im.getbbox()); return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)

def caption(text, size=92, stroke=11):
    """House style: bold white, thick black stroke, colour emoji inline."""
    f = ImageFont.truetype(FONT, size); asc, desc = f.getmetrics(); lh = asc + desc + 2 * stroke
    parts, buf = [], ""
    for ch in text:
        if ord(ch) > 0x2000 and ch not in "’‘…": (parts.append(("t", buf)) if buf else None, parts.append(("e", ch))); buf = ""
        elif ch != "️": buf += ch
    if buf: parts.append(("t", buf))
    imgs = []
    for k, v in parts:
        if k == "t":
            im = Image.new("RGBA", (math.ceil(f.getlength(v)) + 2 * stroke, lh), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((stroke, stroke), v, font=f, fill="white", stroke_width=stroke, stroke_fill="black")
        else:
            e = emoji_img(v, int(size * 1.0)); im = Image.new("RGBA", (e.width + 12, lh), (0, 0, 0, 0))
            im.alpha_composite(e, (6, (lh - e.height) // 2 + 2))
        imgs.append(im)
    out = Image.new("RGBA", (sum(i.width for i in imgs) - stroke * (len(imgs) - 1), lh), (0, 0, 0, 0)); x = 0
    for i in imgs: out.alpha_composite(i, (x, 0)); x += i.width - stroke
    if out.width > W - 80:
        r = (W - 80) / out.width; out = out.resize((W - 80, round(out.height * r)), Image.LANCZOS)
    return out

def stamp(text):
    """Capture-time pill: brand orange -> pink, white bold time."""
    f = ImageFont.truetype(FONT, 50)
    tw = math.ceil(f.getlength(text)); w, h = tw + 64, 84
    t = np.linspace(0, 1, w)[None, :, None]
    g = (np.array(ORANGE) * (1 - t) + np.array(PINK) * t) * np.ones((h, 1, 1))
    pill = Image.fromarray(g.astype(np.uint8)).convert("RGBA")
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=255)
    pill.putalpha(m)
    ImageDraw.Draw(pill).text((32, h / 2), text, font=f, fill="white", anchor="lm")
    out = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0)); sh.putalpha(Image.new("L", out.size, 0))
    shm = Image.new("L", out.size, 0); ImageDraw.Draw(shm).rounded_rectangle((20, 26, w + 19, h + 25), radius=h // 2, fill=140)
    out.paste((0, 0, 0, 255), (0, 0), shm.filter(ImageFilter.GaussianBlur(10)))
    out.alpha_composite(pill, (20, 20))
    return out

def fade(img, a):
    if a >= 1: return img
    img = img.copy(); img.putalpha(img.getchannel("A").point(lambda v: int(v * max(0.0, a)))); return img

def pop(img, u):
    """Caption entrance: 0.12 s scale 1.18 -> 1.0 with fade (snappy, not bouncy)."""
    if u >= 1: return img
    s = 1 + 0.18 * (1 - u) ** 2
    return fade(img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS), min(1, u * 2))

# ---------------------------------------------------------------- the cut (120 BPM: 0.5 s beats, drop at 10.0)
SHOTS = [  # start, end, render, capture time (from metadata), caption
    (0.00, 1.50, push("IMG_2673.HEIC", 0.40, 0.42), "5:48 AM", "was 5am worth it?"),
    (1.50, 2.50, clip("2675"), "6:06 AM", "the metro was packed"),
    (2.50, 3.25, clip("2678"), "6:12 AM", "like… PACKED"),
    (3.25, 4.25, clip("2679"), "6:13 AM", "thousands of people. 6am."),
    (4.25, 5.25, push("IMG_6396.JPG", 0.67, 0.55), "6:28 AM", "kings showed up 👑"),
    (5.25, 6.25, inset("2b7b453a-c09c-48d3-887a-4082d7fd27ea.jpg"), None, "and… jellyfish??"),
    (6.25, 7.25, clip("2680"), "6:36 AM", "we actually ran"),
    (7.25, 8.25, push("IMG_2681.HEIC", 0.39, 0.53, zoom=1.7, max_side=6000), "6:44 AM", "people were FLYING"),
    (8.25, 9.00, push("IMG_2687.HEIC", 0.50, 0.55), "7:15 AM", "finished. somehow."),
    (9.00, 10.00, push("IMG_2693.HEIC", 0.50, 0.60), "7:15 AM", None),
    (10.00, 12.25, push("IMG_2698.HEIC", 0.45, 0.50), "7:19 AM", "worth it? yeah."),
    (12.25, 14.00, push("IMG_2700.HEIC", 0.64, 0.50), "7:20 AM", "every single minute 🧡"),
]
CUT_F = [round(s[0] * FPS) for s in SHOTS] + [N]
CAPS = {s[4]: caption(s[4]) for s in SHOTS if s[4]}
STAMPS = {s[3]: stamp(s[3]) for s in SHOTS if s[3]}
CAP_Y, STAMP_Y = 470, 300

def frame_at(i):
    t = i / FPS
    k = max(j for j in range(len(SHOTS)) if CUT_F[j] <= i)
    t0, t1, fn, ts, cap = SHOTS[k]
    u = (i - CUT_F[k]) / max(1, CUT_F[k + 1] - CUT_F[k] - 1)
    fr = grade(fn(u)).convert("RGBA")
    e = (i - CUT_F[k]) / (0.12 * FPS) if k > 0 else 1.0           # frame 1 (thumbnail) fully drawn
    if ts:
        st = STAMPS[ts]; fr.alpha_composite(fade(st, e * 2), ((W - st.width) // 2, STAMP_Y - st.height // 2))
    if cap:
        c = pop(CAPS[cap], e); fr.alpha_composite(c, ((W - c.width) // 2, CAP_Y - c.height // 2))
    return fr.convert("RGB")

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--still":
        os.makedirs(os.path.join(R3, "stills"), exist_ok=True)
        for ts in sys.argv[2].split(","):
            frame_at(round(float(ts) * FPS)).save(os.path.join(R3, "stills", f"t{float(ts):05.2f}.jpg"), quality=88)
        sys.exit()
    out = os.path.join(R3, "picture.mp4")
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                          "-profile:v", "high", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                          "-colorspace", "bt709", "-g", "15", out], stdin=subprocess.PIPE)
    for i in range(N):
        p.stdin.write(frame_at(i).tobytes())
    p.stdin.close(); p.wait(); print("wrote", out, N, "frames")
