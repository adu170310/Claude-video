"""Prepare real assets for the Athlo reel.

- Logo: un-mixes the real logo JPG from its white background so it sits on a dark set.
  Rings keep their colours; the navy wordmark turns white.
- App screens: full-resolution frames from the real app screen recording, with the phone
  status bar, floating chat button and browser URL bar cropped off. Nothing is drawn or added.
"""
import os, subprocess
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REEL = os.path.dirname(HERE)
ROOT = os.path.dirname(REEL)
A = os.path.join(ROOT, "assets")
PUB = os.path.join(REEL, "public")
os.makedirs(os.path.join(PUB, "screens"), exist_ok=True)

# ---------------------------------------------------------------- logo
src = np.array(Image.open(os.path.join(A, "athlo_logo.jpg")).convert("RGB")).astype(np.float32)
bg = 254.0
mn = src.min(axis=2)
alpha = np.clip((bg - mn) / (bg - 6.0), 0, 1)
alpha[alpha < 0.03] = 0
fg = np.clip((src - (1 - alpha[..., None]) * bg) / np.maximum(alpha[..., None], 1e-3), 0, 255)
fg[fg.max(axis=2) < 140] = 255  # navy wordmark -> white
ys, xs = np.where(alpha > 0.05)
y0, y1, x0, x1 = ys.min() - 8, ys.max() + 8, xs.min() - 8, xs.max() + 8
rgba = np.dstack([fg, alpha * 255]).astype(np.uint8)[y0:y1, x0:x1]
full = Image.fromarray(rgba, "RGBA")
full.save(os.path.join(PUB, "logo_full.png"))
cols = (rgba[..., 3] > 10).sum(axis=0)
gap = [i for i in range(len(cols) // 3, len(cols) * 2 // 3) if cols[i] == 0]
split = gap[len(gap) // 2]
rings = full.crop((0, 0, split, full.height))
# square canvas for the rings so they can sit centred in the orb
s = max(rings.size) + 40
sq = Image.new("RGBA", (s, s), (0, 0, 0, 0))
sq.paste(rings, ((s - rings.width) // 2, (s - rings.height) // 2))
sq.save(os.path.join(PUB, "logo_rings.png"))
print("logo", full.size, "rings", sq.size)

# ---------------------------------------------------------------- real app screens
REC = os.path.join(A, "app_recording.mov")
# 12 distinct, fully loaded frames; each is used once in the tunnel.
# (time, crop) — crop removes the status bar, floating chat button and browser URL bar.
FULL = "crop=1206:1975:0:175"
MENU = "crop=936:1534:270:175"  # the menu drawer only, without the blurred page behind it
SHOTS = [(0.0, FULL), (1.0, FULL), (1.6, FULL), (2.4, FULL), (3.2, FULL), (4.0, FULL),
         (4.4, FULL), (4.8, FULL), (5.6, FULL), (7.6, MENU), (9.5, FULL), (10.5, FULL)]
for f in os.listdir(os.path.join(PUB, "screens")):
    os.remove(os.path.join(PUB, "screens", f))
for i, (t, crop) in enumerate(SHOTS):
    out = os.path.join(PUB, "screens", f"screen_{i}.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", REC, "-frames:v", "1",
                    "-vf", f"{crop},scale=900:-1", "-q:v", "2", out], check=True)
print("screens", len(SHOTS))
