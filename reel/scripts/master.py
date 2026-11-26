#!/usr/bin/env python3
"""Master the score: -14 LUFS integrated, true peak under -1.5 dBTP (limited at -2.3 on a 4x oversampled signal
so the AAC encode keeps its margin). Writes work/score_master.wav and public/soundtrack.wav (studio preview)."""
import json, math, os, shutil, subprocess
import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(R, "work")
TARGET, CEIL = -14.0, -2.3

def measure(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], stderr=subprocess.PIPE, text=True)
    t = p.stderr
    return json.loads(t[t.rfind("{"):t.rfind("}") + 1])

def limit(x, sr, ceil_db, look=0.003, release=0.08):
    up = signal.resample_poly(x, 4, 1, axis=1)
    env = np.abs(up).max(axis=0).reshape(-1, 4).max(axis=1)[: x.shape[1]]
    g = np.minimum(1.0, 10 ** (ceil_db / 20) / np.maximum(env, 1e-9))
    la = int(look * sr)
    g = minimum_filter1d(g, size=2 * la + 1)
    r = math.exp(-1 / (release * sr)); out = np.empty_like(g); cur = 1.0
    for i, v in enumerate(g):
        cur = v if v < cur else v + (cur - v) * r
        out[i] = cur
    out = np.convolve(out, np.ones(la) / la, mode="same")
    return x * out[None, :]

sr, x = wavfile.read(os.path.join(WK, "score_premaster.wav"))
x = x.T.astype(np.float64)
x *= 10 ** ((TARGET - float(measure(os.path.join(WK, "score_premaster.wav"))["input_i"])) / 20)
out = os.path.join(WK, "score_master.wav")
for _ in range(6):
    y = limit(x, sr, CEIL)
    wavfile.write(out, sr, y.T.astype(np.float32))
    m = measure(out)
    print(f"I {m['input_i']} LUFS  TP {m['input_tp']} dBTP  LRA {m['input_lra']}")
    err = TARGET - float(m["input_i"])
    if abs(err) < 0.1 and float(m["input_tp"]) <= -2.0:
        break
    x *= 10 ** (err / 20)
shutil.copy(out, os.path.join(R, "public", "soundtrack.wav"))
