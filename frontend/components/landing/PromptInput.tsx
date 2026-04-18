"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function PromptInput() {
  const router = useRouter();
  const [value, setValue] = useState(
    "Read a BME280 over I2C and display the readings on an SSD1306 OLED."
  );

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    const params = new URLSearchParams({ prompt: value.trim() });
    router.push(`/workspace?${params.toString()}`);
  };

  return (
    <form onSubmit={submit} className="w-full max-w-2xl mx-auto mt-8">
      <div
        className="flex items-center gap-2 rounded-md p-2 border"
        style={{
          background: "var(--color-carbon)",
          borderColor: "var(--color-charcoal)",
        }}
      >
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Describe the firmware you want…"
          className="flex-1 bg-transparent outline-none px-3 py-2 text-snow text-sm placeholder:text-steel"
        />
        <button
          type="submit"
          className="px-4 py-2 rounded text-sm font-medium transition-colors"
          style={{
            background: "var(--color-accent)",
            color: "var(--color-abyss)",
          }}
        >
          Generate
        </button>
      </div>
    </form>
  );
}
