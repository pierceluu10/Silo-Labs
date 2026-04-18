"use client";

import { useState } from "react";
import clsx from "clsx";
import { useSiloStore } from "@/lib/store";

type Tab = "code" | "terminal";

export function CentralHero() {
  const [tab, setTab] = useState<Tab>("code");
  const code = useSiloStore((s) => s.code);
  const buildLog = useSiloStore((s) => s.buildLog);
  const simulateLog = useSiloStore((s) => s.simulateLog);
  const uf2Url = useSiloStore((s) => s.uf2Url);

  return (
    <section
      className="border rounded-sm flex flex-col min-h-0 overflow-hidden"
      style={{
        borderColor: "var(--color-charcoal)",
        background: "var(--color-abyss)",
      }}
    >
      <header
        className="flex items-center gap-0 border-b"
        style={{ borderColor: "var(--color-charcoal)" }}
      >
        {(["code", "terminal"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              "px-4 py-2 text-[11px] uppercase tracking-[0.18em] transition-colors",
            )}
            style={{
              color:
                tab === t ? "var(--color-accent-light)" : "var(--color-steel)",
              borderBottom:
                tab === t ? "1px solid var(--color-accent)" : "1px solid transparent",
            }}
          >
            {t}
          </button>
        ))}
        <div className="flex-1" />
        {uf2Url && (
          <a
            href={uf2Url}
            download
            className="px-3 py-1.5 mr-2 rounded text-[11px] uppercase tracking-[0.18em]"
            style={{ background: "var(--color-accent)", color: "var(--color-abyss)" }}
          >
            .uf2
          </a>
        )}
      </header>
      <div className="flex-1 min-h-0 overflow-auto p-4 font-mono text-xs text-parchment whitespace-pre-wrap">
        {tab === "code" ? (
          code || <span className="text-steel">Code will stream here…</span>
        ) : (
          <>
            {buildLog.map((line, i) => (
              <div key={`b${i}`} style={{ color: "var(--color-steel)" }}>
                [build] {line}
              </div>
            ))}
            {simulateLog.map((line, i) => (
              <div key={`s${i}`} style={{ color: "var(--color-parchment)" }}>
                [wokwi] {line}
              </div>
            ))}
            {!buildLog.length && !simulateLog.length && (
              <span className="text-steel">Build and simulation output will appear here…</span>
            )}
          </>
        )}
      </div>
    </section>
  );
}
