#!/usr/bin/env python3
"""Original 18 s score + sound design for the Athlo 30x30 reel. Everything is synthesised here.

Four sections on one 120 BPM grid (1 beat = 15 frames), cue times read from src/timeline.json:
  hook   0.0-1.5  drop preview, punch hit at 0.8, tape-stop into...
  day 1  1.5-4.5  calm lo-fi keys, soft kick, vinyl, satisfying ticks
  day 10 4.5-7.5  same chords, hats + snare + bass: tempo feel picks up, wonky ticks
  day 20 7.5-10.5 tension: pulsing bass, 16th hats, riser, snare roll, buzzes, alarm rattles
  drop  10.5-14   four-on-the-floor, sidechained supersaws, whooshes, deep hit on LOCKED IN.
  sign  14-15.5   clears to a pad and a sparkle; end card 15.5-18 resolves to C major.
Writes work/score_premaster.wav (48 kHz float stereo).
"""
import json, os
import numpy as np
from scipy import signal
from scipy.io import wavfile

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(os.path.join(R, "src", "timeline.json")))
SR, DUR = 48000, T["duration"] / T["fps"]
N = int(SR * DUR)
rng = np.random.default_rng(30)
BEAT = 60 / T["bpm"]
fr = lambda f: f / T["fps"]

music = np.zeros((2, N)); sfx = np.zeros((2, N)); duck = np.ones(N)

def tt(d): return np.arange(int(d * SR)) / SR
def midi(m): return 440.0 * 2 ** ((m - 69) / 12)
def env(n, a=0.005, d=0.2, s=0.0, r=0.05, hold=None):
    t = np.arange(n) / SR; e = np.ones(n)
    e = np.where(t < a, t / max(a, 1e-6), e)
    dec = s + (1 - s) * np.exp(-(t - a) / max(d, 1e-6))
    e = np.where(t >= a, dec, e)
    if r and n > int(r * SR):
        e[-int(r * SR):] *= np.linspace(1, 0, int(r * SR)) ** 2
    return e
def lp(x, fc, order=2): return signal.sosfilt(signal.butter(order, min(fc, SR / 2.2), "low", fs=SR, output="sos"), x)
def hp(x, fc, order=2): return signal.sosfilt(signal.butter(order, fc, "high", fs=SR, output="sos"), x)
def bp(x, lo, hi, order=2): return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x)
def put(bus, x, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N: return
    if x.ndim == 1: x = np.vstack([x * np.sqrt(0.5 * (1 - pan)), x * np.sqrt(0.5 * (1 + pan))]) * 1.414
    j = min(N, i + x.shape[1]); x = x[:, : j - i]
    if i < 0: x = x[:, -i:]; i = 0
    bus[:, i:j] += x * gain
def reverb(x, secs=1.6, mix=0.25, seed=1):
    n = int(secs * SR); r = np.random.default_rng(seed)
    ir = r.standard_normal((2, n)) * np.exp(-np.arange(n) / SR * 6.9 / secs)
    ir[:, : int(0.012 * SR)] = 0
    ir = np.vstack([lp(ir[0], 6000), lp(ir[1], 6000)]) * 0.06
    if x.ndim == 1: x = np.vstack([x, x])
    wet = np.vstack([signal.fftconvolve(x[c], ir[c])[: x.shape[1]] for c in range(2)])
    return x * (1 - mix) + wet * mix

# ------------------------------------------------------------- instruments
def kick(g=1.0, soft=False):
    t = tt(0.45); f = 48 + (150 if not soft else 95) * np.exp(-t * 32)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (7 if not soft else 10))
    click = hp(rng.standard_normal(len(t)), 3000) * np.exp(-t * 300) * (0.25 if not soft else 0.05)
    return np.tanh((x + click) * (1.6 if not soft else 1.0)) * g
def snare(g=1.0, tone=190):
    t = tt(0.25)
    n = bp(rng.standard_normal(len(t)), 1500, 9000) * np.exp(-t * 22)
    b = np.sin(2 * np.pi * tone * t) * np.exp(-t * 30)
    return (n * 0.7 + b * 0.5) * g
