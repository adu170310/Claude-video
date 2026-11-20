import React, { useMemo } from 'react';
import * as THREE from 'three';

export const ORANGE = '#FFAD01';
export const PINK = '#FC0464';

type GlassProps = {
  roughness?: number;
  thickness?: number;
  tint?: string;
  glow?: number;
  ior?: number;
  opacity?: number;
};

/**
 * Real physically based glass: transmission through the scene behind it, roughness blurs
 * what is seen through it (frosted), clearcoat and env reflections give the soft highlights.
 */
export const Glass: React.FC<GlassProps> = ({ roughness = 0.12, thickness = 0.5, tint = '#ffffff', glow = 0, ior = 1.45, opacity = 1 }) => (
  <meshPhysicalMaterial
    transmission={1}
    roughness={roughness}
    thickness={thickness}
    ior={ior}
    metalness={0}
    clearcoat={1}
    clearcoatRoughness={0.08}
    color="#ffffff"
    attenuationColor={tint}
    attenuationDistance={1.6}
    specularIntensity={1}
    envMapIntensity={1.35}
    emissive={tint}
    emissiveIntensity={glow}
    transparent={opacity < 1}
    opacity={opacity}
  />
);

/** Tube along a smooth curve through points, with rounded caps. */
export const Limb: React.FC<{ pts: [number, number, number][]; r: number; children: React.ReactNode }> = ({ pts, r, children }) => {
  const geo = useMemo(() => {
    const curve = new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p)), false, 'centripetal');
    return new THREE.TubeGeometry(curve, 48, r, 20, false);
  }, [pts, r]);
  const a = pts[0];
  const b = pts[pts.length - 1];
  return (
    <group>
      <mesh geometry={geo}>{children}</mesh>
      <mesh position={a}>
        <sphereGeometry args={[r, 20, 16]} />
        {children}
      </mesh>
      <mesh position={b}>
        <sphereGeometry args={[r, 20, 16]} />
        {children}
      </mesh>
    </group>
  );
};

export type Sport = 'padel' | 'football' | 'running' | 'archery' | 'gym' | 'swimming';
export const SPORTS: Sport[] = ['padel', 'football', 'running', 'archery', 'gym', 'swimming'];

const padelShape = () => {
  const s = new THREE.Shape();
  s.absellipse(0, 0, 0.34, 0.4, 0, Math.PI * 2, false, 0);
  const holes: [number, number][] = [];
  for (let y = -0.24; y <= 0.25; y += 0.12)
    for (let x = -0.24; x <= 0.25; x += 0.12) if ((x / 0.3) ** 2 + (y / 0.34) ** 2 < 0.85) holes.push([x, y]);
  for (const [x, y] of holes) {
    const h = new THREE.Path();
    h.absarc(x, y, 0.035, 0, Math.PI * 2, true);
    s.holes.push(h);
  }
  return s;
};

/** Small glass sport icon, about 1 unit across. All geometry is built here; no outside icon sets. */
export const SportIcon: React.FC<{ sport: Sport; tint: string; glow?: number }> = ({ sport, tint, glow = 0.18 }) => {
  const m = <Glass roughness={0.06} thickness={0.35} tint={tint} glow={glow} ior={1.5} />;
  const padelGeo = useMemo(
    () => new THREE.ExtrudeGeometry(padelShape(), { depth: 0.08, bevelEnabled: true, bevelThickness: 0.03, bevelSize: 0.03, bevelSegments: 4, curveSegments: 40 }),
    [],
  );
  switch (sport) {
    case 'padel':
      return (
        <group rotation={[0, 0, -0.5]}>
          <mesh geometry={padelGeo} position={[0, 0.12, -0.04]}>{m}</mesh>
          <Limb pts={[[0, -0.3, 0], [0, -0.62, 0]]} r={0.055}>{m}</Limb>
        </group>
      );
    case 'football':
      return (
        <mesh>
          <icosahedronGeometry args={[0.42, 1]} />
          <meshPhysicalMaterial transmission={1} roughness={0.05} thickness={0.8} ior={1.5} clearcoat={1} flatShading
            attenuationColor={tint} attenuationDistance={1.2} emissive={tint} emissiveIntensity={glow} envMapIntensity={1.4} />
        </mesh>
      );
    case 'running':
      return (
        <group position={[0, -0.02, 0]}>
          <mesh position={[0.14, 0.43, 0]}>
            <sphereGeometry args={[0.1, 28, 20]} />
            {m}
          </mesh>
          <Limb pts={[[0.06, 0.28, 0], [-0.04, 0.0, 0]]} r={0.06}>{m}</Limb>
          <Limb pts={[[0.04, 0.23, 0], [0.22, 0.12, 0], [0.33, 0.24, 0]]} r={0.045}>{m}</Limb>
          <Limb pts={[[0.04, 0.23, 0], [-0.14, 0.17, 0], [-0.26, 0.04, 0]]} r={0.045}>{m}</Limb>
          <Limb pts={[[-0.04, 0.0, 0], [0.16, -0.14, 0], [0.12, -0.38, 0]]} r={0.05}>{m}</Limb>
          <Limb pts={[[-0.04, 0.0, 0], [-0.16, -0.2, 0], [-0.36, -0.26, 0]]} r={0.05}>{m}</Limb>
        </group>
      );
    case 'archery':
      return (
        <group>
          <mesh>
            <torusGeometry args={[0.4, 0.04, 20, 64]} />
            {m}
          </mesh>
          <mesh>
            <torusGeometry args={[0.24, 0.04, 20, 64]} />
            {m}
          </mesh>
          <mesh>
            <sphereGeometry args={[0.09, 24, 18]} />
            {m}
          </mesh>
          <group rotation={[0, 0, Math.PI / 4]}>
            <Limb pts={[[0, 0.05, 0.02], [0, 0.62, 0.02]]} r={0.022}>{m}</Limb>
            <mesh position={[0, 0.05, 0.02]} rotation={[Math.PI, 0, 0]}>
              <coneGeometry args={[0.06, 0.14, 20]} />
              {m}
            </mesh>
          </group>
        </group>
      );
    case 'gym':
      return (
        <group rotation={[0, 0, 0.35]}>
          <Limb pts={[[-0.5, 0, 0], [0.5, 0, 0]]} r={0.035}>{m}</Limb>
          {[-1, 1].map((sgn) => (
            <group key={sgn}>
              <mesh position={[sgn * 0.28, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
                <cylinderGeometry args={[0.2, 0.2, 0.1, 40]} />
                {m}
              </mesh>
              <mesh position={[sgn * 0.4, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
                <cylinderGeometry args={[0.15, 0.15, 0.08, 40]} />
                {m}
              </mesh>
            </group>
          ))}
        </group>
      );
    case 'swimming': {
      const wave = (y: number): [number, number, number][] =>
        Array.from({ length: 9 }, (_, i) => [-0.45 + i * 0.1125, y + 0.05 * Math.sin(i * 1.6), 0]);
      return (
        <group>
          <mesh position={[0.2, 0.17, 0]}>
            <sphereGeometry args={[0.1, 28, 20]} />
            {m}
          </mesh>
          <Limb pts={[[-0.36, 0.0, 0], [-0.12, 0.26, 0], [0.06, 0.2, 0]]} r={0.045}>{m}</Limb>
          <Limb pts={wave(-0.14)} r={0.035}>{m}</Limb>
          <Limb pts={wave(-0.32)} r={0.035}>{m}</Limb>
        </group>
      );
    }
  }
};
