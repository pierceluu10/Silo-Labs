"use client";

import { motion } from "framer-motion";

interface Props {
  bit: number;
  value: 0 | 1;
  affected: boolean;
}

export function BitCell({ bit, value, affected }: Props) {
  const fill = value === 1
    ? (affected ? "var(--color-accent)" : "var(--color-accent-light)")
    : "var(--color-charcoal)";
  const color = value === 1 ? "var(--color-abyss)" : "var(--color-steel)";

  return (
    <motion.div
      initial={false}
      animate={{ backgroundColor: fill }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="w-5 h-5 flex items-center justify-center text-[9px] font-mono rounded-sm"
      style={{ color }}
      title={`bit ${bit}`}
    >
      {value}
    </motion.div>
  );
}
