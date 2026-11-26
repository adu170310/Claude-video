import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { theme } from "../theme";
import T from "../timeline.json";
import { beatPulse, ei, mix, noise, sp } from "../util";
import { display, Flash, Grad } from "../components/Atoms";

const W = T.weekend;

const cards = [
  { sport: "Padel", time: "7am", icon: "🎾", from: [-1300, 0], rot: -3.5 },
  { sport: "Run", time: "12pm", icon: "🏃", from: [1300, 0], rot: 2.5 },
  { sport: "Swim", time: "5pm", icon: "🏊", from: [0, -1500], rot: -2 },
  { sport: "Football", time: "10pm", icon: "⚽", from: [0, 1500], rot: 3.5 },
];

const SpeedLines: React.FC<{ start: number }> = ({ start }) => {
  const f = useCurrentFrame();
  if (f < start) return null;
  const p = ei(f, [start, start + 8], [0, 1]);
  return (
    <AbsoluteFill style={{ opacity: p * 0.9 }}>
      {Array.from({ length: 36 }).map((_, i) => {
        const ang = (i / 36) * 360 + (i % 3) * 3;
        const travel = ((f - start) * (34 + (i % 5) * 8) + i * 97) % 900;
        const len = 160 + (i % 4) * 90;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: 540,
              top: 880,
              width: len,
              height: i % 2 ? 6 : 10,
              borderRadius: 10,
              background: "linear-gradient(90deg, rgba(244,242,236,0), rgba(244,242,236,0.95))",
              transformOrigin: "0% 50%",
              transform: `rotate(${ang}deg) translateX(${300 + travel}px)`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

export const Weekend: React.FC = () => {
  const f = useCurrentFrame();
  if (f < W.start - 1 || f > W.end + 8) return null;

  const pulse = beatPulse(f, W.start, 15, 4.5);
  const head = sp(f, W.start, theme.spring.slam);
  const lock = sp(f, W.locked, theme.spring.slam);
  const locked = f >= W.locked;
  const clear = ei(f, [W.end - 6, W.end + 1], [0, 1], theme.ease.in);

  return (
    <AbsoluteFill style={{ opacity: 1 - clear }}>
      {/* pulsing brand gradient */}
      <AbsoluteFill style={{ background: theme.gradDiag }} />
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 50% ${45 + Math.sin(f / 6) * 4}%, rgba(255,255,255,${0.1 + pulse * 0.28}), transparent 60%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `linear-gradient(${(f * 3) % 360}deg, rgba(255,173,1,${0.25 * pulse}), rgba(252,4,100,${0.25 * (1 - pulse)}))`,
          mixBlendMode: "soft-light",
        }}
      />

      <AbsoluteFill
        style={{
          transform: `scale(${(1 + clear * 0.5) * (1 + pulse * 0.012) * (1 + lock * 0.04)}) rotate(${clear * -6}deg)`,
          filter: locked ? `brightness(${mix(1, 0.62, lock)}) blur(${lock * 2.5}px)` : undefined,
        }}
      >
        <div
          style={{
            position: "absolute",
            left: 70,
            top: 212,
            ...display(112, theme.c.offwhite),
            whiteSpace: "nowrap",
            opacity: Math.min(1, head * 2),
            transform: `scale(${mix(1.6, 1, head)}) rotate(${noise(f / 2, 1) * 0.8}deg)`,
            transformOrigin: "0% 50%",
            textShadow: "0 8px 30px rgba(16,16,19,0.25)",
          }}
        >
          FINAL WEEKEND
        </div>

        {cards.map((c, i) => {
          const t = W.cards[i];
          const p = sp(f, t, theme.spring.snappy);
          const landed = f > t + 8;
          const bop = landed ? beatPulse(f, W.start, 15, 3) * 10 : 0;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: 70,
                top: 384 + i * 252,
                width: 940,
                height: 228,
                boxSizing: "border-box",
                borderRadius: 46,
                background: theme.c.charcoal,
                boxShadow: "0 40px 70px -30px rgba(16,16,19,0.7), inset 0 0 0 2px rgba(255,255,255,0.06)",
                padding: "0 46px 0 36px",
                display: "flex",
                alignItems: "center",
                gap: 30,
                opacity: f < t ? 0 : 1,
                transform: `translate(${mix(c.from[0], 0, p)}px, ${mix(c.from[1], 0, p) - bop}px) rotate(${mix(c.rot * 6, c.rot, p)}deg)`,
              }}
            >
              <div
                style={{
                  width: 136,
                  height: 136,
                  flex: "none",
                  borderRadius: "50%",
                  background: theme.c.offwhite,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 78,
                }}
              >
                {c.icon}
              </div>
              <span style={{ ...display(92, theme.c.offwhite), flex: 1, whiteSpace: "nowrap" }}>{c.sport}</span>
              <Grad style={{ ...display(80), whiteSpace: "nowrap" }}>{c.time}</Grad>
            </div>
          );
        })}
      </AbsoluteFill>

      {/* LOCKED IN. */}
      {locked && (
        <>
          <SpeedLines start={W.locked} />
          <div
            style={{
              position: "absolute",
              left: -80,
              width: 1240,
              top: 640,
              height: 480,
              background: theme.c.charcoal,
              transform: `rotate(-4deg) scaleY(${Math.min(1, lock * 1.2)}) scale(${1 + Math.sin(f / 7) * 0.006})`,
              boxShadow: "0 50px 100px -30px rgba(16,16,19,0.7)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                ...display(232, theme.c.offwhite),
                textAlign: "center",
                lineHeight: 0.92,
                transform: `scale(${mix(2.8, 1, lock)})`,
                opacity: Math.min(1, lock * 3),
              }}
            >
              LOCKED
              <br />
              <Grad>IN.</Grad>
            </div>
          </div>
        </>
      )}

      <Flash at={W.start} len={6} peak={0.85} />
      <Flash at={W.locked} len={8} peak={0.95} />
    </AbsoluteFill>
  );
};
