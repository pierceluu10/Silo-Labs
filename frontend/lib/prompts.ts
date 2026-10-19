/**
 * Locked on: every run replays the recorded DHT22 demo on RP2040 instead of
 * calling the live agents. The landing toggle shows this and cannot turn it off.
 */
export const DEMO_MODE = true;

export const WORKSPACE_PROMPT =
  "Read a DHT22 temperature and humidity sensor once per second and print the values over serial.";

export const EXAMPLE_PROMPTS = [
  "Read a DHT22 sensor once per second over serial",
  "Sweep a servo from 0 to 180 degrees",
  "Drive a WS2812 rainbow at 30 frames per second",
  "Sample ADC0 at 1 kHz and print filtered readings",
  "Read an MPU6050 and stream acceleration over UART",
] as const;
