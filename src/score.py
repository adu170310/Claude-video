#!/usr/bin/env python3
"""Athlo launch film - original score and sound design, synthesised from scratch.

96 BPM, D major. A soft ambient bed that builds gently, with subtle hits locked to every
text beat in timeline.py. Writes work/score_premaster.wav (48 kHz stereo float).
"""
import math, os, random, sys
import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import *  # noqa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
N = int(DUR * SR)
rng = np.random.default_rng(3)

music = np.zeros((2, N))   # dry music
sfx = np.zeros((2, N))     # dry effects
send = np.zeros((2, N))    # reverb send

def hz(note):
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    n, o = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[n] + 12 * (o + 1) - 69) / 12)

def add(buf, t0, x, gain=1.0, pan=0.0, rev=0.0):
    """Add mono or stereo x at time t0 with equal-power pan and optional reverb send."""
    i = int(round(t0 * SR))
    if x.ndim == 1:
        a = (pan + 1) * math.pi / 4
        x = np.vstack([x * math.cos(a), x * math.sin(a)]) * math.sqrt(2)
    if i < 0:
        x = x[:, -i:]; i = 0
    n = min(x.shape[1], N - i)
    if n <= 0:
        return
    buf[:, i:i + n] += x[:, :n] * gain
    if rev:
        send[:, i:i + n] += x[:, :n] * gain * rev

def tt(d):
    return np.arange(int(d * SR)) / SR

def env_ar(n, a, r, sr=SR):
    e = np.ones(n)
    na, nr = min(n, int(a * sr)), min(n, int(r * sr))
    if na:
        e[:na] = np.sin(np.linspace(0, math.pi / 2, na)) ** 2
    if nr:
        e[-nr:] *= np.cos(np.linspace(0, math.pi / 2, nr)) ** 2
    return e

def lp(x, fc, order=2):
    sos = signal.butter(order, min(fc, SR * 0.45), "low", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=-1)

def hp(x, fc, order=2):
    sos = signal.butter(order, fc, "high", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=-1)

def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=-1)

# ------------------------------------------------------------------ instruments

def pad_voice(f, dur, bright, att=1.6, rel=2.2, detune=7):
    """Warm additive pad: 3 detuned voices, harmonics rolled off by 'bright' (Hz)."""
    t = tt(dur)
    out = np.zeros((2, len(t)))
    for v, (cents, pan) in enumerate([(-detune, -0.6), (0, 0), (detune, 0.6)]):
        fv = f * 2 ** (cents / 1200)
        vib = 1 + 0.0015 * np.sin(2 * math.pi * (0.17 + 0.05 * v) * t + v)
        ph = 2 * math.pi * fv * np.cumsum(vib) / SR
        s = np.zeros(len(t))
        for n in range(1, 14):
            if n * fv > 9000:
                break
            amp = (1 / n) * math.exp(-(n * fv) / bright)
            s += amp * np.sin(n * ph + rng.uniform(0, 6.28))
        a = (pan + 1) * math.pi / 4
        out[0] += s * math.cos(a); out[1] += s * math.sin(a)
    return out * env_ar(len(t), att, rel) / 3

def chord(t0, t1, notes, gain, bright, att=1.6, rel=2.2):
    for nt in notes:
        f = hz(nt)
        w = 1.0 / (1 + 0.15 * max(0, math.log2(f / 220)))
        add(music, t0, pad_voice(f, t1 - t0 + rel * 0.5, bright, att, rel), gain * w / math.sqrt(len(notes)),
            rev=0.45)

def bell(f, dur=2.4, bright=1.0):
    t = tt(dur)
    s = (np.sin(2 * math.pi * f * t) * np.exp(-t / (0.9 * dur / 2.4))
         + 0.35 * bright * np.sin(2 * math.pi * f * 2.0 * t) * np.exp(-t / 0.45)
         + 0.18 * bright * np.sin(2 * math.pi * f * 3.01 * t) * np.exp(-t / 0.22)
         + 0.08 * bright * np.sin(2 * math.pi * f * 4.2 * t) * np.exp(-t / 0.12))
    return s * env_ar(len(t), 0.004, 0.05)

