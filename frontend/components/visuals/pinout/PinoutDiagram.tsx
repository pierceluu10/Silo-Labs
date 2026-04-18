"use client";

import { useSiloStore } from "@/lib/store";
import { Pin } from "./Pin";
import { BOARD_HEIGHT, BOARD_WIDTH, PIN_LAYOUT } from "./pinout_data";

export function PinoutDiagram() {
  const pins = useSiloStore((s) => s.pins);
  const byGpio = new Map(pins.map((p) => [p.pin_number, p]));

  return (
    <div className="flex items-center justify-center h-full w-full">
      <svg
        viewBox={`0 0 ${BOARD_WIDTH} ${BOARD_HEIGHT}`}
        style={{ maxHeight: "100%", maxWidth: "100%" }}
      >
        <rect
          x={0}
          y={0}
          width={BOARD_WIDTH}
          height={BOARD_HEIGHT}
          rx={12}
          fill="var(--color-abyss)"
          stroke="var(--color-charcoal)"
        />
        <text
          x={BOARD_WIDTH / 2}
          y={18}
          textAnchor="middle"
          fontSize={10}
          fill="var(--color-steel)"
          fontFamily="var(--font-mono)"
        >
          Raspberry Pi Pico · RP2040
        </text>
        {PIN_LAYOUT.map((p) => (
          <Pin
            key={p.index}
            layout={p}
            assignment={p.gpio !== null ? byGpio.get(p.gpio) : undefined}
          />
        ))}
      </svg>
    </div>
  );
}
