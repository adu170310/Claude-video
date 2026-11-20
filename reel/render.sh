#!/usr/bin/env bash
# Athlo "One line, every sport." reel: logo matte -> picture -> score -> master.
#   reel/render.sh            full build -> out/athlo_reel_one_line_17s_1080x1920.mp4
#   reel/render.sh stills     one still per beat + contact sheet -> work/reel/stills/
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q scipy pycairo 2>/dev/null || true
python3 reel/prep.py
if [[ "${1:-}" == "stills" ]]; then python3 reel/picture.py --stills; exit; fi
python3 reel/picture.py      # 510 frames + cues.json + motion.json
python3 reel/score.py        # original track, sport hits, ribbon-driven whoosh
python3 reel/master.py       # -14 LUFS, true peak < -1.5 dBTP, mux
