#!/usr/bin/env python3
"""Master to -14 LUFS integrated with true peak below -1.5 dBTP, then mux with the picture.

The limiter runs on a 4x oversampled signal with a -2.3 dB ceiling so the AAC-encoded
file still measures under -1.5 dBTP; the final file is re-measured to prove it.
"""
import json, math, os, subprocess, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work", "reel")
TARGET, CEIL, TP_MAX = -14.0, -2.3, -1.5
FINAL = os.path.join(ROOT, "out", "athlo_reel_one_line_17s_1080x1920.mp4")


def measure(path, extra=()):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *extra, "-i", path, "-vn", "-af",
                        "loudnorm=print_format=json", "-f", "null", "-"], stderr=subprocess.PIPE, text=True)
    t = p.stderr
    return json.loads(t[t.rfind("{"):t.rfind("}") + 1])


def limit(x, sr, ceil_db, look=0.004, release=0.10):
    up = signal.resample_poly(x, 4, 1, axis=1)
    e = np.abs(up).max(axis=0)
    e = e[: (len(e) // 4) * 4].reshape(-1, 4).max(axis=1)
    e = np.pad(e, (0, x.shape[1] - len(e)), mode="edge")
    g = np.minimum(1.0, 10 ** (ceil_db / 20) / np.maximum(e, 1e-9))
    la = int(look * sr)
    g = minimum_filter1d(g, size=2 * la + 1)
    r = math.exp(-1 / (release * sr))
    out = np.empty_like(g)
    cur = 1.0
    for i, v in enumerate(g):
        cur = v if v < cur else v + (cur - v) * r
        out[i] = cur
    out = np.convolve(out, np.ones(la) / la, mode="same")
    return x * out[None, :]


sr, x = wavfile.read(os.path.join(WK, "score_premaster.wav"))
x = x.T.astype(np.float64)
x *= 10 ** ((TARGET - float(measure(os.path.join(WK, "score_premaster.wav"))["input_i"])) / 20)
tmp = os.path.join(WK, "score_master.wav")
ceil = CEIL
for it in range(6):
    y = limit(x, sr, ceil)
    wavfile.write(tmp, sr, y.T.astype(np.float32))
    m = measure(tmp)
    print(f"pass {it}: I {m['input_i']} LUFS  TP {m['input_tp']} dBTP")
    err = TARGET - float(m["input_i"])
    if abs(err) < 0.1 and float(m["input_tp"]) <= ceil + 0.3:
        break
    x *= 10 ** (err / 20)

os.makedirs(os.path.dirname(FINAL), exist_ok=True)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(WK, "picture.mp4"), "-i", tmp,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                "-movflags", "+faststart", "-shortest", FINAL], check=True)
m = measure(FINAL)
size = os.path.getsize(FINAL) / 1e6
print(f"FINAL {FINAL}\n  loudness {m['input_i']} LUFS, true peak {m['input_tp']} dBTP, LRA {m['input_lra']}, size {size:.1f} MB")
assert float(m["input_tp"]) < TP_MAX, "true peak over limit"
assert size < 30
