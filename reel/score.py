#!/usr/bin/env python3
"""Original synthesised track + sound design for the Athlo reel. Nothing sampled.

Reads work/reel/cues.json and motion.json (written by picture.py) so every hit and the
ribbon whoosh follow the picture exactly. Writes work/reel/score_premaster.wav (48 kHz stereo).
"""
import json, math, os, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import BEAT, DUR, S, FPS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work", "reel")
SR = 48000
NS = int(DUR * SR)
rng = np.random.default_rng(2026)

music = np.zeros((2, NS))
sfx = np.zeros((2, NS))


def tt(d):
    return np.arange(int(d * SR)) / SR


def add(bus, t0, x, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if x.ndim == 1:
        l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        x = np.vstack([x * l * 1.414, x * r * 1.414])
    if i0 < 0:
        x, i0 = x[:, -i0:], 0
    n = min(x.shape[1], NS - i0)
    if n > 0:
        bus[:, i0:i0 + n] += gain * x[:, :n]


def env(n, a, d, sus=0.0, curve=4.0):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4))
    return e * (sus + (1 - sus) * np.exp(-curve * np.maximum(t - a, 0) / max(d, 1e-4)))


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "lowpass", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "highpass", fs=SR, output="sos"), x)


def noise(d):
    return rng.standard_normal(int(d * SR))


def mtof(m):
    return 440 * 2 ** ((m - 69) / 12)


def saw(f, t, detune=0.0):
    ph = (f * (1 + detune)) * t
    return 2 * (ph - np.floor(ph + 0.5))


# ------------------------------------------------------------------ music: 128 BPM, F major, F - Dm - Bb - C
CHORDS = [(53, [65, 69, 72]), (50, [62, 65, 69]), (46, [62, 65, 70]), (48, [64, 67, 72])]
BAR = 4 * BEAT
END_STAB = S[9] + 7 * BEAT              # last chord stab in the end card
BUILD0, BUILD1 = S[8], S[9]             # logo beat: drums drop out, riser builds


def kick_clean(d=0.32):
    t = tt(d)
    f = 48 + 95 * np.exp(-t * 28)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    click = np.zeros_like(x)
    click[:96] = hp(noise(0.002), 3000)[:96] * 0.4
    return x + click


def clap():
    x = np.zeros(int(0.3 * SR))
    for k, dt in enumerate((0, 0.011, 0.022)):
        n = bp(noise(0.25), 900, 2600)
        e = env(len(n), 0.001, 0.05 if k < 2 else 0.2)
        i = int(dt * SR)
        x[i:i + len(n)] += (n * e)[:len(x) - i]
    return x * 0.8


def hat(open_=False):
    d = 0.18 if open_ else 0.05
    n = hp(noise(d), 7000, 3)
    return n * env(len(n), 0.001, d * 0.5) * (0.6 if open_ else 0.45)


def pad_stab(notes, d, bright=1.0):
    t = tt(d)
    x = np.zeros(len(t))
    for m in notes:
        for dt in (-0.006, 0.0, 0.007):
            x += saw(mtof(m), t, dt)
    x = lp(x / (3 * len(notes)), 2200 * bright)
    return x * env(len(t), 0.004, d * 0.55)


def pluck(m, d=0.22):
    t = tt(d)
    x = saw(mtof(m), t) * 0.6 + np.sin(2 * np.pi * mtof(m) * t) * 0.6
    cutoff = 5200
    return lp(x, cutoff) * env(len(t), 0.002, d * 0.35)


def bass(m, d):
    t = tt(d)
    x = np.sin(2 * np.pi * mtof(m) * t) + 0.35 * lp(saw(mtof(m), t), 700)
    return x * env(len(t), 0.004, d * 0.8, sus=0.4)


nbeats = int(DUR / BEAT) + 1
for b in range(nbeats):
    t0 = b * BEAT
    bar = int(t0 / BAR)
    root, notes = CHORDS[bar % 4]
    in_build = BUILD0 <= t0 < BUILD1 - 1e-6
    after_end = t0 > END_STAB + 1e-6
    if after_end:
        continue
    # four on the floor (drops out for the build)
    if not in_build:
        add(music, t0, kick_clean(), 0.95)
        if b % 2 == 1:
            add(music, t0, clap(), 0.42, 0.05)
        for k in range(2):
            add(music, t0 + k * BEAT / 2 + BEAT / 4, hat(), 0.5, 0.25)
        add(music, t0 + BEAT / 2, hat(open_=(b % 4 == 3)), 0.5, -0.2)
        # off-beat bass + chord stabs (classic upbeat pump)
        add(music, t0 + BEAT / 2, bass(root - 12, BEAT * 0.45), 0.55)
        add(music, t0 + BEAT / 2, pad_stab(notes, BEAT * 0.42), 0.32, 0.0)
    # bright pluck melody on sixteenths, sparse
    if not in_build and S[1] <= t0 < S[8]:
        pat = [0, 2, 1, 2] if bar % 2 == 0 else [2, 1, 0, None]
        n = pat[b % 4]
        if n is not None:
            m = notes[n] + 12
            add(music, t0 + (0.75 * BEAT if b % 2 else 0), pluck(m), 0.16, 0.35 if b % 2 else -0.35)

