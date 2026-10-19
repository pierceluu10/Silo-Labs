"use client";

import { useState, useEffect, useRef } from "react";
import clsx from "clsx";
import { ArrowsOutSimple, DownloadSimple } from "@phosphor-icons/react";
import { useSiloStore } from "@/lib/store";
import { getApiBase } from "@/lib/sse";
import { CodeEditor } from "@/components/visuals/code-editor/CodeEditor";
import { TerminalView } from "@/components/visuals/terminal/TerminalView";
import { WokwiSimViewer } from "@/components/visuals/wokwi-sim/WokwiSimViewer";
import { MetricsView } from "@/components/visuals/metrics/MetricsView";

type Tab = "code" | "terminal" | "live" | "metrics";

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
      setTab("live");
    }
  }, [simLines.length]);

  return (
    <section
      id="workspace-center"
      className="workspace-stage"
    >
      <header className="workspace-stage__header">
        <div className="workspace-stage__tabs" role="tablist" aria-label="Workspace output">
        {(["code", "terminal", "live", "metrics"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx("workspace-tab", tab === t && "workspace-tab--active")}
            role="tab"
            aria-selected={tab === t}
          >
            {t === "live" ? "Live Sim" : t}
          </button>
        ))}
        </div>
        {tab === "terminal" && devicePart?.is_stub && (
          <span
            title={devicePart.note}
            className="sim-note"
            style={{
              background: "var(--color-warn)",
              color: "var(--color-abyss)",
              fontFamily: "var(--font-mono)",
            }}
          >
            stub: {devicePart.device} → {devicePart.wokwi_part}
          </span>
        )}
        <div className="workspace-stage__actions">
        {uf2Url && (
          <a
            href={`${api}${uf2Url}`}
            download
            className="download-button"
          >
            <DownloadSimple size={14} /> Firmware
          </a>
        )}
        <button
          type="button"
          aria-label="Fullscreen central panel"
          onClick={() => setFullscreen("code")}
          className="icon-button"
        >
          <ArrowsOutSimple size={15} />
        </button>
        </div>
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
        <div style={{ display: tab === "metrics" ? "block" : "none", height: "100%" }}>
          <MetricsView />
        </div>
      </div>
    </section>
  );
}
