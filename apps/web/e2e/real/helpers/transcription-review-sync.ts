import { expect, type Page } from "@playwright/test";

export async function readTranscriptionProgress(
  page: Page,
): Promise<{ reviewed: number; required: number }> {
  const label =
    (await page.getByTestId("transcription-progress").textContent()) ?? "";
  const match = label.match(/(\d+)\s+of\s+(\d+)/);
  if (!match) {
    throw new Error(`Unexpected transcription progress label: ${label}`);
  }
  return { reviewed: Number(match[1]), required: Number(match[2]) };
}

/**
 * Confirm every required region through the transcription UI until progress is complete.
 * APP-013.1: UI-driven only — no API finalize rescue.
 */
export async function syncTranscriptionConfirmationsThroughUi(
  page: Page,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const { reviewed, required } = await readTranscriptionProgress(page);
        if (reviewed >= required) {
          return "complete";
        }
        const confirm = page.locator(
          '[data-testid="confirm-transcription"]:not([disabled])',
        );
        if ((await confirm.count()) === 0) {
          return `waiting:${reviewed}/${required}`;
        }
        const before = reviewed;
        await confirm.first().click();
        await expect
          .poll(
            async () => (await readTranscriptionProgress(page)).reviewed,
            { timeout: 30_000 },
          )
          .toBeGreaterThan(before);
        return `confirmed:${before}->${before + 1}`;
      },
      { timeout: 120_000 },
    )
    .toBe("complete");

  const { reviewed, required } = await readTranscriptionProgress(page);
  expect(reviewed).toBe(required);
}

/** Finalize transcription via UI and wait for submission detail. */
export async function finalizeTranscriptionAndAwaitSubmissionDetail(
  page: Page,
  submissionId: string,
): Promise<void> {
  const finalizeBtn = page.getByTestId("finalize-transcription");
  await expect(finalizeBtn).toBeEnabled({ timeout: 30_000 });
  await Promise.all([
    page
      .waitForURL(
        (url) => {
          try {
            return new URL(url).pathname === `/submissions/${submissionId}`;
          } catch {
            return false;
          }
        },
        { timeout: 90_000 },
      )
      .catch(() => undefined),
    finalizeBtn.click(),
  ]);
  await expect
    .poll(
      async () => new URL(page.url()).pathname,
      { timeout: 120_000 },
    )
    .toBe(`/submissions/${submissionId}`);
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });
}
