import React, { useLayoutEffect, useMemo } from 'react';
import * as THREE from 'three';
import { useThree } from '@react-three/fiber';
import { Environment, Lightformer, RoundedBox, Text, useTexture } from '@react-three/drei';
import { EffectComposer, Bloom, DepthOfField, ToneMapping, Vignette, Noise } from '@react-three/postprocessing';
import { BlendFunction, ToneMappingMode } from 'postprocessing';
import { staticFile, useCurrentFrame } from 'remotion';
import { TL, prog, lerp, easeInOut, easeOut, easeIn, smooth, path, rand, env } from '../anim';
import { Glass, SportIcon, SPORTS, ORANGE, PINK } from './glass';
import { Settle } from './Settle';

const SCREENS = Array.from({ length: 9 }, (_, i) => staticFile(`screens/screen_${i}.jpg`));
const FONT = staticFile('fonts/InterDisplay-Medium.ttf');
useTexture.preload(SCREENS);
useTexture.preload(staticFile('logo_full.png'));
useTexture.preload(staticFile('logo_rings.png'));

// --------------------------------------------------------------------------- shot list
type Shot = { pos: number[]; look: number[]; fov: number; roll?: number; focus: number; range: number; bokeh: number };

function shotAt(f: number): Shot {
  if (f < TL.b3) {
    // Beats 1-2: slow dolly from wide studio into the glass panel and orb
    const p = path(f, [
      [0, [0.9, 1.3, 16.5, 0.0, 0.35, 0, 30]],
      [45, [0.6, 0.85, 14.0, 0.0, 0.2, 0, 31]],
      [85, [0.3, 0.45, 11.4, 0.0, 0.08, 0, 32]],
      [120, [0.08, 0.15, 9.4, 0.0, 0.0, 0, 33]],
    ]);
    return { pos: p.slice(0, 3), look: p.slice(3, 6), fov: p[6], focus: p[2] - 0.6, range: 2.8, bokeh: 3 };
  }
  if (f < TL.b4) {
    // Beat 3: fly-through down the tunnel of real app screens, accelerating
    const t = prog(f, TL.b3, TL.b4);
    const z = 3 - 46 * (0.38 * t + 0.62 * t * t);
    const x = 0.18 * Math.sin(t * 3.2);
    const y = 0.12 * Math.cos(t * 2.4);
    return { pos: [x, y, z], look: [x * 0.4, y * 0.4, z - 12], fov: 58, roll: 0.14 * Math.sin(t * Math.PI), focus: 3.2, range: 3.4, bokeh: 4 };
  }
  if (f < TL.b5) {
    // Beat 4: glass tiles drifting in depth, camera dollies and slides
    const p = path(f, [
      [TL.b4, [0.6, 0.25, 8.4, 0.1, 0.0, -2]],
      [TL.b5, [-0.45, -0.1, 5.6, -0.1, 0.0, -2]],
    ]);
    return { pos: p.slice(0, 3), look: p.slice(3, 6), fov: 38, focus: 5.4, range: 2.4, bokeh: 4.5 };
  }
  if (f < TL.b7) {
    // Beats 5-6: tilt up across the pill, then pull back as the streaks open up
    const p = path(f, [
      [TL.b5, [-0.9, -0.95, 9.6, 0.0, -0.55, 0]],
      [290, [-0.25, -0.55, 8.6, 0.0, -0.45, 0]],
      [TL.b6, [0.3, -0.6, 8.2, 0.0, -0.7, 0]],
      [TL.b7, [0.05, -0.95, 9.8, 0.0, -0.95, 0]],
    ]);
    const d = Math.hypot(p[0], p[1], p[2]);
    return { pos: p.slice(0, 3), look: p.slice(3, 6), fov: 34, focus: d, range: 2.2, bokeh: 3 };
  }
  if (f < TL.b8) {
    // Beat 7: push in on the flare; focus racks onto the logo as it emerges
    const t = prog(f, TL.b7, TL.b8);
    const z = 8.2 - 1.2 * t;
    const rack = 1 - easeOut(prog(f, TL.b7 + 2, TL.b7 + 16));
    return { pos: [0.15 * (1 - t), -0.05, z], look: [0, 0, 0], fov: 32, focus: z - 2.5 * rack, range: 1.2, bokeh: 3 + 3 * rack };
  }
  // Beat 8: end card, slow drift
  const t = prog(f, TL.b8, TL.duration);
  return { pos: [0.35 - 0.6 * t, 0.55 + 0.15 * t, 8.6 - 0.9 * t], look: [0, 0.35, 0], fov: 32, focus: 8.2, range: 3, bokeh: 2.5 };
}

