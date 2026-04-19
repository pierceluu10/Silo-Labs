"use client";

import { useEffect, useRef, useState } from "react";
import { useSiloStore } from "@/lib/store";
import { getApiBase } from "@/lib/sse";
import { WokwiClient } from "@/lib/wokwi-embed/wokwi-client";
import { MessagePortTransport } from "@/lib/wokwi-embed/message-port-transport";

interface SimBundle {
  session_id: string;
  diagram_json: Record<string, unknown>;
  wokwi_toml: string;
  uf2_url: string;
  elf_url: string | null;
}

type Status =
  | { kind: "idle" }
  | { kind: "no-build" }
  | { kind: "no-client-id" }
  | { kind: "loading"; message: string }
  | { kind: "running" }
  | { kind: "error"; message: string };

const CLIENT_ID = process.env.NEXT_PUBLIC_WOKWI_EMBED_CLIENT_ID;

export function WokwiSimViewer() {
  const sessionId = useSiloStore((s) => s.sessionId);
  const uf2Url = useSiloStore((s) => s.uf2Url);
  const apply = useSiloStore((s) => s.apply);
  const apiBase = getApiBase();

  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const clientRef = useRef<WokwiClient | null>(null);
  const startedForSessionRef = useRef<string | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  // Boot the simulator the first time we have a session + UF2 + the iframe
  // has handed us a port.
  useEffect(() => {
    if (!CLIENT_ID) {
      setStatus({ kind: "no-client-id" });
      return;
    }
    if (!sessionId || !uf2Url) {
      setStatus({ kind: "no-build" });
      return;
    }
    if (startedForSessionRef.current === sessionId) return;

    let cancelled = false;
    setStatus({ kind: "loading", message: "Waiting for Wokwi embed to connect…" });

    async function boot(client: WokwiClient) {
      try {
        await new Promise<void>((resolve) => {
          const onConnected = () => {
            client.removeEventListener("wokwi:connected", onConnected as EventListener);
            resolve();
          };
          client.addEventListener("wokwi:connected", onConnected as EventListener);
        });
        if (cancelled) return;
        setStatus({ kind: "loading", message: "Fetching firmware bundle…" });
        const bundleRes = await fetch(`${apiBase}/api/sim-bundle/${sessionId}`);
        if (!bundleRes.ok) throw new Error(`sim-bundle ${bundleRes.status}`);
        const bundle = (await bundleRes.json()) as SimBundle;

        const uf2Res = await fetch(`${apiBase}${bundle.uf2_url}`);
        if (!uf2Res.ok) throw new Error(`uf2 ${uf2Res.status}`);
        const uf2Bytes = new Uint8Array(await uf2Res.arrayBuffer());

        let elfBytes: Uint8Array | null = null;
        if (bundle.elf_url) {
          const elfRes = await fetch(`${apiBase}${bundle.elf_url}`);
          if (elfRes.ok) elfBytes = new Uint8Array(await elfRes.arrayBuffer());
        }

        if (cancelled) return;
        setStatus({ kind: "loading", message: "Uploading project to Wokwi embed…" });
        await client.serialMonitorListen();
        await client.fileUpload(
          "diagram.json",
          JSON.stringify(bundle.diagram_json, null, 2),
        );
        await client.fileUpload("wokwi.toml", bundle.wokwi_toml);
        await client.fileUpload("firmware.uf2", uf2Bytes);
        if (elfBytes) await client.fileUpload("firmware.elf", elfBytes);

        if (cancelled) return;
        setStatus({ kind: "loading", message: "Starting simulation…" });
        await client.simStart({
          firmware: "firmware.uf2",
          elf: elfBytes ? "firmware.elf" : "firmware.uf2",
        });
        if (cancelled) return;
        startedForSessionRef.current = sessionId!;
        setStatus({ kind: "running" });
      } catch (err) {
        if (cancelled) return;
        setStatus({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      }
    }

    function onMessage(event: MessageEvent) {
      const data = event.data as { port?: MessagePort } | undefined;
      if (!data || !data.port || clientRef.current) return;
      const transport = new MessagePortTransport(data.port);
      const client = new WokwiClient(transport);
      clientRef.current = client;
      // Pipe wokwi serial bytes back into our existing simulateLog so the
      // TERMINAL tab keeps streaming alongside this visual view.
      client.addEventListener("serial-monitor:data", (ev) => {
        const detail = (ev as CustomEvent).detail as { payload?: { bytes?: number[] } };
        const bytes = detail?.payload?.bytes;
        if (!bytes) return;
        const text = new TextDecoder().decode(new Uint8Array(bytes));
        for (const line of text.split(/\r?\n/)) {
          if (line.length > 0) apply({ type: "simulate_output", line });
        }
      });
      void boot(client);
    }

    window.addEventListener("message", onMessage);
    return () => {
      cancelled = true;
      window.removeEventListener("message", onMessage);
    };
  }, [sessionId, uf2Url, apiBase, apply]);

  if (status.kind === "no-client-id") {
    return (
      <div className="h-full w-full flex items-center justify-center p-6">
        <div className="max-w-md text-center">
          <p className="text-[12px] font-mono text-steel mb-2">
            Live visual simulator not configured.
          </p>
          <p className="text-[11px] font-mono text-steel/80 leading-relaxed">
            Set <code className="text-snow">NEXT_PUBLIC_WOKWI_EMBED_CLIENT_ID</code> in
            <code className="text-snow"> frontend/.env.local</code> with a Wokwi Embed client id
            (register one at the Wokwi CI dashboard) to enable the in-page visual sim.
          </p>
        </div>
      </div>
    );
  }

  if (status.kind === "no-build") {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <p className="text-[11px] font-mono text-steel">
          Live sim will appear here once the build completes.
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <iframe
        ref={iframeRef}
        title="Wokwi live simulator"
        src={`https://wokwi.com/experimental/embed?client_id=${encodeURIComponent(CLIENT_ID!)}`}
        className="h-full w-full"
        style={{ border: "0", background: "var(--color-abyss)" }}
        allow="serial; usb; clipboard-write"
      />
      {status.kind !== "running" && (
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
          style={{ background: "rgba(5,5,7,0.55)" }}
        >
          <p className="text-[11px] font-mono text-snow px-3 py-1.5 rounded-full"
             style={{ background: "var(--color-carbon)", border: "1px solid var(--color-charcoal)" }}>
            {status.kind === "loading" ? status.message : ""}
            {status.kind === "error" ? `Error: ${status.message}` : ""}
          </p>
        </div>
      )}
    </div>
  );
}