def clap(g=1.0):
    t = tt(0.3); n = bp(rng.standard_normal(len(t)), 900, 6000)
    e = sum(np.exp(-np.clip(t - d, 0, None) * 60) * (t >= d) for d in (0, 0.011, 0.023)) + np.exp(-t * 14) * 0.5
    return n * e * 0.6 * g
def hat(g=1.0, open_=False):
    t = tt(0.3 if open_ else 0.07)
    return hp(rng.standard_normal(len(t)), 7500, 4) * np.exp(-t * (14 if open_ else 70)) * g
def keys(notes, d, g=1.0, bright=1.0):
    t = tt(d + 0.6); out = np.zeros(len(t))
    for k, m in enumerate(notes):
        f = midi(m) * (1 + rng.uniform(-0.0015, 0.0015))
        idx = 1.6 * bright * np.exp(-t * 5)
        out += np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t)) * (0.9 ** k)
        out += 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 3)
    e = env(len(t), a=0.008, d=1.1, s=0.35, r=0.5); e[int(d * SR):] *= np.exp(-np.arange(len(t) - int(d * SR)) / SR * 8)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.2 * t)
    return lp(out * e * trem, 2600 * bright) * g / len(notes) ** 0.5
def bass(m, d, g=1.0, drive=1.5):
    t = tt(d); f = midi(m)
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
    return np.tanh(x * drive) * env(len(t), a=0.004, d=0.4, s=0.7, r=0.03) * g
def saws(notes, d, g=1.0, cutoff=4000):
    t = tt(d); out = np.zeros(len(t))
    for m in notes:
        for k, det in enumerate((-0.12, -0.06, 0, 0.06, 0.12)):
            f = midi(m) * 2 ** (det / 12)
            ph = (f * t + rng.uniform()) % 1.0
            out += (2 * ph - 1) * (0.6 if k != 2 else 1.0)
    out = lp(out, cutoff, 2) / (len(notes) * 4)
    return out * env(len(t), a=0.006, d=0.35, s=0.75, r=0.06) * g
def pad(notes, d, g=1.0, cutoff=1800):
    t = tt(d); out = np.zeros(len(t))
    for m in notes:
        for det in (-0.08, 0.0, 0.08):
            out += np.sin(2 * np.pi * midi(m) * 2 ** (det / 12) * t) + 0.3 * np.sin(2 * np.pi * midi(m) * 2 * t)
    e = np.minimum(1, t / 0.35) * np.minimum(1, (d - t) / 0.4)
    return lp(out, cutoff) * e * g / (len(notes) * 3)
def pluck(m, g=1.0):
    t = tt(0.45); f = midi(m)
    x = sum(np.sin(2 * np.pi * f * h * t) / h * np.exp(-t * (6 + 5 * h)) for h in (1, 2, 3, 4))
    return x * g

# ------------------------------------------------------------- SFX
def tick(m=84, g=1.0, wonk=0.0):
    t = tt(0.16); f = midi(m) * (1 - wonk * np.minimum(1, t * 12))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 34) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR) * np.exp(-t * 60)
    x += hp(rng.standard_normal(len(t)), 4000) * np.exp(-t * 500) * 0.3
    return x * g
def buzz(g=1.0):
    t = tt(0.42)
    x = signal.sawtooth(2 * np.pi * 165 * t) * 0.6 + np.sin(2 * np.pi * 82 * t)
    gate = ((t < 0.17) | ((t > 0.23) & (t < 0.4))).astype(float)
    gate = lp(gate, 60)
    x = lp(x * (1 + 0.5 * np.sin(2 * np.pi * 31 * t)), 900) * gate
    return x * g
def rattle(d=0.85, g=1.0):
    t = tt(d); partials = (2093, 2961, 4187, 5233)
    x = sum(np.sin(2 * np.pi * p * t + rng.uniform(0, 6)) / (k + 1) ** 0.6 for k, p in enumerate(partials))
    strike = (np.sin(2 * np.pi * 24 * t) > 0).astype(float)
    strike = np.abs(np.diff(np.concatenate([[0], strike])))  # impulses at each hammer hit
    e = signal.lfilter([1], [1, -np.exp(-1 / (0.025 * SR))], strike)
    clack = hp(rng.standard_normal(len(t)), 2500) * e * 0.5
    fade = np.minimum(1, (d - t) / 0.08)
    return (x * e * 0.7 + clack) * fade * g
