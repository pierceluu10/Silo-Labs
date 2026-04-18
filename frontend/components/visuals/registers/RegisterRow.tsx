"use client";

import type { RegisterEvent } from "@/lib/store";
import { BitCell } from "./BitCell";

interface Props {
  event: RegisterEvent;
}

export function RegisterRow({ event }: Props) {
  const bits: (0 | 1)[] = Array.from({ length: 32 }, (_, i) => {
    const inField = i >= event.bit_offset && i < event.bit_offset + event.bit_width;
    if (!inField) return 0;
    const shift = i - event.bit_offset;
    return ((event.value >> shift) & 1) as 0 | 1;
  });

  return (
    <div className="space-y-1 py-2 border-b" style={{ borderColor: "var(--color-charcoal)" }}>
      <div className="flex items-baseline justify-between text-[11px] font-mono">
        <div style={{ color: "var(--color-snow)" }}>
          {event.peripheral}.{event.register}.{event.field_name}
        </div>
        <div style={{ color: "var(--color-steel)" }}>
          0x{event.address.toString(16).padStart(8, "0")}
        </div>
      </div>
      <div className="flex gap-[2px] justify-end">
        {bits
          .slice()
          .reverse()
          .map((v, i) => {
            const bit = 31 - i;
            const affected =
              bit >= event.bit_offset && bit < event.bit_offset + event.bit_width;
            return <BitCell key={bit} bit={bit} value={v} affected={affected} />;
          })}
      </div>
      {event.human_explanation && (
        <p className="text-[10px]" style={{ color: "var(--color-parchment)" }}>
          {event.human_explanation}
        </p>
      )}
    </div>
  );
}