# build: snare roll accelerating into the end card
roll_t = BUILD0 + BEAT
k = 0
while roll_t < BUILD1 - 0.02:
    frac = (roll_t - BUILD0) / (BUILD1 - BUILD0)
    add(music, roll_t, clap() * 0.6, 0.15 + 0.35 * frac, (-1) ** k * 0.15)
    step = BEAT / 2 if frac < 0.45 else BEAT / 4 if frac < 0.8 else BEAT / 8
    roll_t += step
    k += 1
# held chord through the build
add(music, BUILD0, pad_stab([65, 69, 72, 77], BUILD1 - BUILD0, bright=0.7) * np.linspace(0.3, 1, int((BUILD1 - BUILD0) * SR)), 0.28)
# final stab with a long tail
tail = pad_stab([53, 65, 69, 72, 77], DUR - END_STAB, bright=1.1)
add(music, END_STAB, tail, 0.6)
add(music, END_STAB, kick_clean(), 0.9)
add(music, END_STAB, bass(41, 1.2), 0.6)

# sidechain pump on the music bus from the kick grid
pump = np.ones(NS)
for b in range(nbeats):
    t0 = b * BEAT
    if BUILD0 <= t0 < BUILD1 or t0 > END_STAB:
        continue
    i0 = int(t0 * SR)
    n = min(int(BEAT * SR), NS - i0)
    if n > 0:
        pump[i0:i0 + n] *= 1 - 0.35 * np.exp(-np.arange(n) / SR * 14)
music *= pump

# ------------------------------------------------------------------ sport hits + UI sounds
def mx(*xs):
    """Sum layers of different lengths."""
    out = np.zeros(max(len(x) for x in xs))
    for x in xs:
        out[:len(x)] += x
    return out


def thump(f0, f1, d, k=20):
    t = tt(d)
    f = f1 + (f0 - f1) * np.exp(-t * k)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6 / d)


def s_type():
    n = bp(noise(0.03), 2500, 7000)
    return mx(n * env(len(n), 0.0005, 0.012) * 0.5, 0.2 * thump(1800, 1200, 0.02))


def s_racket():
    return mx(thump(900, 500, 0.08, 40) * 0.6, bp(noise(0.05), 1500, 4500) * env(int(0.05 * SR), 0.0005, 0.012) * 0.6)


def s_ball_pop(scale=1.0):
    body = thump(420 * scale, 210 * scale, 0.16, 30)
    snap = bp(noise(0.04), 1800, 6000) * env(int(0.04 * SR), 0.0005, 0.01)
    return mx(0.9 * body, 0.7 * snap)


def s_step(i):
    d = 0.14
    body = thump(110, 55, d, 25)
    grit = bp(noise(d), 600, 3000) * env(int(d * SR), 0.001, 0.03)
    return mx(0.8 * body, 0.35 * grit * (0.9 + 0.1 * i))


def s_kick_ball():
    return mx(0.9 * thump(160, 70, 0.18, 30), 0.5 * bp(noise(0.05), 800, 4000) * env(int(0.05 * SR), 0.0005, 0.015))


def s_net_swish():
    d = 0.55
    n = bp(noise(d), 1500, 9000)
    t = tt(d)
    rustle = 0.6 + 0.4 * np.sin(2 * np.pi * 34 * t + 6 * t)
    e = np.minimum(1, t / 0.015) * np.exp(-t * 6)
    return mx(n * e * rustle * 0.9, 0.4 * thump(90, 60, 0.2, 10))


def s_bow_creak(dur):
    t = tt(dur)
    f = 70 + 40 * t / dur
    x = signal.sawtooth(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * t))
    return bp(x, 400, 2500) * np.minimum(1, t / 0.05) * 0.25


def s_twang():
    # Karplus-Strong plucked string
    f, d = 98.0, 0.6
    L = int(SR / f)
    buf = rng.uniform(-1, 1, L)
    out = np.zeros(int(d * SR))
    for i in range(len(out)):
        out[i] = buf[i % L]
        buf[i % L] = 0.996 * 0.5 * (buf[i % L] + buf[(i + 1) % L])
    t = tt(d)
    return out * np.exp(-t * 4) * 0.9 * (1 + 0.6 * np.sin(2 * np.pi * 7 * t) * np.exp(-t * 3))


