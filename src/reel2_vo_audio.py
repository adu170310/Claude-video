#!/usr/bin/env python3
"""Audio for the VO cut of Reel 2.

- VO: high-pass 70 Hz, light FFT noise reduction, gentle compression (ffmpeg). Untrimmed.
- Music (_music only): low 100 BPM beat whose grid puts a downbeat exactly on "us"; a riser into it;
  ducked to -20 dB under the VO (sidechain on the VO envelope), back to full on "us".
- Ambience: event crowd audio under the first line at 20 %, faded out at the first cut.
  (8d56a47c…mp4, the smoke moment from another phone, stands in for IMG_2682.MOV's own audio.)
- Length = VO + 1 s. Both mixes mastered to -14 LUFS / -1.5 dBTP; muxed with work/r2v/picture.mp4."""
import json, math, os, subprocess
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work"); VW = os.path.join(WK, "r2v"); FT = os.path.join(WK, "footage")
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)
SR = 48000
CUES = {k: v["onset"] for k, v in json.load(open(os.path.join(VW, "cues.json"))).items()}
T_US = 32.49
FIRST_CUT = CUES["costume"]
rng = np.random.default_rng(11)

def dec(path, af=None):
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if af: cmd += ["-af", af]
    raw = subprocess.run(cmd + ["-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.astype(np.float64)

# ---- VO, cleaned (nothing trimmed)
vo = dec(os.path.join(FT, "ElevenLabs_VO.mp3"),
         "highpass=f=70,afftdn=nr=6:nf=-55:tn=1,"
         "acompressor=threshold=-20dB:ratio=3:attack=6:release=90:makeup=2,"
         "alimiter=limit=0.95:level=false")
# the cleaning chain adds a few ms of latency: measure it against the raw VO and remove it,
# so the VO stays sample-aligned with the Whisper timings every cut is based on
raw_vo = dec(os.path.join(FT, "ElevenLabs_VO.mp3"))
a, b = raw_vo[0, :SR * 8], vo[0, :SR * 8]
lag = max(range(0, int(0.1 * SR)), key=lambda L: float(np.dot(a[:SR * 7], b[L:L + SR * 7])))
vo = np.concatenate([vo[:, lag:], np.zeros((2, lag))], axis=1)
print(f"VO cleaning latency removed: {lag / SR * 1000:.1f} ms")
VO_N = vo.shape[1]
N = VO_N + SR                                   # + 1 s tail
def pad(x): return np.pad(x[:, :N], ((0, 0), (0, max(0, N - x.shape[1]))))
vo = pad(vo)

def rms(x): return float(np.sqrt(np.mean(x ** 2)) + 1e-12)
vo_rms = rms(vo[:, vo[0] ** 2 > 1e-5])          # level while speaking

# ---- ambience under the first line at 20 %
amb = dec(os.path.join(FT, "8d56a47c-69bb-42e5-b5f3-80565807078f.mp4"))[:, int(6.0 * SR):]
amb = pad(amb) * (vo_rms / rms(amb[:, :int(FIRST_CUT * SR)])) * 0.20
i1, fo = int(FIRST_CUT * SR), int(0.5 * SR)
env = np.zeros(N); env[:int(0.05 * SR)] = np.linspace(0, 1, int(0.05 * SR)); env[int(0.05 * SR):i1] = 1
env[i1:i1 + fo] = np.linspace(1, 0, fo)
amb *= env

# ---- music: 100 BPM, downbeat on "us"
def e(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)
def add(buf, x, t, g=1.0):
    i = int(round(t * SR))
    if i < 0: x = x[:, -i:]; i = 0
    n = min(x.shape[1], N - i)
    if n > 0: buf[:, i:i + n] += g * x[:, :n]
def kick(big=False):
    n = int(0.6 * SR); t = np.arange(n) / SR
    f = 40 + (110 if big else 70) * np.exp(-t / 0.04)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * e(n, 0.002, 0.35 if big else 0.22)
    return np.stack([x, x])
def rim():
    n = int(0.12 * SR); t = np.arange(n) / SR
    x = (0.5 * np.sin(2 * np.pi * 1700 * t) + 0.5 * rng.standard_normal(n)) * e(n, 0.0005, 0.012)
    return np.stack([x * 0.9, x]) * 0.35
def shaker():
    n = int(0.09 * SR)
    x = sosfilt(butter(2, 6000, "hp", fs=SR, output="sos"), rng.standard_normal(n) * e(n, 0.01, 0.025)) * 0.12
    return np.stack([x * 0.7, x])
def padc(freqs, dur, cutoff=1400, amp=0.32):
    n = int(dur * SR); t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.4 * t)) for f in freqs) / len(freqs)
    x = sosfilt(butter(2, cutoff, "lp", fs=SR, output="sos"), x * np.minimum(1, t / 0.2) * np.minimum(1, (dur - t) / 0.5)) * amp
    return np.stack([x, np.roll(x, int(0.01 * SR))])
