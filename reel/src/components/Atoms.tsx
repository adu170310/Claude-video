import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { theme } from "../theme";
import { ei } from "../util";

/** Brand gradient fill on text. */
export const Grad: React.FC<{ children: React.ReactNode; style?: React.CSSProperties; bg?: string }> = ({
  children,
  style,
  bg = theme.grad,
}) => (
  <span
    style={{
      backgroundImage: bg,
      WebkitBackgroundClip: "text",
      backgroundClip: "text",
      WebkitBoxDecorationBreak: "clone",
      paddingRight: "0.04em",
      ...style,
      color: "transparent",
    }}
  >
    {children}
  </span>
);

export const display = (size: number, color: string = theme.c.charcoal): React.CSSProperties => ({
  fontFamily: theme.font.display,
  fontWeight: 900,
  fontSize: size,
  lineHeight: 0.98,
  letterSpacing: "-0.035em",
  color,
});

export const ui = (size: number, color: string = theme.c.charcoal, weight = 500): React.CSSProperties => ({
  fontFamily: theme.font.ui,
  fontWeight: weight,
  fontSize: size,
  lineHeight: 1.18,
  letterSpacing: "-0.01em",
  color,
});

/** Animated check: p = 0..1 fill+draw progress. */
export const Check: React.FC<{ p: number; size?: number; crooked?: number; tint?: string }> = ({
  p,
  size = 84,
  crooked = 0,
  tint = theme.grad,
}) => {
  const fill = Math.min(1, p * 1.6);
  const draw = Math.max(0, Math.min(1, (p - 0.25) / 0.75));
  const len = 60;
  return (
    <div style={{ width: size, height: size, position: "relative", flex: "none" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          border: `4px solid ${theme.c.hair}`,
          boxSizing: "border-box",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: tint,
          transform: `scale(${fill})`,
          boxShadow: fill > 0.5 ? `0 10px 26px -8px ${theme.c.pink}88` : "none",
        }}
      />
      <svg
        viewBox="0 0 48 48"
        style={{ position: "absolute", inset: 0, transform: `rotate(${crooked}deg)`, overflow: "visible" }}
      >
        <path
          d="M13 25 L21 33 L36 16"
          fill="none"
          stroke={theme.c.offwhite}
          strokeWidth={5.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={len}
          strokeDashoffset={len * (1 - draw)}
        />
      </svg>
    </div>
  );
};

/** Procedural film grain (top layer). */
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.07 }) => {
  const frame = useCurrentFrame();
  const n = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='240' height='240' filter='url(%23n)' opacity='0.55'/%3E%3C/svg%3E")`;
  const f = Math.floor(frame);
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        backgroundImage: n,
        backgroundSize: "240px",
        backgroundPosition: `${(f * 67) % 240}px ${(f * 131) % 240}px`,
        opacity,
        mixBlendMode: "overlay",
      }}
    />
  );
};

export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.18 }) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background: `radial-gradient(ellipse 80% 70% at 50% 48%, transparent 58%, rgba(16,16,19,${strength}) 100%)`,
    }}
  />
);

/** Soft drifting colour blobs (depth layer behind everything). */
export const Mesh: React.FC<{ base: string; a?: string; b?: string; amount?: number; speed?: number }> = ({
  base,
  a = theme.c.orange,
  b = theme.c.pink,
  amount = 0.18,
  speed = 1,
}) => {
  const frame = useCurrentFrame() * speed;
  const hex = Math.round(amount * 255)
    .toString(16)
    .padStart(2, "0");
  return (
    <AbsoluteFill style={{ background: base, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          width: 1300,
          height: 1300,
          borderRadius: "50%",
          left: -520 + Math.sin(frame / 60) * 70,
          top: -480 + Math.cos(frame / 75) * 50,
          background: `radial-gradient(circle, ${a}${hex}, transparent 64%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1400,
          height: 1400,
          borderRadius: "50%",
          right: -620 - Math.cos(frame / 70) * 60,
          bottom: -560 + Math.sin(frame / 52) * 60,
          background: `radial-gradient(circle, ${b}${hex}, transparent 64%)`,
        }}
      />
    </AbsoluteFill>
  );
};

/** White flash overlay that fires at `at` and decays. */
export const Flash: React.FC<{ at: number; len?: number; peak?: number; color?: string }> = ({
  at,
  len = 7,
  peak = 0.92,
  color = "#FFFFFF",
}) => {
  const frame = useCurrentFrame();
  if (frame < at - 1 || frame > at + len) return null;
  const o = frame < at ? 0 : ei(frame, [at, at + len], [peak, 0], theme.ease.out);
  return <AbsoluteFill style={{ background: color, opacity: o, pointerEvents: "none" }} />;
};
