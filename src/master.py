#!/usr/bin/env python3
"""Master the score to Instagram loudness (-14 LUFS integrated, -1 dBTP) and mux with picture."""
import json, math, os, subprocess, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work")
TARGET, CEIL = -14.0, -1.5  # sample-peak ceiling on 4x oversampled signal, leaves margin under -1 dBTP

def measure(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], stderr=subprocess.PIPE, text=True)
    t = p.stderr
    return json.loads(t[t.rfind("{"):t.rfind("}") + 1])

def limit(x, sr, ceil_db, look=0.004, release=0.12):
    up = signal.resample_poly(x, 4, 1, axis=1)
    env = np.abs(up).max(axis=0).reshape(-1, 4).max(axis=1)[:x.shape[1]]
    c = 10 ** (ceil_db / 20)
    g = np.minimum(1.0, c / np.maximum(env, 1e-9))
    la = int(look * sr)
    g = minimum_filter1d(g, size=2 * la + 1, origin=0)
    # instant attack, smooth release
    r = math.exp(-1 / (release * sr))
    out = np.empty_like(g); cur = 1.0
    for i, v in enumerate(g):
        cur = v if v < cur else v + (cur - v) * r
        out[i] = cur
    out = np.convolve(out, np.ones(la) / la, mode="same")
    return x * out[None, :]

src = os.path.join(WK, "score_premaster.wav")
sr, x = wavfile.read(src)
x = x.T.astype(np.float64)
m = measure(src)
gain = TARGET - float(m["input_i"])
x *= 10 ** (gain / 20)
for _ in range(3):
    y = limit(x, sr, CEIL)
    tmp = os.path.join(WK, "score_master.wav")
    wavfile.write(tmp, sr, y.T.astype(np.float32))
    m2 = measure(tmp)
    err = TARGET - float(m2["input_i"])
    print(f"I {m2['input_i']} LUFS  TP {m2['input_tp']} dBTP  LRA {m2['input_lra']}")
    if abs(err) < 0.15 and float(m2["input_tp"]) <= -1.0:
        break
    x *= 10 ** (err / 20)

pic = os.path.join(WK, "picture.mp4")
os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
final = os.path.join(ROOT, "out", "athlo_launch_45s_1080x1920.mp4")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", pic, "-i", tmp,
                "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-profile:v", "high",
                "-level", "4.2", "-crf", "17", "-maxrate", "16M", "-bufsize", "32M", "-g", "15", "-bf", "2",
                "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                "-color_range", "tv", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart",
                "-shortest", final], check=True)
print("wrote", final)
