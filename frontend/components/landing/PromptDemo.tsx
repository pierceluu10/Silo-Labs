"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { EXAMPLE_PROMPTS } from "@/lib/prompts";

const TYPE_INTERVAL_MS = 72;
const ERASE_INTERVAL_MS = 34;
const HOLD_INTERVAL_MS = 2200;
const NEXT_PROMPT_DELAY_MS = 420;
const REVEAL_DELAY_SECONDS = 0.65;
const REVEAL_DURATION_SECONDS = 0.55;

export function PromptDemo() {
  const [text, setText] = useState("");
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (reduceMotion) {
      setText(EXAMPLE_PROMPTS[0]);
      return;
    }

    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout>;
    let promptIndex = Math.floor(Math.random() * EXAMPLE_PROMPTS.length);
    let characterIndex = 0;
    let mode: "typing" | "holding" | "erasing" = "typing";

    const tick = () => {
      if (cancelled) return;
      const prompt = EXAMPLE_PROMPTS[promptIndex];

      if (mode === "typing") {
        characterIndex += 1;
        setText(prompt.slice(0, characterIndex));
        if (characterIndex >= prompt.length) {
          mode = "holding";
          timeout = setTimeout(tick, HOLD_INTERVAL_MS);
        } else {
          timeout = setTimeout(tick, TYPE_INTERVAL_MS);
        }
        return;
      }

      if (mode === "holding") {
        mode = "erasing";
        timeout = setTimeout(tick, ERASE_INTERVAL_MS);
        return;
      }

      characterIndex -= 1;
      setText(prompt.slice(0, Math.max(0, characterIndex)));
      if (characterIndex <= 0) {
        promptIndex = (promptIndex + 1) % EXAMPLE_PROMPTS.length;
        mode = "typing";
        timeout = setTimeout(tick, NEXT_PROMPT_DELAY_MS);
      } else {
        timeout = setTimeout(tick, ERASE_INTERVAL_MS);
      }
    };

    timeout = setTimeout(tick, 160);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [reduceMotion]);

  return (
    <motion.div
      className="prompt-demo"
      aria-label="Example firmware prompt"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{
        delay: reduceMotion ? 0 : REVEAL_DELAY_SECONDS,
        duration: reduceMotion ? 0.2 : REVEAL_DURATION_SECONDS,
        ease: [0.23, 1, 0.32, 1],
      }}
    >
      <div className="prompt-demo__line">
        <span className="prompt-demo__symbol">$</span>
        <span className="prompt-demo__text">{text}</span>
        <span aria-hidden className="prompt-demo__caret" />
      </div>
    </motion.div>
  );
}
