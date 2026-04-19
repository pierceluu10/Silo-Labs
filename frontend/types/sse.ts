export type Panel = "top-left" | "top-right" | "bottom-left" | "bottom-right";

export type AgentName =
  | "requirements_parser"
  | "pinout_resolver"
  | "clock_configurator"
  | "peripheral_configurator"
  | "errata_checker"
  | "wokwi_diagram_generator"
  | "code_composer";

export type SSEEvent =
  | { type: "session_ready"; session_id: string }
  | { type: "agent_start"; agent: AgentName; timestamp: number }
  | { type: "agent_reasoning"; agent: AgentName; panel: Panel; delta: string }
  | { type: "agent_complete"; agent: AgentName; duration_ms: number }
  | {
      type: "agent_activity";
      agent: AgentName;
      key: string;
      label: string;
      status: "pending" | "active" | "done";
      value?: string;
    }
  | {
      type: "assign_pin";
      pin_number: number;
      function: string;
      peripheral_instance: string;
      label: string;
      wire_color: string;
    }
  | {
      type: "configure_clock";
      clock_domain: string;
      source: string;
      freq_hz: number;
      divider: number;
    }
  | {
      type: "set_register";
      peripheral: string;
      register: string;
      address: number;
      field_name: string;
      value: number;
      bit_offset: number;
      bit_width: number;
      human_explanation: string;
    }
  | {
      type: "add_wire";
      from_component: string;
      from_pin: string;
      to_component: string;
      to_pin: string;
      color: string;
    }
  | {
      type: "errata_warning";
      errata_id: string;
      severity: "info" | "warning" | "critical";
      description: string;
      workaround: string | null;
    }
  | { type: "code_chunk"; delta: string }
  | { type: "code_complete"; full_code: string }
  | {
      type: "generated_files";
      files: { path: string; content: string; language?: string | null }[];
    }
  | { type: "build_start" }
  | { type: "build_log"; line: string }
  | { type: "build_success"; uf2_url: string }
  | { type: "build_failure"; error: string; stderr: string }
  | { type: "simulate_start" }
  | { type: "simulate_output"; line: string }
  | {
      type: "device_part_info";
      device: string;
      wokwi_part: string;
      is_stub: boolean;
      note: string;
    }
  | { type: "pipeline_complete"; session_id: string; duration_ms: number }
  | { type: "error"; message: string; recoverable: boolean };

export type SSEEventType = SSEEvent["type"];
