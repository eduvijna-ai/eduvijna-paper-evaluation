import type { NextConfig } from "next";
import path from "node:path";

/**
 * Upstream API for same-origin rewrites (avoids browser CORS during CVB hybrid).
 * Browser calls stay on the Next origin; Next proxies to the API container.
 * Set NEXT_PUBLIC_API_BASE_URL="" (or omit) to use these rewrites.
 * Direct cross-origin calls still require backend CORS (see B1_BACKEND_CHANGE_REQUESTS).
 */
const API_UPSTREAM = (
  process.env.API_UPSTREAM_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:18000"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, "../.."),
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      { source: "/health", destination: `${API_UPSTREAM}/health` },
      { source: "/ready", destination: `${API_UPSTREAM}/ready` },
      { source: "/api/:path*", destination: `${API_UPSTREAM}/api/:path*` },
    ];
  },
};

export default nextConfig;
