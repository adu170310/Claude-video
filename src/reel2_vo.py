#!/usr/bin/env python3
"""Reel 2 with voiceover: "every type of person at Dubai Run".

Every cut, label and subtitle is timed off the VO (word timestamps from faster-whisper in
work/r2v/words.json, refined against the VO's energy envelope in work/r2v/cues.json).
Length = VO length + 1 s. 1080x1920, 30 fps. Footage is read from git-ignored work/.

Usage: reel2_vo.py [--still t1,t2,...]
"""
import json, math, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work")
FT, VW = os.path.join(WK, "footage"), os.path.join(WK, "r2v")
W, H, FPS = 1080, 1920, 30
ORANGE = (0xEB, 0x57, 0x17)
F_LABEL = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

VO_LEN = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                               os.path.join(FT, "ElevenLabs_VO.mp3")], capture_output=True, text=True).stdout)
DUR = VO_LEN + 1.0
N = math.ceil(DUR * FPS)
WORDS = json.load(open(os.path.join(VW, "words.json")))
C = {k: v["onset"] for k, v in json.load(open(os.path.join(VW, "cues.json"))).items()}
C["label7"] = 30.66          # "actually": mid-phrase, so Whisper's word start (not an energy onset)
C["us"] = 32.49              # vowel of "us" after the closure of "that's" (from the VO envelope)

def load(name):
    return ImageOps.exif_transpose(Image.open(os.path.join(FT, name))).convert("RGB")

# ---------------------------------------------------------------- grade (matched to Reel 1: natural, a touch warm)
def _lut():
    x = np.arange(256) / 255.0
    s = np.clip(x - 0.035 * np.sin(2 * np.pi * x), 0, 1)
    r, g, b = np.clip(s * 1.03 + 0.006, 0, 1), np.clip(s * 1.0 + 0.002, 0, 1), np.clip(s * 0.96 + 0.006, 0, 1)
    return [int(round(v * 255)) for v in np.concatenate([r, g, b])]
LUT = _lut()
def grade(im):
    a = np.asarray(im.point(LUT)).astype(np.float32)
    l = a.mean(axis=2, keepdims=True)
    return Image.fromarray(np.clip(l + (a - l) * 1.08, 0, 255).astype(np.uint8))

# ---------------------------------------------------------------- framing
def cover(src, cx, cy, s):
    hw, hh = W / (2 * s), H / (2 * s)
    cx = min(max(cx, hw), src.width - hw); cy = min(max(cy, hh), src.height - hh)
    return src.resize((W, H), Image.LANCZOS, box=(cx - hw, cy - hh, cx + hw, cy + hh))

def blur_bg(src):
    s = max(W / src.width, H / src.height)
    im = src.resize((math.ceil(src.width * s), math.ceil(src.height * s)), Image.BILINEAR)
    x0, y0 = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x0, y0, x0 + W, y0 + H)).filter(ImageFilter.GaussianBlur(45))
    return Image.blend(Image.new("RGB", (W, H)), im, 0.55)

def push(src, cx, cy, s0):
    """Full-bleed photo with a gentle 100 -> 106 % push-in over the shot."""
    return lambda u: cover(src, cx, cy, s0 * (1 + 0.06 * u))

def inset_push(src):
    """Photo narrower than 1080: never upscaled. Pushes 94 -> 100 % of native size on its own blurred fill."""
    bg = blur_bg(src)
    def f(u):
        k = 0.94 + 0.06 * u
        w, h = round(src.width * k), round(src.height * k)
        im = src.resize((w, h), Image.LANCZOS)
        out = bg.copy(); x0, y0 = (W - w) // 2, (H - h) // 2
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).rectangle((x0, y0 + 10, x0 + w, y0 + h + 10), fill=150)
        out.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(22)))
        out.paste(im, (x0, y0))
        return out
    return f

SLOW = sorted(os.listdir(os.path.join(VW, "slow2")))       # IMG_2690.MOV stand-in, motion-interpolated
REV_X = [(0.0, 810), (0.22, 705), (0.43, 615), (0.65, 600), (0.87, 675), (1.0, 690)]
def run_clip(u):
    im = Image.open(os.path.join(VW, "slow2", SLOW[min(len(SLOW) - 1, int(u * len(SLOW)))])).convert("RGB")
    x = float(np.interp(u, [p[0] for p in REV_X], [p[1] for p in REV_X]))
    x = min(max(x, 540), im.width - 540)
    return im.crop((round(x - 540), 0, round(x - 540) + W, H))

