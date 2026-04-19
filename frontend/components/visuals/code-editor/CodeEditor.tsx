"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import clsx from "clsx";
import { useSiloStore } from "@/lib/store";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const LANGUAGE_BY_EXT: Record<string, string> = {
  c: "c",
  h: "c",
  cpp: "cpp",
  hpp: "cpp",
  txt: "plaintext",
  cmake: "cmake",
  pio: "plaintext",
  json: "json",
  toml: "toml",
  md: "markdown",
};

function languageFor(file: { path: string; language?: string | null }): string {
  if (file.language) return file.language;
  if (file.path === "CMakeLists.txt") return "cmake";
  const ext = file.path.split(".").pop()?.toLowerCase() ?? "";
  return LANGUAGE_BY_EXT[ext] ?? "plaintext";
}

export function CodeEditor() {
  const code = useSiloStore((s) => s.code);
  const files = useSiloStore((s) => s.generatedFiles);
  const [active, setActive] = useState<string>("main.c");

  // Default-select the first file when the project arrives.
  useEffect(() => {
    if (files.length > 0 && !files.some((f) => f.path === active)) {
      setActive(files[0].path);
    }
  }, [files, active]);

  const activeFile = useMemo(
    () => files.find((f) => f.path === active) ?? null,
    [files, active],
  );

  // Streaming mode: no multi-file project yet, just show the typewriter main.c.
  if (files.length === 0) {
    return (
      <MonacoEditor
        height="100%"
        defaultLanguage="c"
        theme="vs-dark"
        value={code || "// Code will stream here…"}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 12,
          fontFamily: "SFMono-Regular, Menlo, monospace",
          scrollBeyondLastLine: false,
          lineNumbers: "on",
          renderWhitespace: "none",
          automaticLayout: true,
        }}
      />
    );
  }

  const value = activeFile ? activeFile.content : code;
  const language = activeFile ? languageFor(activeFile) : "c";

  return (
    <div className="flex h-full w-full">
      <div
        className="shrink-0 w-44 overflow-y-auto border-r"
        style={{ borderColor: "var(--color-charcoal)", background: "var(--color-carbon)" }}
      >
        <p
          className="px-3 pt-2 pb-1 text-[9px] uppercase tracking-[0.2em] m-0"
          style={{ color: "var(--color-steel)" }}
        >
          Project files
        </p>
        <ul className="m-0 p-0 list-none">
          {files.map((f) => (
            <li key={f.path}>
              <button
                type="button"
                onClick={() => setActive(f.path)}
                className={clsx(
                  "block w-full text-left px-3 py-1 text-[11px] font-mono truncate transition-colors",
                )}
                title={f.path}
                style={{
                  color:
                    active === f.path ? "var(--color-accent-light)" : "var(--color-parchment)",
                  background:
                    active === f.path
                      ? "color-mix(in oklab, var(--color-accent-tint) 70%, transparent)"
                      : "transparent",
                }}
              >
                {f.path}
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="flex-1 min-w-0">
        <MonacoEditor
          height="100%"
          path={activeFile?.path}
          language={language}
          theme="vs-dark"
          value={value}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            fontFamily: "SFMono-Regular, Menlo, monospace",
            scrollBeyondLastLine: false,
            lineNumbers: "on",
            renderWhitespace: "none",
            automaticLayout: true,
          }}
        />
      </div>
    </div>
  );
}