#!/usr/bin/env python3
"""Original chiptune score + sound effects for the speedrun reel, synthesised from scratch.

Pulse/triangle/noise voices (band-limited with polyBLEP), a punchy synth kick and snare,
and every SFX cued from timeline.py. No samples, no borrowed melodies.
-> work/speedrun/score_premaster.wav
"""
import math, os, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import *

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work", "speedrun")
SR = 48000
LEN = int(DUR * SR)
L = np.zeros(LEN); R = np.zeros(LEN)
rng = np.random.default_rng(2026)

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)

def at(b): return int(round(tb(b) * SR))

def add(x, b_or_s, pan=0.0, gain=1.0, secs=False):
    i = int(round(b_or_s * SR)) if secs else at(b_or_s)
    if i >= LEN: return
    x = x[:LEN - i] * gain
    gl, gr = math.cos((pan + 1) * math.pi / 4) * 1.414, math.sin((pan + 1) * math.pi / 4) * 1.414
    L[i:i + len(x)] += x * gl; R[i:i + len(x)] += x * gr

def env(n, a=0.002, d=0.1, s=0.6, r=0.05, hold=None):
    t = np.arange(n) / SR
    hold = (n / SR - r) if hold is None else hold
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rel = np.clip((t - hold) / r, 0, 1)
    return e * (1 - rel)

def _blep(t, dt):
    y = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]; y[m] = x + x - x * x - 1
    m = t > 1 - dt
    x = (t[m] - 1) / dt[m]; y[m] = x * x + x + x + 1
    return y

def pulse(f, n, duty=0.5, vib=0.0, vrate=6.0):
    f = np.broadcast_to(np.asarray(f, float), (n,)).copy()
    if vib: f *= 2 ** (vib / 12 * np.sin(2 * np.pi * vrate * np.arange(n) / SR))
    dt = np.clip(f / SR, 1e-6, 0.45)
    ph = np.cumsum(dt) % 1.0
    s = np.where(ph < duty, 1.0, -1.0)
    s += _blep(ph, dt) - _blep((ph - duty) % 1.0, dt)
    return s * 0.5

def tri(f, n):
    f = np.broadcast_to(np.asarray(f, float), (n,))
    ph = np.cumsum(f / SR) % 1.0
    x = 4 * np.abs(ph - 0.5) - 1
    return np.round(x * 8) / 8          # 4-bit stepped, chip style

def noise(n): return rng.uniform(-1, 1, n)

def hp(x, fc, o=2): return signal.sosfilt(signal.butter(o, fc, "hp", fs=SR, output="sos"), x)
def lp(x, fc, o=2): return signal.sosfilt(signal.butter(o, fc, "lp", fs=SR, output="sos"), x)
def bp(x, lo, hi): return signal.sosfilt(signal.butter(2, [lo, hi], "bp", fs=SR, output="sos"), x)

# ---------------------------------------------------------------- drums
def kick(big=1.0):
    n = int(0.42 * SR); t = np.arange(n) / SR
    f = 48 + 140 * np.exp(-t * 32) + 60 * np.exp(-t * 300)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (7.5 / big))
    x += 0.5 * hp(noise(n), 2500) * np.exp(-t * 300)          # click
    return np.tanh(x * 2.2) * 0.8

def snare():
    n = int(0.3 * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(190 + 60 * np.exp(-t * 40)) / SR) * np.exp(-t * 26)
    sn = bp(noise(n), 1200, 9000) * np.exp(-t * 16)
    return np.tanh((0.7 * body + 1.1 * sn) * 1.5) * 0.6

def hat(open_=False):
    n = int((0.22 if open_ else 0.05) * SR); t = np.arange(n) / SR
    return hp(noise(n), 7000) * np.exp(-t * (14 if open_ else 80)) * 0.35

def crash():
    n = int(1.8 * SR); t = np.arange(n) / SR
    return hp(noise(n), 4000) * np.exp(-t * 2.4) * 0.45

# ---------------------------------------------------------------- instruments
def note_pulse(m, dur_b, duty=0.25, vol=0.3, vib=0.0, d=0.12, s=0.55):
    n = int(tb(dur_b) * SR)
    return pulse(hz(m), n, duty, vib) * env(n, 0.002, d, s, 0.03) * vol

