import type { SSEEvent, SSEEventType } from "@/types/sse";

export function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
}

const API_BASE = getApiBase();

const EVENT_TYPES: readonly SSEEventType[] = [
  "session_ready",
  "agent_start",
  "agent_reasoning",
  "agent_complete",
  "agent_activity",
  "assign_pin",
  "configure_clock",
  "set_register",
  "add_wire",
  "errata_warning",
  "code_chunk",
  "code_complete",
  "generated_files",
  "build_start",
  "build_log",
  "build_success",
  "build_failure",
  "simulate_start",
  "simulate_output",
  "device_part_info",
  "run_plan",
  "metrics_update",
  "metrics_summary",
  "pipeline_complete",
  "error",
] as const;

export type SSEHandler = (event: SSEEvent) => void;

export function openPipelineStream(prompt: string, onEvent: SSEHandler, sessionId?: string): EventSource {
  const params = new URLSearchParams({ prompt });
  if (sessionId) params.set("session_id", sessionId);
  const url = `${API_BASE}/api/stream?${params.toString()}`;
  const source = new EventSource(url);

  for (const type of EVENT_TYPES) {
    source.addEventListener(type, (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data) as SSEEvent;
        onEvent(data);
      } catch {
        // malformed payload — drop
      }
    });
  }

  source.onerror = () => {
    source.close();
  };

  return source;
}
