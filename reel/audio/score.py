#!/usr/bin/env python3
"""Original cinematic ambient score + sound design for the Athlo 15 s reel.

Everything is synthesised here (additive pads, sub, filtered-noise whooshes, bell shimmer,
deep hit, algorithmic reverb). Cue times come from src/timeline.json so sound and picture
stay locked. Writes ../work/reel_premaster.wav (48 kHz stereo float).
"""
import json, math, os
import numpy as np
from scipy import signal
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
REEL = os.path.dirname(HERE)
WORK = os.path.join(os.path.dirname(REEL), "work")
os.makedirs(WORK, exist_ok=True)
TL = json.load(open(os.path.join(REEL, "src", "timeline.json")))
FPS = TL["fps"]
SR = 48000
DUR = TL["duration"] / FPS
N = int(DUR * SR)
rng = np.random.default_rng(30)

music = np.zeros((2, N))
sfx = np.zeros((2, N))
send = np.zeros((2, N))


def sec(frame):
    return frame / FPS


def tt(d):
    return np.arange(int(d * SR)) / SR


def hz(note):
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    n, o = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[n] + 12 * (o + 1) - 69) / 12)


def add(buf, t0, x, gain=1.0, pan=0.0, rev=0.0):
    i = int(round(t0 * SR))
    if x.ndim == 1:
        a = (pan + 1) * math.pi / 4
        x = np.vstack([x * math.cos(a), x * math.sin(a)]) * math.sqrt(2)
    if i < 0:
        x = x[:, -i:]
        i = 0
    n = min(x.shape[1], N - i)
    if n <= 0:
        return
    buf[:, i:i + n] += x[:, :n] * gain
    if rev:
        send[:, i:i + n] += x[:, :n] * gain * rev


def env_ar(n, a, r):
    e = np.ones(n)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.sin(np.linspace(0, math.pi / 2, na)) ** 2
    if nr:
        e[-nr:] *= np.cos(np.linspace(0, math.pi / 2, nr)) ** 2
    return e


def sos(kind, fc, order=2):
    return signal.butter(order, fc, kind, fs=SR, output="sos")


def lp(x, fc):
    return signal.sosfilt(sos("low", min(fc, SR * 0.45)), x, axis=-1)


def hp(x, fc):
    return signal.sosfilt(sos("high", fc), x, axis=-1)


# ------------------------------------------------------------------ pad
def pad_voice(f, dur, bright, att, rel, detune=6):
    t = tt(dur)
    out = np.zeros((2, len(t)))
    for v, (cents, pan) in enumerate([(-detune, -0.7), (0, 0.0), (detune, 0.7)]):
        fv = f * 2 ** (cents / 1200)
        vib = 1 + 0.0012 * np.sin(2 * math.pi * (0.13 + 0.04 * v) * t + v)
        ph = 2 * math.pi * fv * np.cumsum(vib) / SR
        s = np.zeros(len(t))
        for n in range(1, 12):
            if n * fv > 8000:
                break
            s += np.sin(n * ph + v * n) * math.exp(-(n * fv) / bright) / n
        a = (pan + 1) * math.pi / 4
        out[0] += s * math.cos(a)
        out[1] += s * math.sin(a)
    return out * env_ar(len(t), att, rel)[None, :] / 3


chords = [
    (0.0, 6.9, ["D3", "A3", "E4", "F#4", "C#5"], 1500),
    (6.3, 4.6, ["B2", "F#3", "D4", "A4", "C#5"], 1900),
    (10.3, 2.2, ["G2", "D3", "B3", "F#4", "C#5"], 2600),
    (12.25, 2.75, ["D3", "A3", "F#4", "E5", "A5"], 2200),
]
for t0, d, notes, bright in chords:
    for k, nt in enumerate(notes):
        add(music, t0, pad_voice(hz(nt), d + 0.6, bright, att=1.2 if t0 > 0 else 0.5, rel=1.4), gain=0.16, rev=0.5)

# soft swell over the whole piece, a breath before the flash, then the end chord settles
t = np.arange(N) / SR
swell = 0.35 + 0.65 * np.clip(t / sec(TL["deepHit"]), 0, 1) ** 1.6
swell *= 1 - 0.35 * np.exp(-((t - sec(TL["deepHit"] - 3)) / 0.18) ** 2)
fade_out = np.clip((DUR - t) / 1.2, 0, 1) ** 1.5
music *= (swell * fade_out)[None, :]

# sub bass on the root, entering when the panel arrives
for t0, d, f0 in [(sec(TL["b2"]), 4.9, hz("D2")), (6.3, 4.4, hz("B1")), (10.3, 2.0, hz("G1")), (12.3, 2.7, hz("D2"))]:
    tv = tt(d)
    x = np.sin(2 * math.pi * f0 * tv) + 0.25 * np.sin(4 * math.pi * f0 * tv)
    add(music, t0, x * env_ar(len(tv), 0.8, 1.2), gain=0.12)

