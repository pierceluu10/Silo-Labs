"use client";

import { useMemo } from "react";
import { useSiloStore } from "@/lib/store";
import type { NodeMetric } from "@/types/sse";

const NODE_COLOR: Record<string, string> = {
  supervisor: "var(--color-purple)",
  requirements: "var(--color-info)",
  feature_pipeline: "var(--color-accent)",
  join_features: "var(--color-steel)",
  clocks: "var(--color-warn)",
  errata: "var(--color-danger)",
  render_diagram: "var(--color-mist)",
  code: "var(--color-accent-light)",
  build: "var(--color-fog)",
  simulate: "var(--color-info)",
};

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function fmtCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

interface GanttRow {
  metric: NodeMetric;
  startPct: number;
  widthPct: number;
}

export function MetricsView() {
  const nodes = useSiloStore((s) => s.nodeMetrics);
  const summary = useSiloStore((s) => s.runMetrics);

  const { rows, t0, t1, totalDuration } = useMemo(() => {
    if (nodes.length === 0) {
      return { rows: [] as GanttRow[], t0: 0, t1: 0, totalDuration: 0 };
    }
    const t0 = Math.min(...nodes.map((n) => n.started_at_ms));
    const t1 = Math.max(...nodes.map((n) => n.ended_at_ms));
    const span = Math.max(1, t1 - t0);
    return {
      rows: nodes.map<GanttRow>((m) => ({
        metric: m,
        startPct: ((m.started_at_ms - t0) / span) * 100,
        widthPct: Math.max(0.4, ((m.ended_at_ms - m.started_at_ms) / span) * 100),
      })),
      t0,
      t1,
      totalDuration: t1 - t0,
    };
  }, [nodes]);

  if (nodes.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <p className="text-[11px] font-mono text-steel">
          Metrics will populate as the pipeline runs…
        </p>
      </div>
    );
  }

  const inputTokens = summary?.total_input_tokens ?? nodes.reduce((s, n) => s + n.input_tokens, 0);
  const outputTokens = summary?.total_output_tokens ?? nodes.reduce((s, n) => s + n.output_tokens, 0);
  const cost = summary?.total_cost_usd ?? 0;
  const speedup = summary?.parallel_speedup ?? 1;

  return (
    <div className="h-full w-full overflow-auto p-4 silo-scroll">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Wall-clock" value={fmtMs(totalDuration)} />
        <Stat label="Input tokens" value={inputTokens.toLocaleString()} />
        <Stat label="Output tokens" value={outputTokens.toLocaleString()} />
        <Stat
          label="Cost (est.)"
          value={fmtCost(cost)}
          hint={summary ? "Anthropic published rates" : "live, not yet finalized"}
        />
        <Stat
          label="Parallel speedup"
          value={`${speedup.toFixed(2)}×`}
          hint="sum(feature wall-clocks) / max(feature wall-clock)"
        />
        <Stat label="Nodes recorded" value={String(nodes.length)} />
      </div>

      <div className="mt-5">
        <p
          className="text-[9px] uppercase tracking-[0.22em] m-0 mb-2"
          style={{ color: "var(--color-steel)" }}
        >
          Gantt
        </p>
        <div
          className="relative rounded-md border p-3"
          style={{ borderColor: "var(--color-charcoal)" }}
        >
          {rows.map((row, i) => {
            const color = NODE_COLOR[row.metric.node] ?? "var(--color-accent)";
            return (
              <div key={i} className="flex items-center gap-2 py-1 text-[10px] font-mono">
                <span
                  className="shrink-0 w-32 truncate"
                  style={{ color: "var(--color-parchment)" }}
                  title={row.metric.feature_id ? `${row.metric.node} (${row.metric.feature_id})` : row.metric.node}
                >
                  {row.metric.node}
                  {row.metric.feature_id ? ` · ${row.metric.feature_id}` : ""}
                </span>
                <div className="relative flex-1 h-3 rounded" style={{ background: "color-mix(in oklab, var(--color-charcoal) 50%, transparent)" }}>
                  <div
                    className="absolute top-0 h-3 rounded"
                    style={{
                      left: `${row.startPct}%`,
                      width: `${row.widthPct}%`,
                      background: color,
                      opacity: row.metric.status === "error" ? 0.6 : 0.9,
                      boxShadow: row.metric.status === "error" ? "0 0 6px var(--color-danger)" : undefined,
                    }}
                  />
                </div>
                <span className="shrink-0 w-16 text-right" style={{ color: "var(--color-steel)" }}>
                  {fmtMs(row.metric.duration_ms)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-5">
        <p
          className="text-[9px] uppercase tracking-[0.22em] m-0 mb-2"
          style={{ color: "var(--color-steel)" }}
        >
          Per-node tokens
        </p>
        <table className="w-full text-[10px] font-mono">
          <thead>
            <tr style={{ color: "var(--color-steel)" }}>
              <th className="text-left py-1 px-2">Node</th>
              <th className="text-right py-1 px-2">Input</th>
              <th className="text-right py-1 px-2">Output</th>
              <th className="text-right py-1 px-2">Duration</th>
              <th className="text-right py-1 px-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((n, i) => (
              <tr key={i} style={{ borderTop: "1px solid var(--color-charcoal)" }}>
                <td className="py-1 px-2 truncate" style={{ color: "var(--color-snow)" }}>
                  {n.node}
                  {n.feature_id ? ` · ${n.feature_id}` : ""}
                </td>
                <td className="py-1 px-2 text-right" style={{ color: "var(--color-parchment)" }}>{n.input_tokens.toLocaleString()}</td>
                <td className="py-1 px-2 text-right" style={{ color: "var(--color-parchment)" }}>{n.output_tokens.toLocaleString()}</td>
                <td className="py-1 px-2 text-right" style={{ color: "var(--color-parchment)" }}>{fmtMs(n.duration_ms)}</td>
                <td
                  className="py-1 px-2 text-right uppercase tracking-[0.18em]"
                  style={{ color: n.status === "ok" ? "var(--color-accent-light)" : "var(--color-danger)" }}
                >
                  {n.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div
      className="rounded-lg border px-3 py-2"
      style={{
        borderColor: "var(--color-charcoal)",
        background: "color-mix(in oklab, var(--color-carbon) 75%, transparent)",
      }}
    >
      <p
        className="text-[9px] uppercase tracking-[0.22em] m-0 mb-0.5"
        style={{ color: "var(--color-steel)" }}
      >
        {label}
      </p>
      <p
        className="text-[14px] m-0 font-mono"
        style={{ color: "var(--color-snow)" }}
      >
        {value}
      </p>
      {hint && (
        <p className="text-[9px] m-0 mt-0.5 font-mono" style={{ color: "var(--color-steel)" }}>
          {hint}
        </p>
      )}
    </div>
  );
}