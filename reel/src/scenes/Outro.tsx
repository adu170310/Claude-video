import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { theme } from "../theme";
import T from "../timeline.json";
import { ei, mix, sp } from "../util";
import { display, Grad, ui } from "../components/Atoms";

const S = T.sign;
const E = T.end;

/** Charcoal base with a slow, low brand glow (never flat, never black). */
export const DarkBg: React.FC = () => {
  const f = useCurrentFrame();
  if (f < S.start - 4) return null;
  const glow = ei(f, [S.start, E.start + 20], [0.12, 0.3], theme.ease.soft);
  return (
    <AbsoluteFill style={{ background: theme.c.charcoal, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          width: 1500,
          height: 1500,
          left: -210 + Math.sin(f / 40) * 60,
          top: 1150 + Math.cos(f / 50) * 40,
          borderRadius: "50%",
          background: `radial-gradient(circle, rgba(252,4,100,${glow}), transparent 62%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1200,
          height: 1200,
          left: -500 + Math.cos(f / 45) * 50,
          top: -560,
          borderRadius: "50%",
          background: `radial-gradient(circle, rgba(255,173,1,${glow * 0.7}), transparent 62%)`,
        }}
      />
    </AbsoluteFill>
  );
};

export const Sign: React.FC = () => {
  const f = useCurrentFrame();
  if (f < S.start || f > E.start + 6) return null;
  const words = ["This", "is", "your", "sign."];
  const out = ei(f, [E.start - 4, E.start + 4], [0, 1], theme.ease.in);
  const push = ei(f, [S.start, E.start], [1, 1.05], theme.ease.soft);
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        padding: "0 80px",
        transform: `scale(${push}) translateY(${-out * 120}px)`,
        opacity: 1 - out,
      }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", columnGap: 40, rowGap: 0, width: 920, marginTop: -60 }}>
        {words.map((w, i) => {
          const p = sp(f, S.words[i], theme.spring.snappy);
          const el = (
            <span
              key={i}
              style={{
                display: "inline-block",
                ...display(172, theme.c.offwhite),
                opacity: Math.min(1, p * 2),
                transform: `translateY(${mix(90, 0, p)}px) scale(${mix(1.15, 1, p)})`,
              }}
            >
              {i === 3 ? <Grad>{w}</Grad> : w}
            </span>
          );
          return i === 1 ? [el, <div key="br" style={{ flexBasis: "100%", height: 0 }} />] : el;
        })}
      </div>
    </AbsoluteFill>
  );
};

export const EndCard: React.FC = () => {
  const f = useCurrentFrame();
  if (f < E.start) return null;
  const pl = sp(f, E.logo, theme.spring.bouncy);
  const pd = sp(f, E.days, theme.spring.snappy);
  const pj = sp(f, E.join, theme.spring.snappy);
  const pb = sp(f, E.button, theme.spring.bouncy);
  const breathe = 1 + Math.sin((f - E.button) / 9) * 0.018;
  const shine = ((f - E.button - 10) % 45) / 45; // sweep every 1.5 s
  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <Img
        src={staticFile("athlo_logo.png")}
        style={{
          position: "absolute",
          top: 300,
          width: 560,
          opacity: Math.min(1, pl * 2),
          transform: `translateY(${mix(-60, 0, pl)}px) scale(${mix(0.7, 1, pl)})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 540,
          ...display(100),
          opacity: Math.min(1, pd * 2),
          transform: `translateY(${mix(50, 0, pd)}px) scale(${mix(0.9, 1, pd)})`,
        }}
      >
        <Grad>3 days left.</Grad>
      </div>
      <div
        style={{
          position: "absolute",
          top: 690,
          width: 1000,
          textAlign: "center",
          whiteSpace: "nowrap",
          ...display(116, theme.c.offwhite),
          lineHeight: 1.0,
          opacity: Math.min(1, pj * 2),
          transform: `translateY(${mix(60, 0, pj)}px)`,
        }}
      >
        Join the Athlo
        <br />
        30x30 challenge
      </div>
      <div
        style={{
          position: "absolute",
          top: 1110,
          width: 760,
          height: 176,
          borderRadius: 999,
          background: theme.grad,
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 0 70px ${theme.c.pink}55, 0 30px 60px -20px rgba(252,4,100,0.6)`,
          opacity: Math.min(1, pb * 2),
          transform: `translateY(${mix(80, 0, pb)}px) scale(${mix(0.8, 1, pb) * breathe})`,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            width: 160,
            left: mix(-260, 900, shine),
            background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.45), transparent)",
            transform: "skewX(-20deg)",
          }}
        />
        <span style={{ ...ui(68, theme.c.offwhite, 600), position: "relative" }}>Link in bio</span>
      </div>
    </AbsoluteFill>
  );
};
