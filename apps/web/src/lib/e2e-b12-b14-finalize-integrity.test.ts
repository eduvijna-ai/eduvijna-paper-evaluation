import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * APP-013.1 regression guard: B12/B14 real-E2E success paths must not rescue
 * transcription finalize via direct API mutation or forced post-finalize goto.
 */
const SPECS = [
  "e2e/real/zz-b12-longitudinal.spec.ts",
  "e2e/real/zz-b14-reassessment.spec.ts",
] as const;

describe("APP-013.1 B12/B14 finalize integrity", () => {
  for (const rel of SPECS) {
    it(`${rel} must not mutate via transcription/finalize API fallback`, () => {
      const src = readFileSync(join(__dirname, "../..", rel), "utf8");
      expect(src).not.toMatch(/transcription\/finalize/);
      expect(src).not.toMatch(
        /request\.post\([\s\S]{0,200}transcription\/finalize/,
      );
    });
  }
});
