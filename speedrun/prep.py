"""Cut the real Athlo logo off its white background for use on the dark end card."""
import os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "work", "speedrun"); os.makedirs(OUT, exist_ok=True)
src = np.array(Image.open(os.path.join(ROOT, "assets", "athlo_logo.jpg")).convert("RGB")).astype(np.float32)
bg = 254.0
alpha = np.clip((bg - src.min(axis=2)) / (bg - 6.0), 0, 1)   # every brand colour has one channel near 0
alpha[alpha < 0.03] = 0
fg = np.clip((src - (1 - alpha[..., None]) * bg) / np.maximum(alpha[..., None], 1e-3), 0, 255)
fg[fg.max(axis=2) < 140] = 255          # navy wordmark -> white on the dark background
ys, xs = np.where(alpha > 0.05)
crop = np.dstack([fg, alpha * 255]).astype(np.uint8)[ys.min() - 8:ys.max() + 8, xs.min() - 8:xs.max() + 8]
Image.fromarray(crop, "RGBA").save(os.path.join(OUT, "logo.png"))
print("logo", crop.shape)
