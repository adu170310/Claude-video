import React from 'react';
import { AbsoluteFill, continueRender, delayRender, staticFile, useCurrentFrame } from 'remotion';
import { ThreeCanvas } from '@remotion/three';
import { Scene } from './three/Scene';
import { TL, prog, easeOut, easeIn, smooth } from './anim';

// Inter Display Medium: Inter's display optical size (opsz 32) at weight 500, from the OFL Inter font.
const fontHandle = delayRender('Loading Inter Display');
Promise.all(
  [
    ['InterDisplay', 'fonts/InterDisplay-Medium.ttf', '500'],
    ['InterDisplay', 'fonts/InterDisplay-Regular.ttf', '400'],
  ].map(([fam, file, w]) => new FontFace(fam, `url(${staticFile(file)})`, { weight: w }).load().then((ff) => document.fonts.add(ff))),
).then(() => continueRender(fontHandle));

const W = 1080;
const H = 1920;
// Safe area for type: below the top 10% and above the bottom 20%.
export const SAFE_TOP = H * 0.1;
export const SAFE_BOTTOM = H * 0.8;

// Soft dark glow so type reads on any background (bright tunnel screens included).
const GLOW_SHADOW = '0 0 18px rgba(8,9,12,0.55), 0 0 48px rgba(8,9,12,0.5), 0 4px 90px rgba(8,9,12,0.45)';

const Line: React.FC<{ text: string; a: number; b: number; y: number; size?: number; outLen?: number; inLen?: number }> = ({
  text, a, b, y, size = 100, outLen = 9, inLen = 16,
}) => {
  const f = useCurrentFrame();
  if (f < a || f > b) return null;
  const tin = easeOut(prog(f, a, a + inLen));
  const tout = easeIn(prog(f, b - outLen, b));
  const o = tin * (1 - tout);
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <div
        style={{
          position: 'absolute', left: 40, right: 40, top: y, height: size * 3.2, transform: 'translateY(-50%)',
          background: 'radial-gradient(ellipse 52% 46% at 50% 50%, rgba(10,11,14,0.42) 0%, rgba(10,11,14,0.18) 55%, rgba(10,11,14,0) 100%)',
          filter: 'blur(24px)',
        }}
      />
      <div
        style={{
          position: 'absolute', left: 60, right: 60, top: y, textAlign: 'center', whiteSpace: 'pre-line',
          transform: `translateY(calc(-50% + ${(1 - tin) * 20 - tout * 8}px)) scale(${1.0 + (0.012 * (f - a)) / 30})`,
          fontFamily: 'InterDisplay', fontWeight: 500, fontSize: size, lineHeight: 1.04, letterSpacing: '-0.02em',
          color: 'rgba(255,255,255,0.92)', filter: `blur(${(1 - tin) * 14 + tout * 10}px)`, textShadow: GLOW_SHADOW,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

/** Soft light wipe that hides a cut between sets: never darkens, never black. */
const GlowWipe: React.FC<{ at: number; width?: number }> = ({ at, width = 4 }) => {
  const f = useCurrentFrame();
  const i = Math.exp(-Math.pow((f - at) / width, 2));
  if (i < 0.01) return null;
  return (
    <AbsoluteFill style={{ mixBlendMode: 'screen', pointerEvents: 'none' }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 70% 55% at 50% 50%, rgba(255,246,236,${0.95 * i}) 0%, rgba(255,173,1,${0.55 * i}) 38%, rgba(252,4,100,${0.35 * i}) 68%, rgba(252,4,100,${0.12 * i}) 100%)`,
        }}
      />
      <AbsoluteFill style={{ background: `rgba(255,236,222,${0.45 * i})` }} />
    </AbsoluteFill>
  );
};

const WhiteFlash: React.FC = () => {
  const f = useCurrentFrame();
  const up = smooth(prog(f, TL.flashPeak - 5, TL.flashPeak));
  const down = 1 - easeOut(prog(f, TL.b8, TL.b8 + 10));
  const i = Math.min(up, down);
  if (i <= 0.001) return null;
  return <AbsoluteFill style={{ background: `rgba(255,253,250,${i})` }} />;
};

const EndCard: React.FC = () => {
  const f = useCurrentFrame();
  if (f < TL.b8) return null;
  const h = easeOut(prog(f, TL.b8 + 6, TL.b8 + 24));
  const btn = easeOut(prog(f, TL.b8 + 16, TL.b8 + 34));
  const pulse = 1 + 0.015 * Math.sin(Math.max(0, f - TL.b8 - 34) * 0.16);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute', left: 70, right: 70, top: 880, transform: `translateY(calc(-50% + ${(1 - h) * 16}px))`, textShadow: GLOW_SHADOW,
          textAlign: 'center', fontFamily: 'InterDisplay', fontWeight: 500, fontSize: 116, lineHeight: 1.04, letterSpacing: '-0.025em',
          color: 'rgba(255,255,255,0.92)', opacity: h, filter: `blur(${(1 - h) * 14}px)`,
        }}
      >
        Join the Athlo
        <br />
        30x30 challenge
      </div>
      <div
        style={{
          position: 'absolute', left: (W - 760) / 2, width: 760, top: 1250, height: 180, borderRadius: 90,
          transform: `translateY(calc(-50% + ${(1 - btn) * 18}px)) scale(${pulse})`, opacity: btn, filter: `blur(${(1 - btn) * 10}px)`,
          background: 'linear-gradient(100deg, #FFAD01 0%, #FE6A2E 45%, #FC0464 100%)',
          boxShadow: '0 18px 60px rgba(252,4,100,0.35), 0 6px 30px rgba(255,173,1,0.25), inset 0 1px 0 rgba(255,255,255,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'InterDisplay', fontWeight: 500, fontSize: 72, letterSpacing: '-0.015em', color: '#ffffff', textShadow: '0 2px 16px rgba(120,0,40,0.35)',
        }}
      >
        Link in bio
      </div>
    </AbsoluteFill>
  );
};

export const Reel: React.FC = () => (
  <AbsoluteFill style={{ background: '#1b1c20' }}>
    <ThreeCanvas width={W} height={H} flat dpr={1} gl={{ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' }} camera={{ fov: 32, position: [0, 0, 10] }}>
      <Scene />
    </ThreeCanvas>
    <Line text={"Every sport\nin Dubai.\nOne app."} a={-8} b={54} y={930} size={124} inLen={12} />
    <Line text="Just play." a={TL.b3 + 6} b={TL.b4 - 2} y={960} size={116} />
    <Line text={"Every sport.\nOne app."} a={TL.b4 + 4} b={TL.b5 + 2} y={960} size={108} />
    <Line text={"Your sports life,\nunleashed."} a={TL.b6 + 2} b={TL.b7 + 4} y={1385} size={104} />
    <GlowWipe at={TL.b3} />
    <GlowWipe at={TL.b4} />
    <GlowWipe at={TL.b5} />
    <GlowWipe at={TL.b7} width={3} />
    <WhiteFlash />
    <EndCard />
  </AbsoluteFill>
);
