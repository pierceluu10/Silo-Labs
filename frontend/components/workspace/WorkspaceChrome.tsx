"use client";

import { useSiloStore } from "@/lib/store";

interface Props {
  prompt: string;
}

export function WorkspacePromptHeader({ prompt }: Props) {
  const target = useSiloStore((s) => s.target);
  return (
    <div className="workspace-prompt">
      <span className="workspace-brand">SL</span>
      <div>
        <span className="workspace-kicker">
          {target ? `${target.displayName} · ${target.sdk}` : "Firmware run"}
        </span>
        <h1 title={prompt}>{prompt}</h1>
      </div>
    </div>
  );
}