def s_arrow_thunk():
    body = thump(190, 85, 0.22, 22)
    wood = bp(noise(0.08), 300, 1800) * env(int(0.08 * SR), 0.0005, 0.02)
    whizz = bp(noise(0.16), 2000, 8000) * np.linspace(0, 1, int(0.16 * SR)) ** 2
    out = np.zeros(int(0.4 * SR))
    out[:len(whizz)] += 0.25 * whizz
    i = len(whizz)
    out[i:i + len(body)] += 1.1 * body[:len(out) - i]
    out[i:i + len(wood)] += 0.8 * wood[:len(out) - i]
    return out, -0.16


def s_splash():
    d = 0.8
    t = tt(d)
    n = noise(d)
    cut = 9000 * np.exp(-t * 3) + 800
    y = np.zeros_like(n)
    # time-varying one-pole lowpass
    a = np.exp(-2 * np.pi * cut / SR)
    z = 0.0
    for i in range(len(n)):
        z = (1 - a[i]) * n[i] + a[i] * z
        y[i] = z
    y = hp(y, 300) * np.minimum(1, t / 0.01) * np.exp(-t * 4.5) * 2.2
    for _ in range(14):  # droplets
        t0 = rng.uniform(0.05, 0.6)
        f = rng.uniform(900, 2400)
        dd = 0.05
        tb = tt(dd)
        drop = np.sin(2 * np.pi * np.cumsum(f * (1 + 2.5 * tb / dd)) / SR) * np.exp(-tb * 70)
        i = int(t0 * SR)
        y[i:i + len(drop)] += 0.18 * drop[:len(y) - i]
    return y


def s_clank():
    d = 0.5
    t = tt(d)
    x = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * k) * a for f, k, a in
            ((523, 9, 0.5), (1371, 12, 0.35), (2240, 16, 0.25), (3170, 20, 0.15)))
    return mx(x * 0.8, 0.6 * thump(120, 60, 0.15, 20))


def s_shuttle():
    return mx(0.7 * thump(1400, 900, 0.06, 50), 0.5 * bp(noise(0.04), 2000, 6000) * env(int(0.04 * SR), 0.0003, 0.008))


def s_bat_crack():
    d = 0.25
    crack = bp(noise(d), 1200, 6000) * env(int(d * SR), 0.0003, 0.02) * 1.2
    return mx(crack, 0.8 * thump(700, 420, 0.12, 30), 0.4 * thump(150, 80, 0.15, 20))


def s_blip(i):
    m = [72, 74, 77, 79, 81][i % 5]
    t = tt(0.16)
    return (np.sin(2 * np.pi * mtof(m) * t) + 0.3 * np.sin(4 * np.pi * mtof(m) * t)) * np.exp(-t * 22) * 0.5


def s_trophy():
    out = np.zeros(int(0.9 * SR))
    for k, m in enumerate((84, 88, 91, 96)):
        t = tt(0.7)
        x = np.sin(2 * np.pi * mtof(m) * t) * np.exp(-t * 6) * 0.3
        i = int(k * 0.05 * SR)
        out[i:i + len(x)] += x[:len(out) - i]
    return out


def s_logo_pop():
    t = tt(1.2)
    chord = sum(np.sin(2 * np.pi * mtof(m) * t) for m in (65, 72, 77, 81)) / 4
    return 0.5 * chord * np.exp(-t * 3)


def s_riser(d):
    t = tt(d)
    n = noise(d)
    y = np.zeros_like(n)
    cut = 400 + 9000 * (t / d) ** 2
    a = np.exp(-2 * np.pi * cut / SR)
    z = 0.0
    for i in range(len(n)):
        z = (1 - a[i]) * n[i] + a[i] * z
        y[i] = z
    y = hp(y, 200) * (t / d) ** 2.2 * 1.6
    sweep = np.sin(2 * np.pi * np.cumsum(220 * 2 ** (2 * t / d)) / SR) * (t / d) ** 2 * 0.25
    return y + sweep


def s_impact():
    t = tt(1.4)
    boom = np.sin(2 * np.pi * np.cumsum(30 + 90 * np.exp(-t * 10)) / SR) * np.exp(-t * 3)
    crash = hp(noise(1.4), 4000) * np.exp(-t * 4) * 0.35
    return boom * 1.1 + crash


def s_button():
    t = tt(0.3)
    return np.sin(2 * np.pi * 1318 * t) * np.exp(-t * 18) * 0.5 + np.sin(2 * np.pi * 1760 * t) * np.exp(-t * 14) * 0.4


