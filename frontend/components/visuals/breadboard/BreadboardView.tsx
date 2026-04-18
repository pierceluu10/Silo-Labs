"use client";

import { motion } from "framer-motion";
import { useSiloStore } from "@/lib/store";

const PICO_CENTER = { x: 100, y: 160 };
const DEVICE_CENTER = { x: 260, y: 160 };

function gpPosition(pin: string): { x: number; y: number } | null {
  if (!pin.startsWith("GP")) {
    const map: Record<string, { x: number; y: number }> = {
      "3V3": { x: PICO_CENTER.x + 40, y: PICO_CENTER.y - 60 },
      GND: { x: PICO_CENTER.x + 40, y: PICO_CENTER.y + 60 },
      VBUS: { x: PICO_CENTER.x + 40, y: PICO_CENTER.y - 80 },
    };
    return map[pin] ?? null;
  }
  const n = Number(pin.slice(2));
  const side = n < 15 ? -1 : 1;
  const row = n < 15 ? n : n - 15;
  return { x: PICO_CENTER.x + side * 40, y: PICO_CENTER.y - 80 + row * 14 };
}

function devicePosition(pin: string): { x: number; y: number } {
  const offsets: Record<string, number> = { VCC: -30, GND: -10, SCL: 10, SDA: 30, DQ: 0, INT: 20 };
  return { x: DEVICE_CENTER.x - 30, y: DEVICE_CENTER.y + (offsets[pin] ?? 0) };
}

export function BreadboardView() {
  const wires = useSiloStore((s) => s.wires);

  return (
    <svg viewBox="0 0 360 320" className="w-full h-full">
      <rect x={40} y={60} width={120} height={220} rx={6} fill="var(--color-carbon)" stroke="var(--color-charcoal)" />
      <text x={100} y={80} textAnchor="middle" fontSize={10} fill="var(--color-steel)" fontFamily="var(--font-mono)">
        Pi Pico
      </text>
      <rect x={220} y={120} width={100} height={80} rx={4} fill="var(--color-carbon)" stroke="var(--color-charcoal)" />
      <text x={270} y={140} textAnchor="middle" fontSize={10} fill="var(--color-steel)" fontFamily="var(--font-mono)">
        device
      </text>

      {wires.map((w, i) => {
        const from = w.from_component === "pico" ? gpPosition(w.from_pin) : devicePosition(w.from_pin);
        const to = w.to_component === "pico" ? gpPosition(w.to_pin) : devicePosition(w.to_pin);
        if (!from || !to) return null;
        const mid = { x: (from.x + to.x) / 2, y: from.y };
        const d = `M ${from.x} ${from.y} L ${mid.x} ${mid.y} L ${mid.x} ${to.y} L ${to.x} ${to.y}`;
        return (
          <motion.path
            key={`${w.from_pin}-${w.to_pin}-${i}`}
            d={d}
            fill="none"
            stroke={w.color}
            strokeWidth={1.8}
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        );
      })}
    </svg>
  );
}
