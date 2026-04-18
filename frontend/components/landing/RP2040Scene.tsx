"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import type { Group } from "three";

function Chip() {
  const ref = useRef<Group>(null);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.2;
  });
  return (
    <group ref={ref}>
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[3, 0.25, 3]} />
        <meshStandardMaterial color="#0a0a0a" metalness={0.8} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.2, 0]}>
        <boxGeometry args={[1.6, 0.15, 1.6]} />
        <meshStandardMaterial color="#1a1a1a" metalness={0.6} roughness={0.3} />
      </mesh>
      {[-1, 1].map((sx) =>
        [-1.2, -0.6, 0, 0.6, 1.2].map((z) => (
          <mesh key={`${sx}-${z}`} position={[sx * 1.6, 0.1, z]}>
            <boxGeometry args={[0.2, 0.05, 0.15]} />
            <meshStandardMaterial color="#c0c0c0" metalness={1} roughness={0.2} />
          </mesh>
        ))
      )}
    </group>
  );
}

export function RP2040Scene() {
  return (
    <Canvas camera={{ position: [4, 3, 5], fov: 40 }} style={{ background: "transparent" }}>
      <ambientLight intensity={0.4} />
      <pointLight position={[5, 5, 5]} intensity={2} color="#e63946" />
      <spotLight position={[-5, 4, 4]} intensity={1.2} angle={0.5} penumbra={0.5} color="#ff6b6b" />
      <Chip />
    </Canvas>
  );
}
