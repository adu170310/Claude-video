import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { theme } from "../theme";
import T from "../timeline.json";
import { ei, mix, noise, sp } from "../util";
import { Check, display, Grad, Mesh, ui } from "../components/Atoms";
import { AlarmClock } from "../components/AlarmClock";

const D1 = T.day1;
const D10 = T.day10;
const D20 = T.day20;
const START = T.hook.end - 5;
const END = T.weekend.start + 8;

const stages = [
  { at: D1.start, n: "1", sub: "The plan is flawless.", cfg: theme.spring.calm },
  { at: D10.start, n: "10", sub: "Still going. Mostly.", cfg: theme.spring.snappy },
  { at: D20.start, n: "20", sub: "It's fine. Everything's fine.", cfg: theme.spring.bouncy },
];

const Header: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <>
      {stages.map((s, i) => {
        const next = stages[i + 1]?.at ?? 99999;
        if (f < s.at - 4 || f > next + 8) return null;
        const p = sp(f, s.at, s.cfg);
        const ps = sp(f, s.at + 5, s.cfg);
        const out = ei(f, [next - 1, next + 6], [0, 1], theme.ease.in);
        const chaos = i === 2 ? 1 : 0;
        const jx = chaos * noise(f / 1.4, 2) * 5;
        const jr = chaos * noise(f / 1.7, 7) * 1.6 + (i === 1 ? -2 : 0);
        return (
          <div key={i} style={{ position: "absolute", left: 78, top: 214 }}>
            <div
              style={{
                ...display(176),
                whiteSpace: "nowrap",
                opacity: Math.min(1, p * 1.4) * (1 - out),
                transform: `translate(${jx}px, ${mix(70, 0, p) - out * 90}px) rotate(${jr}deg) scale(${mix(0.92, 1, p)})`,
                transformOrigin: "0% 100%",
              }}
            >
              DAY <Grad>{s.n}</Grad>
            </div>
            <div
              style={{
                ...ui(50, theme.c.ink2),
                marginTop: 10,
                whiteSpace: "nowrap",
                opacity: ps * (1 - out),
                transform: `translateY(${mix(30, 0, ps) - out * 60}px)`,
              }}
            >
              {s.sub}
            </div>
          </div>
        );
      })}
    </>
  );
};

type Row = { main: string; aside?: string };
const rows1: Row[] = [
  { main: "6am alarm" },
  { main: "Matching gym fit" },
  { main: "Meal prepped" },
  { main: "Logged: padel, 60 min" },
];
const rows10: Row[] = [
  { main: "6am alarm", aside: "(snoozed ×2)" },
  { main: "Gym fit", aside: "(it's clean, probably)" },
  { main: "Logged: 5K run", aside: "(mostly walking)" },
];

