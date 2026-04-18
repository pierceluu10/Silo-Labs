import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  experimental: {
    reactCompiler: false,
  },
};

export default config;
