#!/usr/bin/env python3
"""Athlo launch film (30 s cut) - original score and sound design, synthesised from scratch.

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

# chord plan: (start, end, notes, gain, brightness Hz). The bed is already playing on frame one.
CH = [
    (0.0, 4.5, ["B1", "F#2", "D3", "C#4"], 0.25, 900),
    (4.3, 7.6, ["D2", "A2", "F#3", "C#4", "E4"], 0.27, 1500),
    (7.5, 10.1, ["G2", "D3", "F#3", "B3", "A4"], 0.26, 1700),
    (10.0, 12.6, ["F#2", "A2", "D3", "F#3", "A4"], 0.26, 1800),
    (12.5, 15.1, ["E2", "B2", "D3", "G3", "F#4"], 0.27, 1900),
    (15.0, 17.6, ["B1", "F#2", "D3", "A3", "F#4"], 0.27, 2100),
    (17.5, 20.1, ["G2", "D3", "B3", "F#4", "A4"], 0.28, 2300),
    (20.0, 22.6, ["A2", "E3", "A3", "C#4", "E4"], 0.28, 2500),
    (22.4, 30.0, ["D2", "A2", "F#3", "A3", "C#4", "E4", "A4"], 0.30, 2800),
]
for i, (a, b, notes, g, br) in enumerate(CH):
    chord(a, b, notes, g, br * 1.45, att=0.3 if i == 0 else 1.0, rel=1.4 if i < len(CH) - 1 else 3.0)

ROOTS = [(0.0, "B1"), (4.375, "D2"), (7.5, "G1"), (10.0, "F#1"), (12.5, "E1"), (15.0, "B1"), (17.5, "G1"),
         (20.0, "A1"), (22.5, "D2")]
for i, (a, nt) in enumerate(ROOTS):
    b = ROOTS[i + 1][0] if i + 1 < len(ROOTS) else 30.0
    t = tt(b - a + 0.6)
    f = hz(nt)
    s = (np.sin(2 * math.pi * f * t) + 0.45 * np.sin(4 * math.pi * f * t) + 0.12 * np.sin(6 * math.pi * f * t)) * env_ar(len(t), 0.25, 0.6)
    add(music, a, s, 0.05 if a < 7.5 else 0.07)

# the chaos: a clock that speeds up until everything collapses
t = 0.0
while t < COLLAPSE:
    p = t / COLLAPSE
    add(sfx, t, tick(3200, 0.04, 0.6), 0.03 + 0.035 * p, pan=0.3 if int(t * 8) % 2 else -0.3)
    t += BEAT / (2 if p < 0.45 else 4)

# heartbeat from the first word, then an arpeggio and light hats as it builds
b = WORDS[0]
while b < LOGO - 0.01:
    add(music, b, thump(70, 38, 0.5, 0.05), 0.11 if b < 15 else 0.15)
    b += BEAT
ARP = {12.5: ["E4", "G4", "B4", "F#5"], 15.0: ["B3", "D4", "F#4", "A4"], 17.5: ["G4", "B4", "D5", "F#5"],
       20.0: ["A3", "C#4", "E4", "A4"]}
for start, notes in ARP.items():
    for j in range(8):
        tn = start + j * BEAT / 2
        if tn >= LOGO - 0.05:
            break
        add(music, tn, pluck(hz(notes[j % 4]) * (2 if j >= 4 else 1)), 0.05, pan=-0.35 if j % 2 else 0.35, rev=0.55)
        if start >= 15.0:
            add(music, tn + BEAT / 4, hat(), 0.012, pan=0.25)

# ------------------------------------------------------------------ sound design

# hook: an immediate hit with the headline, pings as chats and calls pile up
hit(HOOK_IN, "D5", 0.9, sub=1.2)
from film import clutter  # noqa: E402  (same land times as the picture)
r = random.Random(9)
for it in clutter():
    land = it[4]
    if land > 0:
        add(sfx, land - 0.05, ping(r.choice([1320, 1480, 1760, 1175, 990])), 0.032, pan=r.uniform(-0.8, 0.8), rev=0.3)
for tb in (0.9, 2.7):
    tl = tt(0.42)
    buzz = signal.square(2 * math.pi * 165 * tl, 0.3) * (0.6 + 0.4 * np.sin(2 * math.pi * 24 * tl))
    add(sfx, tb, lp(buzz, 900) * env_ar(len(tl), 0.02, 0.05), 0.05, pan=0.4)
# three letters slip, then click back into line
for j in range(3):
    add(sfx, NUDGE + j * 0.03, tick(2600 + 400 * j, 0.04, 0.5), 0.03, pan=(-0.3, 0.1, 0.4)[j])
add(sfx, NUDGE + 0.8, bell(hz("A5"), 1.0, 0.4), 0.02, rev=0.6)
whoosh(HOOK_OUT + 0.2, 0.5, 800, 3000, 0.03, 0, 0, seed=3)
riser(COLLAPSE - 0.9, MERGE - 0.02, 0.10)
whoosh(MERGE - 0.05, 0.75, 3000, 250, 0.09, -0.5, 0.5, seed=4)
impact(MERGE, 1.0, ("D4", "A4", "F#5"))
whoosh(LOGO_UP + 0.45, 0.8, 300, 2500, 0.05, 0, 0, seed=7)
add(sfx, LOGO_UP + 0.9, thump(100, 55, 0.35, 0.15), 0.12, rev=0.15)
whoosh(APP_OUT + 0.22, 0.5, 600, 3000, 0.04, 0, 0, seed=8)

# five words, five moments: a hit on the beat, a card slide, then the UI detail
NOTES = ["D5", "E5", "F#5", "A5", "D6"]
for i, (w0, nt) in enumerate(zip(WORDS, NOTES)):
    hit(w0, nt, 1.0 if i < 4 else 1.2, sub=1.0 if i < 4 else 1.3, pan=(-0.2, 0.2, -0.1, 0.1, 0)[i])
    whoosh(w0 + 0.12, 0.7, 400, 3500, 0.06, 0.7, -0.3, seed=11 + i)
    w1 = WORDS[i + 1] if i < 4 else RECAP[0]
    whoosh(w1 - 0.1, 0.45, 2500, 600, 0.035, -0.2, -0.8, seed=21 + i)
W1, W2, W3, W4, W5 = WORDS
prev = 0   # Discover: the count 0 -> 13
for f in range(int(0.35 * 30), int(1.3 * 30)):
    k = min(1.0, (f / 30 - 0.35) / 0.9)
    n = int(round(13 * (1 - (1 - k) ** 3)))
    if n != prev:
        add(sfx, W1 + f / 30, tick(3600 + 60 * n, 0.03, 0.4), 0.022, pan=-0.2)
        prev = n
add(sfx, W1 + 1.3, bell(hz("A5"), 1.2, 0.5), 0.028, rev=0.6)
add(sfx, W2 + 0.95, tick(1500, 0.05, 0.3), 0.07)             # Book: tap Find a facility
add(sfx, W2 + 1.02, shaped_noise(0.6, lambda p: 4000, 0.7, lambda p: math.exp(-p * 6), 51), 0.02, rev=0.5)
add(sfx, W3 + 0.85, tick(1500, 0.05, 0.3), 0.07)             # Play: tap the Football chip
add(sfx, W3 + 0.95, pluck(hz("A5")), 0.05, rev=0.5)
for w0, nt in ((W4, "F#5"), (W5, "A5")):                      # Train / Compete: the row lights up
    add(sfx, w0 + 0.4, tick(1800, 0.04, 0.3), 0.04)
    add(sfx, w0 + 1.05, bell(hz(nt), 1.2, 0.5), 0.03, rev=0.6)

# the line builds word by word
for j, (tr, nt) in enumerate(zip(RECAP, ["D5", "F#5", "A5", "D6", "F#6"])):
    add(sfx, tr, bell(hz(nt), 1.8, 0.5), 0.045, pan=-0.4 + j * 0.2, rev=0.8)
    add(sfx, tr, thump(95, 50, 0.35, 0.15), 0.10)
whoosh(RECAP_OUT + 0.2, 0.5, 700, 3000, 0.04, 0, 0, seed=31)
riser(LOGO - 1.3, LOGO - 0.02, 0.09, seed=6)

# end card
impact(LOGO, 1.05, ("D4", "A4", "D5", "F#5"))
add(sfx, LOGO + 0.25, shaped_noise(1.4, lambda p: 6500, 0.6, lambda p: math.sin(math.pi * min(1, p * 1.3)), 41), 0.025, rev=0.6)
hit(LINE, "A5", 0.7, sub=0.7)
whoosh(LINE_OUT + 0.2, 0.5, 600, 2800, 0.035, 0, 0, seed=33)
hit(CTA, "D6", 0.9, sub=0.9)
add(sfx, WHOOP, tick(2200, 0.04, 0.3), 0.04, rev=0.3)
add(sfx, BUTTON, ping(1760, 0.3), 0.035, rev=0.4)
add(sfx, PULSE, tick(1500, 0.05, 0.3), 0.06, rev=0.3)
add(sfx, PULSE + 0.05, bell(hz("D6"), 1.5, 0.5), 0.03, rev=0.6)

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
auto = np.interp(tl, [0, 7.5, 12.5, 22.3, 22.6, 30], [1.0, 0.94, 1.0, 1.0, 1.1, 1.1])
mix = music * auto + sfx * 1.0 + wet * 0.55
mix = hp(mix, 35)
# gentle bus glue: soft saturation
mix = np.tanh(mix * 1.4) / 1.4
# fades: in from silence, out over the last 2.2 s
fi = int(0.01 * SR); fo = int(1.8 * SR)
mix[:, :fi] *= np.linspace(0, 1, fi)
mix[:, -fo:] *= np.cos(np.linspace(0, math.pi / 2, fo)) ** 2

from scipy.io import wavfile
out = os.path.join(ROOT, "work", "score_premaster.wav")
pk = np.abs(mix).max()
wavfile.write(out, SR, (mix / pk * 0.5).T.astype(np.float32))
print("wrote", out, f"peak {20 * math.log10(pk):.1f} dBFS before normalising")