const CameraRig: React.FC = () => {
  const f = useCurrentFrame();
  const { camera } = useThree();
  useLayoutEffect(() => {
    const s = shotAt(f);
    const cam = camera as THREE.PerspectiveCamera;
    cam.position.set(s.pos[0], s.pos[1], s.pos[2]);
    cam.up.set(Math.sin(s.roll ?? 0), Math.cos(s.roll ?? 0), 0);
    cam.lookAt(s.look[0], s.look[1], s.look[2]);
    cam.fov = s.fov;
    cam.near = 0.05;
    cam.far = 300;
    cam.updateProjectionMatrix();
  }, [f, camera]);
  return null;
};

// --------------------------------------------------------------------------- studio
const BACKDROP_FRAG = /* glsl */ `
uniform float uOn; uniform vec3 uBase; uniform vec3 uLift; uniform vec3 uO; uniform vec3 uP;
uniform vec3 uDO; uniform vec3 uDP; uniform vec3 uDW;
varying vec3 vDir;
void main(){
  vec3 d = normalize(vDir);
  float hz = 1.0 - smoothstep(0.0, 0.55, abs(d.y + 0.08));
  vec3 col = mix(uBase, uLift, hz * 0.8);
  col += uO * pow(max(dot(d, uDO), 0.0), 18.0) * uOn;
  col += uP * pow(max(dot(d, uDP), 0.0), 18.0) * uOn;
  col += vec3(1.0, 0.93, 0.86) * 0.02 * pow(max(dot(d, uDW), 0.0), 5.0) * uOn;
  gl_FragColor = vec4(col, 1.0);
}`;
const BACKDROP_VERT = /* glsl */ `
varying vec3 vDir;
void main(){ vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

const Backdrop: React.FC<{ on: number }> = ({ on }) => {
  const { camera } = useThree();
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        side: THREE.BackSide,
        depthWrite: false,
        toneMapped: false,
        vertexShader: BACKDROP_VERT,
        fragmentShader: BACKDROP_FRAG,
        uniforms: {
          uOn: { value: 0 },
          uBase: { value: new THREE.Color('#1e1f23') },
          uLift: { value: new THREE.Color('#25262b') },
          uO: { value: new THREE.Color(ORANGE).multiplyScalar(0.11) },
          uP: { value: new THREE.Color(PINK).multiplyScalar(0.09) },
          uDO: { value: new THREE.Vector3(-0.55, 0.42, -1).normalize() },
          uDP: { value: new THREE.Vector3(0.62, 0.12, -1).normalize() },
          uDW: { value: new THREE.Vector3(0, 1, -0.4).normalize() },
        },
      }),
    [],
  );
  mat.uniforms.uOn.value = on;
  return (
    <mesh position={camera.position.clone()} material={mat} renderOrder={-10}>
      <sphereGeometry args={[150, 48, 32]} />
    </mesh>
  );
};

const GLOW_FRAG = /* glsl */ `
uniform vec3 uColor; uniform float uI; varying vec2 vUv;
void main(){ float r = length(vUv - 0.5) * 2.0; float a = pow(max(1.0 - r, 0.0), 2.2); gl_FragColor = vec4(uColor * a * uI, 1.0); }`;
const UV_VERT = /* glsl */ `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`;

/** Soft blurred spotlight card: additive radial glow that sits in depth for parallax. */
const LightCard: React.FC<{ color: string; i: number; pos: [number, number, number]; size: number }> = ({ color, i, pos, size }) => {
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
        vertexShader: UV_VERT,
        fragmentShader: GLOW_FRAG,
        uniforms: { uColor: { value: new THREE.Color(color) }, uI: { value: 0 } },
      }),
    [color],
  );
  mat.uniforms.uI.value = i;
  return (
    <mesh position={pos} material={mat}>
      <planeGeometry args={[size, size]} />
    </mesh>
  );
};

const SpotL: React.FC<{ position: [number, number, number]; target: [number, number, number]; color: string; intensity: number }> = ({ position, target, color, intensity }) => {
  const t = useMemo(() => new THREE.Object3D(), []);
  t.position.set(...target);
  return (
    <>
      <primitive object={t} />
      <spotLight position={position} target={t} angle={0.42} penumbra={1} intensity={intensity} decay={1.6} distance={30} color={color} />
    </>
  );
};

const Studio: React.FC<{ on: number; f: number; floorY?: number }> = ({ on, f, floorY = -2.5 }) => {
  const drift = Math.sin(f * 0.02) * 0.4;
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, floorY, -10]}>
        <planeGeometry args={[80, 60]} />
        <meshStandardMaterial color="#3a3b41" roughness={0.32} metalness={0.1} envMapIntensity={0.35} />
      </mesh>
      <SpotL position={[-3.5, 6, 3]} target={[-1.2, floorY, -1.5]} intensity={34 * on} color={ORANGE} />
      <SpotL position={[3.5, 6, 2]} target={[1.4, floorY, -2.5]} intensity={30 * on} color={PINK} />
      <SpotL position={[0, 8, 5]} target={[0, floorY, 0]} intensity={14 * on} color="#fff4ea" />
      <LightCard color={ORANGE} i={0.12 * on} pos={[-2.4 + drift, 2.4, -9]} size={5.5} />
      <LightCard color={PINK} i={0.11 * on} pos={[2.6 - drift, 0.6, -11]} size={6} />
      <LightCard color="#ffe9d6" i={0.04 * on} pos={[0.2, 4.5, -14]} size={12} />
    </group>
  );
};

// --------------------------------------------------------------------------- beat 1-2: panel + orb
const OrbPanel: React.FC<{ f: number }> = ({ f }) => {
  const rings = useTexture(staticFile('logo_rings.png'));
  rings.colorSpace = THREE.SRGBColorSpace;
  const tIn = easeOut(prog(f, TL.b2 - 4, TL.b2 + 38));
  const bob = Math.sin(f * 0.05) * 0.05;
  const y = lerp(-5.2, 0.15, tIn) + bob;
  const z = lerp(-3.5, 0, tIn);
  const spin = f * 0.018;
  const glow = 0.5 + 0.5 * smooth(prog(f, TL.b2 + 10, TL.b2 + 45));
  return (
    <group position={[0, y, z]} rotation={[-0.16 + 0.12 * (1 - tIn), 0.32 - 0.25 * (1 - tIn) + 0.04 * Math.sin(f * 0.02), 0.04]}>
      <RoundedBox args={[2.5, 3.6, 0.12]} radius={0.12} smoothness={6}>
        <Glass roughness={0.34} thickness={0.6} tint="#f3ecff" />
      </RoundedBox>
      <group position={[0, 0, 0.62]}>
        {/* real Athlo rings, glowing inside a clear glass orb */}
        <mesh scale={1.02}>
          <planeGeometry args={[1, 1]} />
          <meshBasicMaterial map={rings} alphaTest={0.4} toneMapped={false} color={new THREE.Color(1, 1, 1).multiplyScalar(0.9 + 0.7 * glow)} />
        </mesh>
        <LightCard color={ORANGE} i={0.16 * glow} pos={[-0.15, 0, -0.08]} size={2.4} />
        <LightCard color={PINK} i={0.14 * glow} pos={[0.2, 0, -0.1]} size={2.4} />
        <mesh>
          <sphereGeometry args={[0.66, 64, 48]} />
          <Glass roughness={0.02} thickness={0.35} ior={1.25} tint="#fff6ee" />
        </mesh>
        {SPORTS.map((s, i) => {
          const a = spin + (i / SPORTS.length) * Math.PI * 2;
          const R = 1.62;
          return (
            <group key={s} position={[R * Math.cos(a), 0.38 * R * Math.sin(a), 0.75 * R * Math.sin(a)]} rotation={[0.2 * Math.sin(a), -a * 0.4, 0.15 * Math.cos(a)]} scale={0.42}>
              <SportIcon sport={s} tint={i % 2 ? PINK : ORANGE} glow={0.22} />
            </group>
          );
        })}
      </group>
    </group>
  );
};

// --------------------------------------------------------------------------- beat 3: tunnel of real screens
const useRoundedAlpha = () =>
  useMemo(() => {
    const c = document.createElement('canvas');
    c.width = 256;
    c.height = 420;
    const g = c.getContext('2d')!;
    g.fillStyle = '#000';
    g.fillRect(0, 0, 256, 420);
    g.fillStyle = '#fff';
    g.beginPath();
    g.roundRect(4, 4, 248, 412, 26);
    g.fill();
    const t = new THREE.CanvasTexture(c);
    return t;
  }, []);

const Tunnel: React.FC = () => {
  const tex = useTexture(SCREENS);
  tex.forEach((t) => {
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 8;
  });
  const alpha = useRoundedAlpha();
  const items = useMemo(() => {
    const out: { pos: [number, number, number]; rot: [number, number, number]; k: number }[] = [];
    let k = 0;
    const W = 1.8;
    const H = 2.5;
    for (let i = 0; i < 34; i++) {
      const z = 4 - i * 1.55;
      for (const yy of [-1.2, 1.2]) {
        out.push({ pos: [-W, yy, z + (yy > 0 ? 0.5 : 0)], rot: [0, Math.PI / 2, 0], k: k++ });
        out.push({ pos: [W, yy, z + (yy > 0 ? 0 : 0.5)], rot: [0, -Math.PI / 2, 0], k: k++ });
      }
    }
    for (let i = 0; i < 24; i++) {
      const z = 4 - i * 2.35;
      for (const xx of [-0.74, 0.74]) {
        out.push({ pos: [xx, -H, z + (xx > 0 ? 1.1 : 0)], rot: [-Math.PI / 2, 0, 0], k: k++ });
        out.push({ pos: [xx, H, z + (xx > 0 ? 0 : 1.1)], rot: [Math.PI / 2, 0, Math.PI], k: k++ });
      }
    }
    return out;
  }, []);
  return (
    <group>
      {items.map((it) => (
        <mesh key={it.k} position={it.pos} rotation={it.rot}>
          <planeGeometry args={[1.38, 2.26]} />
          <meshBasicMaterial map={tex[(it.k * 5 + Math.floor(it.k / 7)) % tex.length]} alphaMap={alpha} transparent color={new THREE.Color(0.6, 0.6, 0.62)} />
        </mesh>
      ))}
      {/* brand light rails along the tunnel edges */}
      {[
        [-1.78, -2.48, ORANGE],
        [1.78, -2.48, PINK],
        [-1.78, 2.48, PINK],
        [1.78, 2.48, ORANGE],
      ].map(([x, y, c], i) => (
        <mesh key={i} position={[x as number, y as number, -30]}>
          <boxGeometry args={[0.02, 0.02, 70]} />
          <meshBasicMaterial color={new THREE.Color(c as string).multiplyScalar(2.2)} toneMapped={false} />
        </mesh>
      ))}
      <LightCard color={ORANGE} i={0.5} pos={[-0.4, 0.4, -58]} size={6} />
      <LightCard color={PINK} i={0.45} pos={[0.5, -0.3, -59]} size={6} />
    </group>
  );
};

// --------------------------------------------------------------------------- beat 4: drifting glass tiles
const TILE_POS: [number, number, number][] = [
  [-1.2, 1.75, -0.6],
  [1.25, 1.55, -2.6],
  [1.15, -1.75, 0.4],
  [-1.3, -1.6, -2.2],
  [0.15, 3.3, -6.0],
  [-0.4, -3.5, -5.5],
  [2.2, 0.1, -7.5],
  [-2.3, 0.2, -6.8],
];
const Tiles: React.FC<{ f: number }> = ({ f }) => {
  const t = f - TL.b4;
  return (
    <group>
      {TILE_POS.map((p, i) => {
        const s = SPORTS[i % SPORTS.length];
        const dz = t * (0.012 + 0.01 * rand(i));
        return (
          <group key={i} position={[p[0] + Math.sin(t * 0.03 + i) * 0.08, p[1] + t * 0.004 * (i % 2 ? 1 : -1), p[2] + dz]}
            rotation={[0.25 * Math.sin(i * 2.1) + t * 0.002, -0.45 * Math.sign(p[0]) + t * 0.006 * (i % 2 ? 1 : -1), 0.08 * Math.sin(i)]}>
            <RoundedBox args={[1.05, 1.05, 0.2]} radius={0.17} smoothness={5}>
              <Glass roughness={0.32} thickness={0.45} tint="#f4f2f7" />
            </RoundedBox>
            <group position={[0, 0, 0.24]} scale={0.56}>
              <SportIcon sport={s} tint={i % 2 ? PINK : ORANGE} glow={0.14} />
            </group>
          </group>
        );
      })}
    </group>
  );
};

// --------------------------------------------------------------------------- beats 5-6: pill counter + light streaks
const STREAK_FRAG = /* glsl */ `
uniform vec3 uColor; uniform float uHead; uniform float uLen; uniform float uI; varying vec2 vUv;
void main(){
  float d = uHead - vUv.x;
  float a = smoothstep(uLen, 0.0, d) * smoothstep(-0.015, 0.0, d);
  a = a * a;
  float core = 1.0 - abs(vUv.y - 0.5) * 2.0;
  gl_FragColor = vec4(uColor * a * uI * (0.6 + 0.4 * core), 1.0);
}`;

const Streak: React.FC<{ pts: [number, number, number][]; color: string; head: number; i: number; r: number }> = ({ pts, color, head, i, r }) => {
  const geo = useMemo(() => new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p))), 160, r, 10, false), [pts, r]);
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
        vertexShader: UV_VERT,
        fragmentShader: STREAK_FRAG,
        uniforms: { uColor: { value: new THREE.Color(color) }, uHead: { value: 0 }, uLen: { value: 0.45 }, uI: { value: 0 } },
      }),
    [color],
  );
  mat.uniforms.uHead.value = head;
  mat.uniforms.uI.value = i;
  return <mesh geometry={geo} material={mat} />;
};

const STREAKS = Array.from({ length: 7 }, (_, k) => {
  const y = -0.6 - k * 0.15;
  const z = 0.6 - k * 0.55;
  const bend = 0.45 + 0.08 * k;
  const pts: [number, number, number][] = [
    [-5.5, y + bend * 0.9, z - 1.5],
    [-2.5, y - bend * 0.15, z],
    [0, y - bend * 0.5, z + 0.5],
    [2.5, y - bend * 0.1, z],
    [5.5, y + bend * 1.0, z - 1.8],
  ];
  return { pts, color: k % 3 === 1 ? '#fff1e4' : k % 2 ? PINK : ORANGE, r: k % 3 === 1 ? 0.008 : 0.014, delay: k * 4.5 };
});

const PillCounter: React.FC<{ f: number }> = ({ f }) => {
  const fill = easeInOut(prog(f, TL.b5 + 12, TL.b6 - 6));
  const day = Math.max(1, Math.min(30, 1 + Math.floor(fill * 29.999)));
  const L = 2.3;
  const w = Math.max(0.0001, fill * L);
  const lift = smooth(prog(f, TL.b6 - 6, TL.b7)) * 0.55;
  const intro = easeOut(prog(f, TL.b5 - 2, TL.b5 + 22));
  const surge = smooth(prog(f, TL.b6 - 4, TL.b6 + 12));
  return (
    <group>
      <group scale={0.8} position={[0, 0.25 + lift + (1 - intro) * -0.6, (1 - intro) * -1.2]} rotation={[0.1 - 0.06 * fill, -0.18 + 0.2 * fill, 0]}>
        <mesh rotation={[0, 0, Math.PI / 2]} scale={[1, 1, 0.42]}>
          <capsuleGeometry args={[0.46, 2.15, 24, 64]} />
          <Glass roughness={0.26} thickness={0.7} tint="#fff3ea" />
        </mesh>
        {/* track + glowing progress line inside the glass */}
        <mesh position={[0, -0.24, 0]} rotation={[0, 0, Math.PI / 2]}>
          <capsuleGeometry args={[0.035, L, 8, 24]} />
          <meshBasicMaterial color="#5b5c63" transparent opacity={0.55} />
        </mesh>
        <mesh position={[-L / 2 + w / 2, -0.24, 0.005]} rotation={[0, 0, Math.PI / 2]}>
          <capsuleGeometry args={[0.042, w, 8, 24]} />
          <meshBasicMaterial color={new THREE.Color(ORANGE).lerp(new THREE.Color(PINK), fill).multiplyScalar(2.4)} toneMapped={false} />
        </mesh>
        <Text font={FONT} fontSize={0.32} position={[0, 0.06, 0.22]} anchorX="center" anchorY="middle" color="#ffffff" fillOpacity={0.88} letterSpacing={-0.01}>
          {`Day ${day}`}
        </Text>
      </group>
      {STREAKS.map((s, k) => {
        const cyc = 30 - 8 * surge;
        const local = f - TL.b5 - 6 - s.delay;
        const head = local < 0 ? -1 : ((local % cyc) / cyc) * 1.6 - 0.2;
        const i = (1.8 + 1.6 * surge) * env(f, TL.b5 + 4, TL.b7 + 2, 10, 6);
        return <Streak key={k} pts={s.pts} color={s.color} head={head} i={i} r={s.r * (1 + 0.6 * surge)} />;
      })}
    </group>
  );
};

// --------------------------------------------------------------------------- beat 7-8: logo
const FLARE_FRAG = /* glsl */ `
uniform float uI; varying vec2 vUv;
void main(){
  vec2 p = (vUv - 0.5) * 8.0; // world units across the 8x8 plane
  float core = exp(-dot(p, p) * 9.0);
  float halo = exp(-length(p) * 2.6) * 0.35;
  float streak = exp(-abs(p.y) * 45.0) * exp(-abs(p.x) * 0.9);
  vec3 c = vec3(1.0, 0.96, 0.92) * core * 2.2 + vec3(1.0, 0.68, 0.2) * halo + vec3(1.0, 0.55, 0.5) * streak * 1.6;
  gl_FragColor = vec4(c * uI, 1.0);
}`;

const Flare: React.FC<{ i: number }> = ({ i }) => {
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, toneMapped: false,
        vertexShader: UV_VERT, fragmentShader: FLARE_FRAG, uniforms: { uI: { value: 0 } },
      }),
    [],
  );
  mat.uniforms.uI.value = i;
  return (
    <mesh material={mat} position={[0, 0, 0.3]} renderOrder={5}>
      <planeGeometry args={[8, 8]} />
    </mesh>
  );
};

const LogoReveal: React.FC<{ f: number }> = ({ f }) => {
  const logo = useTexture(staticFile('logo_full.png'));
  logo.colorSpace = THREE.SRGBColorSpace;
  const t = f - TL.b7;
  const flare = 2.0 * Math.exp(-Math.pow((t - 3) / 3.2, 2)) + 0.12 * smooth(prog(t, 4, 12)) + 3 * easeIn(prog(f, TL.flashPeak - 6, TL.flashPeak));
  const show = easeOut(prog(t, 3, 15));
  const sc = lerp(0.86, 1, easeOut(prog(t, 2, 22)));
  return (
    <group>
      <mesh scale={[1.85 * sc, (1.85 * sc * 395) / 1441, 1]}>
        <planeGeometry args={[1, 1]} />
        <meshBasicMaterial map={logo} transparent opacity={show} toneMapped={false} color={new THREE.Color(1, 1, 1).multiplyScalar(0.95)} depthWrite={false} />
      </mesh>
      <Flare i={flare} />
      <LightCard color={ORANGE} i={0.14 * show} pos={[-1.6, 0.2, -3]} size={7} />
      <LightCard color={PINK} i={0.12 * show} pos={[1.6, -0.2, -3.5]} size={7} />
    </group>
  );
};

const EndLogo: React.FC<{ f: number }> = ({ f }) => {
  const logo = useTexture(staticFile('logo_full.png'));
  logo.colorSpace = THREE.SRGBColorSpace;
  const w = 1.55;
  return (
    <group position={[0, 1.42 + Math.sin(f * 0.04) * 0.02, 0]}>
      <mesh scale={[w, (w * 395) / 1441, 1]}>
        <planeGeometry args={[1, 1]} />
        <meshBasicMaterial map={logo} transparent toneMapped={false} depthWrite={false} color={new THREE.Color(0.8, 0.8, 0.8)} />
      </mesh>
    </group>
  );
};

// --------------------------------------------------------------------------- composition of sets
export const Scene: React.FC = () => {
  const f = useCurrentFrame();
  const s = shotAt(f);
  const inA = f < TL.b3;
  const inTunnel = f >= TL.b3 && f < TL.b4;
  const inTiles = f >= TL.b4 && f < TL.b5;
  const inPill = f >= TL.b5 && f < TL.b7;
  const inLogo = f >= TL.b7 && f < TL.b8;
  const inEnd = f >= TL.b8;
  // studio lights bloom on over the first second, stay on after
  const on = inA ? 0.18 + 0.82 * smooth(prog(f, 2, 34)) : inLogo ? 0.55 : 1;
  return (
    <>
      <CameraRig />
      <Settle passes={3} />
      <Environment resolution={256} frames={1} background={false}>
        <Lightformer form="rect" intensity={2.2} color="#ffffff" scale={[10, 2.5, 1]} position={[0, 5, 1]} rotation={[Math.PI / 2, 0, 0]} />
        <Lightformer form="rect" intensity={3} color={ORANGE} scale={[3, 8, 1]} position={[-6, 1, 1]} rotation={[0, Math.PI / 2, 0]} />
        <Lightformer form="rect" intensity={2.6} color={PINK} scale={[3, 8, 1]} position={[6, 0, 0]} rotation={[0, -Math.PI / 2, 0]} />
        <Lightformer form="ring" intensity={1.4} color="#ffffff" scale={3} position={[0, 0, 8]} />
        <Lightformer form="rect" intensity={0.6} color="#9aa0ad" scale={[20, 6, 1]} position={[0, -3, -8]} />
      </Environment>
      <ambientLight intensity={0.15} />
      <fog attach="fog" args={['#25262b', 7, inTunnel ? 70 : 26]} />
      <hemisphereLight args={['#4a4b52', '#2a2b30', 0.6]} />
      <Backdrop on={inTunnel ? 0.7 : on} />
      {!inTunnel && <Studio on={on} f={f} />}
      <group visible={inA}>
        <OrbPanel f={f} />
      </group>
      {inTunnel && <Tunnel />}
      <group visible={inTiles}>{inTiles && <Tiles f={f} />}</group>
      <group visible={inPill}>{inPill && <PillCounter f={f} />}</group>
      <group visible={inLogo}>{inLogo && <LogoReveal f={f} />}</group>
      <group visible={inEnd}>{inEnd && <EndLogo f={f} />}</group>
      <EffectComposer multisampling={4}>
        <DepthOfField worldFocusDistance={s.focus} worldFocusRange={s.range} bokehScale={s.bokeh} />
        <Bloom mipmapBlur luminanceThreshold={0.82} luminanceSmoothing={0.2} intensity={0.85} radius={0.72} />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
        <Vignette offset={0.35} darkness={0.32} />
        <Noise premultiply={false} blendFunction={BlendFunction.SOFT_LIGHT} opacity={0.38} />
      </EffectComposer>
    </>
  );
};
