import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // API mode selected via NEXT_PUBLIC_API_MODE (default: mock). No secrets here.
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, "../.."),
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
