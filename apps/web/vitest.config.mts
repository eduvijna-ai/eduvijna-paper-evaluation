import { defineConfig } from "vitest/config";
import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    globals: false,
    pool: "forks",
    maxWorkers: 1,
    minWorkers: 1,
    fileParallelism: false,
    isolate: false,
    setupFiles: ["./vitest.setup.ts"],
    testTimeout: 30000,
    hookTimeout: 30000,
  },
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "./src"),
      "next/link": path.resolve(rootDir, "./src/test/mocks/next-link.tsx"),
      "next/navigation": path.resolve(
        rootDir,
        "./src/test/mocks/next-navigation.ts",
      ),
    },
  },
});
