import React from "react";
import { theme } from "../theme";

/** Twin-bell alarm clock drawn in brand colours. `ring` 0..1 controls the shake-line intensity. */
export const AlarmClock: React.FC<{ size: number; ring: number; hammer: number }> = ({ size, ring, hammer }) => (
  <svg width={size} height={size} viewBox="0 0 200 200" style={{ overflow: "visible" }}>
    <defs>
      <linearGradient id="acg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor={theme.c.orange} />
        <stop offset="1" stopColor={theme.c.pink} />
      </linearGradient>
    </defs>
    {/* shake lines */}
    <g stroke={theme.c.charcoal} strokeWidth={6} strokeLinecap="round" fill="none" opacity={ring}>
      <path d="M14 70 Q2 100 14 130" />
      <path d="M-6 58 Q-22 100 -6 142" />
      <path d="M186 70 Q198 100 186 130" />
      <path d="M206 58 Q222 100 206 142" />
    </g>
    {/* legs */}
    <path d="M58 168 L44 192 M142 168 L156 192" stroke={theme.c.charcoal} strokeWidth={12} strokeLinecap="round" />
    {/* bells */}
    <path d="M30 62 A34 34 0 0 1 78 22 Z" fill={theme.c.charcoal} />
    <path d="M170 62 A34 34 0 0 0 122 22 Z" fill={theme.c.charcoal} />
    {/* hammer */}
    <g transform={`rotate(${hammer * 22} 100 40)`}>
      <path d="M100 40 L100 18" stroke={theme.c.charcoal} strokeWidth={8} strokeLinecap="round" />
      <circle cx={100} cy={14} r={9} fill={theme.c.charcoal} />
    </g>
    {/* body */}
    <circle cx={100} cy={110} r={72} fill="url(#acg)" />
    <circle cx={100} cy={110} r={56} fill={theme.c.offwhite} />
    {/* hands */}
    <path d="M100 110 L100 72" stroke={theme.c.charcoal} strokeWidth={9} strokeLinecap="round" />
    <path d="M100 110 L126 122" stroke={theme.c.charcoal} strokeWidth={9} strokeLinecap="round" />
    <circle cx={100} cy={110} r={8} fill={theme.c.pink} />
  </svg>
);
