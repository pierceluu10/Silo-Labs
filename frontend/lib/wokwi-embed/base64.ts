// SPDX-License-Identifier: MIT
// Adapted from https://github.com/wokwi/wokwi-embed-example (MIT, CodeMagic LTD).
// Tiny helpers to convert between binary firmware blobs and base64 strings.

export function byteArrayToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  // btoa is browser-only; keep this file in client modules.
  return btoa(binary);
}

export function base64ToByteArray(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}