#!/usr/bin/env python3
"""Audio for "every type of person at Dubai Run" (14.5 s).

_nomusic: original crowd ambience only (event audio from 8d56a47c…mp4, the smoke/paramotor moment)
          crossfading into the last shot's own audio (IMG_2690.MOV stand-in).
_music:   a low, chill 100 BPM placeholder beat (beats at 0.3 + 0.6k s, so every cut lands on one),
          with the ambience tucked underneath.
Both mastered to -14 LUFS / -1.5 dBTP and muxed with work/r2t/picture.mp4 into out/."""
import json, os, subprocess
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work", "r2t"); OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)
SR, DUR = 48000, 14.5
N = int(SR * DUR)
rng = np.random.default_rng(3)

def rd(path):
    sr, a = wavfile.read(path)
    a = a.astype(np.float64) / (32768 if a.dtype == np.int16 else 1)
    if a.ndim == 1: a = np.stack([a, a], 1)
    return a.T

def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)

def add(buf, x, t, g=1.0):
    i = int(round(t * SR)); n = min(x.shape[1], N - i)
    if n > 0: buf[:, i:i + n] += g * x[:, :n]

# ---- ambience bed: 6.0-20.5 s of the smoke-moment crowd audio, gentle fades
amb = rd(os.path.join(WK, "..", "r2", "amb8d56.wav"))[:, int(6.0 * SR):int(6.0 * SR) + N]
fi, fo = int(0.05 * SR), int(0.4 * SR)
amb[:, :fi] *= np.linspace(0, 1, fi); amb[:, -fo:] *= np.linspace(1, 0, fo)
# last shot: its own audio (stand-in IMG_2690.MOV, 2.3 s) crossfaded in at 12.3 s
own = rd(os.path.join(WK, "..", "r2", "a2690.wav"))
xf = int(0.15 * SR); i0 = int(12.3 * SR)
own_buf = np.zeros((2, N)); L = min(own.shape[1], N - i0)
own_buf[:, i0:i0 + L] = own[:, :L]
own_buf[:, i0:i0 + xf] *= np.linspace(0, 1, xf)
own_buf[:, i0 + L - fo:i0 + L] *= np.linspace(1, 0, fo)
gate = np.ones(N); gate[i0:i0 + xf] = np.linspace(1, 0.25, xf); gate[i0 + xf:] = 0.25
orig = amb * gate + own_buf * 1.6

# ---- low chill beat, 100 BPM, grid offset 0.3 s
def kick():
    n = int(0.5 * SR); t = np.arange(n) / SR
    f = 42 + 70 * np.exp(-t / 0.04)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.22)
    return np.stack([x, x])

def rim():
    n = int(0.12 * SR); t = np.arange(n) / SR
    x = (0.5 * np.sin(2 * np.pi * 1700 * t) + 0.5 * rng.standard_normal(n)) * env(n, 0.0005, 0.012)
    return np.stack([x * 0.9, x]) * 0.35

def shaker():
    n = int(0.09 * SR)
    x = rng.standard_normal(n) * env(n, 0.01, 0.025)
    x = sosfilt(butter(2, 6000, "hp", fs=SR, output="sos"), x) * 0.12
    return np.stack([x * 0.7, x])

def pad(freqs, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.4 * t)) for f in freqs) / len(freqs)
    e = np.minimum(1, t / 0.25) * np.minimum(1, (dur - t) / 0.4)
    x = sosfilt(butter(2, 1400, "lp", fs=SR, output="sos"), x * e) * 0.32
    return np.stack([x, np.roll(x, int(0.01 * SR))])

def sub(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t) * np.minimum(1, t / 0.02) * np.minimum(1, (dur - t) / 0.1) * 0.45
    return np.stack([x, x])

beat = np.zeros((2, N)); spb = 0.6; off = 0.3
chords = [([220.0, 261.63, 329.63, 392.0], 55.0),      # Am7
          ([174.61, 220.0, 261.63, 329.63], 43.65),    # Fmaj7
          ([196.0, 246.94, 293.66, 349.23], 49.0),     # G7
          ([164.81, 196.0, 246.94, 293.66], 41.2)]     # Em7
add(beat, pad(chords[3][0], off), 0.0, 0.6)            # pickup so frame 1 isn't silent
for b in range(int((DUR - off) / spb) + 1):
    t = off + b * spb
    if b % 4 in (0, 2) or b % 8 == 7: add(beat, kick(), t, 0.85)
    if b % 4 in (1, 3): add(beat, rim(), t)
    add(beat, shaker(), t + spb / 2)
    if b % 4 == 0:
        ch, root = chords[(b // 4) % 4]
        add(beat, pad(ch, 4 * spb), t); add(beat, sub(root, 4 * spb * 0.95), t)
fo2 = int(0.5 * SR); beat[:, -fo2:] *= np.linspace(1, 0, fo2)

def master(x, name):
    pre = os.path.join(WK, name + "_pre.wav")
    x = x / max(1e-9, np.abs(x).max()) * 0.5
    wavfile.write(pre, SR, x.T.astype(np.float32))
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", pre, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       stderr=subprocess.PIPE, text=True).stderr
    m = json.loads(p[p.rfind("{"):p.rfind("}") + 1])
    af = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
          f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']},aresample=48000")
    mp4 = os.path.join(OUT, f"reel2_every_type_{name}.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(WK, "picture.mp4"),
                    "-i", pre, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", af, "-c:a", "aac",
                    "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", "-t", str(DUR), mp4], check=True)
    q = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], stderr=subprocess.PIPE, text=True).stderr
    q = json.loads(q[q.rfind("{"):q.rfind("}") + 1])
    print(f"{os.path.basename(mp4)}: {q['input_i']} LUFS, {q['input_tp']} dBTP")

master(beat + 0.22 * orig, "music")
master(orig, "nomusic")