S_SMOKE = load("5ad9f8c7-ee3f-4e22-8d4a-e0813f4b1bef.jpg")   # stand-in for IMG_2682.MOV
SHOTS = [  # (start, render(u), label shown at start or None)
    (0.0,            push(S_SMOKE, 600, 800, 1.2), None),
    (C["costume"],   push(load("IMG_6396.JPG"), 2700, 1650, 0.635 * 1.08), "1. full costume. zero running."),
    (C["jelly"],     inset_push(load("2b7b453a-c09c-48d3-887a-4082d7fd27ea.jpg")), "2. the jellyfish committee"),
    (C["phone"],     push(S_SMOKE, 840, 1020, 1.5), "3. watched it all on their phone"),
    (C["photo"],     push(load("1170fedb-6d7e-405d-923b-689d7a3e3bb6.jpg"), 640, 820, 1.2), "4. photo every 200m"),
    (C["aesthetic"], inset_push(load("29e42714-a3c1-40f6-bc19-751afc337979.jpg")), "5. here for the aesthetic"),
    (C["family"],    inset_push(load("fa750c1f-380b-4a21-8027-be2eb67daa92.jpg")), "6. family day out"),
    (C["ran"],       run_clip, None),                     # "7. actually ran it." lands on "actually"
]
# snap every cut to the frame that contains the onset
CUT_F = [round(t * FPS) for t, _, _ in SHOTS] + [N]

# ---------------------------------------------------------------- text
def shadowed(lines, size, font=F_LABEL, lead=1.18, align="left", extra=None):
    f = ImageFont.truetype(font, size)
    lh = int(size * lead); asc, desc = f.getmetrics()
    w = max(math.ceil(f.getlength(l)) for l in lines) + 60
    h = lh * (len(lines) - 1) + asc + desc + 60
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
    for i, l in enumerate(lines):
        x = 30 if align == "left" else (w - f.getlength(l)) / 2
        d.text((x, 30 + i * lh), l, font=f, fill="white")
    if extra: extra(d, f)
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.putalpha(txt.getchannel("A").filter(ImageFilter.GaussianBlur(6)).point(lambda v: min(255, int(v * 0.75))))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0)); out.alpha_composite(sh, (0, 3)); out.alpha_composite(txt)
    return out

def fade(img, a):
    if a >= 1: return img
    img = img.copy(); img.putalpha(img.getchannel("A").point(lambda v: int(v * max(0, a)))); return img

LX, LY = 60, 300
_g = np.clip(1 - np.arange(H) / 760.0, 0, 1) ** 1.6 * 0.42 * 255          # soft top scrim (labels)
_g2 = np.clip(1 - np.abs(np.arange(H) - 1330) / 260.0, 0, 1) ** 1.5 * 0.28 * 255   # soft band behind subtitles
SCRIM = Image.new("RGBA", (W, H), (0, 0, 0, 0))
SCRIM.putalpha(Image.fromarray(np.repeat(np.maximum(_g, _g2)[:, None], W, axis=1).astype(np.uint8)))

TITLE = shadowed(["every type of person", "at Dubai Run"], 66)
LABELS = {s[2]: shadowed([s[2]], 56) for s in SHOTS if s[2]}
LABEL7 = shadowed(["7. actually ran it."], 56)
US = shadowed(["(us.)"], 56)
f = ImageFont.truetype(F_BOLD, 46)
WM = shadowed(["athlo"], 46, font=F_BOLD, extra=lambda d, f: d.text((30 + f.getlength("athlo"), 30), ".", font=f, fill=ORANGE))

# ---------------------------------------------------------------- subtitles: <=4 words, phrase breaks set by hand,
# mapped in order onto the Whisper words so every chunk and every word is timed off the VO.
CHUNK_SIZES = [3, 3, 3, 3, 3,            # the Dubai Run | thousands of people | and every single | one of them | is a type
               4, 3, 3, 3,               # the one who came | in full costume | did not run | not even once
               3, 2, 3,                  # the jellyfish committee | nobody asked | they came anyway
               4, 3,                     # experienced the entire event | through a screen
               4, 3,                     # stopped for a photo | every 200 meters
               2, 3,                     # here purely | for the aesthetic
               4, 4,                     # turned it into a | full family day out
               2, 4, 4, 2]               # and then | they were the ones | who actually ran it | that's us