def whoosh(d=0.32, g=1.0, up=True):
    t = tt(d); n = rng.standard_normal(len(t))
    e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
    lo, hi = (500, 6000) if up else (6000, 500)
    fc = lo * (hi / lo) ** (t / d)
    out = np.zeros(len(t)); blk = 512
    for i in range(0, len(t), blk):  # time-varying band-pass
        c = fc[i]; sos = signal.butter(2, [c * 0.6, min(c * 1.6, SR / 2.3)], "band", fs=SR, output="sos")
        out[i:i + blk] = signal.sosfilt(sos, n[i:i + blk])
    return out * e * g
def boom(g=1.0):
    t = tt(2.2); f = 30 + 70 * np.exp(-t * 9)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    crack = lp(rng.standard_normal(len(t)), 3500) * np.exp(-t * 18) * 0.7
    return np.tanh((sub * 1.4 + crack) * 1.3) * g
def riser(d, g=1.0):
    t = tt(d); n = rng.standard_normal(len(t)); out = np.zeros(len(t)); blk = 512
    for i in range(0, len(t), blk):
        c = 300 * (40 ** (i / len(t)))
        sos = signal.butter(2, [c * 0.7, min(c * 1.4, SR / 2.3)], "band", fs=SR, output="sos")
        out[i:i + blk] = signal.sosfilt(sos, n[i:i + blk])
    tone = np.sin(2 * np.pi * np.cumsum(220 * 4 ** (t / d)) / SR) * 0.25
    return (out + tone) * (t / d) ** 2 * g
def shimmer(g=1.0):
    t = tt(1.2)
    x = sum(np.sin(2 * np.pi * midi(m) * t) * np.exp(-t * (3 + k)) for k, m in enumerate((96, 100, 103, 107)))
    return x * np.minimum(1, t / 0.01) * g * 0.4
def tapestop(x, d):
    """Slow a stereo buffer to a halt over its length."""
    n = x.shape[1]; rate = np.linspace(1, 0, n) ** 1.4
    pos = np.cumsum(rate); pos = pos[pos < n - 1]
    return np.vstack([np.interp(pos, np.arange(n), x[c]) for c in range(2)]) * np.linspace(1, 0.2, len(pos))

