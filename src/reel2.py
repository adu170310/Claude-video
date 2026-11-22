#!/usr/bin/env python3
"""Reel 2 "spot the Athlo team": 14 s, 1080x1920, 30 fps, loops.

Footage is read from work/footage and work/r2 (never committed).
Writes work/r2/picture.mp4, then audio + final muxes are done by reel2_audio.py.
"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT = os.path.join(ROOT, "work", "footage")
R2 = os.path.join(ROOT, "work", "r2")
W, H, FPS, DUR = 1080, 1920, 30, 14.0
N = int(DUR * FPS)
ORANGE, PINK = (0xEB, 0x57, 0x17), (0xF0, 0x2E, 0x7A)
FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

# ---------------------------------------------------------------- helpers
def ease(x):  # easeInOutCubic
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2

def back_out(x, k=2.2):
    x = min(max(x, 0.0), 1.0)
    return 1 + (k + 1) * (x - 1) ** 3 + k * (x - 1) ** 2

def gradient(w, h, horizontal=True):
    t = np.linspace(0, 1, w if horizontal else h)
    cols = np.array(ORANGE)[None] * (1 - t[:, None]) + np.array(PINK)[None] * t[:, None]
    if horizontal:
        arr = np.broadcast_to(cols[None], (h, w, 3))
    else:
        arr = np.broadcast_to(cols[:, None], (h, w, 3))
    return Image.fromarray(arr.astype(np.uint8), "RGB")

def cover_blur(src, dark=0.55):
    s = max(W / src.width, H / src.height)
    im = src.resize((math.ceil(src.width * s), math.ceil(src.height * s)), Image.BILINEAR)
    x0, y0 = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x0, y0, x0 + W, y0 + H)).filter(ImageFilter.GaussianBlur(40))
    return Image.blend(Image.new("RGB", (W, H)), im, dark)

def view(src, bg, cx, cy, s):
    """Render source centred on (cx, cy) at scale s (output px per source px) over bg."""
    out = bg.copy()
    x0, y0 = cx - W / (2 * s), cy - H / (2 * s)           # source coords of output (0,0)
    sx0, sy0 = max(0.0, x0), max(0.0, y0)
    sx1, sy1 = min(src.width, x0 + W / s), min(src.height, y0 + H / s)
    ox0, oy0 = round((sx0 - x0) * s), round((sy0 - y0) * s)
    ox1, oy1 = round((sx1 - x0) * s), round((sy1 - y0) * s)
    if ox1 > ox0 and oy1 > oy0:
        tile = src.resize((ox1 - ox0, oy1 - oy0), Image.LANCZOS, box=(sx0, sy0, sx1, sy1),
                          reducing_gap=2.0)
        out.paste(tile, (ox0, oy0))
    return out

def clamp_cover(src, cx, cy, s):
    hw, hh = W / (2 * s), H / (2 * s)
    return min(max(cx, hw), src.width - hw), min(max(cy, hh), src.height - hh)

# ---------------------------------------------------------------- text
_fonts = {}
def font(sz):
    if sz not in _fonts:
        _fonts[sz] = ImageFont.truetype(FONT, sz)
    return _fonts[sz]

_emo = ImageFont.truetype(EMOJI, 109)
def emoji_img(ch, h):
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=_emo, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)

def is_emoji(ch):
    return ord(ch) > 0x2000 and ch not in "’‘"

def caption(text, size=106, stroke=12):
    """Bold white text with thick black stroke; colour emoji inline."""
    parts, buf = [], ""
    for ch in text:
        if is_emoji(ch):
            if buf: parts.append(("t", buf)); buf = ""
            parts.append(("e", ch))
        elif ch == "️":
            continue
        else:
            buf += ch
    if buf: parts.append(("t", buf))
    f = font(size)
    asc, desc = f.getmetrics()
    lh = asc + desc + 2 * stroke
    imgs = []
    for kind, v in parts:
        if kind == "t":
            w = math.ceil(f.getlength(v)) + 2 * stroke
            im = Image.new("RGBA", (w, lh), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((stroke, stroke), v, font=f, fill="white",
                                    stroke_width=stroke, stroke_fill="black")
            imgs.append(im)
        else:
            e = emoji_img(v, int(size * 1.05))
            im = Image.new("RGBA", (e.width + 10, lh), (0, 0, 0, 0))
            im.alpha_composite(e, (5, (lh - e.height) // 2 + 2))
            imgs.append(im)
    tw = sum(i.width for i in imgs) - stroke * (len(imgs) - 1)
    out = Image.new("RGBA", (tw, lh), (0, 0, 0, 0)); x = 0
    for i in imgs:
        out.alpha_composite(i, (x, 0)); x += i.width - stroke
    if out.width > W - 80:
        r = (W - 80) / out.width
        out = out.resize((W - 80, round(out.height * r)), Image.LANCZOS)
    return out

def place(frame, img, cy, alpha=1.0, scale=1.0, cx=W // 2):
    if alpha <= 0: return
    scale = min(scale, max(1.0, (W - 40) / img.width))     # never pop past the frame edges
    if scale != 1.0:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    if alpha < 1.0:
        a = img.getchannel("A").point(lambda v: int(v * alpha)); img = img.copy(); img.putalpha(a)
    frame.alpha_composite(img, (round(cx - img.width / 2), round(cy - img.height / 2)))

_digits = {}
def digit(d):
    if d not in _digits:
        f = font(300); st = 14
        bb = f.getbbox(str(d))
        w, h = bb[2] - bb[0] + 2 * st + 8, bb[3] - bb[1] + 2 * st + 8
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).text((st + 4 - bb[0], st + 4 - bb[1]), str(d), font=f, fill=255)
        outline = Image.new("L", (w, h), 0)
        ImageDraw.Draw(outline).text((st + 4 - bb[0], st + 4 - bb[1]), str(d), font=f, fill=255,
                                     stroke_width=st, stroke_fill=255)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        im.paste((0, 0, 0, 255), (0, 0), outline)
        g = gradient(w, h, horizontal=False).convert("RGBA")
        im.paste(g, (0, 0), m)
        _digits[d] = im
    return _digits[d]

def ring(frame, cx, cy, rx, ry, t):
    """Orange->pink ring that pops in over 0.3 s (t = seconds since pop)."""
    if t < 0: return
    k = back_out(t / 0.3)
    a = min(1.0, t / 0.08)
    rx, ry = rx * (0.55 + 0.45 * k), ry * (0.55 + 0.45 * k)
    pad = 30
    bw, bh = int(2 * rx + 2 * pad), int(2 * ry + 2 * pad)
    if bw < 10 or bh < 10: return
    box = (pad, pad, bw - pad, bh - pad)
    m_outer = Image.new("L", (bw, bh), 0); ImageDraw.Draw(m_outer).ellipse(box, outline=255, width=26)
    m_inner = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(m_inner).ellipse((pad + 5, pad + 5, bw - pad - 5, bh - pad - 5), outline=255, width=16)
    sh = m_outer.filter(ImageFilter.GaussianBlur(6))
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    im.paste((0, 0, 0, 255), (0, 0), sh.point(lambda v: int(v * 0.9)))
    im.paste(gradient(bw, bh).convert("RGBA"), (0, 0), m_inner)
    if a < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    frame.alpha_composite(im, (round(cx - bw / 2), round(cy - bh / 2)))

# ---------------------------------------------------------------- sources
def load(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")

S_R1 = load(os.path.join(R2, "IMG_2687.png"))                          # 4284x5712
S_R2 = load(os.path.join(FT, "399c0a0d-f640-4805-bff4-35fc4512ce22.JPG"))  # 1600x1200
S_R3 = load(os.path.join(FT, "IMG_6396.JPG"))                          # 4032x3024
S_END = load(os.path.join(FT, "6567ddd7-d28d-4bd1-87dc-9b9df440f402.jpg"))  # 1200x1600
REV = sorted(os.listdir(os.path.join(R2, "f2690")))

# rounds: (source, t_start, digit times, zoom start, zoom end, target (cx,cy,s), ring (cx,cy,rx,ry) in source px)
ROUNDS = [
    dict(src=S_R1, t0=1.0, t1=4.0, digits=(1.0, 1.6, 2.2), z0=2.2, z1=2.9,
         tgt=(2150, 3150, 0.47), ring=(2230, 2900, 820, 640)),
    dict(src=S_R2, t0=4.0, t1=7.0, digits=(4.0, 4.45, 4.9), z0=4.9, z1=5.45,
         tgt=(875, 700, 1.6), ring=(875, 700, 330, 420)),
    dict(src=S_R3, t0=7.0, t1=10.0, digits=(7.0, 7.4, 7.8), z0=7.8, z1=8.4,
         tgt=(1640, 2000, 1.0), ring=(1630, 1880, 360, 560)),
]
for r in ROUNDS:
    src = r["src"]
    r["bg"] = cover_blur(src)
    r["s0"] = W / src.width                     # whole photo visible: we look tiny
    r["c0"] = (src.width / 2, src.height / 2)
    cx, cy, s = r["tgt"]
    r["c1"] = clamp_cover(src, cx, cy, s)
    r["ring_pop"] = r["z1"] - 0.05

HOOK_BG = Image.blend(Image.new("RGB", (W, H)),
                      view(S_R1, ROUNDS[0]["bg"], *ROUNDS[0]["c0"], ROUNDS[0]["s0"])
                      .filter(ImageFilter.GaussianBlur(14)), 0.8)

CAP = {k: caption(k) for k in [
    "find the Athlo team 👀", "in 3 seconds", "harder.", "impossible level 💀",
    "ok, you can't", "miss us now", "how many did you get? 👇"]}
CAP_Y = 470          # upper third, clear of IG top bar
DIG_C = (905, 255)   # countdown top-right

# reveal clip: subject centre x per second (from frame checks) for a following crop
REV_X = [(0.0, 810), (0.5, 705), (1.0, 615), (1.5, 600), (2.0, 675), (2.3, 690)]
def rev_x(tt):
    xs = np.array([p[0] for p in REV_X]); vs = np.array([p[1] for p in REV_X])
    return float(np.interp(tt, xs, vs))

def round_frame(r, t):
    src = r["src"]
    k = ease((t - r["z0"]) / (r["z1"] - r["z0"]))
    s = math.exp(math.log(r["s0"]) * (1 - k) + math.log(r["tgt"][2]) * k)
    cx = r["c0"][0] * (1 - k) + r["c1"][0] * k
    cy = r["c0"][1] * (1 - k) + r["c1"][1] * k
    # keep the zoomed view inside the photo once it's big enough to fill
    if s * src.height >= H and s * src.width >= W:
        cx, cy = clamp_cover(src, cx, cy, s)
    fr = view(src, r["bg"], cx, cy, s).convert("RGBA")
    # ring in output coords (follows camera)
    rcx, rcy, rrx, rry = r["ring"]
    ox, oy = (rcx - cx) * s + W / 2, (rcy - cy) * s + H / 2
    ring(fr, ox, oy, rrx * s, rry * s, t - r["ring_pop"])
    # countdown: each digit pops in; "1" stays until the ring lands
    for i, td in enumerate(r["digits"]):
        nxt = r["digits"][i + 1] if i < 2 else r["ring_pop"]
        if td <= t < nxt:
            u = t - td
            place(fr, digit(3 - i), DIG_C[1], cx=DIG_C[0], scale=1.0 + 0.35 * (1 - back_out(u / 0.22)),
                  alpha=min(1, u / 0.06))
    return fr

def frame_at(i):
    t = i / FPS
    if t < 1.0:                                                     # hook
        fr = HOOK_BG.convert("RGBA")
        place(fr, digit(3), DIG_C[1], cx=DIG_C[0])
        if t < 0.5:
            place(fr, CAP["find the Athlo team 👀"], CAP_Y)
        else:
            place(fr, CAP["in 3 seconds"], CAP_Y, scale=1.0 + 0.25 * (1 - back_out((t - 0.5) / 0.18)))
        return fr
    for r in ROUNDS:
        if r["t0"] <= t < r["t1"]:
            fr = round_frame(r, t)
            if r is ROUNDS[1]: place(fr, CAP["harder."], CAP_Y, scale=1.0 + 0.3 * (1 - back_out((t - 4.0) / 0.2)))
            if r is ROUNDS[2]: place(fr, CAP["impossible level 💀"], CAP_Y, scale=1.0 + 0.3 * (1 - back_out((t - 7.0) / 0.2)))
            return fr
    if t < 12.5:                                                    # reveal (stand-in clip)
        tt = (t - 10.0) / 2.5 * 2.3
        idx = min(len(REV) - 1, int(tt / 2.3 * len(REV)))
        im = Image.open(os.path.join(R2, "f2690", REV[idx])).convert("RGB")
        x = min(max(rev_x(tt), 540), im.width - 540)
        fr = im.crop((round(x - 540), 0, round(x - 540) + W, H)).convert("RGBA")
        if t < 11.1: place(fr, CAP["ok, you can't"], CAP_Y)
        else: place(fr, CAP["miss us now"], CAP_Y)
        return fr
    # end card 12.5-14 + loop back into the hook look
    u = (t - 12.5) / 1.5
    s = 1.2 * (1 + 0.04 * u)
    cx, cy = clamp_cover(S_END, 610, 820, s)
    fr = view(S_END, HOOK_BG, cx, cy, s)
    if t >= 13.55:                                                  # dissolve to opening frame
        k = ease((t - 13.55) / (13.967 - 13.55))
        fr = Image.blend(fr.filter(ImageFilter.GaussianBlur(28 * k)), HOOK_BG, k)
    fr = fr.convert("RGBA")
    if t < 13.75:
        place(fr, CAP["how many did you get? 👇"], CAP_Y, alpha=min(1, (13.75 - t) / 0.15))
    if t >= 13.75:
        place(fr, CAP["find the Athlo team 👀"], CAP_Y, alpha=ease((t - 13.75) / 0.2))
        place(fr, digit(3), DIG_C[1], cx=DIG_C[0], alpha=ease((t - 13.75) / 0.2))
    return fr

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--still":
        os.makedirs(os.path.join(R2, "stills"), exist_ok=True)
        for ts in sys.argv[2].split(","):
            i = round(float(ts) * FPS)
            frame_at(i).convert("RGB").save(os.path.join(R2, "stills", f"t{float(ts):05.2f}.jpg"), quality=88)
        sys.exit()
    out = os.path.join(R2, "picture.mp4")
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-profile:v", "high",
                          "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                          "-colorspace", "bt709", "-g", "15", out], stdin=subprocess.PIPE)
    for i in range(N):
        p.stdin.write(frame_at(i).convert("RGB").tobytes())
        if i % 60 == 0: print(f"{i}/{N}", flush=True)
    p.stdin.close(); p.wait()
    print("wrote", out)
