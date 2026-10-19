"use client";

import { useMemo } from "react";
import { useSiloStore } from "@/lib/store";
import type { AgentName } from "@/types/sse";

const AGENT_LABELS: Array<[AgentName, string]> = [
  ["supervisor", "Supervisor"],
  ["requirements_parser", "Requirements"],
  ["pinout_resolver", "Pinout"],
  ["peripheral_configurator", "Peripheral"],
  ["wokwi_diagram_generator", "Wiring"],
  ["clock_configurator", "Clocks"],
  ["errata_checker", "Verification"],
  ["code_composer", "Composer"],
];

function formatDuration(milliseconds: number): string {
  if (milliseconds < 1000) return `${milliseconds} ms`;
  return `${(milliseconds / 1000).toFixed(2)} s`;
}

function formatCost(usd: number): string {
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(3)}`;
}

export function MetricsView() {
  const nodes = useSiloStore((state) => state.nodeMetrics);
  const summary = useSiloStore((state) => state.runMetrics);
  const durations = useSiloStore((state) => state.agentDurations);
  const activeAgent = useSiloStore((state) => state.activeAgent);

  const totals = useMemo(() => {
    const elapsed = summary
      ? summary.ended_at_ms - summary.started_at_ms
      : nodes.length > 0
        ? Math.max(...nodes.map((node) => node.ended_at_ms)) - Math.min(...nodes.map((node) => node.started_at_ms))
        : 0;
    return {
      elapsed,
      inputTokens: summary?.total_input_tokens ?? nodes.reduce((sum, node) => sum + node.input_tokens, 0),
      outputTokens: summary?.total_output_tokens ?? nodes.reduce((sum, node) => sum + node.output_tokens, 0),
      cost: summary?.total_cost_usd ?? 0,
    };
  }, [nodes, summary]);

  const completedAgentCount = Object.keys(durations).length;
  const maxDuration = Math.max(1, ...Object.values(durations));

  return (
    <div className="metrics-view silo-scroll">
      <div className="metrics-summary">
        <Metric label="Elapsed" value={totals.elapsed ? formatDuration(totals.elapsed) : "Live"} />
        <Metric label="Agents" value={`${completedAgentCount} / ${AGENT_LABELS.length}`} />
        <Metric label="Tokens" value={(totals.inputTokens + totals.outputTokens).toLocaleString()} />
        <Metric label="Est. cost" value={formatCost(totals.cost)} />
      </div>

      <section className="metrics-section">
        <div className="metrics-section__heading">
          <h3>Agent execution</h3>
          <span>Strictly sequential</span>
        </div>
        <div className="agent-metrics">
          {AGENT_LABELS.map(([name, label], index) => {
            const duration = durations[name];
            const isActive = activeAgent === name;
            return (
              <div className="agent-metric" key={name} data-state={duration !== undefined ? "done" : isActive ? "active" : "queued"}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{label}</strong>
                <div className="agent-metric__bar">
                  {duration !== undefined && <i style={{ transform: `scaleX(${duration / maxDuration})` }} />}
                  {isActive && <i className="agent-metric__bar--live" />}
                </div>
                <code>{duration !== undefined ? formatDuration(duration) : isActive ? "running" : "queued"}</code>
              </div>
            );
          })}
        </div>
      </section>

      <section className="metrics-section">
        <div className="metrics-section__heading">
          <h3>Pipeline nodes</h3>
          <span>{nodes.length} recorded</span>
        </div>
        <div className="node-metrics">
          {nodes.map((node, index) => (
            <div className="node-metric" key={`${node.node}-${node.feature_id ?? "global"}-${index}`}>
              <span>{node.node.replaceAll("_", " ")}</span>
              <code>{(node.input_tokens + node.output_tokens).toLocaleString()} tok</code>
              <code>{formatDuration(node.duration_ms)}</code>
              <strong data-status={node.status}>{node.status}</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-value">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
