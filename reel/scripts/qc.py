#!/usr/bin/env python3
"""Delivery QC: spec, loudness, true peak, size, no black frames, motion in the first frames."""
import json, os, re, subprocess, sys
import numpy as np

f = sys.argv[1]
probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", f],
                                  capture_output=True, text=True).stdout)
v = next(s for s in probe["streams"] if s["codec_type"] == "video")
a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
size = int(probe["format"]["size"]) / 1e6
t = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True).stderr
ln = json.loads(t[t.rfind("{"):t.rfind("}") + 1])
bd = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-vf", "blackdetect=d=0.0:pix_th=0.10", "-an", "-f", "null", "-"],
                    capture_output=True, text=True).stderr
blacks = re.findall(r"black_start:\S+ black_end:\S+", bd)
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-frames:v", "3", "-vf", "scale=270:480", "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"], capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, 480, 270).astype(float)
checks = [
    ("1080x1920", f"{v['width']}x{v['height']}" == "1080x1920"),
    ("30 fps", v["r_frame_rate"] == "30/1"),
    (f"duration {float(probe['format']['duration']):.2f}s", abs(float(probe["format"]["duration"]) - 18) < 0.05),
    (f"size {size:.1f} MB < 30", size < 30),
    (f"loudness {ln['input_i']} LUFS (target -14)", abs(float(ln["input_i"]) + 14) <= 0.5),
    (f"true peak {ln['input_tp']} dBTP < -1.5", float(ln["input_tp"]) < -1.5),
    (f"no black frames ({len(blacks)} found)", not blacks),
    (f"frame 0 mean luma {fr[0].mean():.0f}", fr[0].mean() > 60),
    (f"motion frame0->2 {np.abs(fr[2] - fr[0]).mean():.2f}", np.abs(fr[2] - fr[0]).mean() > 0.2),
]
for name, ok in checks:
    print(("PASS " if ok else "FAIL ") + name)
print(f"audio {a['codec_name']} {a['sample_rate']} Hz {a.get('bit_rate', '?')} bps")
sys.exit(0 if all(ok for _, ok in checks) else 1)
