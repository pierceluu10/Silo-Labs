import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Silo Labs — RP2040 Firmware Generator",
  description:
    "An AI agent pipeline that translates natural-language requests into compiled RP2040 firmware.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
