#!/usr/bin/env bash
# Full rebuild: logo matte -> score -> master -> picture (Remotion) -> mux -> QC.
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/logo.py
python3 scripts/score.py
python3 scripts/master.py
npx remotion render src/index.ts Reel work/picture.mp4 --muted --codec h264 --crf 16 --concurrency 4 --overwrite
OUT=out/athlo_30x30_day1_vs_final_weekend_1080x1920.mp4
ffmpeg -hide_banner -loglevel error -y -i work/picture.mp4 -i work/score_master.wav \
  -map 0:v -map 1:a -c:v libx264 -preset slow -profile:v high -level 4.2 -crf 17 -maxrate 12M -bufsize 24M \
  -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -g 30 \
  -c:a aac -b:a 256k -ar 48000 -movflags +faststart -shortest "$OUT"
python3 scripts/qc.py "$OUT"
