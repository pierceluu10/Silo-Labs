"use client";

import clsx from "clsx";
import { ArrowsOutSimple, Check, DotsSixVertical } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "framer-motion";
import type { AgentName } from "@/types/sse";
import { useSiloStore } from "@/lib/store";
import { AgentActivityList } from "./AgentActivityList";

const AGENT_LABELS: Record<AgentName, string> = {
  supervisor: "Supervisor",
  requirements_parser: "Requirements",
  pinout_resolver: "Pinout",
  clock_configurator: "Clocks",
  peripheral_configurator: "Peripheral",
  errata_checker: "Errata",
  wokwi_diagram_generator: "Wiring",
  code_composer: "Code",
};

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
  const duration = useSiloStore((s) => s.agentDurations[agent]);
  const reduceMotion = useReducedMotion();
  const isActive = active === agent;
  const completed = duration !== undefined;

  const headerLabel = title ?? `Agent / ${AGENT_LABELS[agent]}`;

  return (
    <motion.section
      layout={!reduceMotion}
      className={clsx(
        "agent-window",
        fullscreen && "agent-window--fullscreen",
      )}
      data-state={isActive ? "active" : completed ? "complete" : "queued"}
      animate={reduceMotion ? undefined : { y: isActive ? -2 : 0 }}
      transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
    >
      <header className="agent-window__header">
        <div className="flex items-center gap-2 min-w-0">
          <DotsSixVertical className="agent-window__grip" size={14} weight="bold" />
          <span className="agent-window__title">
            {headerLabel}
          </span>
          {isActive && <span className="agent-window__live">Working</span>}
          {completed && !isActive && (
            <span className="agent-window__complete"><Check size={10} weight="bold" /> Done</span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setFullscreen(fullscreen ? null : agent)}
          aria-label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          className="icon-button"
        >
          <ArrowsOutSimple size={14} />
        </button>
      </header>
      <div
        className={clsx(
          "agent-window__body",
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
          <p className="activity-label">Activity log</p>
          <div className="flex-1 min-h-0">
            <AgentActivityList items={activities} />
          </div>
        </div>
      </div>
    </motion.section>
  );
}
