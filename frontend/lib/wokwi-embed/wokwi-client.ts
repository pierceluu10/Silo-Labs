// SPDX-License-Identifier: MIT
// Adapted from https://github.com/wokwi/wokwi-embed-example (MIT, CodeMagic LTD).
// JSON-RPC-ish client for the Wokwi experimental embed simulation API.

import type { MessagePortTransport } from "./message-port-transport";
import { byteArrayToBase64 } from "./base64";

interface APIResponse {
  type: "response";
  id: string;
  result: Record<string, unknown>;
  error?: boolean;
}

interface APIEvent {
  type: "event";
  event: string;
  payload: unknown;
  nanos: number;
  paused: boolean;
}

interface APIHello {
  type: "hello";
  [k: string]: unknown;
}

type IncomingFrame = APIResponse | APIEvent | APIHello | { type: string; [k: string]: unknown };

interface PendingCommand {
  resolve: (value: Record<string, unknown>) => void;
  reject: (err: Error) => void;
}

export class WokwiClient extends EventTarget {
  private lastId = 0;
  private pendingCommands = new Map<string, PendingCommand>();

  constructor(private transport: MessagePortTransport) {
    super();
    this.transport.onMessage = (message) => this.processMessage(message as IncomingFrame);
  }

  private processMessage(message: IncomingFrame): void {
    if (message.type === "hello") {
      this.dispatchEvent(new CustomEvent("wokwi:connected", { detail: message }));
      return;
    }
    if (message.type === "response") {
      const r = message as APIResponse;
      const pending = this.pendingCommands.get(r.id);
      if (!pending) return;
      this.pendingCommands.delete(r.id);
      if (r.error) {
        const errMsg =
          (r.result && (r.result as { message?: string }).message) || "Wokwi command failed";
        pending.reject(new Error(errMsg));
      } else {
        pending.resolve(r.result);
      }
      return;
    }
    if (message.type === "event") {
      const e = message as APIEvent;
      this.dispatchEvent(
        new CustomEvent(e.event, { detail: { payload: e.payload, nanos: e.nanos, paused: e.paused } }),
      );
    }
  }

  private sendCommand(command: string, params: unknown = {}): Promise<Record<string, unknown>> {
    const id = `c${++this.lastId}`;
    return new Promise((resolve, reject) => {
      this.pendingCommands.set(id, { resolve, reject });
      this.transport.send({ type: "command", command, params, id });
    });
  }

  // ── File system ────────────────────────────────────────────────────────────
  async fileUpload(name: string, content: string | Uint8Array): Promise<void> {
    if (typeof content === "string") {
      await this.sendCommand("file:upload", { name, text: content });
    } else {
      await this.sendCommand("file:upload", {
        name,
        binary: byteArrayToBase64(content),
      });
    }
  }

  // ── Simulation lifecycle ───────────────────────────────────────────────────
  async simStart(opts: { firmware: string; elf?: string }): Promise<void> {
    await this.sendCommand("sim:start", opts);
  }

  async simPause(): Promise<void> {
    await this.sendCommand("sim:pause");
  }

  async simResume(): Promise<void> {
    await this.sendCommand("sim:resume");
  }

  async simRestart(): Promise<void> {
    await this.sendCommand("sim:restart");
  }

  async serialMonitorListen(): Promise<void> {
    await this.sendCommand("serial-monitor:listen");
  }
}