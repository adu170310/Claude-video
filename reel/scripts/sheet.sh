#!/usr/bin/env bash
# Render one still per beat and tile them into a contact sheet.
set -e
cd "$(dirname "$0")/.."
FR=${1:-38,100,165,222,290,335,358,420}
GL=swangle node scripts/render.mjs stills $FR 2>&1 | grep "^still"
cd ../work/stills
IFS=, read -ra A <<< "$FR"
IN=""; for f in "${A[@]}"; do IN="$IN -i f$(printf %03d $f).png"; done
ffmpeg -v error -y $IN -filter_complex "xstack=inputs=8:layout=0_0|w0_0|w0+w1_0|w0+w1+w2_0|0_h0|w0_h0|w0+w1_h0|w0+w1+w2_h0,scale=1440:-1" "${2:-sheet.jpg}"
