# Athlo 30x30 reel: "Day 1 vs the final weekend" (18 s, 1080x1920, 30 fps)

Remotion picture plus a synthesised score. The only external input is the Athlo logo in `../assets/`.

```
npm install
./build.sh   # logo -> score -> master -> render -> mux -> QC
             # -> out/athlo_30x30_day1_vs_final_weekend_1080x1920.mp4
npm run studio   # live preview with the soundtrack
```

| Time | Section |
|---|---|
| 0.0–1.5 | Hook / cover: split screen, headline band, punch-in at 0.8 s |
| 1.5–4.5 | Day 1: calm checklist ticks itself off |
| 4.5–7.5 | Day 10: card tilts, honest notes, crooked ticks |
| 7.5–10.5 | Day 20: notifications, alarm rattle, camera shake |
| 10.5–14 | Final weekend: beat drop, cards fly in, LOCKED IN. slam |
| 14–15.5 | "This is your sign." |
| 15.5–18 | End card: logo, 3 days left., Join the Athlo 30x30 challenge, Link in bio |

- `src/timeline.json`: every cue on a 120 BPM grid (1 beat = 15 frames), shared by picture and sound.
- `src/theme.ts`: brand colours, fonts (Inter Display Black, Poppins Medium), easings, springs.
- `scripts/score.py`: four-section original score + SFX. `scripts/master.py`: -14 LUFS, limiter. `scripts/qc.py`: spec checks.
- Fonts are bundled from `inter-ui` and `@fontsource/poppins` (both SIL OFL).
