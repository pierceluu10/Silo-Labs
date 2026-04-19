// SPDX-License-Identifier: MIT
// Adapted from https://github.com/wokwi/wokwi-embed-example (MIT, CodeMagic LTD).

export type IncomingMessage = unknown;

export class MessagePortTransport {
  onMessage: (msg: IncomingMessage) => void;

  constructor(private port: MessagePort) {
    this.onMessage = () => {};
    this.port.onmessage = (event) => {
      this.onMessage(event.data);
    };
    this.port.start();
  }

  send(message: unknown): void {
    this.port.postMessage(message);
  }
}