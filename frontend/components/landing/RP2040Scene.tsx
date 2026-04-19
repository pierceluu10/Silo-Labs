"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import { Suspense, useRef } from "react";
import type { Group } from "three";

const PCB_W = 3;
const PCB_H = 0.18;
const PCB_D = 3;
const DIE_W = 1.5;
const DIE_D = 1.5;
const DIE_H = 0.12;
const PINS_PER_SIDE = 14;
const PIN_LEN = 0.22;
const PIN_W = 0.08;
const PIN_H = 0.04;

function Pins({ side }: { side: "N" | "S" | "E" | "W" }) {
  const pitch = (PCB_W - 0.4) / (PINS_PER_SIDE - 1);
  const start = -(PCB_W - 0.4) / 2;
  return (
    <>
      {Array.from({ length: PINS_PER_SIDE }).map((_, i) => {
        const t = start + i * pitch;
        const edge = PCB_W / 2 + PIN_LEN / 2 - 0.02;
        const pos: [number, number, number] =
          side === "N" ? [t, 0, -edge]
          : side === "S" ? [t, 0, edge]
          : side === "E" ? [edge, 0, t]
          : [-edge, 0, t];
        const args: [number, number, number] =
          side === "N" || side === "S"
            ? [PIN_W, PIN_H, PIN_LEN]
            : [PIN_LEN, PIN_H, PIN_W];
        return (
          <mesh key={`${side}-${i}`} position={pos} castShadow>
            <boxGeometry args={args} />
            <meshStandardMaterial color="#d8dadc" metalness={1} roughness={0.25} />
          </mesh>
        );
      })}
    </>
  );
}

function Chip() {
  const ref = useRef<Group>(null);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.18;
  });
  return (
    <group ref={ref} position={[0, 0, 0]}>
      <RoundedBox args={[PCB_W, PCB_H, PCB_D]} radius={0.04} smoothness={4} castShadow receiveShadow>
        <meshPhysicalMaterial
          color="#1d1d20"
          metalness={0.35}
          roughness={0.5}
          clearcoat={0.7}
          clearcoatRoughness={0.2}
        />
      </RoundedBox>

      <RoundedBox
        args={[DIE_W, DIE_H, DIE_D]}
        radius={0.02}
        smoothness={4}
        position={[0, PCB_H / 2 + DIE_H / 2, 0]}
        castShadow
      >
        <meshPhysicalMaterial
          color="#2a2a2e"
          metalness={0.55}
          roughness={0.3}
          clearcoat={1}
          clearcoatRoughness={0.08}
        />
      </RoundedBox>

      <mesh position={[-DIE_W / 2 + 0.12, PCB_H / 2 + DIE_H + 0.002, -DIE_D / 2 + 0.12]}>
        <cylinderGeometry args={[0.025, 0.025, 0.005, 16]} />
        <meshStandardMaterial color="#c7a86b" metalness={0.9} roughness={0.3} />
      </mesh>
      <mesh position={[DIE_W / 2 - 0.12, PCB_H / 2 + DIE_H + 0.002, -DIE_D / 2 + 0.12]}>
        <cylinderGeometry args={[0.018, 0.018, 0.005, 16]} />
        <meshStandardMaterial color="#2a2a2c" metalness={0.6} roughness={0.5} />
      </mesh>

      <Pins side="N" />
      <Pins side="S" />
      <Pins side="E" />
      <Pins side="W" />
    </group>
  );
}

export function RP2040Scene() {
  return (
    <Canvas
      camera={{ position: [3.2, 2.6, 4.2], fov: 38 }}
      shadows
      dpr={[1, 2]}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 6, 4]} intensity={1.4} color="#ffffff" castShadow />
      <directionalLight position={[-3, 4, 5]} intensity={0.8} color="#ffd6d6" />
      <directionalLight position={[0, 2, -5]} intensity={0.5} color="#ffffff" />
      <pointLight position={[3.5, 2, 3]} intensity={18} color="#e63946" distance={10} decay={2} />
      <pointLight position={[-3, 1.5, -2]} intensity={10} color="#ff6b6b" distance={9} decay={2} />
      <pointLight position={[0, 3, -3]} intensity={5} color="#e63946" distance={8} decay={2} />
      <hemisphereLight args={["#5a2a2e", "#101012", 0.5]} />
      <Suspense fallback={null}>
        <Chip />
      </Suspense>
    </Canvas>
  );
}