def pluck(f, dur=0.9):
    t = tt(dur)
    s = np.sin(2 * math.pi * f * t) + 0.3 * np.sin(2 * math.pi * 2 * f * t) * np.exp(-t / 0.08)
    return lp(s * np.exp(-t / 0.28) * env_ar(len(t), 0.003, 0.05), 3800)

def thump(f0=95, f1=42, dur=0.6, click=0.25):
    t = tt(dur)
    f = f1 + (f0 - f1) * np.exp(-t / 0.045)
    s = np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t / 0.18)
    c = hp(rng.normal(0, 1, len(t)), 2500) * np.exp(-t / 0.004) * click
    return (s + c) * env_ar(len(t), 0.001, 0.08)

def hat(dur=0.08):
    t = tt(dur)
    return hp(rng.normal(0, 1, len(t)), 7500, 4) * np.exp(-t / 0.018)

def tick(f=2400, dur=0.05, noise=0.4):
    t = tt(dur)
    s = np.sin(2 * math.pi * f * t) * np.exp(-t / 0.012) + noise * hp(rng.normal(0, 1, len(t)), 3000) * np.exp(-t / 0.003)
    return s * env_ar(len(t), 0.0005, 0.01)

def ping(f, dur=0.35):
    t = tt(dur)
    s = np.sin(2 * math.pi * f * t) * np.exp(-t / 0.06)
    s2 = np.sin(2 * math.pi * f * 1.5 * t) * np.exp(-np.maximum(0, t - 0.07) / 0.08) * (t > 0.07)
    return (s + 0.8 * s2) * env_ar(len(t), 0.002, 0.03)

def shaped_noise(dur, centre, width_oct, amp, seed=0):
    """Noise through a time-varying band (STFT domain). centre/amp: functions of 0..1."""
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    x = r.normal(0, 1, n + 4096)
    f, tf, Z = signal.stft(x, SR, nperseg=2048, noverlap=1536)
    pos = np.clip(tf / dur, 0, 1)
    c = np.array([centre(p) for p in pos])
    a = np.array([amp(p) for p in pos])
    lf = np.log2(np.maximum(f, 1))[:, None]
    g = np.exp(-0.5 * ((lf - np.log2(c)[None, :]) / width_oct) ** 2) * a[None, :]
    _, y = signal.istft(Z * g, SR, nperseg=2048, noverlap=1536)
    y = y[:n]
    return y / (np.abs(y).max() + 1e-9)

def whoosh(t_peak, dur=0.9, f0=300, f1=4000, gain=0.12, pan0=0.6, pan1=-0.6, seed=1):
    """Air whoosh peaking at t_peak, sweeping pan (follows a slide from right to left)."""
    pk = 0.8
    y = shaped_noise(dur, lambda p: f0 * (f1 / f0) ** (min(p / pk, 1) ** 1.3), 0.9,
                     lambda p: (p / pk) ** 2.2 if p < pk else math.exp(-(p - pk) * 14), seed)
    t0 = t_peak - pk * dur
    n = len(y)
    pans = np.linspace(pan0, pan1, n)
    a = (pans + 1) * math.pi / 4
    st = np.vstack([y * np.cos(a), y * np.sin(a)]) * math.sqrt(2)
    add(sfx, t0, st, gain, rev=0.25)

def riser(t0, t1, gain=0.14, seed=5):
    d = t1 - t0
    y = shaped_noise(d, lambda p: 250 * (6000 / 250) ** (p ** 1.5), 1.1, lambda p: p ** 2.5, seed)
    t = tt(d)[:len(y)]
    tone = np.sin(2 * math.pi * np.cumsum(110 * 2 ** (2 * (t / d) ** 2)) / SR) * (t / d) ** 3 * 0.35
    add(sfx, t0, (y + tone) * env_ar(len(y), 0.01, 0.03), gain, rev=0.3)

