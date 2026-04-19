"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import type { AgentName } from "@/types/sse";
import { useSiloStore } from "@/lib/store";
import { AgentActivityList } from "./AgentActivityList";

const AGENT_LABELS: Record<AgentName, string> = {
  requirements_parser: "Requirements",
  pinout_resolver: "Pinout",
  clock_configurator: "Clocks",
  peripheral_configurator: "Peripheral",
  errata_checker: "Errata",
  wokwi_diagram_generator: "Wiring",
  code_composer: "Code",
};

function ExpandIcon({ size = 12 }: { size?: number }) {
  // Two opposing right-angle brackets (matches the "open in fullscreen"
  // glyph in the reference screenshot).
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" aria-hidden>
      <path d="M2 4.5V2h2.5" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" />
      <path d="M10 7.5V10H7.5" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" />
      <path d="M7.5 2H10v2.5" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" />
      <path d="M4.5 10H2V7.5" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" />
    </svg>
  );
}

interface Props {
  /** The single agent this card represents. */
  agent: AgentName;
  /** Optional override title (defaults to "Agent — {AGENT_LABELS[agent]}"). */
  title?: string;
  /** The visual area shown above the activity list (PinoutDiagram, ClockTree, ...). */
  children?: React.ReactNode;
  /** Bigger, fullscreen-mode rendering. */
  fullscreen?: boolean;
}

export function AgentPanel({ agent, title, children, fullscreen = false }: Props) {
  const active = useSiloStore((s) => s.activeAgent);
  const activities = useSiloStore((s) => s.activities[agent]);
  const setFullscreen = useSiloStore((s) => s.setFullscreen);
  const isActive = active === agent;
  const completed = activities.length > 0 && activities.every((a) => a.status === "done");

  const dotColor = isActive
    ? "var(--color-accent)"
    : completed
      ? "var(--color-accent-light)"
      : "var(--color-charcoal)";

  const headerLabel = title ?? `Agent — ${AGENT_LABELS[agent]}`;

  return (
    <motion.section
      layout
      className={clsx(
        "border flex flex-col min-h-0 overflow-hidden transition-colors h-full w-full",
        fullscreen ? "rounded-3xl" : "rounded-2xl",
      )}
      style={{
        borderColor: isActive ? "var(--color-accent)" : "var(--color-charcoal)",
        background: "color-mix(in oklab, var(--color-carbon) 80%, transparent)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        boxShadow: isActive
          ? "0 0 22px var(--color-accent-tint), inset 0 0 0 1px rgba(255,255,255,0.04)"
          : "inset 0 0 0 1px rgba(255,255,255,0.03)",
      }}
    >
      <header
        className="px-3 py-2 flex items-center justify-between border-b"
        style={{ borderColor: "var(--color-charcoal)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
            style={{
              background: dotColor,
              boxShadow: isActive ? "0 0 6px var(--color-accent-tint)" : "none",
              animation: isActive ? "siloPulse 1.1s ease-in-out infinite" : undefined,
            }}
          />
          <span
            className="text-[11px] uppercase tracking-[0.18em] truncate"
            style={{ color: isActive ? "var(--color-accent-light)" : "var(--color-snow)" }}
          >
            {headerLabel}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setFullscreen(fullscreen ? null : agent)}
          aria-label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          className="p-1 rounded hover:bg-[color:var(--color-charcoal)]/40 transition-colors"
          style={{ color: "var(--color-steel)" }}
        >
          <ExpandIcon />
        </button>
      </header>
      <div
        className={clsx(
          "flex-1 min-h-0 grid",
          fullscreen ? "grid-cols-[3fr_2fr] grid-rows-1" : "grid-rows-[minmax(0,1fr)_minmax(0,42%)]",
        )}
      >
        <div className="min-h-0 overflow-hidden p-3">{children}</div>
        <div
          className={clsx(
            "min-h-0 px-3 py-2 border-t flex flex-col",
            fullscreen ? "border-l border-t-0" : "",
          )}
          style={{ borderColor: "var(--color-charcoal)" }}
        >
          <p
            className="text-[9px] uppercase tracking-[0.2em] m-0 mb-1.5 shrink-0"
            style={{ color: "var(--color-steel)" }}
          >
            Agent activity
          </p>
          <div className="flex-1 min-h-0">
            <AgentActivityList items={activities} />
          </div>
        </div>
      </div>
    </motion.section>
  );
}