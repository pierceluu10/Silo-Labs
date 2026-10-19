"use client";

import { DEFAULT_BOARD_PART, useSiloStore } from "@/lib/store";
import { Pin } from "./Pin";
import { BOARD_HEIGHT, BOARD_WIDTH, PIN_LAYOUT } from "./pinout_data";

export function PinoutDiagram() {
  const pins = useSiloStore((s) => s.pins);
  const target = useSiloStore((s) => s.target);
  const byGpio = new Map(pins.map((p) => [p.pin_number, p]));

  // The drawn header layout is the Pico's; other boards get an assignment table.
  if (target && target.boardPart !== DEFAULT_BOARD_PART) {
    return (
      <div className="flex h-full w-full flex-col gap-2" style={{ fontFamily: "var(--font-mono)" }}>
        <span className="text-[10px] text-steel">
          {target.boardName} · {target.displayName}
        </span>
        {pins.length === 0 ? (
          <p className="m-0 text-[11px] text-steel">Pin assignments will stream here…</p>
        ) : (
          <table className="w-full border-collapse text-[11px]">
            <tbody>
              {pins.map((p) => (
                <tr key={`${p.pin_number}-${p.label}`} className="border-b border-charcoal">
                  <td className="py-1 pr-3" style={{ color: p.wire_color }}>
                    {p.pin_name}
                  </td>
                  <td className="py-1 pr-3 text-snow">{p.label}</td>
                  <td className="py-1 text-steel">
                    {p.peripheral_instance} · {p.function}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  }

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
