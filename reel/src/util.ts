import { interpolate, spring, SpringConfig } from "remotion";
import { theme } from "./theme";

export const FPS = 30;
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Spring that is 0 before `start` and settles to 1. Works with fractional frames (motion blur). */
export const sp = (frame: number, start: number, cfg: Partial<SpringConfig> = theme.spring.smooth) =>
  frame < start ? 0 : spring({ frame: frame - start, fps: FPS, config: cfg });

/** Eased, clamped interpolation. Linear is never used. */
export const ei = (
  frame: number,
  inp: [number, number],
  out: [number, number],
  ease: (t: number) => number = theme.ease.out,
) => interpolate(frame, inp, out, { ...clamp, easing: ease });

export const mix = (a: number, b: number, t: number) => a + (b - a) * t;

/** Deterministic smooth noise in [-1,1] for shakes/wobbles. */
export const noise = (t: number, seed = 0) =>
  (Math.sin(t * 1.7 + seed * 12.9) * 0.5 + Math.sin(t * 3.1 + seed * 7.3) * 0.3 + Math.sin(t * 5.3 + seed * 3.1) * 0.2);

/** Decaying pulse that fires every `period` frames from `start`. */
export const beatPulse = (frame: number, start: number, period = 15, decay = 5) => {
  if (frame < start) return 0;
  const ph = (frame - start) % period;
  return Math.exp(-ph / decay);
};
