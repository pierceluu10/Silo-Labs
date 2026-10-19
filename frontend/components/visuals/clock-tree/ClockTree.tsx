"use client";

import { useEffect, useMemo, useState } from "react";
import { Background, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { DEFAULT_BOARD_PART, useSiloStore, type ClockEvent } from "@/lib/store";

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

const DERIVED_COLUMN_WIDTH = 170;
const DERIVED_ROW_HEIGHT = 90;

/**
 * Layered layout built from the configured clock rows, for MCUs without a
 * hand-modeled topology file. Column = hops from a root oscillator.
 */
function deriveTopology(clocks: ClockEvent[]): Topology {
  const sourceOf = new Map(clocks.map((c) => [c.clock_domain, c.source]));
  const ids = Array.from(new Set(clocks.flatMap((c) => [c.source, c.clock_domain])));
  const depth = (id: string, seen = new Set<string>()): number => {
    const source = sourceOf.get(id);
    if (!source || source === id || seen.has(id)) return 0;
    return depth(source, seen.add(id)) + 1;
  };
  const rowsUsed = new Map<number, number>();
  const nodes = ids.map((id) => {
    const column = depth(id);
    const row = rowsUsed.get(column) ?? 0;
    rowsUsed.set(column, row + 1);
    return {
      id,
      kind: "clock",
      label: id,
      default_freq_hz: 0,
      position: { x: column * DERIVED_COLUMN_WIDTH, y: row * DERIVED_ROW_HEIGHT },
    };
  });
  const edges = clocks
    .filter((c) => c.source !== c.clock_domain)
    .map((c) => ({ source: c.source, target: c.clock_domain, kind: "feeds" }));
  return { nodes, edges };
}

function formatHz(hz: number): string {
  if (hz >= 1_000_000) return `${(hz / 1_000_000).toFixed(hz % 1_000_000 === 0 ? 0 : 1)} MHz`;
  if (hz >= 1_000) return `${(hz / 1_000).toFixed(0)} kHz`;
  return `${hz} Hz`;
}

export function ClockTree() {
  const clocks = useSiloStore((s) => s.clocks);
  const boardPart = useSiloStore((s) => s.target?.boardPart ?? DEFAULT_BOARD_PART);
  const [picoTopology, setPicoTopology] = useState<Topology | null>(null);
  // clock_topology.json is the RP2040's hand-modeled tree; other boards derive theirs.
  const isPico = boardPart === DEFAULT_BOARD_PART;
  const derivedTopology = useMemo(() => (isPico ? null : deriveTopology(clocks)), [isPico, clocks]);
  const topology = isPico ? picoTopology : derivedTopology;

  useEffect(() => {
    if (!isPico) return;
    fetch("/clock_topology.json")
      .then((r) => r.json())
      .then((t: Topology) => setPicoTopology(t))
      .catch(() => setPicoTopology({ nodes: [], edges: [] }));
  }, [isPico]);

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
                {freq > 0 ? formatHz(freq) : "-"}
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

  // Defer the ReactFlow render until topology loads so its `fitView` runs
  // against the real nodes (otherwise it fits to nothing on mount and the
  // viewport stays empty). minHeight guards against any 0-height parent.
  if (!topology) {
    return (
      <div className="h-full w-full flex items-center justify-center text-[10px] text-steel font-mono">
        Loading clock topology…
      </div>
    );
  }

  return (
    <div className="h-full w-full" style={{ minHeight: 220 }}>
      <ReactFlow
        // Remount when the node set changes so fitView frames streamed-in clocks.
        key={nodes.length}
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
        panOnDrag={false}
        zoomOnScroll={false}
        nodesDraggable={false}
      >
        <Background color="var(--color-charcoal)" gap={16} />
      </ReactFlow>
    </div>
  );
}
