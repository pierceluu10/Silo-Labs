"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { openPipelineStream } from "@/lib/sse";
import { useSiloStore } from "@/lib/store";
import { AgentPanel } from "./AgentPanel";
import { AgentRunRail } from "./AgentRunRail";
import { CentralHero } from "./CentralHero";
import { FullscreenOverlay } from "./FullscreenOverlay";
import { WorkspacePromptHeader } from "./WorkspaceChrome";
import { PinoutDiagram } from "@/components/visuals/pinout/PinoutDiagram";
import { ClockTree } from "@/components/visuals/clock-tree/ClockTree";
import { RegisterPanel } from "@/components/visuals/registers/RegisterPanel";
import { BreadboardView } from "@/components/visuals/breadboard/BreadboardView";

interface Props {
  prompt: string;
  mcu: string;
}

const item = {
  hidden: { opacity: 0, y: 10, filter: "blur(6px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.4, ease: [0.2, 0.8, 0.2, 1] as const },
  },
};

export function WorkspaceLayout({ prompt, mcu }: Props) {
  const apply = useSiloStore((s) => s.apply);
  const reset = useSiloStore((s) => s.reset);
  const sessionId = useSiloStore((s) => s.sessionId);
  const pipelineComplete = useSiloStore((s) => s.pipelineComplete);
  const errorMessage = useSiloStore((s) => s.errorMessage);

  useEffect(() => {
    reset();
    const source = openPipelineStream(prompt, mcu, apply);
    return () => source.close();
  }, [prompt, mcu, apply, reset]);

  return (
    <>
      <FullscreenOverlay />
      <motion.main
        className="workspace-shell"
        initial="hidden"
        animate="show"
      >
        <motion.header
          variants={item}
          className="workspace-header"
        >
          <WorkspacePromptHeader prompt={prompt} />
          <span
            className="workspace-status"
            data-state={errorMessage ? "error" : pipelineComplete ? "complete" : "running"}
            style={{
              color: errorMessage
                ? "var(--color-danger)"
                : pipelineComplete
                  ? "var(--color-accent-light)"
                  : "var(--color-steel)",
            }}
          >
            {sessionId ? `Run ${sessionId.slice(0, 8)}` : "Connecting"}
            <span>{errorMessage ? "Error" : pipelineComplete ? "Complete" : "Running"}</span>
          </span>
        </motion.header>

        <motion.div variants={item} className="workspace-rail">
          <AgentRunRail />
        </motion.div>
        <motion.div variants={item} id="card-pinout" className="workspace-panel workspace-panel--pinout">
          <AgentPanel agent="pinout_resolver">
            <PinoutDiagram />
          </AgentPanel>
        </motion.div>
        <motion.div
          variants={item}
          className="workspace-center"
        >
          <CentralHero />
        </motion.div>
        <motion.div variants={item} id="card-clocks" className="workspace-panel workspace-panel--clocks">
          <AgentPanel agent="clock_configurator">
            <ClockTree />
          </AgentPanel>
        </motion.div>
        <motion.div variants={item} id="card-wiring" className="workspace-panel workspace-panel--wiring">
          <AgentPanel agent="wokwi_diagram_generator">
            <BreadboardView />
          </AgentPanel>
        </motion.div>
        <motion.div variants={item} id="card-code" className="workspace-panel workspace-panel--registers">
          <AgentPanel agent="peripheral_configurator" title="Peripheral registers">
            <RegisterPanel />
          </AgentPanel>
        </motion.div>
      </motion.main>
    </>
  );
}
