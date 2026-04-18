"use client";

import { useSiloStore } from "@/lib/store";
import { RegisterRow } from "./RegisterRow";

export function RegisterPanel() {
  const registers = useSiloStore((s) => s.registers);
  if (registers.length === 0) {
    return <span className="text-steel">Register writes will stream here…</span>;
  }
  return (
    <div className="flex flex-col w-full">
      {registers.map((r, i) => (
        <RegisterRow key={`${r.address}-${r.field_name}-${i}`} event={r} />
      ))}
    </div>
  );
}