def sub(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t) * np.minimum(1, t / 0.02) * np.minimum(1, (dur - t) / 0.1) * 0.45
    return np.stack([x, x])
def riser(dur):
    n = int(dur * SR); t = np.arange(n) / SR
    x = rng.standard_normal(n)
    out = np.zeros(n); hop = 2400
    for i in range(0, n, hop):                     # sweep a band-pass upward
        fc = 400 * (12 ** (i / n))
        seg = sosfilt(butter(2, [fc * 0.7, min(fc * 1.4, 20000)], "bp", fs=SR, output="sos"), x[i:i + hop])
        out[i:i + hop] = seg
    out *= (t / dur) ** 2 * 0.5
    return np.stack([out, out])
def crash(dur=2.0):
    n = int(dur * SR)
    x = sosfilt(butter(2, 3000, "hp", fs=SR, output="sos"), rng.standard_normal(n)) * e(n, 0.002, 0.7) * 0.35
    return np.stack([x, np.roll(x, 300)])

music = np.zeros((2, N)); spb = 0.6
chords = [([220.0, 261.63, 329.63, 392.0], 55.0), ([174.61, 220.0, 261.63, 329.63], 43.65),
          ([196.0, 246.94, 293.66, 349.23], 49.0), ([164.81, 196.0, 246.94, 293.66], 41.2)]
b_us = int(round(T_US / spb))                  # beat index of "us"
first = -(-(0 - (T_US - b_us * spb)) // spb)   # first beat >= 0
for b in range(int(first), b_us):
    t = T_US - (b_us - b) * spb
    if t < 0: continue
    rel = b_us - b                             # beats before "us"
    if rel % 4 in (0, 2) or rel % 8 == 1: add(music, kick(), t, 0.8)
    if rel % 4 in (1, 3): add(music, rim(), t)
    add(music, shaker(), t + spb / 2)
    if rel % 4 == 0:
        ch, root = chords[(rel // 4) % 4]
        add(music, padc(ch, 4 * spb), t); add(music, sub(root, 4 * spb * 0.95), t)
# pickup pad from frame 1 so the open isn't silent
add(music, padc(chords[3][0], T_US - b_us * spb + 4 * spb), 0.0, 0.6)
# the swell: riser into "us", then a big downbeat + open chord through the tail
add(music, riser(2.0), T_US - 2.0, 0.6)
add(music, kick(True), T_US, 1.1); add(music, crash(), T_US, 0.8)
tail = (N / SR) - T_US
add(music, padc([220.0, 277.18, 329.63, 440.0, 554.37], tail, cutoff=3500, amp=0.5), T_US)   # A major lift
add(music, sub(55.0, tail), T_US, 1.2)
fo2 = int(0.35 * SR); music[:, -fo2:] *= np.linspace(1, 0, fo2)

# sidechain duck: -20 dB while the VO speaks (fast attack, slow release so gaps don't pump), full from "us"
venv = np.abs(vo).max(axis=0)
win = int(0.02 * SR)
venv = np.convolve(venv, np.ones(win) / win, "same")
active = (venv > 10 ** (-40 / 20)).astype(float)
g = np.empty(N); cur = 1.0
att, rel = math.exp(-1 / (0.03 * SR)), math.exp(-1 / (0.8 * SR))
duck = 10 ** (-20 / 20)
for i in range(N):
    tgt = duck if active[i] else 1.0
    cur = tgt + (cur - tgt) * (att if tgt < cur else rel)
    g[i] = cur
iu = int(T_US * SR); r = int(0.04 * SR)
g[iu:iu + r] = np.linspace(g[iu], 1.0, r); g[iu + r:] = 1.0
music *= g

def master(x, name):
    pre = os.path.join(VW, name + "_pre.wav")
    x = x / max(1e-9, np.abs(x).max()) * 0.5
    wavfile.write(pre, SR, x.T.astype(np.float32))
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", pre, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       stderr=subprocess.PIPE, text=True).stderr
    m = json.loads(p[p.rfind("{"):p.rfind("}") + 1])
    af = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
          f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']},aresample=48000")
    mp4 = os.path.join(OUT, f"Reel2_every-type_VO_{name}.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(VW, "picture.mp4"),
                    "-i", pre, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", af, "-c:a", "aac",
                    "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", "-t", f"{N / SR:.3f}", mp4], check=True)
    q = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], stderr=subprocess.PIPE, text=True).stderr
    q = json.loads(q[q.rfind("{"):q.rfind("}") + 1])
    print(f"{os.path.basename(mp4)}: {q['input_i']} LUFS, {q['input_tp']} dBTP, {N / SR:.3f} s")

master(vo + amb + 0.55 * music, "music")
master(vo + amb, "nomusic")
