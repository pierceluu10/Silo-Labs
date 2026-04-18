"use client";

import { useEffect, useRef } from "react";
import type { Terminal as XTerm } from "xterm";
import type { FitAddon as XTermFitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import { useSiloStore } from "@/lib/store";

export function TerminalView() {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const termRef = useRef<XTerm | null>(null);
  const fitRef = useRef<XTermFitAddon | null>(null);
  const buildLen = useRef(0);
  const simLen = useRef(0);

  const buildLog = useSiloStore((s) => s.buildLog);
  const simulateLog = useSiloStore((s) => s.simulateLog);

  useEffect(() => {
    let cancelled = false;
    let resize: (() => void) | null = null;
    (async () => {
      const { Terminal } = await import("xterm");
      const { FitAddon } = await import("xterm-addon-fit");
      if (cancelled || !hostRef.current) return;
      const term = new Terminal({
        fontFamily: "SFMono-Regular, Menlo, monospace",
        fontSize: 12,
        theme: {
          background: "#050507",
          foreground: "#b8b3b0",
          cursor: "#e63946",
          selectionBackground: "rgba(230,57,70,0.3)",
        },
        convertEol: true,
        disableStdin: true,
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(hostRef.current);
      fit.fit();
      termRef.current = term;
      fitRef.current = fit;
      resize = () => fit.fit();
      window.addEventListener("resize", resize);
    })();
    return () => {
      cancelled = true;
      if (resize) window.removeEventListener("resize", resize);
      termRef.current?.dispose();
      termRef.current = null;
    };
  }, []);

  useEffect(() => {
    const term = termRef.current;
    if (!term) return;
    for (let i = buildLen.current; i < buildLog.length; i++) {
      term.writeln(`\x1b[38;5;244m[build]\x1b[0m ${buildLog[i]}`);
    }
    buildLen.current = buildLog.length;
  }, [buildLog]);

  useEffect(() => {
    const term = termRef.current;
    if (!term) return;
    for (let i = simLen.current; i < simulateLog.length; i++) {
      term.writeln(`\x1b[38;5;210m[wokwi]\x1b[0m ${simulateLog[i]}`);
    }
    simLen.current = simulateLog.length;
  }, [simulateLog]);

  return <div ref={hostRef} className="h-full w-full" />;
}
