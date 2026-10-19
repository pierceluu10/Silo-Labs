"use client";

import { Check, CircleNotch } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "framer-motion";
import { useSiloStore } from "@/lib/store";
import type { AgentName } from "@/types/sse";

const AGENTS: Array<{ name: AgentName; label: string; detail: string }> = [
  { name: "supervisor", label: "Supervisor", detail: "Plans the run" },
  { name: "requirements_parser", label: "Requirements", detail: "Extracts the contract" },
  { name: "pinout_resolver", label: "Pinout", detail: "Assigns GPIO" },
  { name: "peripheral_configurator", label: "Peripheral", detail: "Configures DHT22" },
  { name: "wokwi_diagram_generator", label: "Wiring", detail: "Builds the circuit" },
  { name: "clock_configurator", label: "Clocks", detail: "Sets timing" },
  { name: "errata_checker", label: "Verification", detail: "Checks constraints" },
  { name: "code_composer", label: "Composer", detail: "Writes firmware" },
];

function formatDuration(duration: number): string {
  return duration < 1000 ? `${duration}ms` : `${(duration / 1000).toFixed(1)}s`;
}

export function AgentRunRail() {
  const activeAgent = useSiloStore((state) => state.activeAgent);
  const durations = useSiloStore((state) => state.agentDurations);
  const pipelineComplete = useSiloStore((state) => state.pipelineComplete);
  const reduceMotion = useReducedMotion();

  return (
    <aside className="agent-rail" aria-label="Agent execution sequence">
      <div className="agent-rail__header">
        <div>
          <p className="workspace-kicker">Agent sequence</p>
          <h2>One clear handoff at a time</h2>
        </div>
        <span className="agent-rail__count">
          {Object.keys(durations).length}/{AGENTS.length}
        </span>
      </div>

      <ol className="agent-rail__list">
        {AGENTS.map((agent, index) => {
          const duration = durations[agent.name];
          const isActive = activeAgent === agent.name;
          const isComplete = duration !== undefined;
          const status = isComplete ? "complete" : isActive ? "active" : "queued";

          return (
            <motion.li
              key={agent.name}
              layout={!reduceMotion}
              className="agent-run"
              data-status={status}
              animate={reduceMotion ? undefined : { opacity: status === "queued" ? 0.52 : 1 }}
              transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
            >
              <span className="agent-run__index" aria-hidden>
                {isComplete ? (
                  <Check size={13} weight="bold" />
                ) : isActive ? (
                  <CircleNotch size={14} weight="bold" className="agent-run__spinner" />
                ) : (
                  String(index + 1).padStart(2, "0")
                )}
              </span>
              <span className="agent-run__copy">
                <strong>{agent.label}</strong>
                <small>{isActive ? "Working now" : isComplete ? "Handoff complete" : agent.detail}</small>
              </span>
              <span className="agent-run__duration">
                {duration !== undefined ? formatDuration(duration) : isActive ? "live" : ""}
              </span>
            </motion.li>
          );
        })}
      </ol>

      <div className="agent-rail__footer">
        <span>{pipelineComplete ? "Run complete" : activeAgent ? "Serial execution" : "Connecting"}</span>
        <span className="agent-rail__footer-line" />
      </div>
    </aside>
  );
}

