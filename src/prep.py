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

# ---------------------------------------------------------------- real UI details
# Crops of the real app used for the zoomed detail shots. Nothing here is invented.
import json
ui = {
    "hero":   (0.3, (48, 402, 1158, 1600)),    # "Find your next game..." + Book courts copy + Find a facility
    "places": (9.4, (30, 380, 1170, 1330)),    # Places to play, search, sport chips, "13 places"
    "chips":  (1.0, (30, 1470, 1130, 1860)),   # Pick your play / What are you into? + chips
    "menu_train":   (7.4, (330, 760, 1206, 1279)),    # Find players / Clubs / Events
    "menu_compete": (7.4, (330, 931, 1206, 1450)),    # Clubs / Events / Challenges
}
for k, (t, b) in ui.items():
    frame(t).crop(b).save(os.path.join(W, f"ui_{k}.png"))
# Football chip box inside the chips crop, for the tap animation
f = np.array(frame(1.0)).astype(int)
reg = f[1700:1860, 0:396]
m = (np.abs(reg - np.array([232, 230, 225])).max(axis=2) < 9)
ys, xs = np.where(m)
box = [int(xs.min()) - 30, int(ys.min()) + 1700 - 1470, int(xs.max()) + 1 - 30, int(ys.max()) + 1 + 1700 - 1470]
json.dump({"football_chip": box}, open(os.path.join(W, "ui_boxes.json"), "w"))
print("football chip", box)

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
