import dynamic from "next/dynamic";
import { PromptInput } from "@/components/landing/PromptInput";

const RP2040Scene = dynamic(
  () => import("@/components/landing/RP2040Scene").then((m) => m.RP2040Scene),
  { ssr: false }
);

export default function LandingPage() {
  return (
    <main className="min-h-screen grid grid-cols-1 lg:grid-cols-2 gap-8 px-6 py-16 items-center">
      <div className="max-w-xl mx-auto lg:mx-0 text-center lg:text-left space-y-6">
        <p
          className="text-xs uppercase tracking-[0.18em] text-steel font-semibold"
          style={{ letterSpacing: "2.52px" }}
        >
          Silo Labs
        </p>
        <h1
          className="text-6xl font-normal text-snow"
          style={{
            fontFamily: "var(--font-display)",
            lineHeight: 1.0,
            letterSpacing: "-0.65px",
          }}
        >
          Natural language to{" "}
          <span className="accent-glow" style={{ color: "var(--color-accent)" }}>
            RP2040 firmware
          </span>
        </h1>
        <p className="text-parchment text-base leading-relaxed">
          A multi-agent pipeline generates C, validates against the RP2040 SVD, compiles
          with arm-gcc, and simulates in Wokwi — live.
        </p>
        <PromptInput />
      </div>
      <div className="h-[420px] lg:h-[520px]">
        <RP2040Scene />
      </div>
    </main>
  );
}
