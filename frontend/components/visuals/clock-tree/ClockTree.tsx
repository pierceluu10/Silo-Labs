"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useSiloStore } from "@/lib/store";

interface TopologyNode {
  id: string;
  kind: string;
  label: string;
  default_freq_hz: number;
  position: { x: number; y: number };
}

interface TopologyEdge {
  source: string;
  target: string;
  kind: string;
}

interface Topology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

function formatHz(hz: number): string {
  if (hz >= 1_000_000) return `${(hz / 1_000_000).toFixed(hz % 1_000_000 === 0 ? 0 : 1)} MHz`;
  if (hz >= 1_000) return `${(hz / 1_000).toFixed(0)} kHz`;
  return `${hz} Hz`;
}

export function ClockTree() {
  const clocks = useSiloStore((s) => s.clocks);
  const [topology, setTopology] = useState<Topology | null>(null);

  useEffect(() => {
    fetch("/clock_topology.json")
      .then((r) => r.json())
      .then((t: Topology) => setTopology(t))
      .catch(() => setTopology({ nodes: [], edges: [] }));
  }, []);

  const freqByDomain = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of clocks) m.set(c.clock_domain, c.freq_hz);
    return m;
  }, [clocks]);

  const activeEdges = useMemo(() => {
    const s = new Set<string>();
    for (const c of clocks) s.add(`${c.source}-${c.clock_domain}`);
    return s;
  }, [clocks]);

  const { nodes, edges } = useMemo(() => {
    if (!topology) return { nodes: [] as Node[], edges: [] as Edge[] };
    const nodes: Node[] = topology.nodes.map((n) => {
      const configured = freqByDomain.get(n.id);
      const freq = configured ?? n.default_freq_hz;
      const active = configured !== undefined;
      return {
        id: n.id,
        position: { x: n.position.x * 0.85, y: n.position.y * 0.7 },
        data: {
          label: (
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, lineHeight: 1.25 }}>
              <div style={{ color: active ? "var(--color-accent-light)" : "var(--color-snow)" }}>
                {n.label}
              </div>
              <div style={{ color: active ? "var(--color-accent)" : "var(--color-steel)" }}>
                {freq > 0 ? formatHz(freq) : "—"}
              </div>
            </div>
          ),
        },
        style: {
          background: "var(--color-carbon)",
          border: `1px solid ${active ? "var(--color-accent)" : "var(--color-charcoal)"}`,
          boxShadow: active ? "0 0 10px var(--color-accent-tint)" : "none",
          color: "var(--color-snow)",
          padding: 6,
          borderRadius: 4,
          minWidth: 96,
        },
      };
    });
    const edges: Edge[] = topology.edges.map((e, i) => {
      const active = activeEdges.has(`${e.source}-${e.target}`);
      return {
        id: `e${i}-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        animated: active,
        style: {
          stroke: active ? "var(--color-accent)" : "var(--color-charcoal)",
          strokeWidth: active ? 2 : 1,
        },
      };
    });
    return { nodes, edges };
  }, [topology, freqByDomain, activeEdges]);

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        proOptions={{ hideAttribution: true }}
        panOnDrag={false}
        zoomOnScroll={false}
        nodesDraggable={false}
      >
        <Background color="var(--color-charcoal)" gap={16} />
        <Controls showZoom={false} showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
