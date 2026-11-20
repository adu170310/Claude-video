"""Cut the real Athlo logo off its white background, keeping its original colours.

Writes work/reel/logo.png (RGBA, tight crop) and logo.json with the ring geometry
(in cropped pixel coordinates) so the ribbon can trace the real rings exactly.
"""
import json, os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "work", "reel")
os.makedirs(OUT, exist_ok=True)

src = np.array(Image.open(os.path.join(ROOT, "assets", "athlo_logo.jpg")).convert("RGB")).astype(np.float32)
BG = 254.0
# Every brand colour (orange, pink, navy) has one channel near 0, so the min channel
# tells us how much of the white background shows through.
alpha = np.clip((BG - src.min(axis=2)) / (BG - 4.0), 0, 1)
alpha[alpha < 0.04] = 0
fg = np.clip((src - (1 - alpha[..., None]) * BG) / np.maximum(alpha[..., None], 1e-3), 0, 255)

ys, xs = np.where(alpha > 0.1)
pad = 8
x0, y0 = xs.min() - pad, ys.min() - pad
x1, y1 = xs.max() + pad, ys.max() + pad
rgba = np.dstack([fg, alpha * 255]).astype(np.uint8)[y0:y1, x0:x1]
Image.fromarray(rgba, "RGBA").save(os.path.join(OUT, "logo.png"))

# Ring geometry, measured on the source image (outer/inner edges along the ring axes):
# left ring outer 100..487 / 590..966, inner 178..398 / 670..888; right ring outer 330..716, inner 417..639.
meta = {
    "size": [int(x1 - x0), int(y1 - y0)],
    "rings": [
        {"cx": 291.0 - x0, "cy": 778.0 - y0, "r": 150.0, "w": 80.0},
        {"cx": 526.0 - x0, "cy": 778.0 - y0, "r": 151.0, "w": 80.0},
    ],
    "rings_right_edge": 720.0 - x0,
}
json.dump(meta, open(os.path.join(OUT, "logo.json"), "w"), indent=1)
print("logo", meta["size"], meta["rings"])