cues = json.load(open(os.path.join(WK, "cues.json")))
for c in cues:
    t0, n = c["t"], c["name"]
    if n == "type":
        add(sfx, t0, s_type(), 0.6, 0.1)
    elif n == "racket":
        add(sfx, t0, s_racket(), 0.7, -0.5)
    elif n == "ball_pop":
        add(sfx, t0, s_ball_pop(), 1.0, 0.45)
    elif n == "ball_pop_small":
        add(sfx, t0, s_ball_pop(1.15), 0.45, 0.6)
    elif n == "step":
        add(sfx, t0, s_step(c["i"]), 0.95, (-0.15, 0.15)[c["i"] % 2])
    elif n == "kick_ball":
        add(sfx, t0, s_kick_ball(), 0.9, -0.4)
    elif n == "net_swish":
        add(sfx, t0, s_net_swish(), 0.9, 0.15)
    elif n == "bow_creak":
        add(sfx, t0, s_bow_creak(c["dur"]), 0.6, -0.4)
    elif n == "twang":
        add(sfx, t0, s_twang(), 0.75, -0.4)
    elif n == "arrow_thunk":
        x, off = s_arrow_thunk()
        add(sfx, t0 + off, x, 1.0, 0.45)
    elif n == "splash":
        add(sfx, t0, s_splash(), 0.9, 0.0)
    elif n == "clank":
        add(sfx, t0, s_clank(), 0.8, -0.1)
    elif n == "shuttle":
        add(sfx, t0, s_shuttle(), 0.9, 0.2)
    elif n == "bat_crack":
        add(sfx, t0, s_bat_crack(), 0.95, -0.1)
    elif n == "step_blip":
        add(sfx, t0, s_blip(c["i"]), 0.7, -0.5 + 0.25 * c["i"])
    elif n == "trophy":
        add(sfx, t0, s_trophy(), 0.8, 0.4)
    elif n == "logo_pop":
        add(sfx, t0, s_logo_pop(), 0.8)
        add(sfx, t0, s_ball_pop(1.4), 0.5)
    elif n == "riser":
        add(sfx, t0, s_riser(c["end"] - t0), 0.55)
    elif n == "impact":
        add(sfx, t0, s_impact(), 0.9)
    elif n == "button":
        add(sfx, t0, s_button(), 0.7)

# ------------------------------------------------------------------ ribbon whoosh, driven by the ribbon's own motion
mot = json.load(open(os.path.join(WK, "motion.json")))
ft = np.array([m["t"] for m in mot])
spd = np.array([m["speed"] for m in mot])
xs = np.array([m["x"] for m in mot])
ts = np.arange(NS) / SR
sp = np.interp(ts, ft, spd)
sp = signal.sosfiltfilt(signal.butter(2, 12, fs=SR, output="sos"), sp)
level = np.clip(np.log1p(np.maximum(sp, 0) / 250) / np.log1p(12000 / 250), 0, 1) ** 1.3
# STFT shaping: a band of noise whose centre frequency rises with ribbon speed
nz = noise(DUR + 0.1)[:NS]
f, tf, Z = signal.stft(nz, SR, nperseg=1024)
lv = np.interp(tf, ts, level)
centre = 350 + 3800 * lv
bw = 0.9
mask = np.exp(-0.5 * (np.log2(np.maximum(f[:, None], 20) / centre[None, :]) / bw) ** 2)
_, wh = signal.istft(Z * mask * lv[None, :], SR, nperseg=1024)
wh = wh[:NS]
pan = np.clip((np.interp(ts, ft, xs) - 540) / 540, -1, 1) * 0.7
whoosh = np.vstack([wh * np.cos((pan + 1) * np.pi / 4), wh * np.sin((pan + 1) * np.pi / 4)]) * 1.414

# ------------------------------------------------------------------ mix
def rms(x):
    return np.sqrt(np.mean(x ** 2) + 1e-12)


music *= 0.11 / rms(music)
sfx *= 0.075 / rms(sfx)
whoosh *= 0.05 / rms(whoosh)
# duck the music a touch under each sport hit
duck = np.ones(NS)
for c in cues:
    if c["name"] in ("type", "step_blip", "riser", "bow_creak"):
        continue
    i0 = int(c["t"] * SR)
    n = min(int(0.35 * SR), NS - i0)
    if n > 0:
        duck[i0:i0 + n] = np.minimum(duck[i0:i0 + n], 1 - 0.3 * np.exp(-np.arange(n) / SR * 8))
mix = music * duck + sfx + whoosh
# fades: tiny fade-in, short fade-out at the very end
fi, fo = int(0.01 * SR), int(0.35 * SR)
mix[:, :fi] *= np.linspace(0, 1, fi)
mix[:, -fo:] *= np.linspace(1, 0, fo) ** 1.5
mix /= np.abs(mix).max() / 0.8
wavfile.write(os.path.join(WK, "score_premaster.wav"), SR, mix.T.astype(np.float32))
print("wrote score_premaster.wav", mix.shape)