# ------------------------------------------------------------- arrangement
Am, F, C, G = [57, 60, 64, 67], [53, 57, 60, 64], [48, 55, 60, 64], [55, 59, 62, 67]
Fmaj7, Em7, Dm7, Am7 = [53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [45, 52, 55, 60]

def drop_groove(bus, t0, t1, chord_seq, intensity=1.0):
    """Four-on-the-floor with sidechained saws and offbeat bass."""
    b = 0; t = t0
    while t < t1 - 1e-6:
        put(bus, kick(1.0), t, 0.95 * min(intensity, 1.2))
        if b % 2 == 1: put(bus, clap(), t, 0.55)
        put(bus, hat(open_=True), t + BEAT / 2, 0.22, 0.2)
        for s in (0.25, 0.75): put(bus, hat(), t + s * BEAT, 0.16, -0.3)
        b += 1; t += BEAT
    t = t0
    for chord, beats in chord_seq:
        d = beats * BEAT
        if t >= t1: break
        d = min(d, t1 - t)
        s = saws([m + 12 for m in chord], d, 0.55 * intensity, cutoff=5200)
        # sidechain pump on every beat
        tl = np.arange(s.shape[0]) / SR; pump = 1 - 0.75 * np.exp(-((tl % BEAT)) * 14)
        put(bus, reverb(s * pump, 1.2, 0.22), t, 1.0)
        for k in range(int(round(d / (BEAT / 2)))):
            if k % 2 == 1: put(bus, bass(chord[0] - 12, BEAT / 2 * 0.9, 0.55 * intensity, 2.2), t + k * BEAT / 2)
        t += d

# HOOK 0-1.5: drop preview, punch-in hit, tape stop
hook = np.zeros((2, int(1.5 * SR) + SR // 2))
drop_groove(hook, 0.0, 1.5, [(Am, 2), (F, 1)], 0.9)
cut = int(1.2 * SR)
music[:, :cut] += hook[:, :cut]
ts = tapestop(hook[:, cut:int(1.55 * SR)], 0.35)
put(music, ts, 1.2, 1.0)
put(sfx, whoosh(0.22, up=True), fr(T["hook"]["punch"]) - 0.18, 0.35)
put(sfx, boom(0.6)[: int(0.6 * SR)], fr(T["hook"]["punch"]), 0.5)

# DAY 1 1.5-4.5: lo-fi
d1 = fr(T["day1"]["start"])
crackle = (rng.random(N) < 0.0009) * rng.uniform(-1, 1, N); crackle = hp(crackle, 1500) * 0.5
crackle += lp(rng.standard_normal(N), 1200) * 0.012
cm = np.zeros(N); cm[int(d1 * SR):int(fr(T["day20"]["start"]) * SR)] = 1; cm = lp(cm, 8)
music += np.vstack([crackle * cm, np.roll(crackle, 77) * cm]) * 0.5
seq1 = [(Fmaj7, 2), (Em7, 2), (Am7, 2)]
t = d1
for ch, b in seq1:
    put(music, reverb(keys([m + 12 for m in ch], b * BEAT, 0.5), 1.8, 0.3, 2), t, 1.0)
    t += b * BEAT
for k in range(6):
    if k % 2 == 0: put(music, kick(0.55, soft=True), d1 + k * BEAT)
    else: put(music, snare(0.16, 240), d1 + k * BEAT, 1.0, 0.1)
put(sfx, whoosh(0.3, up=False), d1 - 0.22, 0.18)
for i, f in enumerate(T["day1"]["ticks"]):
    put(sfx, reverb(tick([84, 86, 88, 91][i]), 0.7, 0.2), fr(f + 3), 0.45, [-0.2, 0.1, -0.1, 0.2][i])

# DAY 10 4.5-7.5: same chords, busier
d10 = fr(T["day10"]["start"])
seq10 = [(Fmaj7, 2), (Em7, 2), (Dm7, 1), (Am7, 1)]
t = d10
for ch, b in seq10:
    put(music, reverb(keys([m + 12 for m in ch], b * BEAT, 0.5, 1.2), 1.4, 0.25, 3), t, 1.0)
    put(music, bass(ch[0] - 12, b * BEAT * 0.95, 0.4, 1.4), t)
    t += b * BEAT
for k in range(6):
    put(music, kick(0.6, soft=k % 2 == 1), d10 + k * BEAT)
    if k % 2 == 1: put(music, snare(0.32), d10 + k * BEAT, 1.0, 0.05)
    for s in (0, 0.5): put(music, hat(), d10 + (k + s) * BEAT, 0.12 if s else 0.07, 0.3)
put(sfx, whoosh(0.25), fr(T["day10"]["swap"]) - 0.2, 0.25, -0.3)
for i, f in enumerate(T["day10"]["ticks"]):
    put(sfx, tick([84, 83, 81][i], wonk=0.06 * (i + 1)), fr(f + 2), 0.42, [-0.2, 0.2, 0][i])

# DAY 20 7.5-10.5: tension
d20 = fr(T["day20"]["start"]); drop = fr(T["weekend"]["start"])
for k in range(12):  # 8th-note bass pulse on A, opening filter
    tb = d20 + k * BEAT / 2 * 2
for k in range(int((drop - d20) / (BEAT / 2))):
    tb = d20 + k * BEAT / 2
    if tb > drop - 0.12: break
    put(music, lp(bass(45 if k % 8 < 6 else 46, BEAT / 2 * 0.8, 0.28, 2.0), 400 + k * 60), tb)
for k in range(6):
    put(music, kick(0.6), d20 + k * BEAT)
    if k % 2 == 1: put(music, snare(0.25), d20 + k * BEAT)
for k in range(int((drop - d20) / (BEAT / 4))):
    put(music, hat(), d20 + k * BEAT / 4, 0.05 + 0.03 * (k % 2 == 0), 0.35 * (-1) ** k)
put(music, pad([69, 72, 76, 82], drop - d20, 0.28, 2000), d20)  # Am with a b9 rub
roll_t = drop - 1.5; k = 0
while roll_t < drop - 0.12:
    step = BEAT / 2 if roll_t < drop - 1.0 else BEAT / 4 if roll_t < drop - 0.5 else BEAT / 8
    put(music, snare(0.18 + 0.3 * (1 - (drop - roll_t) / 1.5)), roll_t)
    roll_t += step
put(music, riser(2.0, 0.28), drop - 2.0)
for f in T["day20"]["notifs"]:
    put(sfx, buzz(), fr(f) - 0.03, 0.6)
    put(sfx, whoosh(0.18), fr(f) - 0.12, 0.12)
for f in T["day20"]["alarm"]:
    put(sfx, rattle(0.85), fr(f), 0.3, 0.35)

# DROP 10.5-14
w = T["weekend"]; end_drop = fr(w["end"])
drop_groove(music, drop, end_drop, [(Am, 2), (F, 2), (C, 2), (G, 1)], 1.5)
put(sfx, boom(1.0), drop, 0.55)
put(sfx, shimmer(), drop, 0.25)
dirs = [-0.7, 0.7, 0.0, 0.0]
for i, f in enumerate(w["cards"]):
    put(sfx, whoosh(0.24, up=True), fr(f) - 0.12, 0.45, dirs[i])
    put(sfx, kick(0.4, soft=True), fr(f) + 0.12, 0.25)
lk = fr(w["locked"])
put(sfx, whoosh(0.3, up=False), lk - 0.28, 0.3)
put(sfx, reverb(boom(1.0), 2.4, 0.3, 5), lk, 0.95)
put(sfx, shimmer(1.0), lk, 0.3)
dk = np.ones(N); i0 = int(lk * SR); dk[i0:i0 + int(0.9 * SR)] = 1 - 0.45 * np.exp(-np.arange(int(0.9 * SR)) / SR * 3)
duck *= dk
put(sfx, whoosh(0.5, up=False), end_drop - 0.3, 0.35)

# SIGN 14-15.5 and END 15.5-18
s0, e0 = fr(T["sign"]["start"]), fr(T["end"]["start"])
put(music, reverb(pad([57, 64, 69, 71], e0 - s0 + 0.4, 0.8, 1500), 2.5, 0.4, 7), s0)
put(music, bass(33, e0 - s0, 0.4, 1.0), s0)
put(sfx, reverb(shimmer(0.8), 2.0, 0.4, 8), fr(T["sign"]["words"][3]) + 0.05, 0.35)
rev = whoosh(0.6, up=True) * np.linspace(0, 1, int(0.6 * SR)) ** 2
put(sfx, rev, e0 - 0.6, 0.35)
Cmaj9 = [48, 55, 59, 62, 64]
put(music, reverb(pad([m + 12 for m in Cmaj9], DUR - e0, 1.0, 2400), 2.5, 0.35, 9), e0)
put(music, bass(36, DUR - e0, 0.5, 1.1), e0)
arp = [72, 76, 79, 83, 86, 83, 79, 76]
k = 0; ta = e0
while ta < DUR - 0.3:
    put(music, reverb(pluck(arp[k % 8], 0.35), 1.2, 0.3, 10), ta, 1.0, 0.3 * (-1) ** k)
    if k % 2 == 0: put(music, kick(0.45, soft=True), ta)
    k += 1; ta += BEAT / 2
put(sfx, boom(0.5)[: int(0.8 * SR)], e0, 0.35)
put(sfx, tick(91), fr(T["end"]["button"]) + 0.08, 0.4)
put(sfx, shimmer(), fr(T["end"]["button"]) + 0.1, 0.25)

# ------------------------------------------------------------- mix
mix = music * duck * 0.8 + sfx
fade = np.ones(N); nf = int(0.35 * SR); fade[-nf:] = np.linspace(1, 0.0, nf) ** 1.5
mix *= fade

mix = np.vstack([hp(mix[0], 28), hp(mix[1], 28)])
os.makedirs(os.path.join(R, "work"), exist_ok=True)
wavfile.write(os.path.join(R, "work", "score_premaster.wav"), SR, (mix.T / np.abs(mix).max() * 0.8).astype(np.float32))
print("score", mix.shape, "peak", np.abs(mix).max())
