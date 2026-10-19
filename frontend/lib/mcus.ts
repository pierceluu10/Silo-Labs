import { getApiBase } from "@/lib/sse";

/** Target used when none is chosen; the canned DHT22 demo replays only on this MCU. */
export const DEFAULT_MCU = "rp2040";

export interface McuOption {
  name: string;
  display_name: string;
  board_name: string;
  sdk: string;
  peripheral_families: string[];
  buildable: boolean;
}

export async function fetchMcus(signal: AbortSignal): Promise<McuOption[]> {
  const response = await fetch(`${getApiBase()}/api/mcus`, { signal });
  if (!response.ok) throw new Error(`GET /api/mcus failed: ${response.status}`);
  return (await response.json()) as McuOption[];
}
