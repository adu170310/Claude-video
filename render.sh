#!/usr/bin/env bash
# Rebuild the Athlo launch film from scratch: assets -> picture -> score -> master.
set -euo pipefail
cd "$(dirname "$0")"
python3 src/prep.py          # logo mattes, photo crops and stitched app page from the recording
python3 src/film.py          # 1350 frames, 1080x1920 @ 30 fps -> work/picture.mp4
python3 src/score.py         # original ambient score + sound design -> work/score_premaster.wav
python3 src/master.py        # -14 LUFS / -1 dBTP master, mux -> out/athlo_launch_45s_1080x1920.mp4
