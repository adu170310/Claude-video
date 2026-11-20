#!/usr/bin/env bash
# Athlo 30x30 speedrun reel: logo matte -> picture -> chiptune score -> -14 LUFS master + mux.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 speedrun/prep.py       # cut the real logo off its white background
python3 speedrun/picture.py    # 900 frames, 1080x1920 @ 30 fps -> work/speedrun/picture.mp4 (+ safe-area audit)
python3 speedrun/score.py      # original chiptune score + SFX -> work/speedrun/score_premaster.wav
python3 speedrun/master.py     # -14 LUFS / <-1 dBTP, mux -> out/athlo_speedrun_30s_1080x1920.mp4
