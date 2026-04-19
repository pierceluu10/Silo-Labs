"use client";

import { useSiloStore } from "@/lib/store";
import { RegisterRow } from "./RegisterRow";

export function RegisterPanel() {
  const registers = useSiloStore((s) => s.registers);
  const reasoning = useSiloStore((s) => s.agentReasoning);
  const active = useSiloStore((s) => s.activeAgent);

  if (registers.length === 0) {
    // peripheral_configurator either still running, or finished and decided
    // no direct register writes were needed (e.g. when the firmware uses
    // pico-sdk high-level APIs like i2c_init that handle the registers
    // internally). Distinguish so the panel doesn't look broken.
    const periphReasoning = reasoning.peripheral_configurator?.trim() ?? "";
    const finishedEmpty = periphReasoning.length > 0 && active !== "peripheral_configurator";
    return (
      <p
        className="m-0 text-[11px] font-mono leading-relaxed text-steel"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        {finishedEmpty
          ? "No direct register writes — pico-sdk high-level APIs (i2c_init, gpio_set_function, etc.) configure this peripheral."
          : "Register writes will stream here…"}
      </p>
    );
  }
  return (
    <div className="flex flex-col w-full">
      {registers.map((r, i) => (
        <RegisterRow key={`${r.address}-${r.field_name}-${i}`} event={r} />
      ))}
    </div>
  );
}
