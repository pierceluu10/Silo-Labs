"use client";

import { useRef, useState, useCallback, useId } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";

const DEFAULT_PROMPT = "BME280 over I2C → SSD1306 OLED";

const PLACEHOLDER_PROMPT = "Describe the firmware you want on the RP2040…";

/** Expands on hover over the button to prompt + Run; click opens the field, then Run / Enter. */
export function PromptInput() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  /** Empty so placeholder disappears on hover/focus. */
  const [value, setValue] = useState("");
  const [inputFocus, setInputFocus] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const id = useId();
  const label = `${id}-firmware-prompt`;

  const go = useCallback(() => {
    const q = value.trim() || DEFAULT_PROMPT;
    router.push(`/workspace?${new URLSearchParams({ prompt: q })}`);
  }, [value, router]);

  const barVisible = open || inputFocus;

  const collapseIfUnfocused = () => {
    queueMicrotask(() => {
      if (inputRef.current !== document.activeElement) {
        setOpen(false);
      }
    });
  };

  return (
    <div className="flex w-full max-w-2xl min-w-0 justify-start">
      <div
        className={clsx(
          "flex min-w-0 items-stretch gap-2 sm:min-h-[3rem]",
          barVisible ? "w-full" : "w-auto",
        )}
        onMouseLeave={collapseIfUnfocused}
      >
        <AnimatePresence initial={false} mode="popLayout">
          {barVisible && (
            <motion.div
              key="input"
              className="min-h-0 min-w-0 flex-1"
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 6 }}
              transition={{ duration: 0.2 }}
            >
              <label htmlFor={label} className="sr-only">
                Firmware request
              </label>
              <input
                id={label}
                ref={inputRef}
                type="text"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onFocus={() => setInputFocus(true)}
                onBlur={() => setTimeout(() => setInputFocus(false), 120)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    go();
                  }
                }}
                placeholder={inputFocus ? undefined : PLACEHOLDER_PROMPT}
                autoComplete="off"
                className="h-full w-full min-w-0 rounded-md border px-4 py-3 text-sm text-snow outline-none transition-shadow placeholder:text-[var(--color-steel)]"
                style={{
                  background: "var(--color-abyss)",
                  borderColor: "var(--color-charcoal)",
                  fontFamily: "var(--font-sans)",
                }}
                onFocusCapture={(e) => {
                  e.currentTarget.style.borderColor = "var(--color-accent)";
                }}
                onBlurCapture={(e) => {
                  e.currentTarget.style.borderColor = "var(--color-charcoal)";
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>

        <div className="shrink-0 self-center">
          <motion.button
            type="button"
            onMouseEnter={() => setOpen(true)}
            onClick={() => {
              if (barVisible) {
                go();
                return;
              }
              setOpen(true);
              requestAnimationFrame(() => {
                requestAnimationFrame(() => inputRef.current?.focus());
              });
            }}
            className="inline-flex items-center justify-center gap-2 px-5 py-3 text-sm font-semibold tracking-wide"
            style={{
              background: barVisible ? "var(--color-accent)" : "var(--color-carbon)",
              color: barVisible ? "var(--color-abyss)" : "var(--color-accent-light)",
              border: `1px solid ${barVisible ? "var(--color-accent)" : "var(--color-charcoal)"}`,
              borderRadius: "6px",
              fontFamily: "var(--font-sans)",
            }}
          >
            <span
              style={{ color: barVisible ? "var(--color-abyss)" : "var(--color-accent)" }}
              aria-hidden
            >
              ›
            </span>
            <span
              className={clsx(
                barVisible
                  ? "text-[var(--color-abyss)]"
                  : "text-[var(--color-accent-light)]",
              )}
            >
              {barVisible ? "Run" : "Get started"}
            </span>
          </motion.button>
        </div>
      </div>
    </div>
  );
}