def impact(t0, gain=1.0, notes=("D4", "A4", "F#5")):
    add(sfx, t0, thump(80, 34, 2.2, 0.15) * 0.9, gain * 0.55, rev=0.15)
    tl = tt(2.0)
    boom = lp(rng.normal(0, 1, len(tl)), 180) * np.exp(-tl / 0.5)
    add(sfx, t0, boom / (np.abs(boom).max() + 1e-9), gain * 0.18, rev=0.3)
    for i, nt in enumerate(notes):
        add(sfx, t0 + 0.012 * i, bell(hz(nt), 4.0, 0.6), gain * 0.05, pan=(i - 1) * 0.4, rev=0.9)
    sh = shaped_noise(2.5, lambda p: 7000, 0.6, lambda p: math.exp(-p * 4), 9)
    add(sfx, t0, sh, gain * 0.025, rev=0.6)

def hit(t0, note, gain=1.0, sub=1.0, pan=0.0):
    """The text hit: soft low thump + glassy bell + a breath of air."""
    add(sfx, t0, thump(90, 48, 0.7, 0.25), 0.22 * gain * sub, rev=0.12)
    add(sfx, t0, bell(hz(note), 2.6), 0.07 * gain, pan=pan, rev=0.7)
    air = shaped_noise(0.5, lambda p: 6000, 0.7, lambda p: math.exp(-p * 9), int(t0 * 100))
    add(sfx, t0, air, 0.025 * gain, rev=0.3)

# ------------------------------------------------------------------ music

# chord plan: (start, end, notes, gain, brightness Hz)
CH = [
    (0.0, 5.2, ["D2", "A2", "D3"], 0.20, 500),
    (4.8, 11.0, ["B1", "F#2", "D3", "C#4"], 0.22, 900),
    (10.7, 15.2, ["D2", "A2", "F#3", "C#4", "E4"], 0.26, 1500),
    (15.0, 17.6, ["G2", "D3", "F#3", "B3", "A4"], 0.26, 1700),
    (17.5, 20.1, ["F#2", "A2", "D3", "F#3", "A4"], 0.26, 1800),
    (20.0, 22.6, ["E2", "B2", "D3", "G3", "F#4"], 0.27, 1900),
    (22.5, 25.1, ["A2", "E3", "A3", "D4", "E4"], 0.27, 2000),
    (25.0, 27.6, ["D2", "A2", "F#3", "A3", "E4"], 0.27, 2200),
    (27.5, 30.1, ["B1", "F#2", "D3", "A3", "F#4"], 0.27, 2300),
    (30.0, 32.6, ["G2", "D3", "B3", "F#4", "A4"], 0.28, 2400),
    (32.5, 36.4, ["A2", "E3", "A3", "C#4", "E4"], 0.28, 2600),
    (36.2, 45.0, ["D2", "A2", "F#3", "A3", "C#4", "E4", "A4"], 0.30, 2800),
]
for i, (a, b, notes, g, br) in enumerate(CH):
    chord(a, b, notes, g, br * 1.45, att=2.5 if i == 0 else 1.2, rel=1.6 if i < len(CH) - 1 else 3.5)

ROOTS = [(11.0, "D2"), (15.0, "G1"), (17.5, "F#1"), (20.0, "E1"), (22.5, "A1"), (25.0, "D2"), (27.5, "B1"),
         (30.0, "G1"), (32.5, "A1"), (36.25, "D2")]
for i, (a, nt) in enumerate(ROOTS):
    b = ROOTS[i + 1][0] if i + 1 < len(ROOTS) else 44.0
    t = tt(b - a + 0.6)
    f = hz(nt)
    s = (np.sin(2 * math.pi * f * t) + 0.45 * np.sin(4 * math.pi * f * t) + 0.12 * np.sin(6 * math.pi * f * t)) * env_ar(len(t), 0.5, 0.6)
    g = 0.06 if a < 25 else 0.08
    add(music, a, s, g)

# tension in the clutter: a faint clock that speeds up toward the collapse
t = S2 + 0.3
while t < COLLAPSE:
    p = (t - S2) / (COLLAPSE - S2)
    add(sfx, t, tick(3200, 0.04, 0.6), 0.03 + 0.03 * p, pan=0.3 if int(t * 8) % 2 else -0.3)
    t += BEAT / (2 if p < 0.5 else 4)

