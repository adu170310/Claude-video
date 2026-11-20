"""Prepare assets for the Athlo launch film: logo mattes, photo crops, stitched app page."""
import os, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "assets"); W = os.path.join(ROOT, "work", "assets")
os.makedirs(W, exist_ok=True)
REC = os.path.join(A, "app_recording.mov")

def frame(t):
    p = os.path.join(W, f"rec_{t:.2f}.png")
    if not os.path.exists(p):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", REC, "-frames:v", "1", p], check=True)
    return Image.open(p).convert("RGB")

# ---------------------------------------------------------------- logo
# Un-mix the logo from its white background: every brand colour has one channel near 0,
# so alpha = (bg - min channel) / (bg - fg_min). Then recover the true colour.
src = np.array(Image.open(os.path.join(A, "athlo_logo.jpg")).convert("RGB")).astype(np.float32)
bg = 254.0
mn = src.min(axis=2)
alpha = np.clip((bg - mn) / (bg - 6.0), 0, 1)
alpha[alpha < 0.03] = 0
fg = (src - (1 - alpha[..., None]) * bg) / np.maximum(alpha[..., None], 1e-3)
fg = np.clip(fg, 0, 255)
# wordmark pixels (navy) -> white; rings and the orange dot keep their colour
navy = (fg.max(axis=2) < 140)
fg[navy] = 255
ys, xs = np.where(alpha > 0.05)
y0, y1, x0, x1 = ys.min() - 8, ys.max() + 8, xs.min() - 8, xs.max() + 8
rgba = np.dstack([fg, alpha * 255]).astype(np.uint8)[y0:y1, x0:x1]
full = Image.fromarray(rgba, "RGBA")
full.save(os.path.join(W, "logo_full.png"))
# split rings / wordmark at the gap between them (column with no alpha)
cols = (rgba[..., 3] > 10).sum(axis=0)
gap = [i for i in range(len(cols) // 3, len(cols) * 2 // 3) if cols[i] == 0]
split = gap[len(gap) // 2]
full.crop((0, 0, split, full.height)).save(os.path.join(W, "logo_rings.png"))
full.crop((split, 0, full.width, full.height)).save(os.path.join(W, "logo_word.png"))
print("logo", full.size, "split at", split)

# ---------------------------------------------------------------- photos from the recording
crops = {"tennis": (1.5, (48, 1290, 1158, 1980)), "night": (3.0, (48, 620, 1158, 1310)),
         "padel": (4.0, (48, 590, 1090, 1250)), "hoop": (4.5, (48, 1110, 1158, 1770)),
         "grass": (6.0, (48, 1630, 1158, 2240))}
for k, (t, b) in crops.items():
    frame(t).crop(b).save(os.path.join(W, f"photo_{k}.png"))

# ---------------------------------------------------------------- stitched home page
# The recording scrolls fast; stitch three frames into one tall page so we can scroll it
# smoothly and slowly. Offsets measured by row matching: 0.3->1.0 = 891 px, 1.0->1.5 = 1048 px.
f0, f1, f2 = frame(0.3), frame(1.0), frame(1.5)
CUT = 2100  # rows below this hold the floating chat button and browser bar
o1, o2 = 891, 891 + 1048
page = Image.new("RGB", (1206, CUT + o2), (242, 239, 232))
page.paste(f2.crop((0, 330, 1206, CUT)), (0, 330 + o2))
page.paste(f1.crop((0, 330, 1206, CUT)), (0, 330 + o1))
page.paste(f0.crop((0, 330, 1206, CUT)), (0, 330))
page.save(os.path.join(W, "app_page.png"))
f0.crop((0, 150, 1206, 330)).save(os.path.join(W, "app_header.png"))
print("page", page.size)
