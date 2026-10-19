"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { DEFAULT_BOARD_PART, useSiloStore } from "@/lib/store";
import type { WireEvent } from "@/lib/store";

// SVG canvas. Tall enough to fit a stack of labeled pin tabs.
const VIEW_W = 360;
const VIEW_H = 320;

// MCU board geometry — left of the canvas. Pin tabs come out of its right edge.
const BOARD = { x: 38, y: 38, w: 110, h: 244, rx: 8 };
// Device body — right side of the canvas. Pin tabs come out of its left edge.
const DEVICE = { x: 230, y: 78, w: 96, h: 168, rx: 6 };

const TAB_W = 18;
const TAB_H = 14;

interface PinAnchor {
  /** SVG x of the wire endpoint (the tip of the tab). */
  x: number;
  /** SVG y of the wire endpoint. */
  y: number;
  /** Label drawn inside / next to the tab. */
  label: string;
}

const POWER_PINS = new Set(["3V3", "5V", "VBUS", "VSYS", "VIN"]);

/** Power first, ground last; signal pins (GP4, PB7, 21) in natural order between. */
function compareBoardPins(a: string, b: string): number {
  const rank = (p: string) => (POWER_PINS.has(p) ? 0 : p.startsWith("GND") ? 2 : 1);
  return rank(a) - rank(b) || a.localeCompare(b, undefined, { numeric: true });
}

function deviceSortKey(p: string): number {
  // VCC up top, GND at the bottom, signals in between.
  const order = ["VCC", "VIN", "VDD", "SDA", "SCL", "TX", "RX", "DQ", "INT", "CSn", "GND"];
  const i = order.indexOf(p);
  return i === -1 ? 100 : i;
}

function buildAnchors(wires: WireEvent[], boardId: string): {
  board: Map<string, PinAnchor>;
  device: Map<string, PinAnchor>;
} {
  const boardPins = Array.from(
    new Set(
      wires
        .map((w) => (w.from_component === boardId ? w.from_pin : w.to_component === boardId ? w.to_pin : null))
        .filter((p): p is string => p !== null),
    ),
  ).sort(compareBoardPins);

  const devicePins = Array.from(
    new Set(
      wires
        .map((w) => (w.from_component !== boardId ? w.from_pin : w.to_component !== boardId ? w.to_pin : null))
        .filter((p): p is string => p !== null),
    ),
  ).sort((a, b) => deviceSortKey(a) - deviceSortKey(b));

  const board = new Map<string, PinAnchor>();
  const boardStep = (BOARD.h - 32) / Math.max(1, boardPins.length - 1 || 1);
  boardPins.forEach((pin, i) => {
    const y = BOARD.y + 16 + (boardPins.length === 1 ? BOARD.h / 2 - 16 : i * boardStep);
    board.set(pin, { x: BOARD.x + BOARD.w + TAB_W, y, label: pin });
  });

  const device = new Map<string, PinAnchor>();
  const devStep = (DEVICE.h - 24) / Math.max(1, devicePins.length - 1 || 1);
  devicePins.forEach((pin, i) => {
    const y = DEVICE.y + 12 + (devicePins.length === 1 ? DEVICE.h / 2 - 12 : i * devStep);
    device.set(pin, { x: DEVICE.x - TAB_W, y, label: pin });
  });

  return { board, device };
}

function wireEndpoints(
  wire: WireEvent,
  anchors: ReturnType<typeof buildAnchors>,
  boardId: string,
): { from: PinAnchor; to: PinAnchor } | null {
  const fromMap = wire.from_component === boardId ? anchors.board : anchors.device;
  const toMap = wire.to_component === boardId ? anchors.board : anchors.device;
  const from = fromMap.get(wire.from_pin);
  const to = toMap.get(wire.to_pin);
  if (!from || !to) return null;
  return { from, to };
}

/** S-curve between two anchors, biased so curves of nearby pins don't overlap. */
function curvedPath(from: PinAnchor, to: PinAnchor, idx: number): string {
  const dx = to.x - from.x;
  const cx1 = from.x + dx * 0.45 + (idx % 2 === 0 ? 4 : -4);
  const cx2 = to.x - dx * 0.45 + (idx % 2 === 0 ? -4 : 4);
  return `M ${from.x} ${from.y} C ${cx1} ${from.y}, ${cx2} ${to.y}, ${to.x} ${to.y}`;
}

