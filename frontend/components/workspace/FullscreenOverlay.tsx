"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect } from "react";
import type { AgentName } from "@/types/sse";
import { useSiloStore } from "@/lib/store";
import { AgentPanel } from "./AgentPanel";
import { PinoutDiagram } from "@/components/visuals/pinout/PinoutDiagram";
import { ClockTree } from "@/components/visuals/clock-tree/ClockTree";
import { BreadboardView } from "@/components/visuals/breadboard/BreadboardView";
import { RegisterPanel } from "@/components/visuals/registers/RegisterPanel";
import { CodeEditor } from "@/components/visuals/code-editor/CodeEditor";

const VISUALS: Record<AgentName | "code", React.ReactNode> = {
  supervisor: null,
  requirements_parser: null,
  pinout_resolver: <PinoutDiagram />,
  clock_configurator: <ClockTree />,
  peripheral_configurator: <RegisterPanel />,
  errata_checker: null,
  wokwi_diagram_generator: <BreadboardView />,
  code_composer: <CodeEditor />,
  code: <CodeEditor />,
};

export function FullscreenOverlay() {
  const target = useSiloStore((s) => s.fullscreen);
  const setFullscreen = useSiloStore((s) => s.setFullscreen);

  useEffect(() => {
    if (!target) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [target, setFullscreen]);

  return (
    <AnimatePresence>
      {target && (
        <motion.div
          key="overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-8"
          style={{ background: "rgba(5,5,7,0.65)", backdropFilter: "blur(8px)" }}
          onClick={() => setFullscreen(null)}
        >
          <motion.div
            key="panel"
            initial={{ scale: 0.96, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.97, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
            className="relative"
            style={{ width: "min(72vw, 1100px)", height: "min(78vh, 760px)" }}
            onClick={(e) => e.stopPropagation()}
          >
            {target === "code" ? (
              <AgentPanel agent="code_composer" title="Agent — Code" fullscreen>
                {VISUALS.code}
              </AgentPanel>
            ) : (
              <AgentPanel agent={target} fullscreen>
                {VISUALS[target]}
              </AgentPanel>
            )}
            <p
              className="absolute -bottom-7 left-0 right-0 text-center text-[10px] uppercase tracking-[0.2em]"
              style={{ color: "var(--color-steel)" }}
            >
              Press Esc to close
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}