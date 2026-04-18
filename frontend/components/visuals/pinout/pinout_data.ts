export interface PinLayout {
  index: number;
  side: "left" | "right";
  row: number;
  label: string;
  gpio: number | null;
}

const LEFT: (string)[] = [
  "GP0","GP1","GND","GP2","GP3","GP4","GP5","GND","GP6","GP7",
  "GP8","GP9","GND","GP10","GP11","GP12","GP13","GND","GP14","GP15",
];
const RIGHT: (string)[] = [
  "VBUS","VSYS","GND","3V3_EN","3V3_OUT","ADC_VREF","GP28","GND","GP27","GP26",
  "RUN","GP22","GND","GP21","GP20","GP19","GP18","GND","GP17","GP16",
];

function toLayout(labels: string[], side: "left" | "right", offset: number): PinLayout[] {
  return labels.map((label, i) => ({
    index: offset + i + 1,
    side,
    row: i,
    label,
    gpio: label.startsWith("GP") ? Number(label.slice(2)) : null,
  }));
}

export const PIN_LAYOUT: PinLayout[] = [
  ...toLayout(LEFT, "left", 0),
  ...toLayout(RIGHT, "right", 20),
];

export const BOARD_WIDTH = 260;
export const BOARD_HEIGHT = 520;
export const ROW_PITCH = 24;
export const TOP_MARGIN = 28;
