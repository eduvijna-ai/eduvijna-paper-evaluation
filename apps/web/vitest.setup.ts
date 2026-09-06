/** Shared vitest setup — keep minimal to avoid Windows hang on import. */
import { afterEach, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

afterEach(async () => {
  const { cleanup } = await import("@testing-library/react");
  cleanup();
});
