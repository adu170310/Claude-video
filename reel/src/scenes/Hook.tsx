import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { theme } from "../theme";
import T from "../timeline.json";
import { ei, noise } from "../util";
import { Check, display, Grad, ui } from "../components/Atoms";

const H = T.hook;

/** Little charcoal activity chip used on the chaotic side of the cover. */
const Chip: React.FC<{ sport: string; time: string; x: number; y: number; rot: number; seed: number }> = ({
  sport,
  time,
  x,
  y,
  rot,
  seed,
}) => {
  const f = useCurrentFrame();
  const jx = noise(f / 2.2, seed) * 7;
  const jy = noise(f / 2.6, seed + 4) * 6;
  const jr = noise(f / 3, seed + 9) * 2.2;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(${jx}px, ${jy}px) rotate(${rot + jr}deg)`,
        background: theme.c.charcoal,
        borderRadius: 30,
        padding: "18px 30px",
        display: "flex",
        gap: 18,
        alignItems: "baseline",
        boxShadow: "0 24px 40px -16px rgba(16,16,19,0.55)",
        whiteSpace: "nowrap",
      }}
    >
      <span style={display(54, theme.c.offwhite)}>{sport}</span>
      <span style={display(54, theme.c.orange)}>{time}</span>
    </div>
  );
};

/** Motion streaks racing across the pink half. */
const Streaks: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <>
      {Array.from({ length: 16 }).map((_, i) => {
        const speed = 38 + (i % 4) * 9;
        const span = 1100;
        const x = ((f * speed + i * 211) % span) - 300;
        const y = 120 + ((i * 167) % 1500);
        const w = 140 + (i % 3) * 90;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: w,
              height: 6 + (i % 2) * 4,
              borderRadius: 8,
              background: "linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.75))",
              transform: "rotate(-14deg)",
              filter: "blur(1.2px)",
            }}
          />
        );
      })}
    </>
  );
};

export const Hook: React.FC = () => {
  const f = useCurrentFrame();
  if (f >= H.end + 6) return null;

  // exit: the split slides apart, revealing Day 1 (which shares the left half's off-white)
  const ex0 = H.end - 7;
  const rightX = ei(f, [ex0, ex0 + 10], [0, 760], theme.ease.in);
  const bandX = ei(f, [ex0, ex0 + 10], [0, -1400], theme.ease.in);
  const leftO = ei(f, [ex0, ex0 + 7], [1, 0], theme.ease.in);
  const leftY = ei(f, [ex0, ex0 + 9], [0, -60], theme.ease.in);

  // calm side breathes, chaos side shakes
  const calm = Math.sin(f / 14) * 4;
  const bandScale = 1 + Math.sin(f / 9) * 0.006;

  return (
    <AbsoluteFill>
      {/* LEFT: Day 1, calm and aligned */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: 540,
          height: 1920,
          background: theme.c.offwhite,
          opacity: leftO,
          transform: `translateY(${leftY}px)`,
        }}
      >
        <div
          style={{
            position: "absolute",
            left: 60,
            top: 262,
            background: theme.c.charcoal,
            borderRadius: 999,
            padding: "14px 34px 18px",
            ...display(60, theme.c.offwhite),
          }}
        >
          DAY 1
        </div>
        <div style={{ position: "absolute", left: 60, top: 392 + calm, ...display(168) }}>6:00</div>
        <div style={{ position: "absolute", left: 64, top: 556 + calm, ...ui(44, theme.c.ink2) }}>alarm: on time</div>

        <div
          style={{
            position: "absolute",
            left: 56,
            top: 1150 + calm * 0.6,
            width: 430,
            background: theme.c.card,
            borderRadius: 40,
            padding: "30px 32px",
            boxShadow: "0 30px 60px -30px rgba(16,16,19,0.35)",
            display: "flex",
            flexDirection: "column",
            gap: 22,
          }}
        >
          {["Alarm", "Gym fit", "Meal prep"].map((t) => (
            <div key={t} style={{ display: "flex", alignItems: "center", gap: 20 }}>
              <Check p={1} size={60} />
              <span style={ui(46)}>{t}</span>
            </div>
          ))}
        </div>
      </div>

      {/* RIGHT: final weekend, pink chaos */}
      <div
        style={{
          position: "absolute",
          left: 540,
          top: 0,
          width: 540,
          height: 1920,
          overflow: "hidden",
          background: `radial-gradient(circle at 100% 0%, ${theme.c.orange}CC 0%, transparent 30%), ${theme.c.pink}`,
          transform: `translateX(${rightX}px)`,
        }}
      >
        <div style={{ position: "absolute", inset: 0, left: -540 }}>
          <Streaks />
        </div>
        <div
          style={{
            position: "absolute",
            left: 28,
            top: 268,
            background: theme.c.offwhite,
            borderRadius: 999,
            padding: "14px 30px 18px",
            transform: `rotate(${-4 + noise(f / 2, 3) * 1.5}deg) translate(${noise(f / 1.8, 5) * 4}px, 0)`,
            whiteSpace: "nowrap",
            ...display(48, theme.c.pink),
          }}
        >
          FINAL WEEKEND
        </div>
        <Chip sport="Padel" time="7am" x={40} y={400} rot={7} seed={1} />
        <Chip sport="Run" time="12pm" x={92} y={516} rot={-9} seed={2} />
        <Chip sport="Swim" time="5pm" x={30} y={1150} rot={-6} seed={3} />
        <Chip sport="Football" time="10pm" x={16} y={1290} rot={8} seed={4} />
      </div>

      {/* Headline band across the middle */}
      <div
        style={{
          position: "absolute",
          left: -80,
          width: 1240,
          top: 640,
          height: 470,
          background: theme.c.charcoal,
          transform: `translateX(${bandX}px) rotate(-2.5deg) scale(${bandScale})`,
          boxShadow: "0 40px 80px -30px rgba(16,16,19,0.6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{ ...display(102, theme.c.offwhite), textAlign: "center", lineHeight: 1.0 }}>
          Day 1 vs the
          <br />
          <Grad>final weekend</Grad>
          <br />
          of a 30-day
          <br />
          challenge
        </div>
      </div>
    </AbsoluteFill>
  );
};
