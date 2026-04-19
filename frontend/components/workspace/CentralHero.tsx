"use client";

import { useState, useEffect, useRef } from "react";
import clsx from "clsx";
import { useSiloStore } from "@/lib/store";
import { getApiBase } from "@/lib/sse";
import { CodeEditor } from "@/components/visuals/code-editor/CodeEditor";
import { TerminalView } from "@/components/visuals/terminal/TerminalView";
import { WokwiSimViewer } from "@/components/visuals/wokwi-sim/WokwiSimViewer";
import { FollowUpBar } from "./WorkspaceChrome";

type Tab = "code" | "terminal" | "live";

function ExpandIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" aria-hidden>
      <path d="M2 4.5V2h2.5" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" />
      <path d="M10 7.5V10H7.5" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" />
      <path d="M7.5 2H10v2.5" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" />
      <path d="M4.5 10H2V7.5" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" />
    </svg>
  );
}

export function CentralHero() {
  const [tab, setTab] = useState<Tab>("code");
  const uf2Url = useSiloStore((s) => s.uf2Url);
  const sessionId = useSiloStore((s) => s.sessionId);
  const simLines = useSiloStore((s) => s.simulateLog);
  const devicePart = useSiloStore((s) => s.devicePart);
  const setFullscreen = useSiloStore((s) => s.setFullscreen);
  const sawSim = useRef(false);
  const api = getApiBase();

  useEffect(() => {
    sawSim.current = false;
  }, [sessionId]);

  useEffect(() => {
    if (simLines.length > 0 && !sawSim.current) {
      sawSim.current = true;
      setTab("terminal");
    }
  }, [simLines.length]);

  return (
    <section
      id="workspace-center"
      className="relative border rounded-2xl flex flex-col min-h-0 overflow-hidden h-full"
      style={{
        borderColor: "var(--color-charcoal)",
        background: "color-mix(in oklab, var(--color-abyss) 86%, transparent)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.04), 0 10px 40px rgba(0,0,0,0.4)",
      }}
    >
      <header
        className="flex items-center gap-0 border-b"
        style={{ borderColor: "var(--color-charcoal)" }}
      >
        {(["code", "terminal", "live"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx("px-4 py-2 text-[11px] uppercase tracking-[0.18em] transition-colors")}
            style={{
              color: tab === t ? "var(--color-accent-light)" : "var(--color-steel)",
              borderBottom: tab === t ? "1px solid var(--color-accent)" : "1px solid transparent",
            }}
          >
            {t === "live" ? "Live Sim" : t}
          </button>
        ))}
        {tab === "terminal" && devicePart?.is_stub && (
          <span
            title={devicePart.note}
            className="ml-2 px-2 py-0.5 rounded text-[10px] uppercase tracking-[0.18em] cursor-help"
            style={{
              background: "var(--color-warn)",
              color: "var(--color-abyss)",
              fontFamily: "var(--font-mono)",
            }}
          >
            stub: {devicePart.device} → {devicePart.wokwi_part}
          </span>
        )}
        <div className="flex-1" />
        {uf2Url && (
          <a
            href={`${api}${uf2Url}`}
            download
            className="px-3 py-1.5 mr-2 rounded text-[11px] uppercase tracking-[0.18em]"
            style={{ background: "var(--color-accent)", color: "var(--color-abyss)" }}
          >
            .uf2
          </a>
        )}
        <button
          type="button"
          aria-label="Fullscreen central panel"
          onClick={() => setFullscreen("code")}
          className="px-2 py-1.5 mr-2 rounded transition-colors"
          style={{ color: "var(--color-steel)" }}
        >
          <ExpandIcon />
        </button>
      </header>
      <div className="flex-1 min-h-0 relative">
        <div style={{ display: tab === "code" ? "block" : "none", height: "100%" }}>
          <CodeEditor />
        </div>
        <div style={{ display: tab === "terminal" ? "block" : "none", height: "100%" }}>
          <TerminalView />
        </div>
        <div style={{ display: tab === "live" ? "block" : "none", height: "100%" }}>
          <WokwiSimViewer />
        </div>
      </div>
      <div
        className="px-4 pt-3 pb-3 border-t"
        style={{ borderColor: "var(--color-charcoal)" }}
      >
        <FollowUpBar />
      </div>
    </section>
  );
}