"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

const EXAMPLES = [
  "BME280 over I2C → SSD1306 OLED",
  "Servo sweep controlled over UART",
  "WS2812 rainbow at 30fps, brightness control",
  "ADC0 at 1kHz, filtered readings over UART",
];

const TYPE_MS = 95;
const ERASE_MS = 45;
const HOLD_MS = 2600;
const PAUSE_MS = 700;

export function PromptDemo() {
  const [text, setText] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let idx = 0;
    let charIdx = 0;
    let mode: "typing" | "holding" | "erasing" = "typing";

    const tick = () => {
      if (cancelled) return;
      const current = EXAMPLES[idx];
      if (mode === "typing") {
        charIdx += 1;
        setText(current.slice(0, charIdx));
        if (charIdx >= current.length) {
          mode = "holding";
          timeout = setTimeout(tick, HOLD_MS);
        } else {
          timeout = setTimeout(tick, TYPE_MS);
        }
      } else if (mode === "holding") {
        mode = "erasing";
        timeout = setTimeout(tick, ERASE_MS);
      } else {
        charIdx -= 1;
        setText(current.slice(0, Math.max(0, charIdx)));
        if (charIdx <= 0) {
          idx = (idx + 1) % EXAMPLES.length;
          mode = "typing";
          timeout = setTimeout(tick, PAUSE_MS);
        } else {
          timeout = setTimeout(tick, ERASE_MS);
        }
      }
    };

    timeout = setTimeout(tick, 120);
    return () => {
      cancelled = true;
      if (timeout) clearTimeout(timeout);
    };
  }, []);

  return (
    <div
      className="inline-flex max-w-[min(100%,36rem)] rounded-md px-4 py-3 items-center gap-3"
      style={{
        background: "rgba(16, 16, 16, 0.9)",
        border: "1px solid var(--color-charcoal)",
        backdropFilter: "blur(6px)",
        fontFamily: "var(--font-mono)",
        fontSize: "13px",
      }}
    >
      <motion.div
        className="inline-flex min-w-0 items-center gap-3"
        initial={{ opacity: 0, y: 6, filter: "blur(4px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
      >
        <span className="shrink-0" style={{ color: "var(--color-accent-light)" }}>
          $
        </span>
        <span className="text-snow whitespace-pre">{text}</span>
        <span
          aria-hidden
          className="inline-block w-[7px] h-[14px] shrink-0"
          style={{
            background: "var(--color-accent-light)",
            animation: "silo-caret 1.1s steps(2) infinite",
          }}
        />
      </motion.div>
      <style jsx>{`
        @keyframes silo-caret {
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