export function BreadboardView() {
  const wires = useSiloStore((s) => s.wires);
  const target = useSiloStore((s) => s.target);
  const boardId = target?.boardPart ?? DEFAULT_BOARD_PART;
  const [hovered, setHovered] = useState<number | null>(null);

  const anchors = useMemo(() => buildAnchors(wires, boardId), [wires, boardId]);

  return (
    <div className="relative w-full h-full">
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="w-full h-full">
        {/* MCU board body */}
        <rect
          x={BOARD.x}
          y={BOARD.y}
          width={BOARD.w}
          height={BOARD.h}
          rx={BOARD.rx}
          fill="var(--color-carbon)"
          stroke="var(--color-charcoal)"
        />
        <text
          x={BOARD.x + BOARD.w / 2}
          y={BOARD.y + 16}
          textAnchor="middle"
          fontSize={9}
          fill="var(--color-steel)"
          fontFamily="var(--font-mono)"
        >
          {target?.boardName ?? "Pi Pico"}
        </text>

        {/* Device body */}
        <rect
          x={DEVICE.x}
          y={DEVICE.y}
          width={DEVICE.w}
          height={DEVICE.h}
          rx={DEVICE.rx}
          fill="var(--color-carbon)"
          stroke="var(--color-charcoal)"
        />
        <text
          x={DEVICE.x + DEVICE.w / 2}
          y={DEVICE.y + 14}
          textAnchor="middle"
          fontSize={9}
          fill="var(--color-steel)"
          fontFamily="var(--font-mono)"
        >
          device
        </text>

        {/* Board pin tabs (right edge of the board) */}
        {Array.from(anchors.board.values()).map((p) => (
          <g key={`board-${p.label}`}>
            <rect
              x={BOARD.x + BOARD.w}
              y={p.y - TAB_H / 2}
              width={TAB_W}
              height={TAB_H}
              rx={2}
              fill="var(--color-carbon)"
              stroke="var(--color-charcoal)"
            />
            <text
              x={BOARD.x + BOARD.w + TAB_W / 2}
              y={p.y + 3}
              textAnchor="middle"
              fontSize={7}
              fill="var(--color-parchment)"
              fontFamily="var(--font-mono)"
            >
              {p.label}
            </text>
          </g>
        ))}

        {/* Device pin tabs (left edge of device) */}
        {Array.from(anchors.device.values()).map((p) => (
          <g key={`dev-${p.label}`}>
            <rect
              x={DEVICE.x - TAB_W}
              y={p.y - TAB_H / 2}
              width={TAB_W}
              height={TAB_H}
              rx={2}
              fill="var(--color-carbon)"
              stroke="var(--color-charcoal)"
            />
            <text
              x={DEVICE.x - TAB_W / 2}
              y={p.y + 3}
              textAnchor="middle"
              fontSize={7}
              fill="var(--color-parchment)"
              fontFamily="var(--font-mono)"
            >
              {p.label}
            </text>
          </g>
        ))}

        {/* Wires */}
        {wires.map((w, i) => {
          const ep = wireEndpoints(w, anchors, boardId);
          if (!ep) return null;
          const isHovered = hovered === i;
          const dim = hovered !== null && !isHovered;
          const d = curvedPath(ep.from, ep.to, i);
          return (
            <motion.path
              key={`wire-${i}-${w.from_pin}-${w.to_pin}`}
              d={d}
              fill="none"
              stroke={w.color}
              strokeWidth={isHovered ? 2.6 : 1.8}
              strokeLinecap="round"
              opacity={dim ? 0.25 : 1}
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: "pointer", filter: isHovered ? "drop-shadow(0 0 4px " + w.color + ")" : "none" }}
            />
          );
        })}

        {/* Hovered wire midpoint label */}
        {hovered !== null &&
          (() => {
            const w = wires[hovered];
            if (!w) return null;
            const ep = wireEndpoints(w, anchors, boardId);
            if (!ep) return null;
            const mx = (ep.from.x + ep.to.x) / 2;
            const my = (ep.from.y + ep.to.y) / 2 - 10;
            const label = `${w.from_component}:${w.from_pin} → ${w.to_component}:${w.to_pin}`;
            const labelW = label.length * 4.6 + 12;
            return (
              <g pointerEvents="none">
                <rect
                  x={mx - labelW / 2}
                  y={my - 8}
                  width={labelW}
                  height={14}
                  rx={4}
                  fill="var(--color-abyss)"
                  stroke={w.color}
                  strokeWidth={0.8}
                  opacity={0.95}
                />
                <text
                  x={mx}
                  y={my + 2}
                  textAnchor="middle"
                  fontSize={7.5}
                  fill="var(--color-snow)"
                  fontFamily="var(--font-mono)"
                >
                  {label}
                </text>
              </g>
            );
          })()}
      </svg>

      {wires.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <p className="text-[10px] font-mono text-steel m-0">Wiring will appear here…</p>
        </div>
      )}
    </div>
  );
}