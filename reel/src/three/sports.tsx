import React, { useMemo } from 'react';
import * as THREE from 'three';
import { ORANGE, PINK } from './glass';

/** Clean product-style sport objects: matte white or brushed metal, brand-colour accents. ~1 unit tall. */
export type SportObj = 'padel' | 'football' | 'shuttlecock' | 'dumbbell' | 'archery';
export const SPORT_OBJS: SportObj[] = ['padel', 'football', 'shuttlecock', 'dumbbell', 'archery'];

const GRAPHITE = '#2a2c32';

const Matte: React.FC<{ color?: string; side?: THREE.Side }> = ({ color = '#f4f4f6', side }) => (
  <meshPhysicalMaterial color={color} roughness={0.48} clearcoat={0.4} clearcoatRoughness={0.22} envMapIntensity={1.1} side={side} />
);
const Metal: React.FC = () => (
  <meshPhysicalMaterial color="#d9dce3" metalness={1} roughness={0.26} anisotropy={0.85} anisotropyRotation={Math.PI / 2} envMapIntensity={1.5} />
);
const Accent: React.FC<{ color: string }> = ({ color }) => (
  <meshPhysicalMaterial color={color} roughness={0.38} clearcoat={0.6} clearcoatRoughness={0.15} emissive={color} emissiveIntensity={0.12} />
);

const tube = (a: [number, number, number], b: [number, number, number], r: number) =>
  new THREE.TubeGeometry(new THREE.LineCurve3(new THREE.Vector3(...a), new THREE.Vector3(...b)), 1, r, 20, false);

// ------------------------------------------------------------------ football
/** Truncated-icosahedron pattern: pentagons around the 12 icosahedron vertices, hexagons around the 20 face centres. */
function footballTextures() {
  const W = 1024;
  const H = 512;
  const phi = (1 + Math.sqrt(5)) / 2;
  const ip = 1 / phi;
  const raw: number[][] = [];
  for (const s1 of [-1, 1]) for (const s2 of [-1, 1]) raw.push([0, s1, s2 * phi], [s1, s2 * phi, 0], [s1 * phi, 0, s2]);
  const pent = raw.map((v) => new THREE.Vector3(...v).normalize());
  const hexRaw: number[][] = [];
  for (const a of [-1, 1]) for (const b of [-1, 1]) for (const c of [-1, 1]) hexRaw.push([a, b, c]);
  // dual of the icosahedron above: these are its 20 face centres
  for (const a of [-1, 1]) for (const b of [-1, 1]) hexRaw.push([a * ip, 0, b * phi], [0, a * phi, b * ip], [a * phi, b * ip, 0]);
  const hex = hexRaw.map((v) => new THREE.Vector3(...v).normalize());
  const centres = [...pent.map((v, i) => ({ v, pent: true, i })), ...hex.map((v, i) => ({ v, pent: false, i }))];
  const col = document.createElement('canvas');
  col.width = W;
  col.height = H;
  const bump = document.createElement('canvas');
  bump.width = W;
  bump.height = H;
  const cc = col.getContext('2d')!;
  const bc = bump.getContext('2d')!;
  const ci = cc.createImageData(W, H);
  const bi = bc.createImageData(W, H);
  const o = new THREE.Color(ORANGE);
  const p = new THREE.Color(PINK);
  const d = new THREE.Vector3();
  for (let y = 0; y < H; y++) {
    const th = ((y + 0.5) / H) * Math.PI;
    for (let x = 0; x < W; x++) {
      const ph = ((x + 0.5) / W) * Math.PI * 2;
      d.set(-Math.cos(ph) * Math.sin(th), Math.cos(th), Math.sin(ph) * Math.sin(th));
      let b1 = -2;
      let b2 = -2;
      let best = centres[0];
      for (const c of centres) {
        // pentagons slightly smaller than hexagons, as on a real ball
        const s = d.dot(c.v) + (c.pent ? 0.004 : 0);
        if (s > b1) {
          b2 = b1;
          b1 = s;
          best = c;
        } else if (s > b2) b2 = s;
      }
      const seam = b1 - b2 < 0.011;
      const k = (y * W + x) * 4;
      let r = 0.955, g = 0.955, bl = 0.965;
      if (best.pent) {
        const c = best.i % 2 ? p : o;
        [r, g, bl] = [c.r, c.g, c.b].map((v) => Math.pow(v, 1 / 2.2));
      }
      if (seam) [r, g, bl] = [0.22, 0.23, 0.26];
      ci.data[k] = r * 255;
      ci.data[k + 1] = g * 255;
      ci.data[k + 2] = bl * 255;
      ci.data[k + 3] = 255;
      const bv = seam ? 0 : 255;
      bi.data[k] = bi.data[k + 1] = bi.data[k + 2] = bv;
      bi.data[k + 3] = 255;
    }
  }
  cc.putImageData(ci, 0, 0);
  bc.putImageData(bi, 0, 0);
  const map = new THREE.CanvasTexture(col);
  map.colorSpace = THREE.SRGBColorSpace;
  map.anisotropy = 8;
  const bumpMap = new THREE.CanvasTexture(bump);
  return { map, bumpMap };
}

