"use client";

import { Drop, ThermometerSimple } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo } from "react";
import { useSiloStore } from "@/lib/store";

const READING_PATTERN = /(?:temp(?:erature)?[=: ]+)(-?\d+(?:\.\d+)?)\s*(?:°?c)?[^\d]+(?:humidity[=: ]+)(\d+(?:\.\d+)?)\s*%?/i;

function readLatestMeasurement(lines: string[]) {
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const match = lines[index].match(READING_PATTERN);
    if (match) {
      return { temperature: Number(match[1]), humidity: Number(match[2]), line: lines[index] };
    }
  }
  return null;
}

export function Dht22Simulation() {
  const lines = useSiloStore((state) => state.simulateLog);
  const pipelineComplete = useSiloStore((state) => state.pipelineComplete);
  const measurement = useMemo(() => readLatestMeasurement(lines), [lines]);
  const reduceMotion = useReducedMotion();

  return (
    <div className="sensor-simulation">
      <div className="sensor-simulation__scene">
        <div className="sensor-module" aria-label="DHT22 sensor module">
          <div className="sensor-module__vents">
            {Array.from({ length: 18 }, (_, index) => <span key={index} />)}
          </div>
          <strong>DHT22</strong>
          <small>Digital temperature and humidity</small>
          <div className="sensor-module__pins"><span>VCC</span><span>DATA</span><span>GND</span></div>
        </div>
        <motion.div
          className="sensor-simulation__signal"
          animate={reduceMotion || !measurement ? undefined : { scaleX: [0.94, 1, 0.94] }}
          transition={{ duration: 1, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <div className="sensor-readings" aria-live="polite">
        <div className="sensor-reading">
          <ThermometerSimple size={20} weight="duotone" />
          <span>Temperature</span>
          <strong>{measurement ? `${measurement.temperature.toFixed(1)} °C` : "--.- °C"}</strong>
        </div>
        <div className="sensor-reading">
          <Drop size={20} weight="duotone" />
          <span>Humidity</span>
          <strong>{measurement ? `${measurement.humidity.toFixed(1)} %` : "--.- %"}</strong>
        </div>
      </div>

      <div className="sensor-simulation__serial">
        <span>{measurement ? "SERIAL / 115200" : "WAITING FOR FIRMWARE"}</span>
        <code>{measurement?.line ?? "DHT22 readings will stream here once the build completes."}</code>
        <span>{pipelineComplete ? "Simulation complete" : measurement ? "Sampling every 1.0s" : "Preparing circuit"}</span>
      </div>
    </div>
  );
}

