"use client";

import { motion } from "framer-motion";
import type { PinLayout } from "./pinout_data";
import { ROW_PITCH, TOP_MARGIN, BOARD_WIDTH } from "./pinout_data";
import type { PinEvent } from "@/lib/store";

interface Props {
  layout: PinLayout;
  assignment?: PinEvent;
}

export function Pin({ layout, assignment }: Props) {
  const x = layout.side === "left" ? 4 : BOARD_WIDTH - 52;
  const y = TOP_MARGIN + layout.row * ROW_PITCH;
  const active = !!assignment;
  const fill = active ? "var(--color-accent)" : "var(--color-charcoal)";
  const labelColor = active ? "var(--color-accent-light)" : "var(--color-steel)";
  const textX = layout.side === "left" ? 56 : BOARD_WIDTH - 56;
  const textAnchor = layout.side === "left" ? "start" : "end";
  const displayLabel = assignment ? `${layout.label} · ${assignment.label}` : layout.label;

  return (
    <g>
      <motion.rect
        x={x}
        y={y}
        width={48}
        height={ROW_PITCH - 6}
        rx={3}
        animate={{ fill }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        style={{
          filter: active ? "drop-shadow(0 0 6px var(--color-accent))" : "none",
        }}
      />
      <text
        x={textX}
        y={y + ROW_PITCH / 2 - 1}
        fontSize={10}
        textAnchor={textAnchor}
        dominantBaseline="middle"
        fill={labelColor}
        fontFamily="var(--font-mono)"
      >
        {displayLabel}
      </text>
    </g>
  );
}
