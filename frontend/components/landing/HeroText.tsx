"use client";

import Image from "next/image";
import { motion, type Variants } from "framer-motion";
import { PromptInput } from "./PromptInput";

const HIGHLIGHT = "#f0808a";

const container: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.12, delayChildren: 0.1 },
  },
};

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14, filter: "blur(6px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.7, ease: [0.2, 0.8, 0.2, 1] },
  },
};

const highlight: Variants = {
  hidden: { opacity: 0, y: 16, filter: "blur(10px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { delay: 0.45, duration: 0.9, ease: [0.2, 0.8, 0.2, 1] },
  },
};

export function HeroText() {
  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="visible"
      className="max-w-xl mx-auto lg:mx-0 lg:pl-12 text-center lg:text-left space-y-6"
    >
      <motion.div
        variants={fadeUp}
        className="flex items-center justify-center lg:justify-start lg:-ml-6 lg:-mb-4"
      >
        <span className="relative inline-flex items-center justify-center">
          {/* Visible red glow behind the chip mark. */}
          <span
            aria-hidden
            className="absolute inset-0 -z-10 rounded-full"
            style={{
              background:
                "radial-gradient(closest-side, rgba(230,57,70,0.55) 0%, rgba(230,57,70,0.18) 45%, transparent 70%)",
              filter: "blur(28px)",
              transform: "scale(1.35)",
            }}
          />
          <Image
            src="/transparentlogo.png"
            alt="Silo Labs mark"
            width={192}
            height={192}
            priority
            className="relative h-24 w-auto sm:h-28"
          />
        </span>
        <span
          className="-ml-2 mt-1 sm:mt-2 text-xs uppercase text-steel font-semibold sm:-ml-3"
          style={{ letterSpacing: "2.52px" }}
        >
          Silo Labs
        </span>
      </motion.div>
      <motion.h1
        variants={fadeUp}
        className="text-6xl font-normal text-snow"
        style={{
          fontFamily: "var(--font-display)",
          lineHeight: 1.0,
          letterSpacing: "-0.65px",
        }}
      >
        Natural language to{" "}
        <motion.span
          variants={highlight}
          className="hatched-accent inline-block"
          data-text="RP2040 firmware"
        >
          RP2040 firmware
        </motion.span>
      </motion.h1>
      <motion.p
        variants={fadeUp}
        className="text-base leading-relaxed"
        style={{ color: "var(--color-snow)" }}
      >
        A multi-agent pipeline —{" "}
        <span style={{ color: HIGHLIGHT }}>pin routing</span>,{" "}
        <span style={{ color: HIGHLIGHT }}>clock trees</span>,{" "}
        <span style={{ color: HIGHLIGHT }}>register writes</span>, and{" "}
        <span style={{ color: HIGHLIGHT }}>live simulation</span> in one platform.
      </motion.p>
      <motion.div variants={fadeUp} className="pt-2">
        <PromptInput />
      </motion.div>
    </motion.div>
  );
}
