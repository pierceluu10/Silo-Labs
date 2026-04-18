"use client";

import clsx from "clsx";
import type { AgentName } from "@/types/sse";
import { useSiloStore } from "@/lib/store";

const AGENT_LABELS: Record<AgentName, string> = {
  requirements_parser: "Requirements",
  pinout_resolver: "Pinout",
  clock_configurator: "Clocks",
  peripheral_configurator: "Peripheral",
  errata_checker: "Errata",
  wokwi_diagram_generator: "Wiring",
  code_composer: "Code",
};

interface Props {
  title: string;
  agents: AgentName[];
  children?: React.ReactNode;
}

export function AgentPanel({ title, agents, children }: Props) {
  const active = useSiloStore((s) => s.activeAgent);
  const reasoning = useSiloStore((s) => s.agentReasoning);
  const isActive = active !== null && agents.includes(active);

  return (
    <section
      className={clsx(
        "border rounded-sm flex flex-col min-h-0 overflow-hidden transition-colors",
      )}
      style={{
        borderColor: isActive ? "var(--color-accent)" : "var(--color-charcoal)",
        background: "var(--color-carbon)",
        boxShadow: isActive ? "0 0 18px var(--color-accent-tint)" : "none",
      }}
    >
      <header
        className="px-3 py-2 text-[11px] uppercase tracking-[0.18em] border-b flex items-center justify-between"
        style={{
          borderColor: "var(--color-charcoal)",
          color: isActive ? "var(--color-accent-light)" : "var(--color-steel)",
        }}
      >
        <span>{title}</span>
        {isActive && active && <span>{AGENT_LABELS[active]}</span>}
      </header>
      <div className="flex-1 min-h-0 overflow-auto p-3 text-xs text-parchment leading-relaxed font-mono whitespace-pre-wrap">
        {children ?? (
          (agents.map((a) => reasoning[a]).filter(Boolean).join("\n\n")) ||
            <span className="text-steel">idle…</span>
        )}
      </div>
    </section>
  );
}
