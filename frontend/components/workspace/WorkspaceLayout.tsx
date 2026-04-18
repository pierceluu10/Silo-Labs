"use client";

import { useEffect } from "react";
import { openPipelineStream } from "@/lib/sse";
import { useSiloStore } from "@/lib/store";
import { AgentPanel } from "./AgentPanel";
import { CentralHero } from "./CentralHero";
import { PinoutDiagram } from "@/components/visuals/pinout/PinoutDiagram";
import { ClockTree } from "@/components/visuals/clock-tree/ClockTree";

interface Props {
  prompt: string;
}

export function WorkspaceLayout({ prompt }: Props) {
  const apply = useSiloStore((s) => s.apply);
  const reset = useSiloStore((s) => s.reset);
  const sessionId = useSiloStore((s) => s.sessionId);
  const pipelineComplete = useSiloStore((s) => s.pipelineComplete);

  useEffect(() => {
    reset();
    const source = openPipelineStream(prompt, apply);
    return () => source.close();
  }, [prompt, apply, reset]);

  return (
    <main
      className="h-screen p-4 grid gap-4"
      style={{
        gridTemplateColumns: "1fr 2fr 1fr",
        gridTemplateRows: "1fr 1fr",
      }}
    >
      <AgentPanel
        title="Requirements · Pinout"
        agents={["requirements_parser", "pinout_resolver"]}
      >
        <PinoutDiagram />
      </AgentPanel>
      <div className="row-span-2 min-h-0">
        <CentralHero />
      </div>
      <AgentPanel title="Clocks" agents={["clock_configurator"]}>
        <ClockTree />
      </AgentPanel>
      <AgentPanel
        title="Errata · Wiring"
        agents={["errata_checker", "wokwi_diagram_generator"]}
      />
      <AgentPanel
        title="Registers · Code"
        agents={["peripheral_configurator", "code_composer"]}
      />
      <footer
        className="col-span-3 flex items-center justify-between text-[11px] uppercase tracking-[0.18em] mt-0 pt-2 border-t"
        style={{ borderColor: "var(--color-charcoal)", color: "var(--color-steel)" }}
      >
        <span>{sessionId ? `session ${sessionId.slice(0, 8)}` : "connecting…"}</span>
        <span style={{ color: pipelineComplete ? "var(--color-accent-light)" : "var(--color-steel)" }}>
          {pipelineComplete ? "complete" : "running"}
        </span>
      </footer>
    </main>
  );
}
