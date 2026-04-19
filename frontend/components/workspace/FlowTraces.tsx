"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSiloStore } from "@/lib/store";

interface Anchor {
  x: number;
  y: number;
}

const CARD_IDS = ["card-pinout", "card-clocks", "card-wiring", "card-code"] as const;

/**
 * Animated SVG flow lines drawn from each *active* agent card to the central
 * code/terminal window. Lives behind the workspace grid.
 */
export function FlowTraces() {
  const active = useSiloStore((s) => s.activeAgent);
  const [anchors, setAnchors] = useState<{ from: Anchor[]; to: Anchor | null }>({
    from: [],
    to: null,
  });
  const rafRef = useRef<number | null>(null);

  // Map an agent name to the card id whose anchor should glow.
  const cardIdFor = (a: typeof active): (typeof CARD_IDS)[number] | null => {
    if (a === "pinout_resolver" || a === "requirements_parser") return "card-pinout";
    if (a === "clock_configurator") return "card-clocks";
    if (a === "wokwi_diagram_generator" || a === "errata_checker") return "card-wiring";
    if (a === "code_composer" || a === "peripheral_configurator") return "card-code";
    return null;
  };

  useEffect(() => {
    function measure() {
      const center = document.getElementById("workspace-center");
      if (!center) return;
      const cRect = center.getBoundingClientRect();
      const to = { x: cRect.left + cRect.width / 2, y: cRect.top + cRect.height / 2 };
      const from: Anchor[] = [];
      const targetId = cardIdFor(active);
      if (targetId) {
        const el = document.getElementById(targetId);
        if (el) {
          const r = el.getBoundingClientRect();
          from.push({ x: r.left + r.width / 2, y: r.top + r.height / 2 });
        }
      }
      setAnchors({ from, to });
    }
    measure();
    const onResize = () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(measure);
    };
    window.addEventListener("resize", onResize);
    const interval = window.setInterval(measure, 600); // re-measure for layout shifts
    return () => {
      window.removeEventListener("resize", onResize);
      window.clearInterval(interval);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [active]);

  return (
    <svg
      className="pointer-events-none fixed inset-0"
      style={{ zIndex: 1, width: "100vw", height: "100vh" }}
      aria-hidden
    >
      <AnimatePresence>
        {anchors.to &&
          anchors.from.map((p, i) => {
            const midX = (p.x + anchors.to!.x) / 2;
            const midY = (p.y + anchors.to!.y) / 2 + (i % 2 === 0 ? -32 : 32);
            const d = `M ${p.x} ${p.y} Q ${midX} ${midY} ${anchors.to!.x} ${anchors.to!.y}`;
            return (
              <motion.path
                key={`trace-${i}-${active}`}
                d={d}
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.55 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                fill="none"
                stroke="var(--color-accent)"
                strokeWidth={1.4}
                strokeDasharray="4 6"
                strokeLinecap="round"
                style={{ animation: "siloDashFlow 0.9s linear infinite" }}
              />
            );
          })}
      </AnimatePresence>
    </svg>
  );
}