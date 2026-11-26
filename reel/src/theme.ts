// Single source of truth: colours, type, easing, springs. Nothing is inlined in scenes.
import { Easing } from "remotion";

export const theme = {
  c: {
    orange: "#FFAD01",
    pink: "#FC0464",
    charcoal: "#101013",
    offwhite: "#F4F2EC",
    card: "#FFFFFF",
    ink2: "#5E5C57", // secondary text on off-white (contrast 6.4:1)
    hair: "rgba(16,16,19,0.08)",
  },
  grad: "linear-gradient(100deg, #FFAD01 0%, #FC0464 100%)",
  gradDiag: "linear-gradient(160deg, #FFAD01 0%, #FD5A35 45%, #FC0464 100%)",
  font: {
    display: "Inter Display", // Black 900
    ui: "Poppins", // Medium 500 (600 for buttons)
  },
  ease: {
    out: Easing.bezier(0.16, 1, 0.3, 1),
    inOut: Easing.bezier(0.83, 0, 0.17, 1),
    in: Easing.bezier(0.7, 0, 0.84, 0),
    soft: Easing.bezier(0.45, 0, 0.55, 1),
  },
  spring: {
    calm: { damping: 26, stiffness: 90, mass: 1 },
    smooth: { damping: 20, stiffness: 120, mass: 1 },
    snappy: { damping: 14, stiffness: 200, mass: 0.6 },
    bouncy: { damping: 9, stiffness: 190, mass: 0.7 },
    slam: { damping: 13, stiffness: 420, mass: 0.8 },
  },
  // Safe area: no text above 10% (192px) or below 80% (1536px).
  safe: { top: 200, bottom: 1520 },
} as const;
