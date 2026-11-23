#!/usr/bin/env python3
"""Audio for Reel 3 "was 5am worth it?" (14 s, 120 BPM, drop at 10.0 s).

_music:   placeholder track built for the edit: a muffled alarm + sleepy pad under the hook, the beat
          kicking in on the 6:06 AM crowd cut (1.5 s), a riser into the drop on "worth it? yeah." (10.0 s),
          and an outro that resolves back towards the quiet open so the loop feels intentional.
          The clips' own crowd sound sits underneath.
_nomusic: original audio only: each clip's own sound on its shot, over an event-crowd bed.
Both mastered to -14 LUFS / -1.5 dBTP and muxed with work/r3/picture.mp4 into out/."""
import json, os, subprocess
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R3 = os.path.join(ROOT, "work", "r3"); OUT = os.path.join(ROOT, "out")
SR, DUR = 48000, 14.0
N = int(SR * DUR)
rng = np.random.default_rng(5)
DROP, KICKIN, SPB = 10.0, 1.5, 0.5

def rd(p):
    sr, a = wavfile.read(p); a = a.astype(np.float64) / (32768 if a.dtype == np.int16 else 1)
    return (np.stack([a, a]) if a.ndim == 1 else a.T)
def e(n, a, d):
    t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def add(buf, x, t, g=1.0):
    i = int(round(t * SR)); n = min(x.shape[1], N - i)
    if n > 0: buf[:, i:i + n] += g * x[:, :n]
def lp(x, fc): return sosfilt(butter(2, fc, "lp", fs=SR, output="sos"), x, axis=-1)
def hp(x, fc): return sosfilt(butter(2, fc, "hp", fs=SR, output="sos"), x, axis=-1)

# ---------------------------------------------------------------- original audio
CLIPS = [("2675", 1.50, 2.50), ("2678", 2.50, 3.25), ("2679", 3.25, 4.25), ("2680", 6.25, 7.25)]
bed = np.concatenate([rd(os.path.join(R3, f"full_IMG_{t}.wav")) for t in ("2679", "2680", "2675", "2678")], axis=1)
bed = np.pad(bed, ((0, 0), (0, max(0, N - bed.shape[1]))))[:, :N]
bed /= np.sqrt(np.mean(bed ** 2)) + 1e-9
clips = np.zeros((2, N)); gate = np.ones(N)
for tag, t0, t1 in CLIPS:                       # each clip's own sound on its shot, bed ducked under it
    a = rd(os.path.join(R3, "clips", f"{tag}.wav")); a /= np.sqrt(np.mean(a ** 2)) + 1e-9
    n = min(a.shape[1], int((t1 - t0) * SR)); f = int(0.01 * SR)
    a = a[:, :n].copy(); a[:, :f] *= np.linspace(0, 1, f); a[:, -f:] *= np.linspace(1, 0, f)
    add(clips, a, t0, 0.8); gate[int(t0 * SR):int(t0 * SR) + n] = 0.35
orig = bed * 0.35 * gate + clips
# the hook is quieter: half-asleep on the metro
hook = np.ones(N); hook[:int(KICKIN * SR)] = 0.5; orig *= hook

# ---------------------------------------------------------------- music
def kick(big=False):
    n = int(0.5 * SR); t = np.arange(n) / SR
    f = 45 + (120 if big else 85) * np.exp(-t / 0.035)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * e(n, 0.001, 0.3 if big else 0.16); return np.stack([x, x])
def clap():
    n = int(0.25 * SR); x = hp(rng.standard_normal(n), 900) * e(n, 0.001, 0.06) * 0.55
    return np.stack([x, np.roll(x, 200)])
def hat(open_=False):
    n = int((0.2 if open_ else 0.06) * SR)
    x = hp(rng.standard_normal(n), 7000) * e(n, 0.0005, 0.06 if open_ else 0.012) * 0.28; return np.stack([x * 0.8, x])
def chord(freqs, dur, cutoff, amp, saw=False):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for fq in freqs:
        for det in (-0.004, 0.004):
            ph = 2 * np.pi * fq * (1 + det) * t
            x += (2 * ((fq * (1 + det) * t) % 1) - 1) * 0.6 if saw else np.sin(ph)
    x = lp(x / (2 * len(freqs)) * np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.05), cutoff) * amp
    return np.stack([x, np.roll(x, int(0.012 * SR))])
