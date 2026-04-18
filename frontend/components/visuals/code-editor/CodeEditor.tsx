"use client";

import dynamic from "next/dynamic";
import { useSiloStore } from "@/lib/store";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export function CodeEditor() {
  const code = useSiloStore((s) => s.code);

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
