import timeline from './timeline.json';
export const TL = timeline;

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const prog = (f: number, a: number, b: number) => clamp01((f - a) / (b - a));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
export const easeIn = (t: number) => t * t * t;
export const smooth = (t: number) => t * t * (3 - 2 * t);

/** Window envelope: 0 before a, ramps to 1 over [a, a+fin], holds, ramps out over [b-fout, b]. */
export const env = (f: number, a: number, b: number, fin = 10, fout = 10) =>
  Math.min(smooth(prog(f, a, a + fin)), 1 - smooth(prog(f, b - fout, b)));

type Key = [number, number[]];
/** Non-uniform Catmull-Rom (Hermite) through keyframes: smooth, never stops mid-path. */
export function path(f: number, keys: Key[]): number[] {
  const n = keys.length;
  if (f <= keys[0][0]) {
    const [t0, p0] = keys[0];
    const [t1, p1] = keys[1];
    return p0.map((v, i) => v + ((p1[i] - v) / (t1 - t0)) * (f - t0));
  }
  if (f >= keys[n - 1][0]) {
    const [t0, p0] = keys[n - 2];
    const [t1, p1] = keys[n - 1];
    return p1.map((v, i) => v + ((v - p0[i]) / (t1 - t0)) * (f - t1));
  }
  let k = 0;
  while (k < n - 2 && f > keys[k + 1][0]) k++;
  const tang = (j: number) => {
    const a = keys[Math.max(0, j - 1)];
    const b = keys[Math.min(n - 1, j + 1)];
    return b[1].map((v, i) => (v - a[1][i]) / (b[0] - a[0]));
  };
  const [t0, p0] = keys[k];
  const [t1, p1] = keys[k + 1];
  const m0 = tang(k);
  const m1 = tang(k + 1);
  const h = t1 - t0;
  const s = (f - t0) / h;
  const s2 = s * s;
  const s3 = s2 * s;
  const h00 = 2 * s3 - 3 * s2 + 1;
  const h10 = s3 - 2 * s2 + s;
  const h01 = -2 * s3 + 3 * s2;
  const h11 = s3 - s2;
  return p0.map((v, i) => h00 * v + h10 * h * m0[i] + h01 * p1[i] + h11 * h * m1[i]);
}

/** Deterministic pseudo-random in [0,1). */
export const rand = (i: number) => {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};