def note_bass(m, dur_b, vol=0.5):
    n = int(tb(dur_b) * SR)
    return tri(hz(m), n) * env(n, 0.002, 0.2, 0.8, 0.02) * vol

# chords (MIDI roots + quality) per bar of 4 beats
MIN, MAJ = (0, 3, 7), (0, 4, 7)
def chord_at(b):
    if b < 6:   return 57, MIN                                 # Am
    if b < 38:
        prog = [(57, MIN), (53, MAJ), (48, MAJ), (55, MAJ)]    # Am F C G
        return prog[int((b - 6) // 4) % 4]
    if b < 44:  return [(57, MIN), (58, MAJ)][int((b - 38) // 2) % 2]   # boss: Am / Bb
    if b < 48:  return (53, MAJ) if b < 46 else (55, MAJ)       # power-up: F -> G
    if b < 50:  return 48, MAJ                                 # victory: C
    prog = [(53, MAJ), (55, MAJ), (57, MIN), (48, MAJ)]        # end: F G Am C
    return prog[int((b - 50) // 4) % 4] if b < 62 else (48, MAJ)

# ---------------------------------------------------------------- arrangement
def drums():
    for b in range(0, 64):
        sec_boss = BOSS0 <= b < POWER0
        sec_pow = POWER0 <= b < WIN
        if sec_pow: continue
        if b < SESS0:
            add(kick(), b, gain=0.95)                          # four-on-the-floor from frame one
            add(hat(), b + 0.5, 0.3, 0.8)
            continue
        if sec_boss:
            rel = (b - BOSS0) % 4
            if rel in (0,): add(kick(1.4), b, gain=1.0)
            if rel == 2: add(snare(), b, gain=1.0); add(kick(1.4), b + 0.5, gain=0.7)
            if rel == 1: add(kick(1.2), b + 0.5, gain=0.8)
            add(hat(), b + 0.5, 0.3, 0.6)
            continue
        add(kick(), b, gain=1.0)
        if b % 2 == 1: add(snare(), b, gain=0.9)
        sub = 4 if COMBO0 <= b < BOSS0 else 2
        for k in range(sub):
            if k == 0: continue
            add(hat(open_=(sub == 2 and k == 1 and b % 4 == 3)), b + k / sub, 0.35 if k % 2 else -0.35, 0.7)
        add(hat(), b, -0.3, 0.4)
    # snare roll into the boss
    for k in range(8):
        add(snare(), 37 + k / 8, gain=0.4 + 0.07 * k)
    for b in (SESS0, COMBO0, BOSS0, WIN, CARD):
        add(crash(), b, 0.2, 0.9)

def bassline():
    for i in range(64 * 2):
        b = i / 2
        if POWER0 <= b < WIN or b >= 63.5: continue
        root, q = chord_at(b)
        m = root - 24 + (12 if (i % 2 == 1 and not (BOSS0 <= b < POWER0)) else 0)
        if BOSS0 <= b < POWER0:
            n = int(tb(0.5) * SR)
            x = pulse(hz(root - 24), n, 0.5) * env(n, 0.002, 0.1, 0.7, 0.02) * 0.32
            add(lp(x, 900), b)
        else:
            add(note_bass(m, 0.48, 0.55), b)

def arps():
    for i in range(64 * 4):
        b = i / 4
        if b < 0.0 or (POWER0 <= b < WIN) or (BOSS0 <= b < POWER0) or b >= 62: continue
        root, q = chord_at(b)
        if b < SESS0:   # intro: rising arpeggio that climbs with the loading bar
            m = root + q[i % 3] + 12 * ((i // 3) % 3)
            add(note_pulse(m, 0.24, 0.125, 0.10, d=0.05, s=0.3), b, pan=0.25)
            continue
        pat = [0, 1, 2, 1] if (i // 16) % 2 == 0 else [0, 2, 1, 2]
        m = root + 12 + q[pat[i % 4]]
        vol = 0.07 if b < COMBO0 else 0.09
        add(note_pulse(m, 0.24, 0.125, vol, d=0.04, s=0.25), b, pan=0.3)

def lead():
    # original hook, 2-bar phrases over Am F C G (scale degrees picked to sit on each chord)
    hook = [(0, 76, 1), (1, 79, 0.5), (1.5, 76, 0.5), (2, 74, 1), (3, 72, 1),
            (4, 72, 1), (5, 74, 0.5), (5.5, 76, 0.5), (6, 74, 2)]
    for start in (RANK0 - 1, COMBO0 + 2):
        for o, m, dl in hook:
            b = start + o
            if b >= BOSS0 - 0.5: continue
            add(note_pulse(m, dl * 0.95, 0.5, 0.075, vib=0.15, d=0.2, s=0.6), b, pan=-0.2)
    # boss motif: low, ominous
    for k, m in enumerate([57, 58, 57, 56, 57, 64, 63, 62, 57, 58, 57, 52]):
        add(note_pulse(m, 0.45, 0.5, 0.08, d=0.15, s=0.6), BOSS0 + k * 0.5, pan=-0.15)
    # end theme over F G Am C
    end = [(0, 72, 1), (1, 77, 1), (2, 76, 1), (3, 74, 1), (4, 74, 1.5), (5.5, 76, 0.5), (6, 79, 2),
           (8, 76, 1), (9, 77, 1), (10, 79, 1), (11, 81, 1)]
    for o, m, dl in end:
        add(note_pulse(m, dl * 0.95, 0.5, 0.075, vib=0.2, d=0.25, s=0.6), CARD + o, pan=-0.2)
    # final chord rings out
    n = int(tb(2.0) * SR)
    for m in (60, 64, 67, 72):
        add(pulse(hz(m), n, 0.25, 0.1) * env(n, 0.004, 0.5, 0.5, 0.6) * 0.06, 62, pan=(m - 66) / 12)
    add(note_bass(36, 2.0, 0.55), 62)

# ---------------------------------------------------------------- SFX
def blip(m, dur=0.06, duty=0.25, vol=0.25):
    n = int(dur * SR)
    return pulse(hz(m), n, duty) * env(n, 0.001, dur / 2, 0.4, 0.01) * vol

def seq(notes, step, duty=0.25, vol=0.25, dur=None):
    n = int((step * len(notes) + (dur or step)) * SR)
    out = np.zeros(n)
    for k, m in enumerate(notes):
        x = blip(m, dur or step * 0.95, duty, vol)
        i = int(k * step * SR); out[i:i + len(x)] += x
    return out

def sweep(f0, f1, dur, duty=0.5, vol=0.2, curve="exp"):
    n = int(dur * SR); t = np.linspace(0, 1, n)
    f = f0 * (f1 / f0) ** t if curve == "exp" else f0 + (f1 - f0) * t
    return pulse(f, n, duty) * env(n, 0.002, dur, 0.8, 0.02) * vol

def sparkle_sfx():
    n = int(0.45 * SR); out = np.zeros(n)
    for k in range(9):
        m = 96 + int(rng.integers(-5, 7))
        x = blip(m, 0.035, 0.5, 0.12 * (1 - k / 10))
        i = int(k * 0.045 * SR); out[i:i + len(x)] += x
    return out

def sfx():
    # intro: loading ticks + "GO!" stab
    for k in range(16):
        add(blip(72 + k, 0.03, 0.5, 0.10), k * 0.25 + 0.0, pan=0.1)
    add(sweep(200, 1600, tb(1), 0.5, 0.08), 4)
    for m in (69, 72, 76, 81):
        add(note_pulse(m, 0.9, 0.5, 0.10, d=0.3, s=0.4), GO, pan=(m - 75) / 10)
    add(kick(1.3), GO, gain=0.6)
    # sessions: log blip, achievement jingle, sparkle, XP jump
    for i, s in enumerate(SESS):
        add(seq([79, 84], 0.05, 0.5, 0.18), s, pan=-0.2)
        jingle = [72 + i, 76 + i, 79 + i, 84 + i]
        add(seq(jingle, 0.055, 0.25, 0.20, dur=0.09), s + 1, pan=0.1)
        add(sparkle_sfx(), s + 1.25, pan=0.4)
        add(sweep(300, 1400, 0.22, 0.125, 0.10), s + 1, pan=-0.4)
    # rank rolls: rapid counter ticks then a ding
    for k, (b, a, z) in enumerate(RANKS + [RANK_WIN]):
        if b == RANK_WIN[0]: continue
        for j in range(14):
            tt = tb(b) + 0.9 * B * (1 - (1 - j / 14) ** 2)
            add(blip(84 + k * 2 + (j % 2) * 5, 0.025, 0.5, 0.10), tt, pan=0.5, secs=True)
        add(seq([88 + k * 2, 95 + k * 2], 0.06, 0.25, 0.16, dur=0.2), b + 0.95, pan=0.5)
    # combo: rising stabs and a zap on every flash
    for k, (b, n) in enumerate(COMBOS):
        root = [69, 72, 76][k]
        for m in (root, root + 4, root + 7, root + 12):
            add(note_pulse(m, 0.6, 0.5, 0.06, d=0.15, s=0.3), b)
        nxt = COMBOS[k + 1][0] if k + 1 < len(COMBOS) else BOSS0
        step = [2, 1, 0.5][k]; x = b
        while x < nxt - 1e-6:
            add(sweep(2400, 500, 0.08, 0.5, 0.07), x, pan=0.3 * (1 if int(x * 2) % 2 else -1)); x += step
    # boss: two-tone alarm, stomps
    for k in range(8):
        add(blip(81 if k % 2 == 0 else 76, tb(0.45), 0.5, 0.12), BOSS0 + k * 0.5)
    for s in STOMPS:
        n = int(0.6 * SR); t = np.arange(n) / SR
        boom = lp(noise(n), 300) * np.exp(-t * 6) * 1.6
        drop = pulse(220 * np.exp(-t * 5) + 40, n, 0.5) * np.exp(-t * 7) * 0.25
        add(np.tanh(boom + drop), s, gain=0.7)
        add(kick(1.6), s, gain=0.8)
    # power-up: appear shimmer, collect arpeggio, riser to victory
    add(seq([84, 91, 96, 91] * 3, 0.06, 0.125, 0.07), POWER0, pan=0.2)
    collect = [60, 64, 67, 72, 64, 67, 72, 76, 67, 72, 76, 79, 72, 76, 79, 84]
    add(seq(collect, 0.032, 0.25, 0.18), COLLECT)
    n = int(tb(WIN - COLLECT - 0.6) * SR)
    add(hp(noise(n), 2000) * np.linspace(0, 1, n) ** 2 * 0.12, COLLECT + 0.6)
    add(sweep(150, 1200, tb(WIN - COLLECT - 0.6), 0.5, 0.05), COLLECT + 0.6)
    # victory sting: original fanfare
    fan = [(0, 72, 0.33), (0.33, 76, 0.33), (0.67, 79, 0.33), (1.0, 84, 1.6)]
    for o, m, dl in fan:
        for dm, v, pn in ((0, 0.16, -0.2), (-12, 0.07, 0.2)):
            add(note_pulse(m + dm, dl, 0.5, v, vib=0.25 if dl > 1 else 0, d=0.4, s=0.7), WIN + o, pan=pn)
    for m in (60, 64, 67):
        add(note_pulse(m, 1.8, 0.25, 0.05, d=0.4, s=0.6), WIN + 1.0)
    add(kick(1.5), WIN, gain=0.9)
    # press start: a blip on every blink, then the confirm sound into the end card
    for k in range(CARD - END0):
        add(blip(84, 0.05, 0.5, 0.14), END0 + k)
    add(seq([72, 79, 84, 88, 91, 96], 0.04, 0.5, 0.16), CARD - 0.3)
    add(kick(1.4), CARD, gain=0.8)
    add(seq([91, 96], 0.05, 0.5, 0.12), CARD + 1)   # link-in-bio button pops in

drums(); bassline(); arps(); lead(); sfx()
mixed = np.stack([L, R])
mixed = np.tanh(mixed * 0.9) / 0.9 * 0.9            # glue
fade = int(0.35 * SR)
mixed[:, -fade:] *= np.linspace(1, 0, fade) ** 1.5
mixed[:, :int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
os.makedirs(WK, exist_ok=True)
wavfile.write(os.path.join(WK, "score_premaster.wav"), SR, (mixed.T * 0.5).astype(np.float32))
print("peak", np.abs(mixed).max())
