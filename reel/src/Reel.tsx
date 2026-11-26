import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame, getRemotionEnvironment } from "remotion";
import { CameraMotionBlur } from "@remotion/motion-blur";
import { theme } from "./theme";
import T from "./timeline.json";
import { mix, noise, sp } from "./util";
import { Grain, Vignette } from "./components/Atoms";
import { Hook } from "./scenes/Hook";
import { Journey } from "./scenes/Journey";
import { Weekend } from "./scenes/Weekend";
import { DarkBg, EndCard, Sign } from "./scenes/Outro";

/** Virtual camera: punch-in on the hook, shake in Day 20, impacts on the drop and LOCKED IN. */
const Camera: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const f = useCurrentFrame();
  const punch = f < T.hook.end ? sp(f, T.hook.punch, theme.spring.snappy) : 0;
  const scale = 1 + punch * 0.06;
  const punchRot = punch * -0.6;

  let amp = 0;
  if (f >= T.day20.start && f < T.weekend.start) amp = 5;
  for (const n of T.day20.notifs) if (f >= n) amp += 14 * Math.exp(-(f - n) / 4);
  for (const [at, a] of [
    [T.weekend.start, 26],
    [T.weekend.locked, 34],
  ] as const)
    if (f >= at) amp += a * Math.exp(-(f - at) / 5);
  if (f >= T.weekend.start && f < T.weekend.end) amp += 2;
  const x = noise(f / 1.3, 11) * amp;
  const y = noise(f / 1.1, 23) * amp;
  const r = noise(f / 1.7, 31) * amp * 0.03;
  return (
    <AbsoluteFill
      style={{
        transform: `translate(${x}px, ${y}px) rotate(${punchRot + r}deg) scale(${scale})`,
        transformOrigin: "50% 45%",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

const Picture: React.FC = () => (
  <Camera>
    <Journey />
    <Hook />
    <DarkBg />
    <Weekend />
    <Sign />
    <EndCard />
  </Camera>
);

// Frames with fast motion get real (multi-sample) motion blur; the rest render directly.
const BLUR: [number, number][] = [
  [T.hook.punch, T.hook.punch + 8],
  [T.hook.end - 8, T.hook.end + 6],
  [T.weekend.start - 1, T.weekend.cards[3] + 12],
  [T.weekend.locked, T.weekend.locked + 8],
  [T.weekend.end - 6, T.weekend.end + 2],
  [T.day20.notifs[0], T.day20.notifs[0] + 6],
  [T.day20.notifs[1], T.day20.notifs[1] + 6],
  [T.day20.notifs[2], T.day20.notifs[2] + 6],
];

export const Reel: React.FC = () => {
  const f = useCurrentFrame();
  const blur = BLUR.some(([a, b]) => f >= a && f <= b);
  const { isRendering } = getRemotionEnvironment();
  return (
    <AbsoluteFill style={{ background: theme.c.offwhite }}>
      {blur ? (
        <CameraMotionBlur shutterAngle={200} samples={8}>
          <Picture />
        </CameraMotionBlur>
      ) : (
        <Picture />
      )}
      <Vignette strength={f >= T.sign.start ? 0.35 : 0.14} />
      <Grain opacity={0.08} />
      {/* Studio preview only; the final file gets the mastered mix muxed by scripts/build.sh */}
      {!isRendering && <Audio src={staticFile("soundtrack.wav")} />}
    </AbsoluteFill>
  );
};
