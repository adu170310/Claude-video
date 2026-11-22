#!/usr/bin/env python3
"""Reel 2 audio: clock ticks under each countdown, a ding on every reveal, original clip audio
on the reveal, and (music version only) a placeholder 120 BPM beat that loops exactly at 14 s.
Masters both mixes to -14 LUFS / -1.5 dBTP and muxes with work/r2/picture.mp4 into out/."""
import json, os, subprocess
import numpy as np
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R2 = os.path.join(ROOT, "work", "r2")
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)
SR, DUR = 48000, 14.0
N = int(SR * DUR)
rng = np.random.default_rng(7)

def add(buf, x, t, g=1.0):
    i = int(round(t * SR)) % N
    L = x.shape[1]; n = min(L, N - i)
    buf[:, i:i + n] += g * x[:, :n]
    if n < L:                            # wrap the tail so the loop point is seamless
        buf[:, :L - n] += g * x[:, n:]

def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)

def tick(hi=True):
    n = int(0.05 * SR); t = np.arange(n) / SR
    f = 3200 if hi else 2400
    x = 0.6 * np.sin(2 * np.pi * f * t) * env(n, 0.0005, 0.006)
    x += 0.5 * rng.standard_normal(n) * env(n, 0.0002, 0.0025)
    x += 0.4 * np.sin(2 * np.pi * 900 * t) * env(n, 0.0005, 0.012)
    return np.stack([x, x])

def ding():
    n = int(1.6 * SR); t = np.arange(n) / SR
    x = np.zeros(n)
    for ratio, amp, dec in [(1, 1, 0.9), (2.0, 0.45, 0.5), (2.76, 0.3, 0.35), (5.4, 0.15, 0.15)]:
        x += amp * np.sin(2 * np.pi * 1568 * ratio * t) * env(n, 0.002, dec)
    x /= np.abs(x).max()
    d = int(0.012 * SR)                  # slight stereo width
    return np.stack([x, np.concatenate([np.zeros(d), x[:-d]])])

def kick():
    n = int(0.4 * SR); t = np.arange(n) / SR
    f = 45 + 90 * np.exp(-t / 0.03)
    return np.stack([np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.16)] * 2)

def clap():
    n = int(0.25 * SR)
    x = rng.standard_normal(n) * env(n, 0.001, 0.05)
    x = np.convolve(x, np.ones(6) / 6, mode="same") * 0.6
    return np.stack([x, x])

def hat():
    n = int(0.08 * SR)
    x = np.diff(rng.standard_normal(n + 1)) * env(n, 0.0005, 0.018) * 0.25
    return np.stack([x, x])

def bass(freq, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(4 * np.pi * freq * t)
    return np.stack([x * env(n, 0.005, dur * 0.6)] * 2) * 0.5

# --- game SFX (both versions)
sfx = np.zeros((2, N))
for t0, t1 in [(1.0, 2.85), (4.0, 5.4), (7.0, 8.35)]:      # countdown -> ring pop
    k = 0
    for t in np.arange(t0, t1 - 0.01, 0.25):
        add(sfx, tick(k % 2 == 0), t, 0.5); k += 1
for t in (2.85, 5.4, 8.35):
    add(sfx, ding(), t, 0.55)

# --- original audio: the reveal clip (stand-in IMG_2690.MOV), 10.0-12.5
orig = np.zeros((2, N))
sr0, a = wavfile.read(os.path.join(R2, "a2690.wav"))
a = a.astype(np.float64) / 32768
a = np.interp(np.linspace(0, len(a) - 1, int(2.5 * SR)), np.arange(len(a)), a)   # match 2.3->2.5 s retime
fade = int(0.08 * SR); a[:fade] *= np.linspace(0, 1, fade); a[-fade:] *= np.linspace(1, 0, fade)
orig[:, int(10.0 * SR):int(10.0 * SR) + len(a)] += a * 1.4

# --- placeholder beat, 120 BPM, 28 beats = 14 s exactly
beat = np.zeros((2, N)); spb = 0.5
notes = [55.0, 55.0, 65.41, 49.0]                            # A1 A1 C2 G1, one per bar
for b in range(28):
    t = b * spb
    add(beat, kick(), t, 0.9)
    if b % 2 == 1: add(beat, clap(), t, 0.5)
    add(beat, hat(), t + spb / 2, 1.0)
    add(beat, hat(), t, 0.5)
    if b % 4 == 0: add(beat, bass(notes[(b // 4) % 4], 4 * spb), t, 0.8)
# duck the beat a little under each ding
duck = np.ones(N)
for t in (2.85, 5.4, 8.35):
    i = int(t * SR); m = int(0.6 * SR)
    duck[i:i + m] = np.minimum(duck[i:i + m], 0.55 + 0.45 * np.linspace(0, 1, m))
beat *= duck

def master(x, name):
    pre = os.path.join(R2, name + "_pre.wav")
    x = x / max(1e-9, np.abs(x).max()) * 0.5
    wavfile.write(pre, SR, x.T.astype(np.float32))
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", pre, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       stderr=subprocess.PIPE, text=True).stderr
    m = json.loads(p[p.rfind("{"):p.rfind("}") + 1])
    af = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
          f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']},aresample=48000")
    mp4 = os.path.join(OUT, f"reel2_spot_the_team_{name}.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(R2, "picture.mp4"),
                    "-i", pre, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", af,
                    "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart",
                    "-t", str(DUR), mp4], check=True)
    q = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], stderr=subprocess.PIPE, text=True).stderr
    q = json.loads(q[q.rfind("{"):q.rfind("}") + 1])
    print(f"{os.path.basename(mp4)}: {q['input_i']} LUFS, {q['input_tp']} dBTP")

master(sfx + orig + 0.75 * beat, "music")
master(sfx + orig, "nomusic")
