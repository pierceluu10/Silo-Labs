"use client";

import { useState } from "react";

interface Props {
  prompt: string;
}

/**
 * Top-left workspace eyebrow. Mimics the "Genome Analysis" title in the
 * reference screenshot: small all-caps overline + the user's prompt.
 */
export function WorkspacePromptHeader({ prompt }: Props) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span
        className="text-[9px] uppercase tracking-[0.22em] font-mono"
        style={{ color: "var(--color-steel)" }}
      >
        Silo Labs · Workspace
      </span>
      <span
        className="text-[13px] sm:text-sm font-medium truncate"
        style={{ color: "var(--color-snow)", maxWidth: "min(60vw, 720px)" }}
        title={prompt}
      >
        {prompt}
      </span>
    </div>
  );
}

interface BarProps {
  onSubmit?: (text: string) => void;
}

/**
 * Rounded glassy "Ask a follow up question..." bar (UI stub).
 * Pressing Enter does nothing for now since the pipeline is one-shot;
 * the input is captured but a tooltip explains follow-ups are not wired.
 */
export function FollowUpBar({ onSubmit }: BarProps) {
  const [value, setValue] = useState("");
  const [showHint, setShowHint] = useState(false);

  return (
    <div
      className="w-full max-w-2xl mx-auto pointer-events-auto"
      style={{ position: "relative" }}
    >
      <div
        className="flex items-center gap-2 rounded-full pl-4 pr-2 py-2 border"
        style={{
          background: "color-mix(in oklab, var(--color-carbon) 80%, transparent)",
          borderColor: "var(--color-charcoal)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
          boxShadow: "0 6px 30px rgba(0,0,0,0.35)",
        }}
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (onSubmit) onSubmit(value);
              setShowHint(true);
              setTimeout(() => setShowHint(false), 2500);
            }
          }}
          placeholder="Ask a follow up question…"
          className="flex-1 bg-transparent border-0 outline-none text-sm px-2"
          style={{ color: "var(--color-snow)" }}
        />
        <button
          type="button"
          aria-label="Send follow-up"
          onClick={() => {
            if (onSubmit) onSubmit(value);
            setShowHint(true);
            setTimeout(() => setShowHint(false), 2500);
          }}
          className="w-8 h-8 flex items-center justify-center rounded-full transition-colors"
          style={{ background: "var(--color-charcoal)", color: "var(--color-snow)" }}
        >
          ›
        </button>
      </div>
      {showHint && (
        <p
          className="absolute -top-7 left-0 right-0 text-center text-[10px]"
          style={{ color: "var(--color-steel)" }}
        >
          Conversational follow-ups land in a future build — pipeline is one-shot for now.
        </p>
      )}
    </div>
  );
}