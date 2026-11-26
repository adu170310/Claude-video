"""Cut the real Athlo logo off its white background -> public/athlo_logo.png (white wordmark for dark end card)."""
import os, numpy as np
from PIL import Image
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = np.array(Image.open(os.path.join(R, "..", "assets", "athlo_logo.jpg")).convert("RGB")).astype(np.float32)
bg = 254.0
alpha = np.clip((bg - src.min(axis=2)) / (bg - 6.0), 0, 1); alpha[alpha < 0.03] = 0
fg = np.clip((src - (1 - alpha[..., None]) * bg) / np.maximum(alpha[..., None], 1e-3), 0, 255)
fg[fg.max(axis=2) < 140] = 255          # navy wordmark -> off-white on charcoal
fg[(fg.max(axis=2) >= 250) & (fg.min(axis=2) > 200)] = [244, 242, 236]
ys, xs = np.where(alpha > 0.05)
rgba = np.dstack([fg, alpha * 255]).astype(np.uint8)[ys.min()-8:ys.max()+8, xs.min()-8:xs.max()+8]
Image.fromarray(rgba, "RGBA").save(os.path.join(R, "public", "athlo_logo.png"))
print(rgba.shape)
