"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { openPipelineStream } from "@/lib/sse";
import { useSiloStore } from "@/lib/store";
import { AgentPanel } from "./AgentPanel";
import { CentralHero } from "./CentralHero";
import { FullscreenOverlay } from "./FullscreenOverlay";
import { WorkspacePromptHeader } from "./WorkspaceChrome";
import { PinoutDiagram } from "@/components/visuals/pinout/PinoutDiagram";
import { ClockTree } from "@/components/visuals/clock-tree/ClockTree";
import { RegisterPanel } from "@/components/visuals/registers/RegisterPanel";
import { BreadboardView } from "@/components/visuals/breadboard/BreadboardView";

interface Props {
  prompt: string;
}

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.06 },
  },
};

const item = {
  hidden: { opacity: 0, y: 10, filter: "blur(6px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.4, ease: [0.2, 0.8, 0.2, 1] as const },
  },
};

export function WorkspaceLayout({ prompt }: Props) {
  const apply = useSiloStore((s) => s.apply);
  const reset = useSiloStore((s) => s.reset);
  const sessionId = useSiloStore((s) => s.sessionId);
  const pipelineComplete = useSiloStore((s) => s.pipelineComplete);
  const errorMessage = useSiloStore((s) => s.errorMessage);

  useEffect(() => {
    reset();
    const source = openPipelineStream(prompt, apply);
    return () => source.close();
  }, [prompt, apply, reset]);

  return (
    <>
      <FullscreenOverlay />
      <motion.main
        className="h-screen p-4 grid gap-3"
        style={{
          gridTemplateColumns: "1fr 2fr 1fr",
          gridTemplateRows: "auto 1fr 1fr",
          position: "relative",
          zIndex: 2,
        }}
        variants={container}
        initial="hidden"
        animate="show"
      >
        <motion.header
          variants={item}
          className="col-span-3 flex items-center justify-between px-1 py-1"
        >
          <WorkspacePromptHeader prompt={prompt} />
          <span
            className="text-[10px] uppercase tracking-[0.22em] font-mono"
            style={{
              color: errorMessage
                ? "var(--color-danger)"
                : pipelineComplete
                  ? "var(--color-accent-light)"
                  : "var(--color-steel)",
            }}
          >
            {sessionId ? `session ${sessionId.slice(0, 8)}` : "connecting…"}
            {" · "}
            {errorMessage ? "error" : pipelineComplete ? "complete" : "running"}
          </span>
        </motion.header>

        <motion.div variants={item} id="card-pinout" className="min-h-0 flex flex-col">
          <AgentPanel agent="pinout_resolver">
            <PinoutDiagram />
          </AgentPanel>
        </motion.div>
        <motion.div
          variants={item}
          className="row-span-2 min-h-0 flex flex-col"
        >
          <CentralHero />
        </motion.div>
        <motion.div variants={item} id="card-clocks" className="min-h-0 flex flex-col">
          <AgentPanel agent="clock_configurator">
            <ClockTree />
          </AgentPanel>
        </motion.div>
        <motion.div variants={item} id="card-wiring" className="min-h-0 flex flex-col">
          <AgentPanel agent="wokwi_diagram_generator">
            <BreadboardView />
          </AgentPanel>
        </motion.div>
        <motion.div variants={item} id="card-code" className="min-h-0 flex flex-col">
          <AgentPanel agent="peripheral_configurator" title="Agent — Registers">
            <RegisterPanel />
          </AgentPanel>
        </motion.div>
      </motion.main>
    </>
  );
}