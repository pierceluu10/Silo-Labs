"use client";

import { useSiloStore } from "@/lib/store";

const FAMILY_COLOR: Record<string, string> = {
  I2C: "var(--color-accent)",
  SPI: "var(--color-warn)",
  UART: "var(--color-info)",
  PWM: "var(--color-purple)",
  ADC: "var(--color-accent-light)",
  GPIO: "var(--color-steel)",
};

export function PlanPanel() {
  const plan = useSiloStore((s) => s.runPlan);
  if (!plan || plan.features.length === 0) return null;

  return (
    <div
      className="rounded-2xl border px-3 py-2 backdrop-blur-md"
      style={{
        borderColor: "var(--color-charcoal)",
        background: "color-mix(in oklab, var(--color-carbon) 78%, transparent)",
        maxWidth: "min(60vw, 760px)",
      }}
    >
      <div className="flex items-baseline gap-3 flex-wrap">
        <span
          className="text-[9px] uppercase tracking-[0.22em] font-mono"
          style={{ color: "var(--color-steel)" }}
        >
          Run plan · {plan.features.length} feature{plan.features.length === 1 ? "" : "s"}
        </span>
        {plan.rationale && (
          <span
            className="text-[10.5px] font-mono"
            style={{ color: "var(--color-parchment)" }}
          >
            {plan.rationale}
          </span>
        )}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {plan.features.map((f) => {
          const color = FAMILY_COLOR[f.peripheral_family.toUpperCase()] ?? "var(--color-accent)";
          return (
            <div
              key={f.id}
              title={`${f.peripheral_family} · ${f.intent}${f.depends_on.length ? ` · depends on ${f.depends_on.join(", ")}` : ""}`}
              className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-mono"
              style={{
                background: "color-mix(in oklab, var(--color-charcoal) 35%, transparent)",
                color: "var(--color-snow)",
                border: `1px solid ${color}`,
              }}
            >
              <span
                className="inline-block w-1.5 h-1.5 rounded-full"
                style={{ background: color }}
              />
              <span style={{ color: "var(--color-parchment)" }}>{f.peripheral_family}</span>
              <span style={{ color: "var(--color-snow)" }}>· {f.device_name}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}