let FOOTBALL: ReturnType<typeof footballTextures> | null = null;

const Football: React.FC = () => {
  const tex = useMemo(() => (FOOTBALL ??= footballTextures()), []);
  return (
    <mesh rotation={[0.4, 0.3, 0]}>
      <sphereGeometry args={[0.5, 96, 64]} />
      <meshPhysicalMaterial map={tex.map} bumpMap={tex.bumpMap} bumpScale={1.2} roughness={0.42} clearcoat={0.5} clearcoatRoughness={0.2} />
    </mesh>
  );
};

// ------------------------------------------------------------------ padel racket
const Padel: React.FC = () => {
  const { face, rim } = useMemo(() => {
    const s = new THREE.Shape();
    s.absellipse(0, 0, 0.36, 0.42, 0, Math.PI * 2, false, 0);
    for (let y = -0.3; y <= 0.31; y += 0.085)
      for (let x = -0.3; x <= 0.31; x += 0.085) {
        const xo = x + (Math.round(y / 0.085) % 2 ? 0.0425 : 0);
        if ((xo / 0.29) ** 2 + (y / 0.34) ** 2 < 0.92) {
          const h = new THREE.Path();
          h.absarc(xo, y, 0.022, 0, Math.PI * 2, true);
          s.holes.push(h);
        }
      }
    const face = new THREE.ExtrudeGeometry(s, { depth: 0.06, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.012, bevelSegments: 3, curveSegments: 48 });
    face.translate(0, 0, -0.03);
    const r = new THREE.Shape();
    r.absellipse(0, 0, 0.395, 0.455, 0, Math.PI * 2, false, 0);
    const hole = new THREE.Path();
    hole.absellipse(0, 0, 0.37, 0.43, 0, Math.PI * 2, true, 0);
    r.holes.push(hole);
    const rim = new THREE.ExtrudeGeometry(r, { depth: 0.1, bevelEnabled: true, bevelThickness: 0.01, bevelSize: 0.008, bevelSegments: 3, curveSegments: 64 });
    rim.translate(0, 0, -0.05);
    return { face, rim };
  }, []);
  const throatL = useMemo(() => tube([-0.15, -0.38, 0], [-0.04, -0.6, 0], 0.028), []);
  const throatR = useMemo(() => tube([0.15, -0.38, 0], [0.04, -0.6, 0], 0.028), []);
  return (
    <group position={[0, 0.22, 0]} scale={0.95}>
      <mesh geometry={face}><Matte /></mesh>
      <mesh geometry={rim}><Accent color={ORANGE} /></mesh>
      <mesh geometry={throatL}><Metal /></mesh>
      <mesh geometry={throatR}><Metal /></mesh>
      <mesh position={[0, -0.84, 0]}>
        <cylinderGeometry args={[0.058, 0.052, 0.48, 32]} />
        <Accent color={PINK} />
      </mesh>
      <mesh position={[0, -0.6, 0]}>
        <cylinderGeometry args={[0.062, 0.062, 0.05, 32]} />
        <Metal />
      </mesh>
      <mesh position={[0, -1.09, 0]}>
        <cylinderGeometry args={[0.07, 0.07, 0.035, 32]} />
        <Metal />
      </mesh>
    </group>
  );
};