assert sum(CHUNK_SIZES) == len(WORDS), (sum(CHUNK_SIZES), len(WORDS))

def disp(w):
    w = re.sub(r"[,.]$", "", w).lower()
    return {"dubai": "Dubai"}.get(w, w)

CHUNKS, k = [], 0
for n in CHUNK_SIZES:
    ws = WORDS[k:k + n]; k += n
    words = [disp(w["w"]) for w in ws]
    CHUNKS.append([(wd, w["s"], w["e"]) for wd, w in zip(words, ws)])
CHUNKS[0] = [({"run": "Run"}.get(w, w), s, e) for w, s, e in CHUNKS[0]]   # "the Dubai Run"
SUB_F = ImageFont.truetype(F_BOLD, 64)
SUB_Y = 1330

def sub_layer(t):
    for ci, ch in enumerate(CHUNKS):
        start = ch[0][1]
        nxt = CHUNKS[ci + 1][0][1] if ci + 1 < len(CHUNKS) else DUR
        end = nxt if nxt - ch[-1][2] < 0.5 else ch[-1][2] + 0.3
        if start - 0.03 <= t < end:
            words = [w[0] for w in ch]
            widths = [SUB_F.getlength(w + " ") for w in words]
            total = sum(widths) - SUB_F.getlength(" ")
            img = Image.new("RGBA", (W, 140), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
            x = (W - total) / 2
            for (word, ws, we), wd in zip(ch, widths):
                lit = t >= ws - 0.03                                  # spoken / being spoken: full white
                d.text((x, 30), word, font=SUB_F, fill=(255, 255, 255, 255 if lit else 120))
                x += wd
            sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
            sh.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(6)).point(lambda v: min(255, int(v * 0.8))))
            out = Image.new("RGBA", img.size, (0, 0, 0, 0)); out.alpha_composite(sh, (0, 3)); out.alpha_composite(img)
            return out
    return None

# ---------------------------------------------------------------- compose
def frame_at(i):
    t = i / FPS
    k = max(j for j in range(len(SHOTS)) if CUT_F[j] <= i)
    t0, fn, lab = SHOTS[k]
    u = (i - CUT_F[k]) / max(1, CUT_F[k + 1] - CUT_F[k] - 1)
    fr = grade(fn(u)).convert("RGBA")
    fr.alpha_composite(SCRIM)
    ts = CUT_F[k] / FPS
    if k == 0:
        fr.alpha_composite(TITLE, (LX - 30, LY - 30))               # frame 1 fully lit (thumbnail)
    elif lab:
        fr.alpha_composite(fade(LABELS[lab], (t - ts) / 0.1), (LX - 30, LY - 30))
    if t >= C["label7"] - 0.02:
        fr.alpha_composite(fade(LABEL7, (t - C["label7"] + 0.02) / 0.1), (LX - 30, LY - 30))
    if t >= C["us"] - 0.02:
        fr.alpha_composite(fade(US, (t - C["us"] + 0.02) / 0.08), (LX - 30, LY - 30 + 66))
    s = sub_layer(t)
    if s: fr.alpha_composite(s, (0, SUB_Y - 70))
    if t >= DUR - 1.0:
        fr.alpha_composite(fade(WM, (t - (DUR - 1.0)) / 0.2), (W - WM.width - 34, H - 170 - WM.height))
    return fr.convert("RGB")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--chunks":
        for c in CHUNKS: print(f"{c[0][1]:6.2f}-{c[-1][2]:6.2f}", " ".join(w for w, _, _ in c))
        sys.exit()
    if len(sys.argv) > 2 and sys.argv[1] == "--still":
        os.makedirs(os.path.join(VW, "stills"), exist_ok=True)
        for ts in sys.argv[2].split(","):
            frame_at(round(float(ts) * FPS)).save(os.path.join(VW, "stills", f"t{float(ts):05.2f}.jpg"), quality=88)
        sys.exit()
    print("VO", VO_LEN, "DUR", DUR, "frames", N, "cuts", [round(c / FPS, 3) for c in CUT_F])
    out = os.path.join(VW, "picture.mp4")
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                          "-profile:v", "high", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                          "-colorspace", "bt709", "-g", "15", out], stdin=subprocess.PIPE)
    for i in range(N):
        p.stdin.write(frame_at(i).tobytes())
    p.stdin.close(); p.wait()
    print("wrote", out)