# heartbeat: soft kick on every beat from the tagline, building
b = S3
while b < LOGO - 0.01:
    k = 0.11 if b < 25 else 0.16
    if b < LANDS[0] - SLIDE or (b - S3) % (2 * BEAT) < 1e-6 or b >= 25:
        add(music, b, thump(70, 38, 0.5, 0.05), k)
    b += BEAT
# light hats and an arpeggio once the app screens arrive
ARP = {25.0: ["D4", "F#4", "A4", "E5"], 27.5: ["B3", "D4", "F#4", "A4"], 30.0: ["G4", "B4", "D5", "F#5"],
       32.5: ["A3", "C#4", "E4", "A4"]}
for start, notes in ARP.items():
    for j in range(8 if start < 32.5 else 12):
        tn = start + j * BEAT / 2
        if tn >= LOGO - 0.05:
            break
        add(music, tn, pluck(hz(notes[j % 4]) * (2 if j % 8 >= 4 else 1)), 0.05, pan=-0.35 if j % 2 else 0.35, rev=0.55)
        add(music, tn + BEAT / 4, hat(), 0.012, pan=0.25)

# ------------------------------------------------------------------ sound design

hit(OPEN_IN, "D5", 0.9, sub=1.3)
add(sfx, OPEN_IN, shaped_noise(3.0, lambda p: 900, 1.4, lambda p: math.exp(-p * 2.5), 21), 0.03, rev=0.6)
# scatter: the letters drift away as tiny glints
r = random.Random(2)
for i in range(26):
    tg = SCATTER + r.uniform(0, 1.6)
    add(sfx, tg, bell(r.choice([hz("A5"), hz("D6"), hz("E6"), hz("F#6")]), 0.8, 0.3), 0.012 * (1 - (tg - SCATTER) / 2),
        pan=r.uniform(-0.9, 0.9), rev=0.7)

# clutter: notification pings, a buzzing phone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
r = random.Random(9)
for i in range(15):
    tp = S2 + 0.15 + r.uniform(0, 2.0)
    add(sfx, tp, ping(r.choice([1320, 1480, 1760, 1175, 990])), 0.035, pan=r.uniform(-0.8, 0.8), rev=0.3)
for tb in (6.1, 8.4):
    tl = tt(0.42)
    buzz = signal.square(2 * math.pi * 165 * tl, 0.3) * (0.6 + 0.4 * np.sin(2 * math.pi * 24 * tl))
    add(sfx, tb, lp(buzz, 900) * env_ar(len(tl), 0.02, 0.05), 0.05, pan=0.4)
for i, tc in enumerate(CAPS):
    add(sfx, tc, tick(1800, 0.06, 0.3), 0.08, rev=0.3)
    add(sfx, tc, thump(110, 60, 0.3, 0.1), 0.12)
riser(COLLAPSE - 1.3, MERGE - 0.02, 0.10)
whoosh(MERGE - 0.05, 1.1, 3000, 250, 0.10, -0.5, 0.5, seed=4)
impact(MERGE, 1.0, ("D4", "A4", "F#5"))
hit(ONE_APP, "A5", 0.6, sub=0.6)
whoosh(S2_OUT + 0.4, 0.8, 600, 3000, 0.05, 0, 0, seed=7)

# tagline: each word on its beat, rising notes
for i, (tw, nt) in enumerate(zip(WORDS, ["D5", "E5", "F#5", "A5", "D6"])):
    hit(tw, nt, 1.0 if i < 4 else 1.25, sub=1.0 if i < 4 else 1.4, pan=(-0.2, 0.2, -0.1, 0.1, 0)[i])
for j, nt in enumerate(["D5", "F#5", "A5", "D6", "F#6"]):
    add(sfx, FULL + j * 0.06, bell(hz(nt), 2.5, 0.4), 0.025, pan=-0.5 + j * 0.25, rev=0.9)
add(sfx, FULL, shaped_noise(2.0, lambda p: 5000, 0.8, lambda p: math.sin(math.pi * p), 33), 0.03, rev=0.5)
whoosh(S3_OUT + 0.35, 0.8, 500, 3500, 0.06, 0.3, -0.3, seed=8)