// ------------------------------------------------------------------ shuttlecock
const Shuttlecock: React.FC = () => {
  const ribs = useMemo(
    () =>
      Array.from({ length: 16 }, (_, i) => {
        const a = (i / 16) * Math.PI * 2;
        return tube([0.155 * Math.cos(a), -0.12, 0.155 * Math.sin(a)], [0.43 * Math.cos(a), 0.52, 0.43 * Math.sin(a)], 0.008);
      }),
    [],
  );
  return (
    <group position={[0, -0.1, 0]}>
      <mesh position={[0, -0.18, 0]} rotation={[Math.PI, 0, 0]}>
        <sphereGeometry args={[0.17, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <Matte />
      </mesh>
      <mesh position={[0, -0.145, 0]}>
        <cylinderGeometry args={[0.172, 0.172, 0.075, 48]} />
        <Accent color={PINK} />
      </mesh>
      <mesh position={[0, 0.2, 0]}>
        <cylinderGeometry args={[0.43, 0.155, 0.64, 48, 1, true]} />
        <meshPhysicalMaterial color="#f7f7f9" roughness={0.55} transmission={0.35} thickness={0.05} side={THREE.DoubleSide} clearcoat={0.2} />
      </mesh>
      {ribs.map((g, i) => (
        <mesh key={i} geometry={g}><Matte color="#ffffff" /></mesh>
      ))}
      {[
        [0.06, 0.22],
        [0.26, 0.31],
      ].map(([y, r], i) => (
        <mesh key={i} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[r, 0.012, 12, 64]} />
          <Accent color={ORANGE} />
        </mesh>
      ))}
    </group>
  );
};

// ------------------------------------------------------------------ dumbbell
const Dumbbell: React.FC = () => (
  <group rotation={[0, 0, 0.32]} scale={0.92}>
    <mesh rotation={[0, 0, Math.PI / 2]}>
      <cylinderGeometry args={[0.045, 0.045, 1.0, 32]} />
      <Metal />
    </mesh>
    {[-1, 1].map((s) => (
      <group key={s}>
        <mesh position={[s * 0.44, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.25, 0.25, 0.3, 6]} />
          <Matte />
        </mesh>
        <mesh position={[s * 0.595, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.17, 0.17, 0.02, 48]} />
          <Accent color={s > 0 ? PINK : ORANGE} />
        </mesh>
        <mesh position={[s * 0.27, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.075, 0.075, 0.05, 32]} />
          <Metal />
        </mesh>
      </group>
    ))}
  </group>
);

// ------------------------------------------------------------------ archery target
const Archery: React.FC = () => {
  const rings: [number, number, string][] = [
    [0.4, 0.5, '#f4f4f6'],
    [0.3, 0.4, GRAPHITE],
    [0.2, 0.3, '#f4f4f6'],
    [0.1, 0.2, PINK],
    [0.0, 0.1, ORANGE],
  ];
  const fletch = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(0, 0);
    s.lineTo(0.16, 0);
    s.lineTo(0.12, 0.06);
    s.lineTo(0.02, 0.06);
    s.closePath();
    return new THREE.ShapeGeometry(s);
  }, []);
  return (
    <group rotation={[0.15, -0.35, 0]}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.52, 0.52, 0.1, 96]} />
        <Matte />
      </mesh>
      {rings.map(([a, b, c], i) => (
        <mesh key={i} position={[0, 0, 0.051 + i * 0.0015]}>
          <ringGeometry args={[a, b, 96]} />
          {c === PINK || c === ORANGE ? <Accent color={c} /> : <Matte color={c} />}
        </mesh>
      ))}
      {/* arrow in the centre */}
      <group position={[0.02, 0.03, 0.06]} rotation={[0.55, 0.65, 0]}>
        <mesh position={[0, 0, 0.32]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.014, 0.014, 0.64, 16]} />
          <Metal />
        </mesh>
        {[0, 1, 2].map((k) => (
          <mesh key={k} geometry={fletch} position={[0, 0, 0.5]} rotation={[0, -Math.PI / 2, (k * Math.PI * 2) / 3]}>
            <meshPhysicalMaterial color={PINK} roughness={0.4} side={THREE.DoubleSide} />
          </mesh>
        ))}
      </group>
    </group>
  );
};

export const SportObject: React.FC<{ kind: SportObj }> = ({ kind }) => {
  switch (kind) {
    case 'padel':
      return <Padel />;
    case 'football':
      return <Football />;
    case 'shuttlecock':
      return <Shuttlecock />;
    case 'dumbbell':
      return <Dumbbell />;
    case 'archery':
      return <Archery />;
  }
};