def bass(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    x = lp(np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + np.sin(2 * np.pi * f * t), 300) * e(n, 0.005, dur) * 0.5
    return np.stack([x, x])
def riser(dur):
    n = int(dur * SR); t = np.arange(n) / SR; x = rng.standard_normal(n); out = np.zeros(n); hop = 2400
    for i in range(0, n, hop):
        fc = 300 * (25 ** (i / n)); out[i:i + hop] = sosfilt(butter(2, [fc * 0.7, min(fc * 1.4, 22000)], "bp", fs=SR, output="sos"), x[i:i + hop])
    out *= (t / dur) ** 2 * 0.6; return np.stack([out, out])
def alarm():
    """Generic two-tone wake-up beeps (not any phone's real alarm), heard muffled 'through sleep'."""
    out = np.zeros((2, int(1.4 * SR)))
    for k, t0 in enumerate(np.arange(0.0, 1.3, 0.16)):
        n = int(0.07 * SR); t = np.arange(n) / SR
        x = np.sin(2 * np.pi * (1320 if k % 2 == 0 else 1760) * t) * np.minimum(1, t / 0.003) * np.minimum(1, (0.07 - t) / 0.01) * 0.35
        add_i = int(t0 * SR); out[:, add_i:add_i + n] += x
    return lp(out, 2200)

music = np.zeros((2, N))
# hook (0-1.5): alarm + low muffled pad
add(music, alarm(), 0.02, 0.9)
add(music, chord([220.0, 261.63, 329.63], KICKIN, 600, 0.35), 0.0)
PROG = [([220.0, 261.63, 329.63, 392.0], 55.0), ([174.61, 220.0, 261.63, 349.23], 43.65),
        ([261.63, 329.63, 392.0, 493.88], 65.41), ([196.0, 246.94, 293.66, 392.0], 49.0)]   # Am F C G
b = 0
t = KICKIN
while t < DUR - 1e-6:
    pre_drop = t < DROP
    bar_pos = b % 4
    kick_big = abs(t - DROP) < 1e-6
    add(music, kick(kick_big), t, 1.0 if not pre_drop else 0.85)
    if bar_pos in (1, 3): add(music, clap(), t, 0.9 if not pre_drop else 0.7)
    add(music, hat(), t + SPB / 2, 1.0)
    if not pre_drop: add(music, hat(True), t + SPB / 2, 0.6)
    if bar_pos == 0:
        ch, root = PROG[(b // 4) % 4]
        dur = min(4 * SPB, DUR - t)
        add(music, chord(ch, dur, 2600 if pre_drop else 5000, 0.30 if pre_drop else 0.42, saw=not pre_drop), t)
        add(music, bass(root, dur), t, 0.9)
    b += 1; t = KICKIN + b * SPB
# 8th-note bass pulse + riser into the drop, small silence gap right before it for impact
add(music, riser(2.0), DROP - 2.0, 0.7)
gap = np.ones(N); g0, g1 = int((DROP - 0.12) * SR), int(DROP * SR); gap[g0:g1] = 0.15
music *= gap
# outro: last 0.5 s thins out so the loop back to the quiet hook doesn't jar
fo = int(0.5 * SR); music[:, -fo:] *= np.linspace(1, 0.25, fo)

def loud(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], stderr=subprocess.PIPE, text=True).stderr
    return json.loads(p[p.rfind("{"):p.rfind("}") + 1])

def master(x, name):
    """Gain to -14 LUFS, then a look-ahead limiter at -2 dBFS (4x oversampled peak check), iterate."""
    pre = os.path.join(R3, name + "_pre.wav")
    x = x / max(1e-9, np.abs(x).max()) * 0.5
    wavfile.write(pre, SR, x.T.astype(np.float32))
    gain = -14.0 - float(loud(pre)["input_i"])
    mp4 = os.path.join(OUT, f"Reel3_was-5am-worth-it_{name}.mp4")
    for _ in range(4):
        af = (f"volume={gain:.2f}dB,aresample=192000,alimiter=limit=0.79:attack=2:release=60:level=false,"
              "aresample=48000")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(R3, "picture.mp4"),
                        "-i", pre, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "320k",
                        "-ar", "48000", "-movflags", "+faststart", "-t", str(DUR), mp4], check=True)
        q = loud(mp4); err = -14.0 - float(q["input_i"])
        if abs(err) < 0.2 and float(q["input_tp"]) <= -1.0: break
        gain += err
    print(f"{os.path.basename(mp4)}: {q['input_i']} LUFS, {q['input_tp']} dBTP")

master(music + 0.12 * orig, "music")
master(orig, "nomusic")