# a quiet high plucked pattern during the counter, rising with the days
for k in range(10):
    t0 = sec(TL["b5"] + 10) + k * 0.24
    f0 = hz(["A5", "D6", "E6", "F#6", "A6"][k % 5]) * (1 if k < 5 else 2 ** (2 / 12))
    tv = tt(0.9)
    x = (np.sin(2 * math.pi * f0 * tv) + 0.3 * np.sin(2 * math.pi * 2 * f0 * tv)) * np.exp(-tv * 7)
    add(music, t0, x, gain=0.045 + 0.004 * k, pan=-0.5 + 0.1 * k, rev=0.7)


# ------------------------------------------------------------------ sound design
def whoosh(d=1.1, lo=300, hi=5000, peak=0.62):
    n = int(d * SR)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    blk = 256
    zi = None
    centre = np.concatenate([np.geomspace(lo, hi, int(n * peak)), np.geomspace(hi, lo * 1.5, n - int(n * peak))])
    for i in range(0, n, blk):
        c = centre[i]
        sec_ = signal.butter(2, [c / 1.6, min(c * 1.6, SR * 0.45)], "band", fs=SR, output="sos")
        if zi is None:
            zi = np.zeros((sec_.shape[0], 2))
        out[i:i + blk], zi = signal.sosfilt(sec_, noise[i:i + blk], zi=zi)
    e = np.concatenate([np.linspace(0, 1, int(n * peak)) ** 2, np.linspace(1, 0, n - int(n * peak)) ** 1.5])
    x = out * e
    pan = np.linspace(-0.6, 0.6, n)
    a = (pan + 1) * math.pi / 4
    return np.vstack([x * np.cos(a), x * np.sin(a)]) * 1.4


for k, fr in enumerate(TL["whooshes"]):
    d = 1.0 if k != 1 else 1.3
    add(sfx, sec(fr) - d * 0.62, whoosh(d, 250 + 60 * k, 4200 + 400 * k), gain=0.32, rev=0.35)

# shimmer on the logo reveal: inharmonic bell partials + air sparkle
t0 = sec(TL["logoShimmer"])
for k, nt in enumerate(["D6", "F#6", "A6", "C#7", "E7", "A7"]):
    f0 = hz(nt)
    tv = tt(2.4)
    x = sum(np.sin(2 * math.pi * f0 * r * tv + k) * g for r, g in [(1, 1), (2.76, 0.35), (5.4, 0.12)])
    x *= np.exp(-tv * 2.2) * env_ar(len(tv), 0.004, 0.3)
    add(sfx, t0 + k * 0.045, x, gain=0.05, pan=-0.6 + 0.24 * k, rev=0.8)
tv = tt(1.6)
spark = hp(rng.standard_normal(len(tv)), 7000) * np.exp(-tv * 3) * env_ar(len(tv), 0.08, 0.4)
add(sfx, t0, np.vstack([spark, np.roll(spark, 97)]), gain=0.05, rev=0.6)

# riser into the flash
tv = tt(0.7)
rise = lp(hp(rng.standard_normal(len(tv)), 1500), 9000) * np.linspace(0, 1, len(tv)) ** 3
add(sfx, sec(TL["deepHit"]) - 0.7, np.vstack([rise, np.roll(rise, 61)]), gain=0.12, rev=0.3)

# deep hit on the white flash: pitch-dropping sine + body + noise thump
t0 = sec(TL["deepHit"])
tv = tt(2.6)
fsweep = 34 + 46 * np.exp(-tv * 9)
boom = np.sin(2 * math.pi * np.cumsum(fsweep) / SR) * np.exp(-tv * 1.6)
body = np.sin(2 * math.pi * 110 * tv) * np.exp(-tv * 14) * 0.35
thump = lp(rng.standard_normal(len(tv)), 400) * np.exp(-tv * 22) * 0.6
hit = (boom + body + thump) * env_ar(len(tv), 0.002, 0.5)
add(sfx, t0, hit, gain=0.75, rev=0.25)

# ------------------------------------------------------------------ reverb (synthetic stereo IR)
ir_t = tt(2.8)
ir = rng.standard_normal((2, len(ir_t))) * np.exp(-ir_t * 2.4)[None, :]
ir = lp(ir, 6500)
ir[:, : int(0.012 * SR)] = 0
ir /= np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
wet = np.vstack([signal.fftconvolve(send[c], ir[c])[:N] for c in range(2)])

mix = music + sfx + 0.35 * wet
mix = hp(mix, 28)
mix *= np.clip(t / 0.05, 0, 1)[None, :]  # click-free start
mix *= np.clip((DUR - t) / 0.08, 0, 1)[None, :]
mix /= np.abs(mix).max() / 0.7
wavfile.write(os.path.join(WORK, "reel_premaster.wav"), SR, mix.T.astype(np.float32))
print("wrote work/reel_premaster.wav", f"{DUR:.2f}s")
