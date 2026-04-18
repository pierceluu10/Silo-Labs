export default function LandingPage() {
  return (
    <main className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-2xl text-center space-y-6">
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
      </div>
    </main>
  );
}