const Card: React.FC = () => {
  const f = useCurrentFrame();
  const enter = sp(f, START + 2, theme.spring.calm);
  const tilt10 = sp(f, D10.start, theme.spring.bouncy);
  const tilt20 = sp(f, D20.start, theme.spring.bouncy);
  const wob10 = f > D10.start ? noise(f / 9, 1) * 0.9 : 0;
  const wob20 = f > D20.start ? noise(f / 3.2, 3) * 3.2 : 0;
  const rot = mix(0, -3.2, tilt10) + tilt20 * 8.2 + wob10 + wob20;
  const dim = tilt20;
  const breathe = Math.sin(f / 20) * 4;
  const dayN = f < D10.start ? 1 : f < D20.start ? 10 : 20;

  const swapOut = (i: number) => ei(f, [D10.swap - 3 + i * 2, D10.swap + 4 + i * 2], [0, 1], theme.ease.in);

  return (
    <div
      style={{
        position: "absolute",
        left: 70,
        top: 540,
        width: 940,
        height: 800,
        perspective: 1600,
        transform: `translateY(${mix(160, 0, enter) + breathe + dim * 40}px) rotate(${rot}deg) scale(${mix(0.95, 1, enter) - dim * 0.06})`,
        opacity: Math.min(1, enter * 1.5) * (1 - dim * 0.45),
        filter: dim > 0.01 ? `blur(${dim * 3.5}px)` : undefined,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: theme.c.card,
          borderRadius: 56,
          boxShadow: "0 50px 90px -40px rgba(16,16,19,0.38), 0 2px 0 rgba(16,16,19,0.04)",
          transform: `rotateX(${Math.sin(f / 30) * 1.2}deg) rotateY(${Math.cos(f / 36) * 1.6}deg)`,
          padding: "46px 52px",
          boxSizing: "border-box",
          overflow: "hidden",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 30 }}>
          <span style={ui(46, theme.c.charcoal, 600)}>Today's plan</span>
          <span
            style={{
              ...ui(44, theme.c.pink, 600),
              background: "rgba(252,4,100,0.08)",
              borderRadius: 999,
              padding: "6px 26px",
            }}
          >
            Day {dayN}/30
          </span>
        </div>
        <div style={{ height: 2, background: theme.c.hair, marginBottom: 14 }} />

        {/* Day 1 rows */}
        {f < D10.swap + 12 && (
          <div style={{ position: "absolute", left: 52, right: 52, top: 168 }}>
            {rows1.map((r, i) => {
              const o = swapOut(i);
              const pin = sp(f, START + 8 + i * 4, theme.spring.calm);
              return (
                <div
                  key={i}
                  style={{
                    height: 148,
                    display: "flex",
                    alignItems: "center",
                    gap: 30,
                    opacity: Math.min(1, pin * 1.5) * (1 - o),
                    transform: `translateY(${mix(30, 0, pin) - o * 40}px)`,
                  }}
                >
                  <Check p={sp(f, D1.ticks[i] + 2, theme.spring.smooth)} />
                  <span style={{ ...ui(52), whiteSpace: "nowrap" }}>{r.main}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* Day 10 rows */}
        {f >= D10.swap && (
          <div style={{ position: "absolute", left: 52, right: 52, top: 172 }}>
            {rows10.map((r, i) => {
              const pin = sp(f, D10.swap + 4 + i * 4, theme.spring.snappy);
              const crooked = [-16, 12, -8][i];
              return (
                <div
                  key={i}
                  style={{
                    height: 196,
                    display: "flex",
                    alignItems: "center",
                    gap: 30,
                    opacity: Math.min(1, pin * 1.6),
                    transform: `translateY(${mix(50, 0, pin)}px) rotate(${mix(4, 0, pin)}deg)`,
                  }}
                >
                  <Check p={sp(f, D10.ticks[i] + 1, theme.spring.bouncy)} crooked={crooked} />
                  <div style={{ display: "flex", flexDirection: "column" }}>
                    <span style={{ ...ui(54), whiteSpace: "nowrap" }}>{r.main}</span>
                    <span style={{ ...ui(46, theme.c.pink), whiteSpace: "nowrap" }}>{r.aside}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

const notifs = [
  { icon: "⏰", app: "Alarm", body: "Snooze ×6", h: 200 },
  { icon: "🏃", app: "30x30 Challenge", body: "Your friend logged another session 👀", h: 262 },
  { icon: "🏆", app: "30x30 Challenge", body: "Leaderboard updated", h: 200 },
];

const Notifications: React.FC = () => {
  const f = useCurrentFrame();
  if (f < D20.notifs[0] - 2) return null;
  const gap = 24;
  return (
    <>
      {notifs.map((n, i) => {
        const t = D20.notifs[i];
        if (f < t - 1) return null;
        const p = sp(f, t, theme.spring.bouncy);
        let push = 0;
        for (let j = i + 1; j < notifs.length; j++) push += sp(f, D20.notifs[j], theme.spring.bouncy) * (notifs[j].h + gap);
        const since = f - t;
        const buzz = since < 14 ? Math.sin(since * 2.6) * 14 * Math.exp(-since / 5) : 0;
        const wob = noise(f / 4, i + 2) * 1.3;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: 70,
              top: 556 + push,
              width: 940,
              height: n.h,
              boxSizing: "border-box",
              transform: `translate(${buzz}px, ${mix(-520, 0, p)}px) rotate(${wob}deg) scale(${mix(0.86, 1, Math.min(1, p))})`,
              opacity: Math.min(1, p * 2.5),
              background: "#FFFFFF",
              borderRadius: 48,
              boxShadow: "0 36px 70px -28px rgba(16,16,19,0.45), 0 0 0 2px rgba(16,16,19,0.04)",
              padding: "30px 36px",
              display: "flex",
              gap: 28,
              alignItems: "flex-start",
            }}
          >
            <div
              style={{
                width: 100,
                height: 100,
                flex: "none",
                borderRadius: 28,
                background: theme.gradDiag,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 58,
              }}
            >
              {n.icon}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={ui(44, theme.c.ink2, 600)}>{n.app}</span>
                <span style={ui(44, theme.c.ink2)}>now</span>
              </div>
              <span style={ui(52)}>{n.body}</span>
            </div>
          </div>
        );
      })}
    </>
  );
};

const Alarm: React.FC = () => {
  const f = useCurrentFrame();
  if (f < D20.start - 2) return null;
  const p = sp(f, D20.start + 1, theme.spring.bouncy);
  const ringing = D20.alarm.some((a) => f >= a && f < a + 26);
  const amp = ringing ? 11 : 2.5;
  const r = Math.sin(f * 2.3) * amp;
  const jx = ringing ? Math.sin(f * 3.1) * 6 : 0;
  return (
    <div
      style={{
        position: "absolute",
        left: 770,
        top: 196,
        transform: `translate(${jx}px, ${mix(-300, 0, p)}px) rotate(${r}deg) scale(${p})`,
        transformOrigin: "50% 60%",
      }}
    >
      <AlarmClock size={230} ring={ringing ? 1 : 0.15} hammer={ringing ? Math.sin(f * 3.4) : 0} />
    </div>
  );
};

export const Journey: React.FC = () => {
  const f = useCurrentFrame();
  if (f < START || f > END) return null;
  // Day 20 warms the background; the drop blows everything away.
  const heat = sp(f, D20.start, theme.spring.smooth);
  const blow = ei(f, [T.weekend.start - 1, END], [0, 1], theme.ease.in);
  return (
    <AbsoluteFill
      style={{
        transform: `scale(${1 + blow * 0.35})`,
        opacity: 1 - blow,
        filter: blow > 0 ? `blur(${blow * 14}px)` : undefined,
      }}
    >
      <Mesh base={theme.c.offwhite} amount={0.1 + heat * 0.2 + (f > D10.start ? 0.05 : 0)} speed={1 + heat * 2} />
      <Header />
      <Card />
      <Alarm />
      <Notifications />
    </AbsoluteFill>
  );
};
