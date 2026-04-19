"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { ActivityItem } from "@/lib/store";

function StatusDot({ status }: { status: ActivityItem["status"] }) {
  if (status === "done") {
    return (
      <svg width={12} height={12} viewBox="0 0 12 12" aria-hidden>
        <circle cx={6} cy={6} r={5.5} fill="var(--color-accent)" />
        <path
          d="M3.4 6.2 L5.2 8 L8.7 4.5"
          fill="none"
          stroke="var(--color-abyss)"
          strokeWidth={1.4}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (status === "active") {
    return (
      <span
        className="inline-block w-3 h-3 rounded-full"
        style={{
          background: "var(--color-accent)",
          boxShadow: "0 0 6px var(--color-accent-tint)",
          animation: "siloPulse 1.1s ease-in-out infinite",
        }}
      />
    );
  }
  return (
    <span
      className="inline-block w-3 h-3 rounded-full border"
      style={{ borderColor: "var(--color-charcoal)" }}
    />
  );
}

interface Props {
  items: ActivityItem[];
}

export function AgentActivityList({ items }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll the list to the bottom whenever a new item is appended or an
  // existing item changes status — keeps the most recent activity in view as
  // the agent works.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // Two rAFs so layout from any item-add animation has a chance to settle
    // before we measure scrollHeight.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      });
    });
  }, [items.length, items.map((i) => i.status).join("|")]);

  if (items.length === 0) {
    return (
      <p className="text-[10px] font-mono text-steel m-0">Awaiting first action…</p>
    );
  }
  return (
    <div
      ref={scrollRef}
      className="h-full overflow-y-auto pr-1 silo-scroll"
    >
      <ul className="m-0 p-0 list-none flex flex-col gap-1.5">
        <AnimatePresence initial={false}>
          {items.map((item) => (
            <motion.li
              key={item.key}
              layout
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="flex items-start gap-2"
            >
              <span className="mt-0.5 shrink-0">
                <StatusDot status={item.status} />
              </span>
              <span
                className={
                  "text-[10.5px] font-mono leading-relaxed break-words " +
                  (item.status === "done"
                    ? "text-parchment"
                    : item.status === "active"
                      ? "text-snow"
                      : "text-steel")
                }
              >
                {item.label}
              </span>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  );
}