# app screens: a slide whoosh into each landing, then UI taps
for i, land in enumerate(LANDS):
    whoosh(land - 0.12, SLIDE + 0.2, 350, 3800, 0.10, 0.7, -0.5, seed=11 + i)
    add(sfx, land, thump(100, 55, 0.35, 0.15), 0.16, rev=0.15)
    add(sfx, land, tick(2000, 0.05, 0.2), 0.05, rev=0.2)
L1, L2, L3, L4 = LANDS
for c in range(19):  # typing "Padel, Dubai Marina"
    add(sfx, L1 - 0.25 + c * 0.7 / 19, tick(4200 + 300 * (c % 3), 0.025, 0.8), 0.018, pan=0.15)
add(sfx, L1 + 0.45, tick(1500, 0.05, 0.3), 0.06)
for tp in (0.2, 0.75, 1.42):
    add(sfx, L2 + tp, tick(1500, 0.05, 0.3), 0.06)
for j, nt in enumerate(["A5", "D6"]):
    add(sfx, L2 + 1.55 + j * 0.09, bell(hz(nt), 1.2, 0.5), 0.03, rev=0.6)
add(sfx, L3 + 0.75, tick(1500, 0.05, 0.3), 0.06)
for j, nt in enumerate(["F#5", "A5", "D6"]):
    add(sfx, L3 + 0.95 + j * 0.08, bell(hz(nt), 1.2, 0.5), 0.028, rev=0.6)
for j, nt in enumerate(["D5", "E5", "F#5", "A5"]):   # rank #7 -> #3
    add(sfx, L4 + 0.35 + (j + 0.5) * 1.3 / 4, bell(hz(nt), 0.9, 0.5), 0.03, rev=0.6)
add(sfx, L4 + 1.7, bell(hz("D6"), 1.6, 0.5), 0.035, rev=0.7)

# close
whoosh(S4_OUT + 0.45, 0.9, 3000, 400, 0.06, -0.4, 0.4, seed=19)
riser(LOGO - 1.5, LOGO - 0.02, 0.10, seed=6)
impact(LOGO, 1.1, ("D4", "A4", "D5", "F#5"))
add(sfx, WORDMARK, shaped_noise(1.4, lambda p: 6500, 0.6, lambda p: math.sin(math.pi * min(1, p * 1.3)), 41), 0.025, rev=0.6)
hit(LINE, "A5", 0.75, sub=0.7)
hit(CTA, "F#5", 0.6, sub=0.5)
add(sfx, PILL, ping(1760, 0.3), 0.03, rev=0.4)

# ------------------------------------------------------------------ mix

def reverb_ir(dur=3.4, rt=2.6, seed=12):
    r = np.random.default_rng(seed)
    t = tt(dur)
    decay = np.exp(-6.9 * t / rt)
    ir = r.normal(0, 1, (2, len(t))) * decay
    ir = lp(ir, 6500)
    ir[:, :int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
    return ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True))

ir = reverb_ir()
wet = np.vstack([signal.fftconvolve(send[c], ir[c])[:N] for c in range(2)])
wet = hp(wet, 180)

# gentle build: the music bed rises section by section
tl = np.arange(N) / SR
auto = np.interp(tl, [0, 15, 25, 25.5, 36, 36.5, 45], [1.0, 0.92, 0.95, 1.0, 1.0, 1.12, 1.12])
mix = music * auto + sfx * 1.0 + wet * 0.55
mix = hp(mix, 35)
# gentle bus glue: soft saturation
mix = np.tanh(mix * 1.4) / 1.4
# fades: in from silence, out over the last 2.2 s
fi = int(0.05 * SR); fo = int(2.2 * SR)
mix[:, :fi] *= np.linspace(0, 1, fi)
mix[:, -fo:] *= np.cos(np.linspace(0, math.pi / 2, fo)) ** 2

from scipy.io import wavfile
out = os.path.join(ROOT, "work", "score_premaster.wav")
pk = np.abs(mix).max()
wavfile.write(out, SR, (mix / pk * 0.5).T.astype(np.float32))
print("wrote", out, f"peak {20 * math.log10(pk):.1f} dBFS before normalising")
