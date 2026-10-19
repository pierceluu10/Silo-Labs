"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, LockSimple } from "@phosphor-icons/react";
import { AnimatePresence, motion, useAnimationControls, useReducedMotion } from "framer-motion";
import clsx from "clsx";
import { DEMO_MODE, WORKSPACE_PROMPT } from "@/lib/prompts";
import { DEFAULT_MCU, fetchMcus, type McuOption } from "@/lib/mcus";

const PLACEHOLDER = "Describe the firmware you want...";
// Thumb travel (px) for the "locked" nudge when someone tries to switch demo mode off.
const LOCKED_NUDGE_PX = [0, -5, 2, 0];

export function PromptInput() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const mcuId = useId();
  const demoNoteId = useId();
  const thumbControls = useAnimationControls();
  const reduceMotion = useReducedMotion();
  const [isOpen, setIsOpen] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [value, setValue] = useState(DEMO_MODE ? WORKSPACE_PROMPT : "");
  const [mcus, setMcus] = useState<McuOption[]>([]);
  const [mcu, setMcu] = useState(DEFAULT_MCU);
  const isExpanded = isOpen || isFocused;

  useEffect(() => {
    if (DEMO_MODE) return;
    const controller = new AbortController();
    fetchMcus(controller.signal)
      .then(setMcus)
      .catch((error: unknown) => {
        // Backend offline: the picker stays hidden and runs default to RP2040.
        if (!controller.signal.aborted) console.warn(error);
      });
    return () => controller.abort();
  }, []);

  const run = useCallback(() => {
    const params = DEMO_MODE
      ? { prompt: WORKSPACE_PROMPT, mcu: DEFAULT_MCU }
      : { prompt: value.trim() || WORKSPACE_PROMPT, mcu };
    router.push(`/workspace?${new URLSearchParams(params)}`);
  }, [router, value, mcu]);

  const nudgeLockedSwitch = () => {
    if (reduceMotion) return;
    void thumbControls.start({
      x: LOCKED_NUDGE_PX,
      transition: { duration: 0.32, ease: [0.23, 1, 0.32, 1] },
    });
  };

  const openInput = () => {
    setIsOpen(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const closeHoverPreview = () => {
    setIsOpen(false);
  };

  return (
    <div className="prompt-panel">
      <div className="prompt-input" onMouseLeave={closeHoverPreview}>
        <AnimatePresence initial={false} mode="popLayout">
          {isExpanded && (
            <motion.div
              key="prompt-field"
              className="prompt-input__field"
              initial={reduceMotion ? { opacity: 0 } : { opacity: 0, transform: "translate3d(12px, 0, 0)" }}
              animate={{ opacity: 1, transform: "translate3d(0, 0, 0)" }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, transform: "translate3d(8px, 0, 0)" }}
              transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
            >
              <label className="sr-only" htmlFor={inputId}>Firmware request</label>
              <input
                ref={inputRef}
                id={inputId}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                readOnly={DEMO_MODE}
                aria-describedby={DEMO_MODE ? demoNoteId : undefined}
                onFocus={() => setIsFocused(true)}
                onBlur={() => {
                  setIsFocused(false);
                  setIsOpen(false);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    run();
                  }
                  if (event.key === "Escape") {
                    inputRef.current?.blur();
                    setIsOpen(false);
                  }
                }}
                placeholder={PLACEHOLDER}
                autoComplete="off"
              />
            </motion.div>
          )}
        </AnimatePresence>

        {!DEMO_MODE && mcus.length > 0 && (
          <div className="prompt-input__mcu">
            <label className="sr-only" htmlFor={mcuId}>Target MCU</label>
            <select id={mcuId} value={mcu} onChange={(event) => setMcu(event.target.value)}>
              {mcus.map((option) => (
                <option key={option.name} value={option.name}>
                  {option.display_name}
                  {option.buildable ? "" : " (code only)"}
                </option>
              ))}
            </select>
          </div>
        )}

        <motion.button
          type="button"
          className={clsx("prompt-input__button", isExpanded && "prompt-input__button--active")}
          onMouseEnter={() => setIsOpen(true)}
          onClick={isExpanded ? run : openInput}
          whileTap={{ scale: 0.97 }}
        >
          <span>{isExpanded ? "Run" : "Get Started"}</span>
          <ArrowRight size={16} weight="bold" />
        </motion.button>
      </div>

      {DEMO_MODE && (
        <div className="demo-mode">
          <button
            type="button"
            role="switch"
            aria-checked="true"
            aria-disabled="true"
            aria-label="Demo mode"
            aria-describedby={demoNoteId}
            className="demo-mode__switch"
            onClick={nudgeLockedSwitch}
          >
            <motion.span className="demo-mode__thumb" animate={thumbControls}>
              <LockSimple size={9} weight="bold" aria-hidden />
            </motion.span>
          </button>
          <span className="demo-mode__label" aria-hidden>
            Demo mode
          </span>
          <span id={demoNoteId} className="demo-mode__note">
            Replays a recorded DHT22 run on RP2040. Locked on.
          </span>
        </div>
      )}
    </div>
  );
}
