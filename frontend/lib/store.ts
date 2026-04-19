import { create } from "zustand";
import type { AgentName, FeatureSpec, NodeMetric, RunMetrics, SSEEvent } from "@/types/sse";

export interface PinEvent {
  pin_number: number;
  function: string;
  peripheral_instance: string;
  label: string;
  wire_color: string;
}

export interface ClockEvent {
  clock_domain: string;
  source: string;
  freq_hz: number;
  divider: number;
}

export interface RegisterEvent {
  peripheral: string;
  register: string;
  address: number;
  field_name: string;
  value: number;
  bit_offset: number;
  bit_width: number;
  human_explanation: string;
}

export interface WireEvent {
  from_component: string;
  from_pin: string;
  to_component: string;
  to_pin: string;
  color: string;
}

export interface ErrataEvent {
  errata_id: string;
  severity: "info" | "warning" | "critical";
  description: string;
  workaround: string | null;
}

export interface DevicePartInfo {
  device: string;
  wokwi_part: string;
  is_stub: boolean;
  note: string;
}

export interface ActivityItem {
  key: string;
  label: string;
  status: "pending" | "active" | "done";
  value?: string;
}

export interface GeneratedFile {
  path: string;
  content: string;
  language?: string | null;
}

export type FullscreenTarget = AgentName | "code" | null;

export interface RunPlanState {
  features: FeatureSpec[];
  rationale: string;
}

export interface SiloState {
  sessionId: string | null;
  activeAgent: AgentName | null;
  runPlan: RunPlanState | null;
  nodeMetrics: NodeMetric[];
  runMetrics: RunMetrics | null;
  agentReasoning: Record<AgentName, string>;
  activities: Record<AgentName, ActivityItem[]>;
  pins: PinEvent[];
  clocks: ClockEvent[];
  registers: RegisterEvent[];
  wires: WireEvent[];
  errata: ErrataEvent[];
  code: string;
  generatedFiles: GeneratedFile[];
  buildLog: string[];
  simulateLog: string[];
  uf2Url: string | null;
  devicePart: DevicePartInfo | null;
  pipelineComplete: boolean;
  errorMessage: string | null;
  fullscreen: FullscreenTarget;
  setFullscreen: (target: FullscreenTarget) => void;
  apply: (event: SSEEvent) => void;
  reset: () => void;
}

const emptyReasoning = (): Record<AgentName, string> => ({
  supervisor: "",
  requirements_parser: "",
  pinout_resolver: "",
  clock_configurator: "",
  peripheral_configurator: "",
  errata_checker: "",
  wokwi_diagram_generator: "",
  code_composer: "",
});

const emptyActivities = (): Record<AgentName, ActivityItem[]> => ({
  supervisor: [],
  requirements_parser: [],
  pinout_resolver: [],
  clock_configurator: [],
  peripheral_configurator: [],
  errata_checker: [],
  wokwi_diagram_generator: [],
  code_composer: [],
});

const initial = () => ({
  sessionId: null as string | null,
  activeAgent: null as AgentName | null,
  agentReasoning: emptyReasoning(),
  activities: emptyActivities(),
  pins: [] as PinEvent[],
  clocks: [] as ClockEvent[],
  registers: [] as RegisterEvent[],
  wires: [] as WireEvent[],
  errata: [] as ErrataEvent[],
  code: "",
  generatedFiles: [] as GeneratedFile[],
  buildLog: [] as string[],
  simulateLog: [] as string[],
  uf2Url: null as string | null,
  devicePart: null as DevicePartInfo | null,
  pipelineComplete: false,
  errorMessage: null as string | null,
  fullscreen: null as FullscreenTarget,
  runPlan: null as RunPlanState | null,
  nodeMetrics: [] as NodeMetric[],
  runMetrics: null as RunMetrics | null,
});

export const useSiloStore = create<SiloState>((set) => ({
  ...initial(),
  reset: () => set(initial()),
  setFullscreen: (target) => set({ fullscreen: target }),
  apply: (event) =>
    set((state) => {
      switch (event.type) {
        case "session_ready":
          return { sessionId: event.session_id };
        case "agent_start":
          return { activeAgent: event.agent };
        case "agent_complete":
          return { activeAgent: null };
        case "agent_reasoning": {
          const prev = state.agentReasoning[event.agent] ?? "";
          return {
            agentReasoning: { ...state.agentReasoning, [event.agent]: prev + event.delta },
          };
        }
        case "agent_activity": {
          const prev = state.activities[event.agent] ?? [];
          const idx = prev.findIndex((a) => a.key === event.key);
          const next: ActivityItem = {
            key: event.key,
            label: event.label,
            status: event.status,
            value: event.value,
          };
          const updated = idx >= 0 ? prev.map((a, i) => (i === idx ? next : a)) : [...prev, next];
          return {
            activities: { ...state.activities, [event.agent]: updated },
          };
        }
        case "assign_pin":
          return { pins: [...state.pins, { ...event }] };
        case "configure_clock":
          return { clocks: [...state.clocks, { ...event }] };
        case "set_register":
          return { registers: [...state.registers, { ...event }] };
        case "add_wire":
          return { wires: [...state.wires, { ...event }] };
        case "errata_warning":
          return {
            errata: [
              ...state.errata,
              {
                errata_id: event.errata_id,
                severity: event.severity,
                description: event.description,
                workaround: event.workaround,
              },
            ],
          };
        case "code_chunk":
          return { code: state.code + event.delta };
        case "code_complete":
          return { code: event.full_code };
        case "generated_files":
          return {
            generatedFiles: event.files.map((f) => ({
              path: f.path,
              content: f.content,
              language: f.language ?? null,
            })),
          };
        case "build_log":
          return { buildLog: [...state.buildLog, event.line] };
        case "build_success":
          return { uf2Url: event.uf2_url };
        case "build_failure":
          return { errorMessage: event.error };
        case "simulate_output":
          return { simulateLog: [...state.simulateLog, event.line] };
        case "device_part_info":
          return {
            devicePart: {
              device: event.device,
              wokwi_part: event.wokwi_part,
              is_stub: event.is_stub,
              note: event.note,
            },
          };
        case "run_plan":
          return {
            runPlan: { features: event.features, rationale: event.rationale },
          };
        case "metrics_update":
          return { nodeMetrics: [...state.nodeMetrics, event.node] };
        case "metrics_summary":
          return {
            runMetrics: event.metrics,
            nodeMetrics: event.metrics.nodes,
          };
        case "pipeline_complete":
          return { pipelineComplete: true };
        case "error":
          return { errorMessage: event.message };
        default:
          return {};
      }
    }),
}));
